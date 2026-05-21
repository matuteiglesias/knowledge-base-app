from __future__ import annotations

import argparse
import asyncio
import json
import sys

from backend.llm.agent_framework_provider import AgentFrameworkSummaryProvider


async def _run(prompt: str, model: str | None = None, env_file_path: str | None = None, agent_mode: str = "client") -> int:
    provider = AgentFrameworkSummaryProvider(model=model, env_file_path=env_file_path, agent_mode=agent_mode)
    if agent_mode == "agent":
        response = await provider._invoke_agent_mode(prompt)
    else:
        client = provider._get_client()
        response = await client.get_response(
            [provider._Message("user", [prompt])],
            response_format={"type": "json_object"},
        )

    raw_text = None
    try:
        raw_text = getattr(response.messages[0], "text", None)
    except Exception:
        raw_text = None
    if not raw_text:
        raw_text = str(response)

    print(raw_text)
    parsed = json.loads(raw_text)
    if not isinstance(parsed, dict):
        raise RuntimeError("smoke response must be a JSON object")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--prompt", required=True)
    p.add_argument("--provider", choices=["agent-framework"], default="agent-framework")
    p.add_argument("--model", default=None)
    p.add_argument("--env-file-path", default=None)
    p.add_argument("--agent-mode", choices=["client", "agent"], default="client")
    args = p.parse_args()

    try:
        return asyncio.run(_run(prompt=args.prompt, model=args.model, env_file_path=args.env_file_path, agent_mode=args.agent_mode))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
