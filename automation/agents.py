#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

from openai_common import call_openai, now_berlin, word_count

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Agenten"

AGENTS = {
    "gold": {
        "slug":"goldpreis",
        "hour":8,"minute":0,
        "topic":"Goldpreis",
        "prompt": """Research current news and developments about the gold price and retrieve the current gold price in US dollars, prioritizing finanzen.net/rohstoffe/goldpreis and corroborating with other reliable current financial sources. Write a journalistic German article of about 500 words on today's gold-price development, market situation, key drivers and short outlook. SEO: Use the keyword “Goldpreis” exactly 7 times in the complete article text. Use “Goldpreis aktuell”, “Goldkurs”, “Gold-Preis”, “Goldpreis-Entwicklung” and “gelbes Edelmetall” exactly once each. Do not invent facts. Do not include a source list."""
    },
    "bitcoin": {
        "slug":"bitcoin-kurs",
        "hour":8,"minute":0,
        "topic":"Bitcoin Kurs",
        "prompt": """Research current news and developments about Bitcoin and retrieve the current Bitcoin price in US dollars from reliable current sources such as finanzen.net, CoinMarketCap, CoinGecko or Investing.com. Write a journalistic German article of about 500 words on today's Bitcoin price development, market situation, key drivers and short outlook. SEO: Use the keyword “Bitcoin Kurs” exactly 7 times in the complete article text. Use “Bitcoin Kurs aktuell”, “Bitcoin-Preis”, “BTC-Kurs”, “Bitcoin-Kursentwicklung” and “Kryptowährung” exactly once each. Do not invent facts. Do not include a source list."""
    },
    "rheinmetall": {
        "slug":"rheinmetall-aktie",
        "hour":8,"minute":15,
        "topic":"Rheinmetall Aktie",
        "prompt": """Research current news and developments about Rheinmetall stock and retrieve the current Rheinmetall share price from reliable current financial sources such as finanzen.net, boerse.de, MarketScreener or Investing.com. Write a journalistic German article of about 500 words on today's Rheinmetall stock development, market situation, important drivers, analyst opinions if available and short outlook. SEO: Use “Rheinmetall Aktie” exactly 7 times. Use “Rheinmetall-Aktie”, “Rheinmetall Kurs”, “Rheinmetall Aktienkurs”, “Rüstungsaktie” and “DAX-Konzern” exactly once each. Do not invent facts. Do not include a source list."""
    }
}

SCHEMA = {
    "type":"object","additionalProperties":False,
    "properties":{
        "headline":{"type":"string"},
        "teaser":{"type":"string"},
        "body_markdown":{"type":"string"}
    },
    "required":["headline","teaser","body_markdown"]
}

def due_names():
    now = now_berlin()
    if now.weekday() >= 5:
        return []
    return [name for name,cfg in AGENTS.items() if now.hour==cfg["hour"] and now.minute==cfg["minute"]]

def render(a):
    return f"# {a['headline'].strip()}\n\n{a['teaser'].strip()}\n\n{a['body_markdown'].strip()}\n"

def validate(name, text):
    errors = []
    wc = word_count(text)
    if not 400 <= wc <= 650:
        errors.append(f"article should be about 500 words; got {wc}")
    if name=="gold":
        checks=[("Goldpreis",7),("Goldpreis aktuell",1),("Goldkurs",1),("Gold-Preis",1),("Goldpreis-Entwicklung",1),("gelbes Edelmetall",1)]
    elif name=="bitcoin":
        checks=[("Bitcoin Kurs",7),("Bitcoin Kurs aktuell",1),("Bitcoin-Preis",1),("BTC-Kurs",1),("Bitcoin-Kursentwicklung",1),("Kryptowährung",1)]
    else:
        checks=[("Rheinmetall Aktie",7),("Rheinmetall-Aktie",1),("Rheinmetall Kurs",1),("Rheinmetall Aktienkurs",1),("Rüstungsaktie",1),("DAX-Konzern",1)]
    for phrase,count in checks:
        got=text.count(phrase)
        if got!=count:
            errors.append(f"{phrase!r} must occur exactly {count} times; got {got}")
    return errors

def generate(name):
    cfg=AGENTS[name]
    today=now_berlin().strftime("%Y-%m-%d")
    existing=list(OUT.glob(f"{today}_*_{cfg['slug']}.md"))
    if existing:
        print(f"{name}: daily article already exists: {existing[0].name}")
        return None

    base = cfg["prompt"] + """
Return a concise headline, a short teaser, and the complete body in Markdown with sensible subheadings.
The headline and teaser are part of the complete article text for SEO counting. No placeholders.
"""
    result=None
    errors=[]
    for attempt in range(3):
        prompt=base
        if errors:
            prompt += "\nThe previous attempt failed local validation. Correct these exact issues:\n- " + "\n- ".join(errors)
        result=call_openai(prompt, SCHEMA, f"dwn_{cfg['slug'].replace('-','_')}", max_output_tokens=6000)
        text=render(result)
        errors=validate(name,text)
        if not errors:
            break
    if errors:
        raise RuntimeError(f"{name} validation failed after retries: " + "; ".join(errors))
    now=now_berlin()
    rel=f"Agenten/{now:%Y-%m-%d_%H%M}_{cfg['slug']}.md"
    (ROOT/rel).write_text(render(result),encoding="utf-8")
    print(f"{name}: created {rel}")
    return rel

def main():
    if "--scheduled" in sys.argv:
        names=due_names()
        if not names:
            print("No agent due at this Europe/Berlin minute.")
            return 0
    else:
        names=sys.argv[1:] or list(AGENTS)
    OUT.mkdir(parents=True,exist_ok=True)
    for name in names:
        if name not in AGENTS:
            raise RuntimeError(f"Unknown agent: {name}")
        generate(name)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
