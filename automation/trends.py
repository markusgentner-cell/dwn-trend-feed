#!/usr/bin/env python3
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from openai_common import call_openai, validate_editorial, render_article, slugify, ARTICLE_SCHEMA, now_berlin

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "latest.json"
REGISTER = ROOT / "processed-trends.json"
ARTICLES = ROOT / "articles" / "trends"

def due_now():
    now = now_berlin()
    return now.weekday() < 5 and 7 <= now.hour <= 13 and now.minute < 10

def parse_volume(text):
    m = re.search(r"([\d.]+)\+?", text)
    if not m:
        return 0
    return int(m.group(1).replace(".", ""))

def trend_name(text):
    m = re.match(r"(.+?)\s+[\d.]+\+", text.strip())
    return (m.group(1) if m else text).strip()

def verify_latest(data):
    errors = []
    if not data.get("ok"):
        errors.append("latest.json ok != true")
    captured = datetime.fromisoformat(data["captured_at"].replace("Z","+00:00"))
    age = datetime.now(timezone.utc) - captured
    if age > timedelta(hours=4):
        errors.append(f"latest.json is stale ({age.total_seconds()/3600:.1f}h old)")
    src = data.get("final_url") or data.get("source_url","")
    required = ["geo=DE","hours=4","category=3","status=active","sort=search-volume"]
    for token in required:
        if token not in src:
            errors.append(f"missing URL filter {token}")
    body = data.get("body_text","")
    labels = ["Deutschland","Letzte 4","Wirtschaft und Finanzen","Nur aktive Trends","Nach Suchvolumen"]
    for label in labels:
        if label not in body:
            errors.append(f"missing target-view label: {label}")
    return errors

def schema():
    return {
        "type":"object",
        "additionalProperties":False,
        "properties":{
            "articles":{"type":"array","items":ARTICLE_SCHEMA,"maxItems":3},
            "skipped":{"type":"array","items":{
                "type":"object","additionalProperties":False,
                "properties":{"trend":{"type":"string"},"reason":{"type":"string"}},
                "required":["trend","reason"]
            }}
        },
        "required":["articles","skipped"]
    }

def main():
    if "--scheduled" in sys.argv and not due_now():
        print("Not a scheduled Europe/Berlin trend slot; exiting.")
        return 0

    latest = json.loads(LATEST.read_text(encoding="utf-8"))
    errs = verify_latest(latest)
    if errs:
        print("ABORT: " + "; ".join(errs))
        return 0

    processed_data = json.loads(REGISTER.read_text(encoding="utf-8"))
    processed = {str(x.get("trend","")).casefold() for x in processed_data.get("processed",[])}
    rows = []
    for row in latest.get("rows",[]):
        name = trend_name(row.get("text",""))
        if not name or name.casefold() in processed:
            continue
        rows.append({"trend":name,"volume":parse_volume(row.get("text","")),"raw":row.get("text","")})
    rows.sort(key=lambda x: x["volume"], reverse=True)
    if not rows:
        print("No unprocessed active trends.")
        return 0

    existing = sorted(p.name for p in ARTICLES.glob("*.md"))
    prompt = f"""
The verified Google Trends input is fresh and already filtered for Germany, last 4 hours,
Business & Finance, active only, search volume descending.

Candidate trends in strict descending search-volume order:
{json.dumps(rows, ensure_ascii=False, indent=2)}

Already processed trend names:
{json.dumps(sorted(processed), ensure_ascii=False)}

Existing DWN trend article filenames in this repository:
{json.dumps(existing, ensure_ascii=False)}

Task:
- Research the current news situation for candidates using web search.
- Explicitly search Deutsche Wirtschaftsnachrichten / deutsche-wirtschafts-nachrichten.de for thematic duplicates.
- Starting from the highest-volume candidate, select up to THREE suitable new DWN topics.
- Skip processed, irrelevant, unreliable, insufficiently current, or thematically duplicate candidates and move downward.
- Preserve candidate priority: do not choose a lower-volume candidate while an unprocessed higher-volume candidate is suitable.
- Each selected article must be a complete publication-ready German DWN business-news article, factual and current.
- Use sensible Markdown subheadings in body_markdown, but do not repeat the main headline there.
- source_basis: concise prose naming the key source types/outlets used; do not include raw URLs.
- Provide exactly 5 alternative headlines.
- Provide exactly 9 curiosity bullets, each beginning with a German question word and max 15 words.
- Provide exactly 3 meta titles, each <=60 characters.
- Provide exactly 3 meta descriptions, each 150-160 characters including spaces.
- Conclusion must have its own heading and exactly 95-105 words.
- No placeholders, research notes, images, or social-media copy.
- Return skipped candidates with a concise reason.
"""

    result = None
    validation = []
    for attempt in range(3):
        p = prompt
        if validation:
            p += "\nPrevious output failed local validation. Correct these errors exactly:\n- " + "\n- ".join(validation)
        result = call_openai(p, schema(), "dwn_trend_package", max_output_tokens=24000)
        validation = []
        arts = result.get("articles", [])
        if len(arts) > 3:
            validation.append("more than 3 articles returned")
        index = {x["trend"].casefold(): i for i,x in enumerate(rows)}
        last = -1
        for a in arts:
            key = a.get("trend","").casefold()
            if key not in index:
                validation.append(f"unknown trend selected: {a.get('trend')}")
                continue
            if index[key] < last:
                validation.append("articles not in descending candidate priority")
            last = index[key]
            validation.extend([f"{a.get('trend')}: {e}" for e in validate_editorial(a)])
        if not validation:
            break
    if validation:
        raise RuntimeError("Editorial validation failed after retries: " + "; ".join(validation))

    arts = result.get("articles", [])
    if not arts:
        print("No suitable new trend after research/duplicate checks.")
        for s in result.get("skipped",[]):
            print(f"- {s['trend']}: {s['reason']}")
        return 0

    now = now_berlin()
    reg = processed_data.setdefault("processed", [])
    created = []
    for offset, a in enumerate(arts):
        dt = now + timedelta(minutes=offset)
        slug = slugify(a["headline"])
        rel = f"articles/trends/{dt:%Y-%m-%d_%H%M}_{slug}.md"
        path = ROOT / rel
        if path.exists():
            raise RuntimeError(f"Refusing to overwrite existing article: {rel}")
        path.write_text(render_article(a), encoding="utf-8")
        entry = {
            "trend": a["trend"],
            "article_path": rel,
            "processed_at": dt.isoformat(timespec="seconds")
        }
        if not any(x.get("trend","").casefold()==a["trend"].casefold() and x.get("article_path")==rel for x in reg):
            reg.append(entry)
        created.append(rel)

    REGISTER.write_text(json.dumps(processed_data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("Created:")
    for p in created:
        print(p)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
