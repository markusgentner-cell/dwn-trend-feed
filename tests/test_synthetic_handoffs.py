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

if __name__=="__main__":
    unittest.main()
