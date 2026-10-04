# AGENTS.md: buidl

Hackathon / grant brief → working product repo, on GitHub Actions. Humans: see [README.md](README.md).

## Setup / test
```bash
python3 -m unittest discover -s tests -v                       # offline unit tests
python3 -m buidl run --requirements examples/ethonline2026/requirements.json --plan examples/ethonline2026/plan.json \
  --mode none --no-grok --out /tmp/p --result /tmp/r.json      # template e2e without Grok (needs forge + node 20)
python3 -m buidl run --brief-url <url> --mode none             # full run with Grok (XAI_API_KEY)
```

## Structure
| Path | What |
|---|---|
| `buidl/brief.py` | fetch URL → text, Grok parse → requirements.json |
| `buidl/catalog.py` | load hub blocks.json, blockchainlab-index catalog, grokhack-index, starters; score/shortlist |
| `buidl/plan.py` | Grok plan + normalisation (slug, testnet, contract name, bill-of-blocks validation) |
| `buidl/generate.py` | product repo: template, vendored libs, Grok contract with forge verification loop + fallback, submission pack, docs |
| `buidl/publish.py` | create repo (FORGE_TOKEN / gh) or sandbox branch; wait for CI + Pages; HTTP 200 checks |
| `buidl/templates/product/` | the product template (contracts, web, scripts/ci.sh, workflows) |
| `scripts/` | workflow helpers: issue-form inputs, run recording, hub page |
| `runs/` | one JSON per pipeline run (written by the workflow) |
| `examples/` | real parsed briefs + plans used by CI |

## Rules
- Stdlib-only Python; no new runtime deps without a reason.
- Never print or commit secrets; gitleaks runs before every publish and in CI.
- Generated products must pass `scripts/ci.sh`; a run is success only after CI green + Pages 200.
- Keep the template's constructor contract (no-arg) in sync with `web/src/main.js` deploy flow.
