#!/usr/bin/env python3
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "handoff" / "inbox"
PROCESSED = ROOT / "handoff" / "processed"
REJECTED = ROOT / "handoff" / "rejected"

ARTICLE_PATTERNS = [
    re.compile(r"^articles/trends/\d{4}-\d{2}-\d{2}_\d{4}_[a-z0-9-]+\.md$"),
    re.compile(r"^articles/mail/\d{4}-\d{2}-\d{2}_\d{4}_[a-z0-9-]+\.md$"),
    re.compile(r"^Agenten/\d{4}-\d{2}-\d{2}_\d{4}_(goldpreis|bitcoin-kurs|rheinmetall-aktie)\.md$"),
]
REGISTER_PATHS = {"processed-trends.json", "processed-press-releases.json"}

def allowed_article_path(path: str) -> bool:
    return any(p.match(path) for p in ARTICLE_PATTERNS)

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def append_register(register_path: str, entry: dict):
    if register_path not in REGISTER_PATHS:
        raise ValueError(f"register path not allowed: {register_path}")
    path = ROOT / register_path
    data = load_json(path)
    processed = data.setdefault("processed", [])

    if register_path == "processed-trends.json":
        key = (entry.get("trend"), entry.get("article_path"), entry.get("processed_at"))
        for item in processed:
            if (item.get("trend"), item.get("article_path"), item.get("processed_at")) == key:
                return
    else:
        gmail_id = entry.get("gmail_message_id")
        if gmail_id and any(item.get("gmail_message_id") == gmail_id for item in processed):
            return

    processed.append(entry)
    save_json(path, data)

def process_item(item: dict):
    register_only = item.get("register_only") is True
    article_path = item.get("article_path", "")
    content = item.get("article_content")

    if not register_only:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("article_content missing or empty")
        if not allowed_article_path(article_path):
            raise ValueError(f"article_path not allowed: {article_path}")

        target = ROOT / article_path
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            existing = target.read_text(encoding="utf-8")
            if existing != content:
                raise ValueError(f"target already exists with different content: {article_path}")
        else:
            target.write_text(content, encoding="utf-8")

    register = item.get("register")
    if register is not None:
        if not isinstance(register, dict):
            raise ValueError("register must be an object")
        register_path = register.get("path")
        entry = register.get("entry")
        if not isinstance(entry, dict):
            raise ValueError("register.entry must be an object")
        if not register_only and entry.get("article_path") != article_path:
            raise ValueError("register article_path does not match handoff article_path")
        append_register(register_path, entry)
    elif register_only:
        raise ValueError("register_only item requires register")

def process_one(path: Path):
    payload = load_json(path)
    version = payload.get("version")
    if version == 1:
        items = [payload]
    elif version == 2:
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("version 2 handoff requires non-empty items array")
    else:
        raise ValueError("unsupported handoff version")

    for item in items:
        if not isinstance(item, dict):
            raise ValueError("each handoff item must be an object")
        process_item(item)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(PROCESSED / path.name))

def main():
    INBOX.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    REJECTED.mkdir(parents=True, exist_ok=True)

    failures = []
    for path in sorted(INBOX.glob("*.json")):
        try:
            process_one(path)
        except Exception as exc:
            failures.append((path.name, str(exc)))
            REJECTED.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(REJECTED / path.name))

    if failures:
        details = "; ".join(f"{name}: {reason}" for name, reason in failures)
        raise SystemExit(f"handoff failures: {details}")

if __name__ == "__main__":
    main()
