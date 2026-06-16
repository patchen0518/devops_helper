"""Tool registry: convert MCP tool schemas to Gemini function declarations."""

from __future__ import annotations

from dataclasses import dataclass

from google.genai import types

from devops_helper.config import Config, is_destructive
from devops_helper.mcp_manager import MCPManager


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters_json_schema: dict
    mcp_server_id: str
    destructive: bool
    group: str


class Registry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, td: ToolDefinition) -> None:
        self._tools[td.name] = td

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def all_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def build_gemini_tool(self) -> types.Tool:
        declarations = []
        for td in self._tools.values():
            schema = sanitize_schema_for_gemini(td.parameters_json_schema)
            decl = types.FunctionDeclaration(
                name=td.name,
                description=td.description[:1000],
                parameters=schema,
            )
            declarations.append(decl)
        return types.Tool(function_declarations=declarations)


def build_registry(mcp_manager: MCPManager, config: Config) -> Registry:
    registry = Registry()
    for info in mcp_manager.list_all_tools():
        name = _safe_tool_name(info.name)
        td = ToolDefinition(
            name=name,
            description=info.description,
            parameters_json_schema=info.input_schema,
            mcp_server_id=info.server_id,
            destructive=is_destructive(name, config.destructive_patterns),
            group=info.server_id,
        )
        registry.register(td)
    return registry


def _safe_tool_name(name: str) -> str:
    """Gemini tool names: [a-zA-Z0-9_.-:], max 64 chars."""
    import re
    cleaned = re.sub(r"[^a-zA-Z0-9_.:\-]", "_", name)
    return cleaned[:64]


def sanitize_schema_for_gemini(schema: dict) -> dict:
    """
    Gemini rejects several JSON Schema features. Strip them out recursively:
    - $ref, $schema, $defs, definitions
    - oneOf, anyOf, allOf at property level (keep at top if simple)
    - additionalProperties (boolean form)
    - format values Gemini doesn't support
    - default values at property level (some versions reject these)
    """
    if not isinstance(schema, dict):
        return schema

    STRIP_KEYS = {
        "$ref", "$schema", "$defs", "definitions",
        "additionalProperties", "default", "examples",
    }

    result: dict = {}

    # Prefer explicit type narrowing for oneOf/anyOf at top level
    if "oneOf" in schema or "anyOf" in schema:
        variants = schema.get("oneOf") or schema.get("anyOf") or []
        # Take the first concrete (non-null) type
        for variant in variants:
            if isinstance(variant, dict) and variant.get("type") != "null":
                base = {k: v for k, v in variant.items() if k not in STRIP_KEYS}
                # Merge description from parent if missing
                if "description" in schema and "description" not in base:
                    base["description"] = schema["description"]
                return sanitize_schema_for_gemini(base)
        # Fall through to object if we can't resolve
        return {"type": "object", "description": schema.get("description", "")}

    for k, v in schema.items():
        if k in STRIP_KEYS:
            continue
        if k == "properties" and isinstance(v, dict):
            result[k] = {pk: sanitize_schema_for_gemini(pv) for pk, pv in v.items()}
        elif k == "items" and isinstance(v, dict):
            result[k] = sanitize_schema_for_gemini(v)
        elif k == "allOf" and isinstance(v, list):
            # Merge all schemas — take first non-empty one
            merged: dict = {}
            for sub in v:
                if isinstance(sub, dict):
                    merged.update(sanitize_schema_for_gemini(sub))
            result.update(merged)
        else:
            result[k] = v

    # Gemini requires type field; default to object
    if "type" not in result and "properties" not in result and "enum" not in result:
        result["type"] = "object"

    return result
