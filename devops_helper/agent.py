"""Async Gemini agent loop with manual function calling."""

from __future__ import annotations

import logging

from google import genai
from google.genai import types

from devops_helper.config import Config
from devops_helper.dispatcher import dispatch_all
from devops_helper.mcp_manager import MCPManager
from devops_helper.registry import Registry

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert DevOps engineer assistant. You have access to tools covering:
Kubernetes, AWS (EKS, CloudWatch), CI/CD (GitHub Actions, ArgoCD), and observability
(Grafana, Prometheus, Terraform).

Guidelines:
- Always explain what you are about to do before calling a destructive tool.
- If a tool call is aborted by the user, acknowledge it and ask what they'd like to do instead.
- For large outputs (logs, metrics), summarize the key findings rather than repeating everything.
- Prefer showing status and context before suggesting changes.
- Never guess resource names — always list or describe them first if unsure.
"""

MAX_ITERATIONS = 10


class Agent:
    def __init__(self, registry: Registry, mcp_manager: MCPManager, config: Config) -> None:
        self._registry = registry
        self._mcp_manager = mcp_manager
        self._config = config
        self._client = genai.Client(api_key=config.gemini_api_key)
        self._gemini_tool = registry.build_gemini_tool()
        self._history: list[types.Content] = []

    async def turn(self, user_message: str) -> str:
        self._history.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
        )

        for iteration in range(MAX_ITERATIONS):
            response = await self._client.aio.models.generate_content(
                model=self._config.gemini_model,
                contents=self._history,
                config=types.GenerateContentConfig(
                    tools=[self._gemini_tool] if self._registry.all_tools() else None,
                    system_instruction=SYSTEM_PROMPT,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )

            candidate = response.candidates[0]

            # Guard against safety/token-limit stops with no content
            if not candidate.content or not candidate.content.parts:
                reason = getattr(candidate, "finish_reason", "unknown")
                return f"Model stopped unexpectedly (reason: {reason}). Please rephrase."

            self._history.append(candidate.content)

            function_calls = [
                part.function_call
                for part in candidate.content.parts
                if part.function_call is not None
            ]

            if not function_calls:
                # Terminal text response
                text_parts = [
                    part.text
                    for part in candidate.content.parts
                    if part.text
                ]
                return "\n".join(text_parts)

            # Dispatch all tool calls
            responses = await dispatch_all(function_calls, self._registry, self._mcp_manager)

            # All responses go back in a single Content block
            self._history.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(name=r.name, response=r.response)
                        for r in responses
                    ],
                )
            )

        return "Maximum tool iterations reached. Please rephrase your request."

    def reset(self) -> None:
        self._history.clear()
