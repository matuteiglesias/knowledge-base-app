from __future__ import annotations

import argparse
import json
from typing import Any

import requests

from shared.config import GROBID_URL


def probe_grobid(*, url: str | None = None, timeout: float = 1.5) -> dict[str, Any]:
    """Probe the configured GROBID endpoint without sending a PDF.

    The configured processFulltextDocument endpoint commonly answers GET with a
    client-method response such as 405. That still proves the service is reachable,
    so any HTTP response below 500 counts as reachable. Connection errors, timeouts,
    and server-side failures fail the preflight.
    """

    target = url or GROBID_URL
    try:
        response = requests.get(target, timeout=timeout)
        reachable = response.status_code < 500
        return {
            "grobid_url": target,
            "reachable": reachable,
            "http_status": response.status_code,
            "error": None if reachable else f"HTTP {response.status_code}",
        }
    except requests.RequestException as exc:
        return {
            "grobid_url": target,
            "reachable": False,
            "http_status": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def require_grobid(*, url: str | None = None, timeout: float = 1.5) -> dict[str, Any]:
    result = probe_grobid(url=url, timeout=timeout)
    if not result["reachable"]:
        raise RuntimeError(
            "GROBID is not reachable at "
            f"{result['grobid_url']}. Start or configure the GROBID service (or set GROBID_URL), "
            "then rerun `make corpus-check-grobid` or `make corpus-build`. "
            f"Probe detail: {result['error']}"
        )
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-fast GROBID service preflight for Paper KB")
    parser.add_argument("--url", default=None, help="override configured GROBID_URL")
    parser.add_argument("--timeout", type=float, default=1.5)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        result = require_grobid(url=args.url, timeout=args.timeout)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        status = result["http_status"]
        print(f"[grobid] reachable url={result['grobid_url']} http_status={status}")


if __name__ == "__main__":
    main()
