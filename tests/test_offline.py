"""Offline unit tests for buidl (no network, no Grok)."""
import json
import unittest
from pathlib import Path

from buidl import brief, catalog, plan

ROOT = Path(__file__).resolve().parents[1]


class BriefTests(unittest.TestCase):
    def test_html_to_text_strips_scripts_and_tags(self):
        t = brief.html_to_text("<html><script>x=1</script><h1>Prizes</h1><p>Best &amp; brightest</p></html>")
        self.assertIn("Prizes", t)
        self.assertIn("Best & brightest", t)
        self.assertNotIn("x=1", t)

    def test_short_brief_rejected(self):
        with self.assertRaises(ValueError):
            brief.load(None, "too short")


class CatalogTests(unittest.TestCase):
    def test_terms_and_scoring(self):
        req = {"keywords": ["ERC-20", "governance"], "tracks": [{"name": "Best DeFi", "sponsor": "Uniswap", "sponsor_tech": ["Uniswap v4 hooks"]}]}
        terms = catalog.requirement_terms(req)
        self.assertIn("uniswap", terms)
        hi = catalog.score({"ref": "Blockchains/v4-core", "summary": "Uniswap v4 hooks core", "stars": 10}, terms)
        lo = catalog.score({"ref": "Blockchains/other", "summary": "unrelated", "stars": 10}, terms)
        self.assertGreater(hi, lo)


class PlanTests(unittest.TestCase):
    def test_normalise_drops_unknown_blocks_and_fixes_names(self):
        cat = {"hub": [{"ref": "Blockchains/blockchainlab-starters"}], "index": [], "grokhack": [], "starters": []}
        p = plan.normalise({"title": "My Cool App!", "chain_key": "optimism", "contract": {"name": "Test"},
                            "bill_of_blocks": [{"ref": "Blockchains/blockchainlab-starters"}, {"ref": "Nope/made-up"}]}, cat)
        self.assertEqual(p["slug"], "my-cool-app")
        self.assertEqual(p["chain"]["id"], 11155420)
        self.assertEqual(p["contract"]["name"], "TestCore")
        refs = [b["ref"] for b in p["bill_of_blocks"]]
        self.assertIn("Blockchains/openzeppelin-contracts", refs)
        self.assertNotIn("Nope/made-up", refs)
        self.assertEqual(p["unverified_blocks"][0]["ref"], "Nope/made-up")


class ExampleTests(unittest.TestCase):
    def test_examples_are_valid(self):
        for d in (ROOT / "examples").iterdir():
            if d.is_dir():
                req = json.loads((d / "requirements.json").read_text())
                self.assertTrue(req.get("program"), d)
                self.assertTrue(req.get("sources"), d)


if __name__ == "__main__":
    unittest.main()
