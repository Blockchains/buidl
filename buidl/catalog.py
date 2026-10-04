"""Block catalogues used for planning: hub blocks.json, blockchainlab-index catalog (forks + reuse fields),
grokhack-index repos and the blockchainlab-starters directories. Produces a scored shortlist for the planner."""
from __future__ import annotations

import json
import math
import os
import re
import urllib.request

SOURCES = {
    "hub": "https://blockchains.github.io/blocks.json",
    "index": "https://raw.githubusercontent.com/Blockchains/blockchainlab-index/main/catalog.json",
    "grokhack": "https://raw.githubusercontent.com/Blockchains/grokhack-index/main/repos.json",
    "starters": "https://api.github.com/repos/Blockchains/blockchainlab-starters/contents/starters",
}

STOP = set("the a an and or of to for in on with by is are be as at from this that your you we our it its use using build best new app apps project".split())


def _get(url: str):
    headers = {"User-Agent": "buidl", "Accept": "application/json"}
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {tok}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
        return json.load(r)


def load() -> dict:
    out = {"hub": [], "index": [], "grokhack": [], "starters": [], "errors": {}}
    try:
        for b in _get(SOURCES["hub"]).get("blocks", []):
            out["hub"].append({"ref": b["repo"], "source": "hub", "summary": b.get("summary", ""), "kind": b.get("kind", []),
                               "entrypoints": [e.get("name") for e in b.get("entrypoints", [])][:4]})
    except Exception as e:
        out["errors"]["hub"] = str(e)
    try:
        for r in _get(SOURCES["index"]).get("repos", []):
            reuse = r.get("reuse") or {}
            out["index"].append({"ref": r["fork"], "source": "blockchainlab-index", "upstream": r.get("upstream"), "summary": r.get("description") or "",
                                 "category": r.get("category"), "tags": r.get("tags", []), "capabilities": sorted((r.get("capabilities") or {}).keys()),
                                 "stars": r.get("stars", 0), "license": r.get("license"), "reuse_method": reuse.get("method"),
                                 "install": (reuse.get("install") or [])[:2], "pin": reuse.get("pin") or r.get("commit")})
    except Exception as e:
        out["errors"]["index"] = str(e)
    try:
        for r in _get(SOURCES["grokhack"]):
            out["grokhack"].append({"ref": r["fork"], "source": "grokhack-index", "upstream": r.get("upstream"), "summary": r.get("description") or "",
                                    "category": r.get("category"), "stars": r.get("stars", 0)})
    except Exception as e:
        out["errors"]["grokhack"] = str(e)
    try:
        for d in _get(SOURCES["starters"]):
            if d.get("type") == "dir":
                out["starters"].append({"ref": f"Blockchains/blockchainlab-starters/starters/{d['name']}", "source": "starter", "summary": d["name"].replace("-", " ")})
    except Exception as e:
        out["errors"]["starters"] = str(e)
    return out


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9][a-z0-9.+-]{1,}", text.lower()) if t not in STOP}


def requirement_terms(req: dict) -> set[str]:
    bits = list(req.get("keywords", [])) + list(req.get("required_chains", [])) + list(req.get("required_sdks", []))
    for t in req.get("tracks", []):
        bits += [t.get("name", ""), t.get("sponsor", "")] + list(t.get("sponsor_tech", []))
    if req.get("grant"):
        bits += [req["grant"].get("objective") or ""] + list(req["grant"].get("metrics") or [])
    return _tokens(" ".join(str(b) for b in bits if b))


def score(entry: dict, terms: set[str]) -> float:
    hay = _tokens(" ".join([entry.get("ref", ""), entry.get("upstream") or "", entry.get("summary", ""), entry.get("category") or "",
                            " ".join(entry.get("tags", [])), " ".join(entry.get("capabilities", []))]))
    overlap = len(hay & terms)
    return overlap * 10 + math.log10(1 + (entry.get("stars") or 0))


def shortlist(cat: dict, req: dict, n_index: int = 40, n_grok: int = 12) -> dict:
    terms = requirement_terms(req)
    idx = sorted(cat["index"], key=lambda e: -score(e, terms))[:n_index]
    grk = sorted(cat["grokhack"], key=lambda e: -score(e, terms))[:n_grok]
    return {"terms": sorted(terms)[:80], "hub": cat["hub"], "starters": cat["starters"], "index": idx, "grokhack": grk}


def known_refs(cat: dict) -> set[str]:
    refs = set()
    for k in ("hub", "index", "grokhack", "starters"):
        refs |= {e["ref"] for e in cat[k]}
    return refs
