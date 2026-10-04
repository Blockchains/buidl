# How to submit a brief

You need: the brief (a public URL and/or pasted text). Everything else runs on GitHub Actions.

## Option A — open an issue (recommended)
1. Go to **[New issue → Brief](https://github.com/Blockchains/buidl/issues/new?template=brief.yml)**.
2. Fill **Brief URL(s)** (one or more, space separated) and/or **Pasted brief**. Optional: **Repo name** (kebab-case) and **Publish mode**.
3. Submit. The *Brief to product* workflow starts (only for the repo owner / collaborators — issues from others are ignored so nobody can spend the xAI budget).
4. In ~20–40 minutes a comment appears with the repo, the live Pages URL, CI status, target tracks, the bill of blocks and the Grok cost.

## Option B — Actions tab / CLI
- **Actions → Brief to product → Run workflow**: `brief_url`, `brief_text`, `name`, `mode`.
- CLI: `gh workflow run buidl.yml -R Blockchains/buidl -f brief_url=https://ethglobal.com/events/<event>/prizes -f name=my-entry`

## Which URL works best
| Source | Use |
|---|---|
| ETHGlobal | the event's **/prizes** page (`https://ethglobal.com/events/<event>/prizes`) — all sponsor tracks, prizes and qualification rules are server-rendered |
| Devpost | the hackathon overview + `/rules` page (give both URLs) |
| DoraHacks / Gitcoin / Questbook | the BUIDL / round page; if it is rendered client-side and the text is thin, paste the brief instead |
| Grants (Optimism, Arbitrum, Solana, Base, …) | the forum post or grant page with objectives, eligibility and milestone rules (several URLs are fine) |

The pipeline refuses briefs under 200 characters (usually a JS-only page) — paste the text in that case. Pages behind a login cannot be fetched.

## What you get
A repo (or sandbox branch) with: Foundry contract + tests, a live app on GitHub Pages (connect wallet → deploy the contract from the browser on
the planned testnet → call every function), CI, `docs/submission/` (project description by judging criterion, sponsor/track mapping, demo
script, Marp deck at `/deck.html`, grant milestones + budget or a roadmap), `COMPLIANCE.md` against the brief's rules, and README / AGENTS.md /
llms.txt / blocks.json.

## Before you submit to the organiser
- Work through every `todo` / `partial` row in `COMPLIANCE.md` (typically: record the demo video, sponsor SDK keys, mainnet deploys, team details).
- Read `docs/submission/TRACKS.md` — sponsor integrations needing API keys are marked *planned*; wire them in before claiming the track.
- Deploy the contract from the live app (or `forge script`) and add the address to `web/src/project.json` → `deployments`.
- Generated text is a draft by Grok: check facts, numbers and the budget table.
