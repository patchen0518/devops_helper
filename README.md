# devops-helper

A conversational CLI agent for DevOps engineers. Ask questions and run operations across Kubernetes, AWS, CI/CD pipelines, and observability stacks in plain language — powered by Google Gemini.

```
devops> what pods are crash-looping in production?
devops> show me CloudWatch alarms that are firing right now
devops> scale the api-server deployment to 3 replicas in staging
```

Destructive operations (scale, delete, sync, apply, destroy) always show a confirmation panel before executing — similar to `terraform plan`.

## Prerequisites

- Python 3.12+, [uv](https://docs.astral.sh/uv/)
- A [Gemini API key](https://aistudio.google.com/apikey)
- For MCP servers: `uvx` (bundled with uv), `npx`, or Docker depending on the server

## Setup

```bash
# Install dependencies
uv sync

# Copy the config template
cp .devops-helper.example.yaml .devops-helper.yaml
```

Edit `.devops-helper.yaml` to enable the servers you have access to, then set your credentials:

```bash
export GEMINI_API_KEY=your-key-here
export AWS_REGION=us-east-1          # if using AWS servers
```

## Usage

```bash
# Interactive REPL
uv run devops-helper

# Single query and exit (scriptable)
uv run devops-helper --one-shot "list deployments in the default namespace"

# Override the Gemini model
uv run devops-helper --model gemini-2.5-pro
```

Type `exit` or press Ctrl+D to quit the REPL.

## Supported Integrations

Each integration is backed by an official or well-maintained MCP server. Configure only the ones you need — unconfigured servers are silently skipped.

| Integration | What it covers | Requires |
|---|---|---|
| Kubernetes | Pods, deployments, logs, scaling, rollouts | kubeconfig |
| AWS CloudWatch | Metrics, logs, alarms | AWS credentials + `AWS_REGION` |
| AWS EKS | Cluster and node operations | AWS credentials + `AWS_REGION` |
| GitHub + Actions | Repos, workflow runs, PRs, issues | Docker + `GITHUB_TOKEN` |
| ArgoCD | App sync status, trigger sync | `ARGOCD_URL` + `ARGOCD_TOKEN` |
| Grafana | Dashboards, datasources, annotations | `GRAFANA_URL` + `GRAFANA_TOKEN` |
| Prometheus | PromQL instant and range queries | `PROMETHEUS_URL` |
| Terraform | Registry, HCP Terraform workspaces | Docker; `TFE_TOKEN` for HCP |

## Configuration

`.devops-helper.yaml` is loaded from the current directory, then `~/.devops-helper.yaml` as a fallback. It is gitignored — never commit credentials.

```yaml
# Override the default model (optional)
gemini_model: gemini-2.5-pro

mcp_servers:
  kubernetes:
    command: uvx
    args: ["kubernetes-mcp-server@latest"]

  aws_cloudwatch:
    command: uvx
    args: ["awslabs.cloudwatch-mcp-server@latest"]
    env:
      AWS_REGION: "${AWS_REGION}"       # expands from your environment

# Tools matching these patterns prompt for confirmation before running
destructive_patterns:
  - "delete_*"
  - "scale_*"
  - "destroy_*"
  # ... see .devops-helper.example.yaml for the full default list
```

`${VAR}` references in `env` blocks are expanded from your shell environment at startup.

### Safety gate

When Gemini calls a tool whose name matches a `destructive_pattern`, execution is paused and a plan panel is shown:

```
┌──────────────────────────────────────────────────────┐
│  PLANNED OPERATION                                   │
│                                                      │
│  Tool:   scale_deployment                            │
│  Server: kubernetes                                  │
│                                                      │
│  namespace:   production                             │
│  deployment:  api-server                             │
│  replicas:    0                                      │
└──────────────────────────────────────────────────────┘
  Type 'yes' to confirm, anything else to abort:
```

Only the literal string `yes` proceeds. Anything else aborts and tells Gemini the operation was cancelled.

## Development

```bash
uv run pytest tests/                          # run all tests
uv run pytest tests/test_dispatcher.py        # single file
uv run ruff check devops_helper/              # lint
uv run ruff check --fix devops_helper/        # auto-fix
```
