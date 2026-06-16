"""Tests for schema sanitization and tool registration."""

from __future__ import annotations

from devops_helper.config import is_destructive
from devops_helper.registry import sanitize_schema_for_gemini, _safe_tool_name


def test_safe_tool_name_strips_invalid_chars():
    assert _safe_tool_name("my tool!") == "my_tool_"


def test_safe_tool_name_truncates_to_64():
    long_name = "a" * 100
    assert len(_safe_tool_name(long_name)) <= 64


def test_sanitize_removes_dollar_ref():
    schema = {"$ref": "#/definitions/Foo", "type": "object"}
    result = sanitize_schema_for_gemini(schema)
    assert "$ref" not in result


def test_sanitize_removes_additional_properties():
    schema = {"type": "object", "additionalProperties": True, "properties": {}}
    result = sanitize_schema_for_gemini(schema)
    assert "additionalProperties" not in result


def test_sanitize_flattens_one_of():
    schema = {
        "oneOf": [
            {"type": "string", "description": "a string"},
            {"type": "null"},
        ]
    }
    result = sanitize_schema_for_gemini(schema)
    assert result.get("type") == "string"


def test_sanitize_nested_properties():
    schema = {
        "type": "object",
        "properties": {
            "pod_name": {
                "type": "string",
                "description": "Pod name",
                "default": "my-pod",         # should be stripped
                "additionalProperties": False, # should be stripped
            }
        }
    }
    result = sanitize_schema_for_gemini(schema)
    pod_schema = result["properties"]["pod_name"]
    assert "default" not in pod_schema
    assert "additionalProperties" not in pod_schema
    assert pod_schema["type"] == "string"


def test_is_destructive_prefix_pattern():
    patterns = ["delete_*", "*_delete", "scale_*"]
    assert is_destructive("delete_pod", patterns)
    assert is_destructive("scale_deployment", patterns)
    assert is_destructive("pod_delete", patterns)
    assert not is_destructive("get_pods", patterns)
    assert not is_destructive("list_deployments", patterns)


def test_is_destructive_case_insensitive():
    patterns = ["delete_*"]
    assert is_destructive("DELETE_POD", patterns)
    assert is_destructive("Delete_Namespace", patterns)


def test_is_destructive_no_false_positive_on_get():
    patterns = ["delete_*", "*_delete", "scale_*", "*_scale", "update_*"]
    # "get_last_update_time" should NOT be destructive (doesn't start/end with patterns)
    assert not is_destructive("get_last_update_time", patterns)
    assert not is_destructive("list_updates_available", patterns)
