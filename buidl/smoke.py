"""Browser smoke test for a generated product site (Playwright/Chromium).
Checks: page renders the product copy, no JS errors, live block number from the public RPC, the deploy form, and one form per contract
function once an address is given. Usage: python3 -m buidl.smoke <site-url>   (exit 1 on failure)"""
import json
import sys
import urllib.request

from playwright.sync_api import sync_playwright

url = sys.argv[1].rstrip("/") + "/"
art = json.load(urllib.request.urlopen(url + "contracts/App.json", timeout=30))
n_fns = sum(1 for x in art["abi"] if x.get("type") == "function")
errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url + "?address=0x000000000000000000000000000000000000dEaD", wait_until="domcontentloaded")
    page.wait_for_function("() => document.querySelector('#hero-title').innerText.length > 2", timeout=30000)
    page.wait_for_function("() => /live block #\\d+|unreachable/.test(document.querySelector('#chain-line').innerText)", timeout=45000)
    page.wait_for_selector("#deploy-box button", timeout=30000)
    page.wait_for_function(f"() => document.querySelectorAll('#fns .fn').length === {n_fns}", timeout=30000)
    res = {"title": page.title(), "hero": page.inner_text("#hero-title"), "chain_line": page.inner_text("#chain-line"),
           "function_forms": page.locator("#fns .fn").count(), "abi_functions": n_fns, "deploy_button": page.inner_text("#deploy-box button"),
           "deck": urllib.request.urlopen(url + "deck.html", timeout=30).status, "js_errors": errors}
    b.close()
print(json.dumps(res, indent=1))
sys.exit(1 if errors or "live block" not in res["chain_line"] else 0)
