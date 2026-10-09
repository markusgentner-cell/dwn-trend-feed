# GitHub-native DWN editorial automation

The trend workflow and the three market agents (Goldpreis, Bitcoin-Kurs, Rheinmetall-Aktie) run entirely in GitHub Actions.

## Required repository secret

Create a repository secret named `OPENAI_API_KEY`.

GitHub: Settings -> Secrets and variables -> Actions -> New repository secret.

The key is never stored in the repository. OpenAI recommends GitHub Secrets for API keys used by GitHub Actions.

## Workflows

- `.github/workflows/dwn-trends-api.yml`
  - GitHub schedules broad UTC windows and `automation/trends.py` gates execution using Europe/Berlin.
  - Reads `latest.json` and `processed-trends.json`.
  - Verifies freshness and the required Google Trends filters.
  - Uses OpenAI Responses API with web search.
  - Selects up to three suitable trends by descending search volume.
  - Checks DWN thematic duplicates through web research.
  - Validates SEO/editorial constraints locally before writing.
  - Writes final Markdown directly to `articles/trends/` and updates `processed-trends.json`.

- `.github/workflows/dwn-market-agents-api.yml`
  - Goldpreis and Bitcoin at 08:00 Europe/Berlin.
  - Rheinmetall at 08:15 Europe/Berlin.
  - Uses OpenAI Responses API with web search.
  - Validates approximate length and exact SEO keyword counts.
  - Writes final Markdown directly to `articles/agenten/`.
  - Refuses to create a second article for the same agent/date.

## Model

Default: `gpt-5.6-sol`. Override with `OPENAI_MODEL` if required.
