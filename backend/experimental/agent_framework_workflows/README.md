# Experimental Agent Framework Workflows (Milestone F)

This directory is **experimental only**.

- It is not imported by API startup.
- It is not part of production summary generation.
- Production remains `backend.exports.generate_summaries` (normal Python orchestration).

## Purpose

Prototype a one-paper hierarchical workflow (`groups -> section summaries -> final summary`) using Agent Framework workflow decorators when available.

## Install notes

Agent Framework does not auto-load `.env` files. Set env vars directly or load via `python-dotenv` in your shell bootstrap.

Example install:

```bash
pip install agent-framework agent-framework-openai
```

## Manual run

Mock provider:

```bash
python3 -m backend.experimental.agent_framework_workflows.hierarchical_summary_experiment \
  --corpus tesislcd \
  --paper-id <paper_id> \
  --provider mock
```

Agent Framework provider:

```bash
OPENAI_API_KEY=... OPENAI_CHAT_MODEL=... \
python3 -m backend.experimental.agent_framework_workflows.hierarchical_summary_experiment \
  --corpus tesislcd \
  --paper-id <paper_id> \
  --provider agent-framework \
  --agent-mode client
```

Optional agent wrapper mode:

```bash
OPENAI_API_KEY=... OPENAI_CHAT_MODEL=... \
python3 -m backend.experimental.agent_framework_workflows.hierarchical_summary_experiment \
  --corpus tesislcd \
  --paper-id <paper_id> \
  --provider agent-framework \
  --agent-mode agent
```

## Output location

Writes only to experimental run directories:

`corpora/<corpus>/experimental_runs/agent_framework_workflows/<run_id>/<paper_id>.workflow_result.json`

