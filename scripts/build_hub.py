"""Build the buidl hub page (index.html + runs.json) from runs/*.json into the given site dir."""
import html
import json
import sys
from pathlib import Path

site = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
site.mkdir(parents=True, exist_ok=True)
runs = []
for p in sorted(Path("runs").glob("*.json")):
    try:
        runs.append(json.loads(p.read_text()))
    except json.JSONDecodeError:
        pass
latest = {}
for r in sorted(runs, key=lambda r: r.get("started_at", "")):
    if r.get("slug"):
        latest[r["slug"]] = r
promoted = json.loads(Path("runs/promoted.json").read_text()) if Path("runs/promoted.json").exists() else {}
(site / "runs.json").write_text(json.dumps(list(latest.values()), indent=1))
e = html.escape
rows = []
for slug, r in sorted(latest.items(), key=lambda kv: kv[1].get("started_at", ""), reverse=True):
    pub, plan = r.get("publish") or {}, (r.get("steps") or {}).get("plan") or {}
    sandbox = f"p/{slug}/" if (site / "p" / slug).exists() else ""
    links = []
    if slug in promoted:
        links += [f'<a href="{e(promoted[slug]["pages_url"])}">live app</a>', f'<a href="{e(promoted[slug]["repo_url"])}">repo</a>']
    if pub.get("pages_url"):
        links.append(f'<a href="{e(pub["pages_url"])}">{"sandbox app" if pub.get("mode") == "branch" else "live app"}</a>')
    elif sandbox:
        links.append(f'<a href="{sandbox}">sandbox app</a>')
    if pub.get("repo_url"):
        links.append(f'<a href="{e(pub["repo_url"])}">source</a>')
    if r.get("run_url"):
        links.append(f'<a href="{e(r["run_url"])}">run</a>')
    rows.append(f"<tr><td><b>{e(plan.get('title') or slug)}</b><br><small>{e(slug)}</small></td><td>{e(str((r.get('steps') or {}).get('parse', {}).get('program') or ''))}</td>"
                f"<td>{e(r.get('status', ''))}</td><td>{' · '.join(links)}</td></tr>")
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>buidl — brief to product</title><meta name="description" content="Paste a hackathon or grant brief, get a working product repo with contracts, live app and submission pack.">
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:980px;margin:0 auto;padding:24px;background:#0b0d12;color:#e8ecf3}}a{{color:#a99bff}}
table{{width:100%;border-collapse:collapse}}td,th{{border-bottom:1px solid #222a3a;padding:8px;text-align:left;vertical-align:top}}code{{color:#ffd479}}</style></head><body>
<h1>buidl — brief → product</h1>
<p>GitHub-native pipeline: a hackathon / grant brief becomes a repo with a Foundry contract, a live GitHub Pages app, CI, and a submission pack
(project description, track mapping, demo script, Marp deck, milestones/budget, compliance checklist), assembled from
<a href="https://blockchains.github.io/blocks.json">Blockchain Lab blocks</a>. Verified before success: build, tests, CI green, Pages 200.</p>
<p><b>Run it:</b> <a href="https://github.com/Blockchains/buidl/issues/new?template=brief.yml">open a Brief issue</a> or
<a href="https://github.com/Blockchains/buidl/actions/workflows/buidl.yml">Actions → Brief to product → Run workflow</a> ·
<a href="https://github.com/Blockchains/buidl">source</a> · <a href="https://github.com/Blockchains/buidl/blob/main/docs/HOW-TO-SUBMIT-A-BRIEF.md">how to submit a brief</a> ·
<a href="runs.json">runs.json</a></p>
<h2>Products</h2><table><tr><th>Product</th><th>Brief</th><th>Status</th><th>Links</th></tr>{''.join(rows) or '<tr><td colspan=4>No runs yet</td></tr>'}</table>
</body></html>"""
(site / "index.html").write_text(page)
print(f"hub: {len(latest)} products -> {site}/index.html")
