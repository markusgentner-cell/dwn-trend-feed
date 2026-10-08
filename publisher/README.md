# DWN handoff publisher

This repository uses a two-stage publishing flow for automated ChatGPT editorial jobs.

1. A scheduled agent performs research and produces the complete final Markdown article.
2. The agent writes exactly one JSON handoff file to `handoff/inbox/`.
3. GitHub Actions processes that handoff inside GitHub, writes the final article, updates the relevant processed register atomically, moves the handoff to `handoff/processed/`, and commits everything in one repository commit.

## Handoff schema

```json
{
  "version": 1,
  "article_path": "articles/trends/2026-10-08_1234_example.md",
  "article_content": "# Complete article...",
  "register": {
    "path": "processed-trends.json",
    "entry": {
      "trend": "example",
      "article_path": "articles/trends/2026-10-08_1234_example.md",
      "processed_at": "2026-10-08T12:34:00+02:00"
    }
  }
}
```

For agent articles under `Agenten/`, omit the `register` object.

Only these output paths are accepted:
- `articles/trends/YYYY-MM-DD_HHMM_<slug>.md`
- `articles/mail/YYYY-MM-DD_HHMM_<slug>.md`
- `Agenten/YYYY-MM-DD_HHMM_goldpreis.md`
- `Agenten/YYYY-MM-DD_HHMM_bitcoin-kurs.md`
- `Agenten/YYYY-MM-DD_HHMM_rheinmetall-aktie.md`

The publisher is idempotent: identical already-published files are accepted, but conflicting content at an existing target path is rejected.
