"""Write runs/<slug>-<run_id>.json + summary.md (job summary + issue comment) from the pipeline result."""
import json
import os
import sys
from pathlib import Path

res = json.loads(Path(sys.argv[1]).read_text()) if Path(sys.argv[1]).exists() else {"status": "failed", "error": "no result.json"}
run_id = os.environ.get("GITHUB_RUN_ID", "local")
run_url = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ.get('GITHUB_REPOSITORY', 'Blockchains/buidl')}/actions/runs/{run_id}"
res["run_url"] = run_url
slug = res.get("slug", "unknown")
Path("runs").mkdir(exist_ok=True)
for c in (res.get("steps", {}).get("local_ci") or {},):
    c.pop("tail", None)
Path(f"runs/{slug}-{run_id}.json").write_text(json.dumps(res, indent=2))
pub = res.get("publish") or {}
plan = res.get("steps", {}).get("plan") or {}
gen = res.get("steps", {}).get("generate") or {}
u = res.get("grok_usage") or {}
lines = [f"## buidl: {plan.get('title', slug)} — **{res.get('status')}**", ""]
if pub:
    lines += [f"- Repo: {pub.get('repo_url')}", f"- Live app: {pub.get('pages_url')} ({'200 OK' if (pub.get('live') or {}).get('ok') else 'not live'})",
              f"- CI: {(pub.get('ci') or {}).get('conclusion')} {(pub.get('ci') or {}).get('url', '')}", f"- Pages deploy: {(pub.get('pages') or {}).get('conclusion')} {(pub.get('pages') or {}).get('url', '')}",
              f"- Browser smoke test: {'passed' if (pub.get('smoke') or {}).get('ok') and not (pub.get('smoke') or {}).get('skipped') else (pub.get('smoke') or {}).get('skipped') or 'failed'}"]
    if pub.get("mode") == "branch":
        lines += ["", f"Sandbox mode (no `FORGE_TOKEN`). Promote to its own repo with `python3 -m buidl promote {slug}` (needs gh as Blockchains) or add the `FORGE_TOKEN` secret and re-run."]
if plan:
    lines += ["", f"- Contract: `{plan.get('contract')}` ({(gen.get('contract') or {}).get('source', '?')}, {len((gen.get('contract') or {}).get('attempts', []))} Grok attempts) on {plan.get('chain')}",
              f"- Tracks: {', '.join(t for t in plan.get('tracks', []) if t)}", f"- Blocks: {', '.join(plan.get('blocks', []))}"]
if res.get("error"):
    lines += ["", "```", res["error"][:1500], "```"]
lines += ["", f"Grok: {u.get('calls', 0)} calls, {u.get('prompt_tokens', 0)}+{u.get('completion_tokens', 0)} tokens, ${u.get('usd', 0)} · elapsed {res.get('elapsed_s', '?')}s · [run]({run_url})"]
Path("summary.md").write_text("\n".join(lines) + "\n")
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
        f.write("\n".join(lines) + "\n")
print("\n".join(lines))
