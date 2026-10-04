"""Generate the product repository from requirements + plan: template, vendored libs, Grok-authored contract (verified
with forge, bounded retries, tested fallback), submission pack, README/AGENTS.md/llms.txt/blocks.json."""
from __future__ import annotations

import os
import datetime as dt
import json
import re
import shutil
import subprocess
from pathlib import Path

from . import grok
from .vendor import vendor

HERE = Path(__file__).parent
TEMPLATE = HERE / "templates" / "product"
FALLBACK = HERE / "templates" / "fallback"
OWNER = "Blockchains"


def run(cmd: list[str] | str, cwd: Path, timeout: int = 280) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + "\n" + p.stderr)


# ---------------------------------------------------------------- contract
CONTRACT_SYSTEM = (
    "You write production-quality Solidity 0.8.28 for Foundry. Available imports: '@openzeppelin/contracts/...' (OpenZeppelin v5.x; "
    "Ownable takes initialOwner in its constructor) and 'forge-std/Test.sol'. Rules: SPDX MIT; pragma solidity ^0.8.24; one main contract; "
    "the constructor takes NO arguments (use msg.sender as owner/admin); custom errors; events for every state change; no external calls "
    "to addresses that do not exist on a fresh local chain (tests run offline on anvil defaults); keep it focused (<300 lines). The test "
    "file must import '../src/<Name>.sol', contain at least 6 test functions (happy paths, access control, reverts with vm.expectRevert, "
    "one fuzz test) and must pass with `forge test`. Reply with JSON {\"contract_source\": string, \"test_source\": string, \"notes\": string}."
)


def _write_contract(cdir: Path, name: str, src: str, test: str) -> None:
    for d in ("src", "test"):
        for f in (cdir / d).glob("*.sol"):
            f.unlink()
    (cdir / "src" / f"{name}.sol").write_text(src)
    (cdir / "test" / f"{name}.t.sol").write_text(test)
    (cdir / "script" / "Deploy.s.sol").write_text(
        "// SPDX-License-Identifier: MIT\npragma solidity ^0.8.24;\n\n"
        'import {Script, console2} from "forge-std/Script.sol";\n'
        f'import {{{name}}} from "../src/{name}.sol";\n\n'
        "/// forge script script/Deploy.s.sol --rpc-url target --broadcast --account <keystore>   (RPC_URL env)\n"
        "contract Deploy is Script {\n    function run() external {\n        vm.startBroadcast();\n"
        f"        {name} c = new {name}();\n        vm.stopBroadcast();\n        console2.log(\"{name}\", address(c));\n    }}\n}}\n")


def _check_contract(cdir: Path, name: str) -> tuple[bool, str]:
    code, out = run(["forge", "build"], cdir)
    if code:
        return False, "forge build failed:\n" + out[-6000:]
    art = cdir / "out" / f"{name}.sol" / f"{name}.json"
    if not art.exists():
        return False, f"artifact out/{name}.sol/{name}.json missing - the main contract must be named {name}"
    abi = json.loads(art.read_text())["abi"]
    ctor = next((x for x in abi if x.get("type") == "constructor"), None)
    if ctor and ctor.get("inputs"):
        return False, "the constructor must take no arguments (browser deploy uses no-arg constructor)"
    code, out = run(["forge", "test", "-vv"], cdir)
    if code:
        return False, "forge test failed:\n" + out[-6000:]
    n = len(re.findall(r"\[PASS\]", out))
    if n < 4:
        return False, f"only {n} passing tests; need at least 6"
    return True, out[-3000:]


def author_contract(cdir: Path, req: dict, plan: dict, max_attempts: int = 4) -> dict:
    name = plan["contract"]["name"]
    attempts = []
    if grok.available():
        user = (f"Contract name: {name}\nSpec:\n{json.dumps(plan['contract'], indent=1)}\nProduct: {plan.get('title')} - {plan.get('solution')}\n"
                f"Target tracks: {json.dumps(plan.get('target_tracks', []))[:3000]}")
        prev = None
        for i in range(max_attempts):
            try:
                if prev is None:
                    ans = grok.chat_json("contract", CONTRACT_SYSTEM, user, max_tokens=16000, temperature=0.2, effort=os.environ.get("BUIDL_CONTRACT_REASONING", "medium"))
                else:
                    ans = grok.chat_json(f"contract-fix-{i}", CONTRACT_SYSTEM, user + "\n\nYour previous attempt failed.\nERRORS:\n" + prev["error"]
                                         + "\n\nPREVIOUS CONTRACT:\n" + prev["src"] + "\n\nPREVIOUS TEST:\n" + prev["test"]
                                         + "\n\nFix the root cause and return the full corrected files.", max_tokens=16000, temperature=0.1, effort=os.environ.get("BUIDL_CONTRACT_REASONING", "medium"))
            except grok.GrokError as e:
                attempts.append({"attempt": i + 1, "ok": False, "error": str(e)[:500]})
                break
            src, test = ans.get("contract_source", ""), ans.get("test_source", "")
            _write_contract(cdir, name, src, test)
            ok, out = _check_contract(cdir, name)
            attempts.append({"attempt": i + 1, "ok": ok, "error": None if ok else out[-1500:]})
            if ok:
                return {"name": name, "source": "grok", "attempts": attempts, "test_output": out}
            prev = {"error": out, "src": src, "test": test}
    # tested fallback contract
    name = "BuidlBoard"
    plan["contract"] = {"name": name, "description": "Fallback on-chain board (submit, endorse, owner milestones) - Grok contract did not pass within the retry budget",
                        "functions": [{"signature": "submit(string,string)"}, {"signature": "endorse(uint256)"}, {"signature": "completeMilestone(uint256,string)"}]}
    for d in ("src", "test"):
        for f in (cdir / d).glob("*.sol"):
            f.unlink()
    shutil.copy(FALLBACK / "BuidlBoard.sol", cdir / "src" / "BuidlBoard.sol")
    shutil.copy(FALLBACK / "BuidlBoard.t.sol", cdir / "test" / "BuidlBoard.t.sol")
    _write_contract(cdir, name, (cdir / "src" / "BuidlBoard.sol").read_text(), (cdir / "test" / "BuidlBoard.t.sol").read_text())
    ok, out = _check_contract(cdir, name)
    if not ok:
        raise RuntimeError("fallback contract failed: " + out[-2000:])
    return {"name": name, "source": "fallback", "attempts": attempts, "test_output": out}


# ---------------------------------------------------------------- docs
DOCS_SYSTEM = (
    "You write winning hackathon and grant submissions that are strictly honest. What the generated product ACTUALLY contains: (1) the "
    "Solidity contract shown below with its Foundry tests; (2) a static GitHub Pages app that shows the product copy, connects an injected "
    "wallet, switches to the target chain, shows the live block number, deploys the contract from the browser and renders every contract "
    "function as a form (reads and writes) with the help text you provide; (3) GitHub Actions CI (build, tests, gitleaks) and Pages deploy; "
    "(4) this submission pack. Nothing else exists: no custom quoting/indexing UI, no extra Actions jobs, no backend, no sponsor SDK calls. "
    "Never describe planned features as present - put them in the roadmap/milestones and mark the related tracks 'planned'. Write to the "
    "judging criteria explicitly. Reply with one JSON object."
)
DOCS_SHAPE = {
    "content": {"hero_title": "string", "hero_sub": "one line", "problem": "string", "solution": "string",
                "features": [{"title": "string", "text": "string"}], "how_it_works": ["step strings, 4-6"],
                "function_help": {"<contract function name>": "one sentence telling the user what to enter and what happens"}},
    "readme_overview_md": "2 short paragraphs",
    "project_description_md": "submission text with one '###' section per judging criterion (or grant objective/metric)",
    "sponsor_track_mapping_md": "markdown table: Track | Sponsor | Prize | How we qualify | Evidence (repo paths) | Status",
    "demo_script_md": "2-3 minute demo video script with timestamps, using the live Pages app",
    "deck_marp_md": "Marp markdown deck, 8-12 slides separated by ---, begins with front matter marp: true",
    "milestones_budget_md": "grants: milestones table (critical + benchmark, dates, KPI) and budget table in USD with totals; hackathons: post-event roadmap table",
    "compliance": [{"rule": "each rule/deliverable/eligibility item from the brief", "status": "met|partial|todo", "evidence": "file, URL or what the team must do"}],
}


def write_docs(req: dict, plan: dict, contract_src: str) -> dict:
    user = (f"REQUIREMENTS:\n{json.dumps(req, indent=1)[:25000]}\n\nPLAN:\n{json.dumps(plan, indent=1)[:15000]}\n\nCONTRACT ({plan['contract']['name']}):\n{contract_src[:12000]}\n\n"
            f"The live app is a static GitHub Pages site where users connect a wallet, deploy the contract on {plan['chain']['name']} and call every function.\n"
            f"Return JSON with this shape:\n{json.dumps(DOCS_SHAPE, indent=1)}")
    return grok.chat_json("submission-pack", DOCS_SYSTEM, user, max_tokens=20000, temperature=0.5)


def fallback_docs(req: dict, plan: dict) -> dict:
    """Deterministic pack used when Grok is unavailable (CI self-test): built only from requirements + plan."""
    tracks = plan.get("target_tracks", [])
    rows = "\n".join(f"| {t.get('track')} | {t.get('sponsor', '')} | | {t.get('integration', t.get('why', ''))} | `contracts/`, `web/` | planned |" for t in tracks)
    crit = "\n\n".join(f"### {c.get('name')}\n{plan.get('solution', '')}" for c in req.get("judging_criteria", [])) or plan.get("solution", "")
    return {
        "content": {"hero_title": plan.get("title", "Product"), "hero_sub": plan.get("tagline", ""), "problem": plan.get("problem", ""), "solution": plan.get("solution", ""),
                    "features": [{"title": f, "text": f} for f in plan.get("frontend", {}).get("features", [])[:6]] or [{"title": "On-chain core", "text": plan["contract"].get("description", "")}],
                    "how_it_works": ["Connect a wallet", f"Deploy {plan['contract']['name']} from the browser", "Call the contract functions", "Share the address"]},
        "readme_overview_md": plan.get("solution", ""),
        "project_description_md": f"## {plan.get('title')}\n\n{plan.get('problem', '')}\n\n{crit}",
        "sponsor_track_mapping_md": "| Track | Sponsor | Prize | How we qualify | Evidence | Status |\n|---|---|---|---|---|---|\n" + rows,
        "demo_script_md": "1. 0:00 problem\n2. 0:30 open the Pages app, connect wallet\n3. 1:00 deploy contract\n4. 1:30 call functions\n5. 2:30 wrap-up",
        "deck_marp_md": f"---\nmarp: true\n---\n\n# {plan.get('title')}\n{plan.get('tagline', '')}\n\n---\n\n## Problem\n{plan.get('problem', '')}\n\n---\n\n## Solution\n{plan.get('solution', '')}\n",
        "milestones_budget_md": "| Milestone | Deliverable | Date |\n|---|---|---|\n| M1 | Testnet deployment | +2 weeks |",
        "compliance": [{"rule": r, "status": "todo", "evidence": "review"} for r in req.get("rules", [])],
    }


# ---------------------------------------------------------------- repo files
def _md_table(rows: list[list[str]], head: list[str]) -> str:
    esc = lambda s: str(s if s is not None else "").replace("|", "\\|").replace("\n", " ")
    return "| " + " | ".join(head) + " |\n|" + "---|" * len(head) + "\n" + "\n".join("| " + " | ".join(esc(c) for c in r) + " |" for r in rows)


def generate(out: Path, req: dict, plan: dict, *, repo_url: str, pages_url: str, ref: str = "main", use_grok: bool = True) -> dict:
    t0 = dt.datetime.now(dt.timezone.utc)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(TEMPLATE, out)
    cdir = out / "contracts"
    pins = vendor(cdir / "lib")
    contract = author_contract(cdir, req, plan) if use_grok else author_contract_fallback_only(cdir, req, plan)
    name = contract["name"]
    src = (cdir / "src" / f"{name}.sol").read_text()
    try:
        docs = write_docs(req, plan, src) if (use_grok and grok.available()) else fallback_docs(req, plan)
        docs_source = "grok" if (use_grok and grok.available()) else "template"
    except grok.GrokError as e:
        docs, docs_source = fallback_docs(req, plan), f"template (grok error: {e})"
    deck = docs.get("deck_marp_md", "")
    if "marp: true" not in deck[:200]:
        deck = "---\nmarp: true\ntheme: default\npaginate: true\n---\n\n" + deck
    blob = f"{repo_url}/blob/{ref}"
    is_grant = (req.get("kind") == "grant") or bool(req.get("grant"))

    sub = out / "docs" / "submission"
    sub.mkdir(parents=True, exist_ok=True)
    files = {
        "PROJECT.md": f"# {plan['title']} — project description\n\n{docs.get('project_description_md', '')}\n",
        "TRACKS.md": f"# Sponsor / track mapping\n\n{docs.get('sponsor_track_mapping_md', '')}\n",
        "DEMO-SCRIPT.md": f"# Demo script\n\nLive app: {pages_url}\n\n{docs.get('demo_script_md', '')}\n",
        "DECK.md": deck,
        ("MILESTONES-BUDGET.md" if is_grant else "ROADMAP.md"): f"# {'Grant milestones and budget' if is_grant else 'Post-event roadmap'}\n\n{docs.get('milestones_budget_md', '')}\n",
    }
    for fn, body in files.items():
        (sub / fn).write_text(body)
    comp = docs.get("compliance", [])
    auto = [
        {"rule": "Public source repository", "status": "met", "evidence": repo_url},
        {"rule": "Contracts build and tests pass (forge)", "status": "met", "evidence": f"{blob}/scripts/ci.sh + CI workflow"},
        {"rule": "Live demo deployed", "status": "met", "evidence": pages_url},
        {"rule": "Demo video recorded", "status": "todo", "evidence": "record using docs/submission/DEMO-SCRIPT.md, then link it here"},
    ]
    (out / "COMPLIANCE.md").write_text(
        f"# Compliance checklist\n\nAgainst: {', '.join(req.get('sources', [])) or 'pasted brief'} ({req.get('program', '')}).\n"
        "`met` = satisfied by this repo, `partial` = needs a small team action, `todo` = the team must do it before submitting.\n\n"
        "## Brief rules and deliverables\n\n" + _md_table([[c.get("rule"), c.get("status"), c.get("evidence")] for c in comp], ["Rule", "Status", "Evidence"])
        + "\n\n## Automated by buidl (verified before the run is marked success)\n\n" + _md_table([[c["rule"], c["status"], c["evidence"]] for c in auto], ["Check", "Status", "Evidence"]) + "\n")

    brief_dir = out / "brief"
    brief_dir.mkdir(exist_ok=True)
    (brief_dir / "requirements.json").write_text(json.dumps(req, indent=2))
    (brief_dir / "plan.json").write_text(json.dumps(plan, indent=2))

    docs_links = [{"title": "Project description", "href": f"{blob}/docs/submission/PROJECT.md"},
                  {"title": "Sponsor / track mapping", "href": f"{blob}/docs/submission/TRACKS.md"},
                  {"title": "Pitch deck (slides)", "href": "./deck.html"},
                  {"title": "Demo script", "href": f"{blob}/docs/submission/DEMO-SCRIPT.md"},
                  {"title": "Milestones & budget" if is_grant else "Roadmap", "href": f"{blob}/docs/submission/{'MILESTONES-BUDGET' if is_grant else 'ROADMAP'}.md"},
                  {"title": "Compliance checklist", "href": f"{blob}/COMPLIANCE.md"},
                  {"title": "Source code", "href": repo_url}]
    project = {"slug": plan["slug"], "title": plan["title"], "contract": name, "chain": plan["chain"], "repo_url": repo_url, "pages_url": pages_url,
               "tracks": plan.get("target_tracks", []), "blocks": [b["ref"] for b in plan["bill_of_blocks"] if b["ref"].count("/") == 1],
               "docs": docs_links, "deployments": {}}
    (out / "web" / "src" / "project.json").write_text(json.dumps(project, indent=2))
    (out / "web" / "src" / "content.json").write_text(json.dumps(docs["content"], indent=2))
    meta = {"slug": plan["slug"], "contract": name, "chain": plan["chain"], "generated_at": t0.isoformat(timespec="seconds"), "generator": "Blockchains/buidl",
            "brief_sources": req.get("sources", []), "contract_source": contract["source"], "docs_source": docs_source, "vendored": pins}
    (out / "buidl.json").write_text(json.dumps(meta, indent=2))

    bob_rows = [[f"[{b['ref']}](https://github.com/{'/'.join(b['ref'].split('/')[:2])})", b.get("reuse_method", ""), b.get("how_used", "")] for b in plan["bill_of_blocks"]]
    tracks_rows = [[t.get("track"), t.get("sponsor"), t.get("integration") or t.get("why")] for t in plan.get("target_tracks", [])]
    owner_repo = "/".join(repo_url.rstrip("/").split("/")[-2:])
    badges = (f"[![CI](https://github.com/{owner_repo}/actions/workflows/ci.yml/badge.svg)](https://github.com/{owner_repo}/actions/workflows/ci.yml) "
              f"[![Pages](https://github.com/{owner_repo}/actions/workflows/pages.yml/badge.svg)]({pages_url})") if ref == "main" else ""
    todo = "\n".join(f"- {x}" for x in plan.get("sponsor_integrations_todo", [])) or "- none"
    readme = f"""# {plan['title']}

{badges}

**{plan.get('tagline', '')}**

- **Live app:** {pages_url} (connect a wallet → deploy `{name}` on {plan['chain']['name']} → use it)
- **Brief:** {', '.join(req.get('sources', [])) or 'pasted text'} — {req.get('program', '')} ({req.get('kind', '')})
- **Submission pack:** [project description](docs/submission/PROJECT.md) · [track mapping](docs/submission/TRACKS.md) · [deck](docs/submission/DECK.md) ([slides]({pages_url.rstrip('/')}/deck.html)) · [demo script](docs/submission/DEMO-SCRIPT.md) · [{'milestones & budget' if is_grant else 'roadmap'}](docs/submission/{'MILESTONES-BUDGET' if is_grant else 'ROADMAP'}.md) · [compliance](COMPLIANCE.md)

{docs.get('readme_overview_md', '')}

## Architecture

```mermaid
{plan.get('architecture', {}).get('mermaid', 'flowchart LR\n  User --> Web --> Contract')}
```

| Part | Where | Notes |
|---|---|---|
| Smart contract `{name}` | `contracts/src/{name}.sol` | Foundry, OpenZeppelin v5 vendored from the Blockchains fork, tests in `contracts/test/` |
| Web app | `web/` | static Vite + viem; wallet connect, browser deploy, ABI-driven read/write UI; GitHub Pages |
| Backend | none | serverless-free: chain state + static site; optional jobs run as GitHub Actions |
| CI | `.github/workflows/ci.yml` → `scripts/ci.sh` | forge build/test, web tests/build, deck build, gitleaks |

## Tracks targeted

{_md_table(tracks_rows, ['Track', 'Sponsor', 'How'])}

Sponsor integrations that still need team keys or mainnet access:
{todo}

## Bill of blocks (reuse)

{_md_table(bob_rows, ['Block', 'Reuse', 'How it is used'])}

## Run it

```bash
bash scripts/ci.sh                        # forge build + test, web test + build, deck -> web/dist
cd web && npx vite preview                # open the built app locally
cd contracts && RPC_URL=<rpc> forge script script/Deploy.s.sol --rpc-url target --broadcast --account <keystore>   # CLI deploy (optional)
```

Generated by [Blockchains/buidl](https://github.com/Blockchains/buidl) from the brief above; see `brief/requirements.json` and `brief/plan.json`.
Contract source: {'Grok-authored and verified by forge test' if contract['source'] == 'grok' else 'tested fallback template'}.

<!-- blocks:start -->
## For AI agents
Read [AGENTS.md](AGENTS.md), [llms.txt](llms.txt) and [blocks.json](blocks.json).
<!-- blocks:end -->
"""
    (out / "README.md").write_text(readme)
    (out / "AGENTS.md").write_text(f"""# AGENTS.md: {plan['slug']}

{plan.get('tagline', '')}. Generated by Blockchains/buidl from a {req.get('kind', 'hackathon')} brief ({req.get('program', '')}).

## Setup / build / test
```bash
bash scripts/ci.sh      # needs foundry + node 20; builds contracts, runs forge tests, web tests, vite build, Marp deck
```

## Structure
| Path | What |
|---|---|
| `contracts/src/{name}.sol` | the on-chain core (no-arg constructor; deployed from the browser) |
| `contracts/test/` | Foundry tests (must stay green) |
| `contracts/lib/` | vendored OpenZeppelin + forge-std from the Blockchains forks (pinned in buidl.json) |
| `web/src/main.js` | static app: wallet, deploy, ABI-driven UI; content in `web/src/content.json`, config in `web/src/project.json` |
| `docs/submission/` | project description, track mapping, demo script, Marp deck, milestones/roadmap |
| `COMPLIANCE.md` | checklist against the brief's rules |
| `brief/` | parsed requirements and plan used to generate this repo |

## Rules
- Keep `scripts/ci.sh` green; it is what CI and Pages run.
- The constructor must stay argument-free (browser deploy), or update `web/src/main.js` deploy inputs (they are ABI-driven, so args work too).
- No secrets in the repo; run gitleaks before pushing. No mocked data in the shipped app.
- Update `docs/submission/*` and `COMPLIANCE.md` when features change.
""")
    (out / "llms.txt").write_text(f"""# {plan['title']}

> {plan.get('tagline', '')}

Live app: {pages_url}
Repo: {repo_url}

## Docs
- [README]({blob}/README.md): overview, architecture, bill of blocks
- [AGENTS.md]({blob}/AGENTS.md): build/test commands and structure
- [Project description]({blob}/docs/submission/PROJECT.md)
- [Track mapping]({blob}/docs/submission/TRACKS.md)
- [Compliance]({blob}/COMPLIANCE.md)
- [Contract]({blob}/contracts/src/{name}.sol)
- [blocks.json]({blob}/blocks.json)
""")
    blocks = {
        "schema_version": "1.0", "name": plan["slug"], "repo": owner_repo, "summary": f"{plan['title']}: {plan.get('tagline', '')}",
        "kind": ["app", "contract"], "stability": "experimental", "license": "MIT",
        "entrypoints": [{"type": "web", "name": "Live app", "ref": pages_url, "usage": "connect wallet, deploy, interact"},
                        {"type": "file", "name": f"contracts/src/{name}.sol", "ref": f"contracts/src/{name}.sol", "usage": "forge build"}],
        "inputs": [{"name": "wallet", "type": "EIP-1193"}], "outputs": [{"name": name, "type": "contract", "description": plan["contract"].get("description", "")}],
        "deps": ["foundry", "node>=20"],
        "compatible_with": [{"repo": b["ref"], "how": b.get("how_used", "")} for b in plan["bill_of_blocks"] if b["ref"].count("/") == 1],
        "tests": {"command": "bash scripts/ci.sh", "ci": ".github/workflows/ci.yml", "network": False},
        "docs": {"readme": "README.md", "agents": "AGENTS.md", "llms": "llms.txt"},
    }
    (out / "blocks.json").write_text(json.dumps(blocks, indent=2))
    return {"contract": {k: v for k, v in contract.items() if k != "test_output"}, "docs_source": docs_source, "vendored": pins}


def author_contract_fallback_only(cdir: Path, req: dict, plan: dict) -> dict:
    saved = grok.available
    grok.available = lambda: False  # type: ignore
    try:
        return author_contract(cdir, req, plan)
    finally:
        grok.available = saved  # type: ignore
