"""Brief intake: fetch a URL (or take pasted text), reduce it to readable text, and parse it with Grok."""
from __future__ import annotations

import json
import re
import urllib.request
from html.parser import HTMLParser

from . import grok

MAX_CHARS = 60000


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template", "iframe"}
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "br", "td", "th", "header", "footer"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_text(raw: str) -> str:
    p = _Text()
    p.feed(raw)
    text = "".join(p.out)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (buidl brief fetcher; +https://github.com/Blockchains/buidl)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode(r.headers.get_content_charset() or "utf-8", errors="replace")
    return html_to_text(raw) if "<html" in raw[:5000].lower() or "<body" in raw.lower() else raw


def load(url: str | None, text: str | None) -> dict:
    parts, sources = [], []
    if url:
        for u in [x.strip() for x in re.split(r"[\s,]+", url) if x.strip()]:
            parts.append(f"=== SOURCE {u} ===\n{fetch(u)}")
            sources.append(u)
    if text and text.strip():
        parts.append(f"=== PASTED BRIEF ===\n{text.strip()}")
    body = "\n\n".join(parts)
    if len(body) < 200:
        raise ValueError("brief is too short (<200 chars) - give a URL with server-rendered text or paste the brief")
    return {"sources": sources, "text": body[:MAX_CHARS], "truncated": len(body) > MAX_CHARS, "chars": len(body)}


SCHEMA = {
    "kind": "hackathon | grant | bounty",
    "program": "string - event or programme name",
    "organizer": "string",
    "summary": "2-3 sentences",
    "deadlines": [{"name": "string", "date": "ISO date if stated, else text", "notes": "string"}],
    "tracks": [{"name": "string", "sponsor": "string", "prize_usd": "number or null (total for the track)", "prize_text": "string as written",
                "requirements": ["what a submission must do to qualify"], "sponsor_tech": ["SDKs/APIs/products to use"]}],
    "judging_criteria": [{"name": "string", "weight": "number or null", "description": "string"}],
    "required_chains": ["chains/networks named in the brief"],
    "required_sdks": ["SDKs/protocols the brief requires or rewards"],
    "deliverables": [{"name": "e.g. public repo, demo video, pitch deck, live demo, milestones", "required": "bool", "notes": "string"}],
    "rules": ["eligibility and submission rules, one per item"],
    "grant": {"objective": "string", "metrics": ["success metrics"], "budget": "string", "milestone_rules": ["string"], "eligibility": ["string"]},
    "keywords": ["10-20 technical keywords useful to select building blocks"],
}

SYSTEM = (
    "You extract structured requirements from hackathon, bounty and grant briefs. Only use facts present in the brief; "
    "use null/empty lists when something is not stated - never invent prizes, dates or sponsors. Keep every track. "
    "For grants fill `grant` (otherwise set it to null) and treat milestones/reporting as deliverables. Reply with one JSON object."
)


def parse(brief: dict) -> dict:
    user = f"Return JSON matching this shape:\n{json.dumps(SCHEMA, indent=1)}\n\nBRIEF ({brief['chars']} chars{', truncated' if brief['truncated'] else ''}):\n{brief['text']}"
    req = grok.chat_json("parse-brief", SYSTEM, user, max_tokens=12000, temperature=0.1)
    req.setdefault("tracks", [])
    req.setdefault("keywords", [])
    req["sources"] = brief["sources"]
    return req
