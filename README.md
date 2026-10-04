# buidl — brief → product

[![CI](https://github.com/Blockchains/buidl/actions/workflows/ci.yml/badge.svg)](https://github.com/Blockchains/buidl/actions/workflows/ci.yml)
[![Brief to product](https://github.com/Blockchains/buidl/actions/workflows/buidl.yml/badge.svg)](https://github.com/Blockchains/buidl/actions/workflows/buidl.yml)

GitHub-native pipeline that turns a **hackathon, bounty or grant brief** (ETHGlobal, Devpost, DoraHacks, Gitcoin, Optimism / Arbitrum / Solana / Base
grants, or pasted text) into a **working product repo**: a Foundry contract with tests, a static app live on GitHub Pages (wallet connect,
deploy-from-browser, ABI-driven UI), CI, and a full **submission pack** written to the brief's judging criteria — assembled from
[Blockchain Lab blocks](https://blockchains.github.io/blocks.json) with maximum reuse. A run is only marked success once the product
builds, its tests pass, CI is green and its Pages URL returns 200.

**Trigger:** open a [**Brief** issue](https://github.com/Blockchains/buidl/issues/new?template=brief.yml) (owner/collaborators) or run
[Actions → Brief to product](https://github.com/Blockchains/buidl/actions/workflows/buidl.yml) with a URL or pasted brief.
Hub of generated products: **https://blockchains.github.io/buidl/**

```
brief URL / text ─► fetch + HTML→text ─► Grok (grok-4.7): structured requirements
                     (tracks, prizes, sponsor tech, judging criteria, deadlines, chains/SDKs, deliverables, rules, grant metrics)
                ─► catalogue: hub blocks.json (31) + blockchainlab-index (236 forks, reuse fields) + grokhack-index (99) + starters
                    scored against the brief ─► Grok plan: product concept, target tracks, contract spec, architecture (mermaid), bill of blocks
                    (refs validated against the catalogue; unknown refs dropped and reported)
                ─► generate: template (Foundry + Vite/viem + CI + Pages) · OpenZeppelin v5.7.0 + forge-std vendored from Blockchains forks ·
                    Grok-authored contract + tests, verified with forge (≤4 attempts, errors fed back; tested fallback contract otherwise) ·
                    submission pack: PROJECT.md (per judging criterion), TRACKS.md (sponsor mapping), DEMO-SCRIPT.md, DECK.md (Marp → deck.html),
                    MILESTONES-BUDGET.md (grants) / ROADMAP.md, COMPLIANCE.md (every brief rule) · README, AGENTS.md, llms.txt, blocks.json
                ─► verify locally: scripts/ci.sh (forge build/test, web tests, vite build, deck) + gitleaks
                ─► publish + verify on GitHub: CI green → Pages deployed → site, deck and contract artifact return 200
```

## Output: what a generated repo contains

| Path | What |
|---|---|
| `contracts/` | Foundry project: `src/<Name>.sol` (no-arg constructor), `test/` (≥6 tests incl. fuzz), `script/Deploy.s.sol`, vendored `lib/` |
| `web/` | static Vite + viem app: content from the plan, wallet connect (EIP-1193), chain switch/add, **deploy from the browser**, every read/write function as a form, live block from the public RPC |
| `docs/submission/` | `PROJECT.md`, `TRACKS.md`, `DEMO-SCRIPT.md`, `DECK.md` (Marp; built to `/deck.html`), `MILESTONES-BUDGET.md` or `ROADMAP.md` |
| `COMPLIANCE.md` | checklist of every rule/deliverable in the brief (met / partial / todo) + the automated checks |
| `brief/` | `requirements.json`, `plan.json` (bill of blocks, architecture) |
| `.github/workflows/` | `ci.yml` (scripts/ci.sh + gitleaks), `pages.yml` |
| `README.md`, `AGENTS.md`, `llms.txt`, `blocks.json`, `buidl.json` | docs for humans and agents, block manifest, generator metadata |

## Publish modes

| Mode | When | Result |
|---|---|---|
| `create` | `FORGE_TOKEN` secret is set (auto) | new public repo `Blockchains/<slug>`, Pages enabled, CI + Pages verified |
| `branch` | no `FORGE_TOKEN` (auto, sandbox) | branch `product/<slug>` in this repo (workflows kept in `.buidl/workflows/`, since `GITHUB_TOKEN` cannot write workflow files); CI via [Product CI](.github/workflows/product-ci.yml); live at `https://blockchains.github.io/buidl/p/<slug>/`. Promote later: `python3 -m buidl promote <slug>` |
| `none` | local runs / CI self-test | generate + test only |

**The one secret needed for fully hands-off repo creation:** `FORGE_TOKEN` — a fine-grained PAT owned by Blockchains with
*Administration: read/write* (create repos), *Contents: read/write*, *Workflows: read/write*, *Pages: read/write*, *Actions: read* on all repositories.
`XAI_API_KEY` is already required (set as a secret).

## Run locally

```bash
python3 -m buidl run --brief-url https://ethglobal.com/events/ethonline2026/prizes --mode none --out /tmp/p   # needs XAI_API_KEY, forge, node 20
python3 -m buidl run --brief-file brief.txt --name my-entry --mode create                                      # gh logged in as Blockchains (or FORGE_TOKEN)
python3 -m buidl promote <slug>                                                                                # sandbox branch -> Blockchains/<slug>
```

Stdlib-only Python 3.10+; Foundry; Node 20; `gh` for publishing. Docs: [How to submit a brief](docs/HOW-TO-SUBMIT-A-BRIEF.md) ·
[Cost and time](docs/COST-AND-TIME.md) · [Demo runs](docs/DEMOS.md).

## Reuse map

| Block | Used for |
|---|---|
| [Blockchains/openzeppelin-contracts](https://github.com/Blockchains/openzeppelin-contracts) `v5.7.0`, [Blockchains/forge-std](https://github.com/Blockchains/forge-std) `v1.17.0` | vendored into every product |
| [blocks.json hub](https://blockchains.github.io/blocks.json), [blockchainlab-index](https://github.com/Blockchains/blockchainlab-index), [grokhack-index](https://github.com/Blockchains/grokhack-index), [blockchainlab-starters](https://github.com/Blockchains/blockchainlab-starters) | planning catalogue / bill of blocks |
| [blockchainlab-compose](https://github.com/Blockchains/blockchainlab-compose), [grokhack-forge](https://github.com/Blockchains/grokhack-forge) | same publish pattern (create repo → wait CI → result JSON); buidl adds briefs, front end, Pages and submission packs |

<!-- blocks:start -->
## Use as a building block
Read [AGENTS.md](AGENTS.md), [llms.txt](llms.txt) and [blocks.json](blocks.json). How all Blockchains blocks fit together:
[Build with Blocks](https://github.com/Blockchains/.github/blob/main/docs/BUILD-WITH-BLOCKS.md).
<!-- blocks:end -->
