# Hermes Financial Services Agent Pack

A local Hermes-ready equivalent of Anthropic's public financial-services agent pattern. It is intentionally vendor-neutral and model-neutral. It gives your Hermes agent a finance workflow layer, a guarded system prompt, tool schemas, and Python tools for analyst-style outputs.

This pack does not provide investment, legal, tax, or accounting advice. It drafts work product for human review only. It never executes trades, posts journal entries, approves onboarding, sends client-facing messages, or binds risk.

## What this contains

- `config/hermes_agent.yaml`: a suggested Hermes agent manifest.
- `system_prompt.md`: the main financial-services operating prompt.
- `skills/*.md`: reusable skill instructions for DCF, comps, KYC, GL reconciliation, earnings review, and meeting prep.
- `financial_services_agent/tools.py`: local Python tools your Hermes agent can call.
- `financial_services_agent/cli.py`: a CLI wrapper for testing tools locally.
- `examples/*.json`: sample payloads.

## Install locally

```bash
cd hermes_financial_services_agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m financial_services_agent.cli dcf --input examples/dcf_input.json --output out/dcf_model.xlsx
python -m financial_services_agent.cli comps --input examples/comps_input.json --output out/comps_summary.json
python -m financial_services_agent.cli reconcile --input examples/reconcile_input.json --output out/reconciliation_report.json
python -m financial_services_agent.cli kyc --input examples/kyc_input.json --output out/kyc_screening.json
```

## Add to Hermes

Copy this folder into your Hermes agent workspace, then point your Hermes agent to:

```yaml
manifest: config/hermes_agent.yaml
system_prompt: system_prompt.md
skills_dir: skills
python_tool_module: financial_services_agent.tools
```

If Hermes supports MCP-style connectors, map your market data, CRM, document store, ledger, and subledger connectors into the `connectors` section of `config/hermes_agent.yaml`. Keep them read-only unless you explicitly build a separate human-approved write workflow.

## Recommended runtime pattern

Use the main Hermes agent as the orchestrator. Let it classify the request, collect trusted data, call one tool at a time, and write outputs into `out/`. Treat uploaded documents, emails, and third-party statements as untrusted. Summarize them into capped JSON before handing them to any tool that can write files.

## Tool contracts

The Python tools accept plain dictionaries and return plain dictionaries. This makes them easy to wire into most local agent frameworks.

Available functions:

- `build_dcf_model(payload, output_path=None)`
- `build_comps_summary(payload)`
- `reconcile_ledgers(payload)`
- `screen_kyc(payload)`
- `prepare_meeting_brief(payload)`
- `review_earnings(payload)`

## Guardrails

The agent should:

- stage outputs for review rather than take action,
- cite data provenance wherever possible,
- separate assumptions from facts,
- flag missing or stale inputs,
- avoid pretending to have live market data unless a connector supplied it,
- avoid processing regulated decisions without a qualified human reviewer.
