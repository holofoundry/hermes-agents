from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .tools import (
        build_comps_summary,
        build_dcf_model,
        prepare_meeting_brief,
        reconcile_ledgers,
        review_earnings,
        screen_kyc,
    )
except ImportError:
    import sys
    from pathlib import Path as _Path

    sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

    from financial_services_agent.tools import (
        build_comps_summary,
        build_dcf_model,
        prepare_meeting_brief,
        reconcile_ledgers,
        review_earnings,
        screen_kyc,
    )


def _load(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _dump(data, path: str | None):
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    else:
        print(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hermes Financial Services Agent CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["dcf", "comps", "reconcile", "kyc", "meeting", "earnings"]:
        p = sub.add_parser(name)
        p.add_argument("--input", required=True)
        p.add_argument("--output")
    args = parser.parse_args()
    payload = _load(args.input)

    if args.command == "dcf":
        result = build_dcf_model(payload, args.output if args.output and args.output.endswith(".xlsx") else None)
        if not (args.output and args.output.endswith(".xlsx")):
            _dump(result, args.output)
    elif args.command == "comps":
        _dump(build_comps_summary(payload), args.output)
    elif args.command == "reconcile":
        _dump(reconcile_ledgers(payload), args.output)
    elif args.command == "kyc":
        _dump(screen_kyc(payload), args.output)
    elif args.command == "meeting":
        _dump(prepare_meeting_brief(payload), args.output)
    elif args.command == "earnings":
        _dump(review_earnings(payload), args.output)


if __name__ == "__main__":
    main()
