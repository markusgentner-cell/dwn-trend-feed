#!/usr/bin/env python3
"""Remove dated generated editorial artifacts older than ten full days (Berlin)."""
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import re

ROOT = Path(__file__).resolve().parents[1]
DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:_|$)")
CATEGORIES = ("agenten", "mail", "trends")

def main():
    today = datetime.now(ZoneInfo("Europe/Berlin")).date()
    cutoff = today - timedelta(days=10)
    removed = []
    for category in CATEGORIES:
        for folder in (ROOT / "articles" / category, ROOT / "assets" / category):
            if not folder.exists():
                continue
            for item in folder.rglob("*"):
                if not item.is_file() or item.name == ".gitkeep":
                    continue
                parts = item.relative_to(folder).parts
                match = next((DATE.match(p) for p in parts if DATE.match(p)), None)
                if not match:
                    continue  # Never delete undated files automatically.
                try:
                    stamp = datetime.strptime(match.group(1), "%Y-%m-%d").date()
                except ValueError:
                    continue
                if stamp < cutoff:
                    item.unlink()
                    removed.append(str(item.relative_to(ROOT)))
    for p in removed:
        print("Deleted:", p)
    print(f"Berlin date: {today}; cutoff: {cutoff}; removed: {len(removed)}")
if __name__ == "__main__":
    main()
