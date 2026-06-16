# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run tests
uv run pytest tests/

# Run a single test file or test
uv run pytest tests/test_dispatcher.py
uv run pytest tests/test_dispatcher.py::test_dispatch_read_only_executes_immediately

# Lint
uv run ruff check devops_helper/

# Auto-fix lint issues
uv run ruff check --fix devops_helper/

# Run the agent (interactive REPL)
uv run devops-helper

# Run a one-shot query
uv run devops-helper --one-shot "list pods in production"

# Run with verbose logging (shows MCP connection details)
uv run devops-helper --verbose
```

## Architecture

The agent is a **Gemini-powered MCP client**: rather than implementing AWS/Kubernetes/CI/CD API wrappers, it connects to external MCP servers at startup, discovers their tools, maps them to Gemini function declarations, and routes tool calls through the MCP protocol.

### Agent loop (`agent.py`)

Manual function calling — Automatic Function Calling (AFC) is **disabled** (`AutomaticFunctionCallingConfig(disable=True)`). This is intentional: the safety gate in `dispatcher.py` must intercept every tool call before execution. The loop runs up to 10 iterations per turn: send history → get response → if function calls, dispatch all → append all `FunctionResponse`s → repeat until a text response is returned.

### Safety gate (`dispatcher.py`)

Tools whose names match `destructive_patterns` (configured in `.devops-helper.yaml`) are gated behind a `terraform plan`-style confirmation panel before execution. Non-destructive tools run concurrently via `asyncio.gather`; destructive tools run sequentially to avoid interleaved prompts. A `FunctionResponse` is **always** returned for every `FunctionCall` — never leave one unanswered or Gemini errors on the next turn.

### MCP server management (`mcp_manager.py`)

`MCPManager` uses `contextlib.AsyncExitStack` to hold open all `stdio_client` + `ClientSession` context managers across all connected servers simultaneously. Each server runs as a stdio subprocess. Tool name collisions across servers are resolved by prefixing with `{server_id}__`. Output is truncated to 8,000 characters before being returned to Gemini.

### Schema sanitization (`registry.py::sanitize_schema_for_gemini`)

MCP servers emit JSON Schema features Gemini rejects (`$ref`, `oneOf`/`anyOf`, `additionalProperties`, `default`, etc.). `sanitize_schema_for_gemini()` strips these before building `FunctionDeclaration` objects. This runs at registry build time (startup), not per-call.

### Configuration (`.devops-helper.yaml`)

Each MCP server entry specifies `command`, `args`, and `env`. Env values support `${VAR}` expansion from the process environment. `destructive_patterns` is a list of glob patterns matched case-insensitively against tool names — prefer prefix patterns (`delete_*`) over contains patterns (`*delete*`) to avoid false positives on read-only tools.

## Verified MCP server install methods

| Server | Command |
|---|---|
| AWS CloudWatch | `uvx awslabs.cloudwatch-mcp-server@latest` |
| AWS EKS | `uvx awslabs.eks-mcp-server@latest` |
| Kubernetes | `uvx kubernetes-mcp-server@latest` |
| ArgoCD | `npx -y argocd-mcp@latest stdio` |
| Grafana | `uvx mcp-grafana` (stdio is the default transport) |
| Prometheus | `uvx prometheus-mcp-server@latest` |
| GitHub | Docker only: `docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN ghcr.io/github/github-mcp-server` |
| Terraform | Docker only: `docker run -i --rm hashicorp/terraform-mcp-server:latest stdio` |

`awslabs.terraform-mcp-server` is yanked — use the HashiCorp Docker image instead. `awslabs.aws-api-mcp-server` exposes hundreds of tools and should not be configured (too many declarations for Gemini).

## Key constraints

- Python 3.12 only (pinned in `.python-version`). Use `uv` — not `pip` directly.
- `asyncio_mode = "auto"` in pytest — all async tests run without explicit `@pytest.mark.asyncio`.
- Line length: 100. Ruff selects `E`, `F`, `I` rules only.
- `.devops-helper.yaml` is gitignored — credentials live there, never in code.
