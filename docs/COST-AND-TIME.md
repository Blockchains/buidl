# Cost and time per brief

Measured on real runs (ETHOnline 2026 prizes page, Optimism Season 9 Grants Council + Missions posts), model `grok-4.7`.

| Stage | Grok calls | Typical time | Typical Grok cost |
|---|---|---|---|
| Fetch + parse brief (`reasoning_effort=low`) | 1 | 20–60 s | $0.03–0.06 |
| Plan + bill of blocks (low) | 1 | 55–90 s | $0.04–0.06 |
| Contract + tests (`medium`, forge build/test loop, ≤4 attempts) | 1–4 | 3–5 min per attempt | $0.15–0.18 per attempt |
| Submission pack / docs (low) | 1 | 1–2 min | $0.03–0.05 |
| Local CI (forge test, vitest, Vite build, Marp deck) | – | 1–2 min | – |
| Publish: product CI + Pages deploy + 200 checks + browser smoke | – | 4–8 min | – |

**Total: about $0.25–0.70 of Grok and 12–30 minutes per brief**, depending on how many contract repair attempts are needed.
If Grok cannot produce a compiling, passing contract within 4 attempts the pipeline falls back to the tested `BuidlBoard` contract
so you still get a working, deployable product (and the run summary says so).

GitHub Actions: one `buidl` job (~15–30 min) + one `product-ci` job (~3 min) + one `pages` job (~2 min, rebuilds every product branch).
Public repos run on free minutes; private repos use your Actions quota (ubuntu-latest, 1x multiplier).

Cost is printed per call in the job log (`[grok] <stage> <model> <secs> <tokens> $<cost>`) and totalled in `runs/<slug>-<run_id>.json`.
Knobs (env): `BUIDL_MODELS` (default `grok-4.7,grok-4.5`, tried in order), `BUIDL_REASONING` (default `low`), `BUIDL_CONTRACT_REASONING` (default `medium`), `BUIDL_GROK_TIMEOUT` (seconds, default 900).
