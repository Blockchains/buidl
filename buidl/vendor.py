"""Vendor pinned Solidity libraries from the Blockchains forks into a generated project (hermetic builds, no submodules)."""
from __future__ import annotations

import io
import os
import shutil
import tarfile
import urllib.request
from pathlib import Path

CACHE = Path(os.environ.get("BUIDL_CACHE", Path.home() / ".cache" / "buidl"))
LIBS = {
    # name: (fork, ref, subpaths to keep)
    "openzeppelin-contracts": ("Blockchains/openzeppelin-contracts", "v5.7.0", ["contracts", "LICENSE"]),
    "forge-std": ("Blockchains/forge-std", "v1.17.0", ["src", "LICENSE-MIT", "LICENSE-APACHE"]),
}


def _download(fork: str, ref: str) -> Path:
    dest = CACHE / f"{fork.replace('/', '__')}@{ref}"
    if dest.exists():
        return dest
    url = f"https://codeload.github.com/{fork}/tar.gz/{ref}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "buidl"}), timeout=120) as r:
        data = r.read()
    tmp = dest.with_suffix(".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        tf.extractall(tmp, filter="data")
    (inner,) = list(tmp.iterdir())
    inner.rename(dest)
    shutil.rmtree(tmp, ignore_errors=True)
    return dest


def vendor(lib_dir: Path) -> list[dict]:
    pins = []
    for name, (fork, ref, keep) in LIBS.items():
        src = _download(fork, ref)
        out = lib_dir / name
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        for k in keep:
            p = src / k
            if p.is_dir():
                shutil.copytree(p, out / k, ignore=shutil.ignore_patterns("mocks", "*.md") if name == "openzeppelin-contracts" else None)
            elif p.exists():
                shutil.copy2(p, out / k)
        pins.append({"name": name, "fork": fork, "ref": ref})
    return pins
