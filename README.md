# tocify (Claude fork) — RSS → triage → `digest.md`

A GitHub Action fetches new items from journal and preprint RSS feeds, has Claude score them
against your interests, and commits a ranked `digest.md` (plus a dated copy in `digests/`).
Forked from [voytek/tocify](https://github.com/voytek/tocify); the OpenAI and Cursor backends
were removed in favour of a Claude backend.

## Files you edit
- `feeds.txt` — RSS feeds (`Name | URL`, `#` comments).
- `authors.txt` — authors to track. Their items skip the keyword prefilter, are never dropped by the item cap, and are flagged to the model.
- `interests.md` — `## Keywords` (local prefilter) and `## Narrative` (given to the model).
- `prompt.txt` — the scoring prompt; fill in the calibration section.

## Setup
1. Repo **Settings → Secrets and variables → Actions**: add secret `ANTHROPIC_API_KEY`; optionally add variable `ANTHROPIC_MODEL` (otherwise the default in `integrations/claude_triage.py` is used).
2. **Actions** tab: enable workflows (they are off by default on forks), then run **ToC Digest** once via *Run workflow*.
3. Local run: copy `.env.example` to `.env`, then `pip install -r requirements.txt && python digest.py`.

## Behaviour worth knowing
- Runs weekly. RSS feeds only retain recent items, so a monthly run would miss most of the month; read the files in `digests/` at month-end.
- `seen_ids.json` records items already triaged so overlapping lookback windows do not repeat them. A failed run does not update it.
- Titles, links and dates in the digest come from the feed, never from the model; the model supplies only score, rationale and tags.
- Author matching uses surname + first initial and only works where feeds publish author names.

Config via environment variables: see the top of `digest.py`.
