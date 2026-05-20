# Experimental Agent Framework Workflows

This directory contains **optional experiments** for Microsoft Agent Framework Functional Workflow API.

## Status

- **Experimental only**.
- **Not used by production summary generation**.
- Production path remains: `backend.exports.generate_summaries` + `AgentFrameworkSummaryProvider`.

Microsoft documents the Functional Workflow API as experimental; treat this code as a sandbox for manual evaluation.

## Run manually

```bash
python3 -m backend.experimental.agent_workflows.hierarchical_summary_workflow \
  --corpus tesislcd \
  --paper-id <paper_id> \
  --provider mock
```

With real LLM provider:

```bash
OPENAI_API_KEY=... OPENAI_CHAT_MODEL=... \
python3 -m backend.experimental.agent_workflows.hierarchical_summary_workflow \
  --corpus tesislcd \
  --paper-id <paper_id> \
  --provider agent-framework
```

## Design notes

- Uses `@workflow` and `@step` **only when** `agent_framework` is installed (lazy import).
- Does not change or override production summary artifacts.
- Intended to validate workflow ergonomics before any production adoption decision.
