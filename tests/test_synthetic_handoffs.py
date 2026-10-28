#!/usr/bin/env python3
"""Offline synthetic regression tests: never touch production articles."""
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

publisher = load("dwn_publisher", "publisher/process_handoff.py")

class PublisherTests(unittest.TestCase):
    def test_two_item_batch_second_invalid_leaves_no_article(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/"handoff/inbox").mkdir(parents=True)
            for reg in publisher.REGISTER_PATHS:
                (root/reg).write_text('{"processed": []}', encoding="utf-8")
            valid = "articles/trends/2026-10-28_0950_test-nur-simulation.md"
            body = '# Test\n\n<a href="https://example.org/a" target="_blank" rel="noopener nofollow">Studie</a> und <a href="https://example.org/b" target="_blank" rel="noopener nofollow">Statistik</a>.'
            payload = {"version":2,"items":[
                {"article_path":valid,"article_content":body,"register":{"path":"processed-trends.json","entry":{"trend":"Test","article_path":valid,"processed_at":"2026-10-28T09:50:00+01:00"}}},
                {"article_path":"articles/trends/invalid.md","article_content":body}
            ]}
            handoff=root/"handoff/inbox/test.json"
            handoff.write_text(json.dumps(payload),encoding="utf-8")
            with patch.object(publisher,"ROOT",root),patch.object(publisher,"INBOX",root/"handoff/inbox"),patch.object(publisher,"PROCESSED",root/"handoff/processed"),patch.object(publisher,"REJECTED",root/"handoff/rejected"):
                with self.assertRaises(ValueError):
                    publisher.process_one(handoff)
            self.assertFalse((root/valid).exists())
            self.assertEqual(json.loads((root/"processed-trends.json").read_text())["processed"],[])
            self.assertTrue(handoff.exists())

    def test_valid_synthetic_handoff(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"handoff/inbox").mkdir(parents=True)
            for reg in publisher.REGISTER_PATHS:
                (root/reg).write_text('{"processed": []}',encoding="utf-8")
            path="articles/mail/2026-10-28_1020_test-nur-simulation.md"
            body='# Test\n\n<a href="https://example.org/a" target="_blank" rel="noopener nofollow">Studie</a> und <a href="https://example.org/b" target="_blank" rel="noopener nofollow">Statistik</a>.'
            h=root/"handoff/inbox/test.json"
            h.write_text(json.dumps({"version":2,"items":[{"article_path":path,"article_content":body,"register":{"path":"processed-press-releases.json","entry":{"gmail_message_id":"synthetic-001","article_path":path,"status":"processed"}}}]}),encoding="utf-8")
            with patch.object(publisher,"ROOT",root),patch.object(publisher,"INBOX",root/"handoff/inbox"),patch.object(publisher,"PROCESSED",root/"handoff/processed"),patch.object(publisher,"REJECTED",root/"handoff/rejected"):
                publisher.process_one(h)
            self.assertTrue((root/path).exists())
            self.assertTrue((root/"handoff/processed/test.json").exists())


class SchedulingTests(unittest.TestCase):
    def test_market_catchup_after_noon(self):
        import sys
        sys.path.insert(0, str(ROOT/"automation"))
        agents = load("dwn_agents_synthetic", "automation/agents.py")
        fake_now = datetime(2026, 10, 28, 15, 30, tzinfo=ZoneInfo("Europe/Berlin"))
        with patch.object(agents, "now_berlin", return_value=fake_now):
            self.assertEqual(set(agents.due_names()), {"gold", "bitcoin", "rheinmetall"})

    def test_market_no_weekend_generation(self):
        import sys
        sys.path.insert(0, str(ROOT/"automation"))
        agents = load("dwn_agents_weekend", "automation/agents.py")
        fake_now = datetime(2026, 10, 31, 15, 30, tzinfo=ZoneInfo("Europe/Berlin"))
        with patch.object(agents, "now_berlin", return_value=fake_now):
            self.assertEqual(agents.due_names(), [])

    def test_trend_twelve_hour_cooldown(self):
        import sys
        sys.path.insert(0, str(ROOT/"automation"))
        trends = load("dwn_trends_synthetic", "automation/trends.py")
        self.assertIn("cutoff = now_berlin() - timedelta(hours=12)", (ROOT/"automation/trends.py").read_text())
        now = datetime(2026, 10, 28, 15, 0, tzinfo=ZoneInfo("Europe/Berlin"))
        register = [{"trend":"Testtrend","processed_at":(now-timedelta(hours=13)).isoformat()},
                    {"trend":"Neuer Trend","processed_at":(now-timedelta(hours=11)).isoformat()}]
        # Exercise the real candidate-filter path without making external API calls.
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"latest.json").write_text(json.dumps({"ok":True,"captured_at":now.astimezone(ZoneInfo("UTC")).isoformat(),
                "final_url":"https://trends.google.com/?geo=DE&hours=4&category=3&status=active&sort=search-volume",
                "body_text":"Deutschland","rows":[{"text":"Testtrend 1000+"},{"text":"Neuer Trend 900+"}]}))
            (root/"processed-trends.json").write_text(json.dumps({"processed":register}))
            (root/"articles/trends").mkdir(parents=True)
            captured=[]
            class SyntheticStop(Exception): pass
            def fake_openai(prompt, *args, **kwargs):
                captured.append(prompt)
                raise SyntheticStop()
            with patch.object(trends,"ROOT",root),patch.object(trends,"LATEST",root/"latest.json"),patch.object(trends,"REGISTER",root/"processed-trends.json"),patch.object(trends,"ARTICLES",root/"articles/trends"),patch.object(trends,"now_berlin",return_value=now),patch.object(trends,"call_openai",side_effect=fake_openai),patch.object(trends,"verify_latest",return_value=[]):
                with self.assertRaises(SyntheticStop):
                    trends.main()
            self.assertIn('"trend": "Testtrend"', captured[0])
            self.assertNotIn('"trend": "Neuer Trend"', captured[0].split("Candidate trends in strict descending search-volume order:")[1].split("Trend names still within")[0])

if __name__=="__main__":
    unittest.main()
