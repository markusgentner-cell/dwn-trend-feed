#!/usr/bin/env python3
"""Create neutral daylight editorial images for generated articles without images."""
import base64
import os
import re
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from openai import OpenAI
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"
DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})_")
MAX_PER_RUN = 8

def main():
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    cutoff = datetime.now(ZoneInfo("Europe/Berlin")).date() - timedelta(days=10)
    count = 0
    for category in ("agenten", "mail", "trends"):
        for article in sorted((ROOT / "articles" / category).glob("*.md"), reverse=True):
            m = DATE.match(article.name)
            if not m or datetime.strptime(m.group(1), "%Y-%m-%d").date() < cutoff:
                continue
            # Flat root assets/ directory; deterministic collision-free naming.
            target = OUT / f"{category}-{article.stem}.webp"
            if target.exists():
                continue
            title = next((line.lstrip("# ").strip() for line in article.read_text(encoding="utf-8").splitlines() if line.startswith("# ")), article.stem)
            prompt = (
                "Create a photorealistic editorial DAYLIGHT photograph for a serious German business "
                f"news article titled: {title[:240]}. "
                "Use a generic, plausible business-related setting. No people, no text, no "
                "letters, no numbers, no logos, no watermarks, no brand identities, no charts. "
                "This is a symbolic illustration, not a claimed photograph of a real event."
            )
            response = client.images.generate(model="gpt-image-1", prompt=prompt, size="1536x1024")
            raw = base64.b64decode(response.data[0].b64_json)
            im = Image.open(BytesIO(raw)).convert("RGB")
            OUT.mkdir(parents=True, exist_ok=True)
            im.save(target, format="WEBP", quality=86, method=6)
            print("Created", target.relative_to(ROOT))
            count += 1
            if count >= MAX_PER_RUN:
                return
    print("Created", count, "images")

if __name__ == "__main__":
    main()
