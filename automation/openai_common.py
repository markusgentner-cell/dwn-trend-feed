#!/usr/bin/env python3
import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-sol")
API_URL = "https://api.openai.com/v1/responses"

def now_berlin():
    return datetime.now(ZoneInfo("Europe/Berlin"))

def api_key():
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return key

def response_text(data):
    for item in data.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    return part.get("text", "")
    raise RuntimeError("OpenAI response contained no output_text")

def call_openai(prompt, schema, name, max_output_tokens=20000):
    body = {
        "model": MODEL,
        "instructions": (
            "You are a senior German business-news editor for Deutsche Wirtschaftsnachrichten (DWN). "
            "Research current facts with web search. Never invent facts. Distinguish verified facts from company claims. "
            "Return only the requested structured output."
        ),
        "input": prompt,
        "tools": [{"type": "web_search"}],
        "reasoning": {"effort": "medium"},
        "max_output_tokens": max_output_tokens,
        "text": {
            "format": {
                "type": "json_schema",
                "name": name,
                "strict": True,
                "schema": schema
            }
        }
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key()}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"OpenAI API HTTP {exc.code}: {detail}") from exc
    return json.loads(response_text(data))

def words(text):
    return re.findall(r"\b[\wÄÖÜäöüß’-]+\b", text, flags=re.UNICODE)

def word_count(text):
    return len(words(text))

def slugify(value):
    value = value.lower()
    value = value.replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:80] or "artikel"

def render_article(a):
    lines = [
        f"# {a['headline']}",
        "",
        a["teaser"].strip(),
        "",
        a["body_markdown"].strip(),
        "",
        "## Quellenbasis",
        "",
        a["source_basis"].strip(),
        "",
        "## Alternative Überschriften",
        ""
    ]
    lines += [f"{i}. {x.strip()}" for i, x in enumerate(a["alternative_headlines"], 1)]
    lines += ["", "## Neugier-Bulletpoints", ""]
    lines += [f"- {x.strip()}" for x in a["bullets"]]
    lines += ["", "## Meta-Titles", ""]
    lines += [f"{i}. {x.strip()}" for i, x in enumerate(a["meta_titles"], 1)]
    lines += ["", "## Meta-Descriptions", ""]
    lines += [f"{i}. {x.strip()}" for i, x in enumerate(a["meta_descriptions"], 1)]
    lines += ["", f"## {a['conclusion_heading'].strip()}", "", a["conclusion"].strip(), ""]
    return "\n".join(lines)

def validate_editorial(a):
    errors = []
    if len(a.get("alternative_headlines", [])) != 5:
        errors.append("exactly 5 alternative headlines required")
    bullets = a.get("bullets", [])
    if len(bullets) != 9:
        errors.append("exactly 9 bullets required")
    qwords = ("wer","was","wann","wo","warum","wieso","weshalb","wie","welche","welcher","welches","wen","wem","wessen")
    for i, b in enumerate(bullets):
        first = re.sub(r"^[^A-Za-zÄÖÜäöüß]+", "", b).split(" ",1)[0].lower().rstrip("?:,.;")
        if first not in qwords:
            errors.append(f"bullet {i+1} must start with a question word")
        if word_count(b) > 15:
            errors.append(f"bullet {i+1} has more than 15 words")
    titles = a.get("meta_titles", [])
    if len(titles) != 3:
        errors.append("exactly 3 meta titles required")
    for i, t in enumerate(titles):
        if len(t) > 60:
            errors.append(f"meta title {i+1} exceeds 60 characters")
    descs = a.get("meta_descriptions", [])
    if len(descs) != 3:
        errors.append("exactly 3 meta descriptions required")
    for i, d in enumerate(descs):
        if not 150 <= len(d) <= 160:
            errors.append(f"meta description {i+1} must be 150-160 characters, got {len(d)}")
    wc = word_count(a.get("conclusion",""))
    if not 95 <= wc <= 105:
        errors.append(f"conclusion must be 95-105 words, got {wc}")
    for key in ("headline","teaser","body_markdown","source_basis","conclusion_heading","conclusion"):
        if not str(a.get(key,"")).strip():
            errors.append(f"{key} is empty")
    return errors

ARTICLE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "trend": {"type": "string"},
        "headline": {"type": "string"},
        "teaser": {"type": "string"},
        "body_markdown": {"type": "string"},
        "source_basis": {"type": "string"},
        "alternative_headlines": {"type": "array", "items": {"type": "string"}, "minItems": 5, "maxItems": 5},
        "bullets": {"type": "array", "items": {"type": "string"}, "minItems": 9, "maxItems": 9},
        "meta_titles": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
        "meta_descriptions": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
        "conclusion_heading": {"type": "string"},
        "conclusion": {"type": "string"}
    },
    "required": [
        "trend","headline","teaser","body_markdown","source_basis","alternative_headlines",
        "bullets","meta_titles","meta_descriptions","conclusion_heading","conclusion"
    ]
}
