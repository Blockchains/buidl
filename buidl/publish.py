"""Publish + verify a generated product on GitHub.

mode=create : new public repo Blockchains/<slug> (needs a token with repo-create + workflow rights: FORGE_TOKEN in Actions,
              or a local `gh` login), Pages enabled (workflow build), wait for CI + Pages, check the site returns 200.
mode=branch : sandbox without FORGE_TOKEN: push branch product/<slug> to the pipeline repo itself (GITHUB_TOKEN), workflows stored
              under .buidl/workflows (GITHUB_TOKEN cannot write .github/workflows), CI via the pipeline's product-ci.yml and the site
              via its pages.yml at https://<owner>.github.io/<repo>/p/<slug>/. `python -m buidl promote` turns it into a real repo later.
"""
from __future__ import annotations

import calendar
import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

OWNER = os.environ.get("BUIDL_OWNER", "Blockchains")


def sh(cmd: list[str], cwd: Path | None = None, env: dict | None = None, check: bool = True, timeout: int = 280) -> str:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})}, timeout=timeout)
    if check and p.returncode:
        raise RuntimeError(f"{' '.join(cmd[:4])}... failed ({p.returncode}): {(p.stderr or p.stdout)[-1500:]}")
    return p.stdout.strip()


def http_status(url: str) -> int:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "buidl-verify", "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def wait_http(urls: list[str], timeout_s: int = 900) -> dict:
    deadline, status = time.time() + timeout_s, {}
    while time.time() < deadline:
        status = {u: http_status(u + ("&" if "?" in u else "?") + f"t={int(time.time())}") for u in urls}
        if all(s == 200 for s in status.values()):
            return {"ok": True, "status": status}
        time.sleep(20)
    return {"ok": False, "status": status}


def browser_smoke(url: str) -> dict:
    """Headless-Chromium check of the live site (buidl/smoke.py). Skipped (ok) when Playwright is not installed."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        return {"ok": True, "skipped": "playwright not installed"}
    import subprocess, sys
    last = {}
    for _ in range(3):
        r = subprocess.run([sys.executable, "-m", "buidl.smoke", url], capture_output=True, text=True, timeout=240)
        last = {"ok": r.returncode == 0, "output": r.stdout[-2000:], "stderr": r.stderr[-1500:]}
        if last["ok"]:
            return last
        time.sleep(20)
    return last


def _gitleaks(path: Path) -> None:
    exe = shutil.which("gitleaks")
    if not exe:
        return
    sh([exe, "detect", "--source", str(path), "--no-banner", "--redact", "--no-git"], timeout=200)


def find_run(repo: str, workflow: str, *, sha: str | None = None, title_contains: str | None = None, since: float = 0, env: dict | None = None, timeout_s: int = 300) -> int | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        out = sh(["gh", "run", "list", "-R", repo, "--workflow", workflow, "--limit", "30", "--json", "databaseId,headSha,displayTitle,createdAt"], env=env, check=False)
        try:
            runs = json.loads(out or "[]")
        except json.JSONDecodeError:
            runs = []
        for r in runs:
            created = calendar.timegm(time.strptime(r["createdAt"], "%Y-%m-%dT%H:%M:%SZ"))
            if sha and r["headSha"] != sha:
                continue
            if title_contains and title_contains not in r["displayTitle"]:
                continue
            if created + 5 < since:
                continue
            return r["databaseId"]
        time.sleep(10)
    return None


def wait_run(repo: str, run_id: int, env: dict | None = None, timeout_s: int = 1500) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        out = sh(["gh", "run", "view", str(run_id), "-R", repo, "--json", "status,conclusion,url"], env=env, check=False)
        try:
            d = json.loads(out)
        except json.JSONDecodeError:
            d = {}
        if d.get("status") == "completed":
            return d
        time.sleep(20)
    return {"status": "timeout", "conclusion": None, "url": f"https://github.com/{repo}/actions/runs/{run_id}"}


def failed_log(repo: str, run_id: int, env: dict | None = None) -> str:
    return sh(["gh", "run", "view", str(run_id), "-R", repo, "--log-failed"], env=env, check=False, timeout=120)[-6000:]


def _commit(path: Path, message: str) -> str:
    if not (path / ".git").exists():
        sh(["git", "init", "-q", "-b", "main"], path)
    sh(["git", "add", "-A"], path)
    sh(["git", "-c", "user.name=buidl-bot", "-c", "user.email=buidl-bot@users.noreply.github.com", "commit", "-q", "-m", message, "--allow-empty"], path)
    return sh(["git", "rev-parse", "HEAD"], path)


def _verify_ci(repo: str, workflow: str, *, sha: str | None, title: str | None, since: float, env: dict | None, reruns: int = 1) -> dict:
    rid = find_run(repo, workflow, sha=sha, title_contains=title, since=since, env=env)
    if not rid:
        return {"ok": False, "error": f"no {workflow} run found"}
    res = wait_run(repo, rid, env=env)
    tries = 0
    while res.get("conclusion") != "success" and tries < reruns:
        tries += 1
        sh(["gh", "run", "rerun", str(rid), "-R", repo, "--failed"], env=env, check=False)
        time.sleep(15)
        res = wait_run(repo, rid, env=env)
    out = {"ok": res.get("conclusion") == "success", "run_id": rid, "url": res.get("url"), "conclusion": res.get("conclusion"), "reruns": tries}
    if not out["ok"]:
        out["failed_log_tail"] = failed_log(repo, rid, env=env)[-3000:]
    return out


def publish_create(path: Path, slug: str, description: str, token_env: dict | None = None) -> dict:
    repo = f"{OWNER}/{slug}"
    env = token_env or {}
    _gitleaks(path)
    exists = sh(["gh", "repo", "view", repo, "--json", "name"], env=env, check=False)
    if exists:
        # only overwrite repos this pipeline generated
        probe = sh(["gh", "api", f"repos/{repo}/contents/buidl.json", "-q", ".name"], env=env, check=False)
        if probe != "buidl.json":
            raise RuntimeError(f"{repo} exists and was not generated by buidl - choose another name")
    sha = _commit(path, f"buidl: generate {slug}")
    since = time.time()
    if not exists:
        sh(["gh", "repo", "create", repo, "--public", "--description", description[:300]], env=env)
        sh(["gh", "api", "-X", "POST", f"repos/{repo}/pages", "-f", "build_type=workflow"], env=env, check=False)
    sh(["gh", "auth", "setup-git"], env=env, check=False)
    sh(["git", "push", "-q", "-f", f"https://github.com/{repo}.git", "HEAD:main"], path, env=env, timeout=280)
    sh(["gh", "repo", "edit", repo, "--homepage", f"https://{OWNER.lower()}.github.io/{slug}/", "--add-topic", "buidl", "--add-topic", "hackathon", "--add-topic", "blockchain"], env=env, check=False)
    sh(["gh", "api", "-X", "POST", f"repos/{repo}/pages", "-f", "build_type=workflow"], env=env, check=False)
    ci = _verify_ci(repo, "ci.yml", sha=sha, title=None, since=since, env=env)
    pages_since = time.time()
    sh(["gh", "workflow", "run", "pages.yml", "-R", repo, "--ref", "main"], env=env, check=False)
    pages = _verify_ci(repo, "pages.yml", sha=sha, title=None, since=pages_since, env=env)
    url = f"https://{OWNER.lower()}.github.io/{slug}/"
    live = wait_http([url, url + "deck.html", url + "contracts/App.json"]) if pages["ok"] else {"ok": False}
    smoke = browser_smoke(url) if live["ok"] else {"ok": False}
    return {"mode": "create", "repo": repo, "repo_url": f"https://github.com/{repo}", "pages_url": url, "sha": sha, "ci": ci, "pages": pages, "live": live, "smoke": smoke,
            "ok": ci["ok"] and pages["ok"] and live["ok"] and smoke["ok"]}


def publish_branch(path: Path, slug: str, host_repo: str, nonce: str) -> dict:
    branch = f"product/{slug}"
    wf = path / ".github" / "workflows"
    if wf.exists():
        dest = path / ".buidl" / "workflows"
        dest.parent.mkdir(exist_ok=True)
        shutil.rmtree(dest, ignore_errors=True)
        shutil.move(str(wf), dest)
        if not any((path / ".github").iterdir()):
            (path / ".github").rmdir()
    _gitleaks(path)
    sha = _commit(path, f"buidl: generate {slug}")
    tok = os.environ.get("GITHUB_TOKEN", "")
    remote = f"https://x-access-token:{tok}@github.com/{host_repo}.git" if tok else f"https://github.com/{host_repo}.git"
    sh(["git", "push", "-q", "-f", remote, f"HEAD:refs/heads/{branch}"], path, timeout=280)
    since = time.time()
    sh(["gh", "workflow", "run", "product-ci.yml", "-R", host_repo, "--ref", "main", "-f", f"branch={branch}", "-f", f"nonce={nonce}"])
    ci = _verify_ci(host_repo, "product-ci.yml", sha=None, title=nonce, since=since, env=None)
    pages_since = time.time()
    sh(["gh", "workflow", "run", "pages.yml", "-R", host_repo, "--ref", "main", "-f", f"nonce={nonce}"])
    pages = _verify_ci(host_repo, "pages.yml", sha=None, title=nonce, since=pages_since, env=None)
    owner, name = host_repo.split("/")
    url = f"https://{owner.lower()}.github.io/{name}/p/{slug}/"
    live = wait_http([url, url + "deck.html", url + "contracts/App.json"]) if pages["ok"] else {"ok": False}
    smoke = browser_smoke(url) if live["ok"] else {"ok": False}
    return {"mode": "branch", "repo": host_repo, "branch": branch, "repo_url": f"https://github.com/{host_repo}/tree/{branch}", "pages_url": url, "sha": sha,
            "ci": ci, "pages": pages, "live": live, "smoke": smoke, "ok": ci["ok"] and pages["ok"] and live["ok"] and smoke["ok"]}
