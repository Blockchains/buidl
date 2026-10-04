"""Read pipeline inputs from a workflow_dispatch payload or an issue-form body; write them to files/GITHUB_OUTPUT (no shell interpolation)."""
import json
import os
import re
from pathlib import Path

ev = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
out = Path("inputs")
out.mkdir(exist_ok=True)
if "issue" in ev:
    body = ev["issue"].get("body") or ""
    fields = {}
    for m in re.finditer(r"^### (.+?)\n+(.*?)(?=^### |\Z)", body, re.S | re.M):
        v = m.group(2).strip()
        fields[m.group(1).strip().lower()] = "" if v == "_No response_" else v
    url, text, name, mode = fields.get("brief url(s)", ""), fields.get("pasted brief", ""), fields.get("repo name", ""), fields.get("publish mode", "auto") or "auto"
    issue = str(ev["issue"]["number"])
else:
    i = ev.get("inputs") or {}
    url, text, name, mode, issue = i.get("brief_url", ""), i.get("brief_text", ""), i.get("name", ""), i.get("mode", "auto"), ""
name = re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")[:40]
mode = mode if mode in {"auto", "create", "branch", "none"} else "auto"
(out / "brief_text.txt").write_text(text)
args = ["--brief-file", "inputs/brief_text.txt", "--mode", mode]
if url:
    args += ["--brief-url", url]
if name:
    args += ["--name", name]
(out / "args.json").write_text(json.dumps(args))
with open(os.environ["GITHUB_OUTPUT"], "a") as f:
    f.write(f"issue={issue}\nmode={mode}\n")
print("inputs:", json.dumps({"url": url, "name": name, "mode": mode, "issue": issue, "text_chars": len(text)}))
