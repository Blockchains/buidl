"""Planning: Grok chooses a product concept and a bill of blocks from the shortlisted catalogue, maximising reuse."""
from __future__ import annotations

import json
import re

from . import grok
from .catalog import known_refs

TESTNETS = {
    "base": {"id": 84532, "name": "Base Sepolia", "rpc": "https://sepolia.base.org", "explorer": "https://sepolia.basescan.org"},
    "optimism": {"id": 11155420, "name": "OP Sepolia", "rpc": "https://sepolia.optimism.io", "explorer": "https://sepolia-optimism.etherscan.io"},
    "arbitrum": {"id": 421614, "name": "Arbitrum Sepolia", "rpc": "https://sepolia-rollup.arbitrum.io/rpc", "explorer": "https://sepolia.arbiscan.io"},
    "ethereum": {"id": 11155111, "name": "Sepolia", "rpc": "https://ethereum-sepolia-rpc.publicnode.com", "explorer": "https://sepolia.etherscan.io"},
    "polygon": {"id": 80002, "name": "Polygon Amoy", "rpc": "https://rpc-amoy.polygon.technology", "explorer": "https://amoy.polygonscan.com"},
    "hedera": {"id": 296, "name": "Hedera Testnet", "rpc": "https://testnet.hashio.io/api", "explorer": "https://hashscan.io/testnet"},
    "arc": {"id": 5042002, "name": "Arc Testnet", "rpc": "https://rpc.testnet.arc.network", "explorer": "https://testnet.arcscan.app"},
    "celo": {"id": 11142220, "name": "Celo Sepolia", "rpc": "https://forno.celo-sepolia.celo-testnet.org", "explorer": "https://celo-sepolia.blockscout.com"},
    "worldchain": {"id": 4801, "name": "World Chain Sepolia", "rpc": "https://worldchain-sepolia.g.alchemy.com/public", "explorer": "https://worldchain-sepolia.explorer.alchemy.com"},
    "unichain": {"id": 1301, "name": "Unichain Sepolia", "rpc": "https://sepolia.unichain.org", "explorer": "https://sepolia.uniscan.xyz"},
}

SHAPE = {
    "slug": "kebab-case repo name, 3-40 chars, prefix-free",
    "title": "product name",
    "tagline": "one line",
    "problem": "2-3 sentences",
    "solution": "2-4 sentences",
    "chain_key": f"one of {sorted(TESTNETS)} - the EVM testnet the demo targets",
    "target_tracks": [{"track": "exact track name from requirements", "sponsor": "string", "why": "fit", "integration": "what the product does with the sponsor tech"}],
    "contract": {"name": "PascalCase Solidity contract name", "description": "what it stores/enforces", "functions": [{"signature": "e.g. register(string uri)", "purpose": "string"}],
                 "events": ["string"], "notes": "constructor MUST take no arguments (owner = msg.sender)"},
    "frontend": {"features": ["user-visible features the generic app delivers: wallet connect, browser deploy, a form per contract function, live block"]},
    "roadmap": ["features beyond the generated scope (custom UI, indexers, Actions jobs, sponsor SDKs) - for the roadmap/milestones"],
    "architecture": {"mermaid": "flowchart LR ... (no quotes inside node labels)", "components": [{"name": "string", "kind": "contract|frontend|action|external", "block_ref": "catalogue ref or null"}]},
    "bill_of_blocks": [{"ref": "EXACT ref from the catalogue", "how_used": "string", "reuse_method": "vendored|npm|submodule|pattern|starter|api"}],
    "sponsor_integrations_todo": ["sponsor SDK steps that need team API keys or mainnet - honest list"],
    "risks": ["string"],
}

SYSTEM = (
    "You are a senior hackathon/grant architect for Blockchain Lab. Design ONE product that can be fully built, tested and deployed "
    "with this fixed stack: a single Foundry Solidity contract (OpenZeppelin v5 from the Blockchains fork available) and a generic static Vite "
    "web app on GitHub Pages (viem, injected wallet; deploys the contract from the browser and renders each contract function as a form). "
    "The contract therefore carries the product logic: design its functions so the product is usable through those forms alone. "
    "No paid API keys may be required for the demo to work. Maximise genuine reuse of the catalogue: bill_of_blocks lists only blocks the product "
    "really uses (code vendored/imported, a starter it is based on, a data API it calls, a pattern its contract follows) - typically 4-12 "
    "entries, each with a concrete how_used; no generic lists, awesome lists or org-meta repos. Every ref must be copied exactly from the "
    "catalogue given; prefer hub blocks and starters, then forks. Maximise the number of tracks/criteria the product can "
    "credibly target, but be honest: anything needing sponsor keys goes in sponsor_integrations_todo. Reply with one JSON object."
)


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")
    return re.sub(r"-+", "-", s)[:40] or "buidl-product"


def _slim_req(req: dict) -> dict:
    keep = ("kind", "program", "summary", "tracks", "judging_criteria", "required_chains", "required_sdks", "deliverables", "rules", "grant", "keywords", "deadlines")
    return {k: req[k] for k in keep if k in req}


def make_plan(req: dict, short: dict, cat: dict, name: str | None = None) -> dict:
    def slim(e: dict) -> dict:
        return {k: (v[:140] if isinstance(v, str) else v) for k, v in e.items() if k in ("ref", "summary", "category", "reuse_method", "kind") and v}
    compact = {k: [slim(e) for e in short[k]] for k in ("hub", "starters", "index", "grokhack")}
    user = (f"REQUIREMENTS:\n{json.dumps(_slim_req(req))[:24000]}\n\nCATALOGUE (shortlisted for this brief):\n{json.dumps(compact)[:45000]}\n\n"
            f"Return JSON with this shape:\n{json.dumps(SHAPE, indent=1)}")
    plan = grok.chat_json("plan", SYSTEM, user, max_tokens=12000, temperature=0.4)
    return normalise(plan, cat, name)


def normalise(plan: dict, cat: dict, name: str | None = None) -> dict:
    plan["slug"] = _slugify(name or plan.get("slug") or plan.get("title", ""))
    key = str(plan.get("chain_key", "base")).lower().replace(" ", "")
    plan["chain"] = TESTNETS.get(key) or next((v for k, v in TESTNETS.items() if k in key), TESTNETS["base"])
    c = plan.setdefault("contract", {})
    c["name"] = re.sub(r"[^A-Za-z0-9]", "", c.get("name") or "App") or "App"
    if not c["name"][0].isalpha():
        c["name"] = "App" + c["name"]
    if c["name"] in {"App", "Test", "Script", "Vm", "Deploy"}:
        c["name"] += "Core"
    refs = known_refs(cat)
    kept, dropped = [], []
    for b in plan.get("bill_of_blocks", []):
        (kept if b.get("ref") in refs else dropped).append(b)
    for must in ("Blockchains/openzeppelin-contracts", "Blockchains/forge-std"):
        if not any(b["ref"] == must for b in kept):
            kept.append({"ref": must, "how_used": "vendored into contracts/lib at a pinned tag", "reuse_method": "vendored"})
    kept.append({"ref": "Blockchains/buidl", "how_used": "product template, CI, Pages, submission pack generator", "reuse_method": "template"})
    plan["bill_of_blocks"], plan["unverified_blocks"] = kept, dropped
    return plan
