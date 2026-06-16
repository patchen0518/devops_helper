"""Tests for MCPManager output truncation."""

from __future__ import annotations

from devops_helper.mcp_manager import _truncate


def test_truncate_short_text_unchanged():
    text = "Hello world"
    assert _truncate(text) == text


def test_truncate_long_text():
    text = "\n".join([f"line {i}" for i in range(500)])
    result = _truncate(text, max_chars=200)
    # Allow overhead for the "[N lines truncated]" header line
    assert len(result) <= 300
    assert "[" in result and "truncated" in result


def test_truncate_keeps_tail():
    lines = [f"line {i}" for i in range(100)]
    text = "\n".join(lines)
    result = _truncate(text, max_chars=100)
    # The last line should always be present
    assert "line 99" in result


def test_truncate_exact_limit_unchanged():
    text = "a" * 8000
    result = _truncate(text, max_chars=8000)
    assert result == text
