# Sources, limits and safety

## Research sources

| Source | Used for | Auth | Notes |
|---|---|---|---|
| Official hackathon site / rules URL | Organiser intent, criteria, rules | none | User-supplied; SSRF-validated; robots.txt respected |
| GitHub REST search | Existing repositories, activity, language, stars | optional `GITHUB_TOKEN` | Unauthenticated rate limit is low; token raises it |
| arXiv API | Research papers and methods | none | Atom feed |
| OpenAlex | Scholarly works, venues, citations | none | Polite pool via user agent |
| Crossref | Publication metadata and DOIs | none | REST API |
| Wikipedia API | Background and definitions | none | Used cautiously as context, not proof |
| Hacker News (Algolia) | Practitioner discussion and product signals | none | Public API |
| RSS feeds | News and lab announcements | none | Configurable list |
| DuckDuckGo Instant Answer API | Definitions and broad context | none | Not a full web-search index; many queries return no results |

Every retrieved source is stored in `research_sources` with session, URL, title,
source type, reliability and retrieval timestamp. Duplicate URLs within a
session are ignored. Continuous Intelligence stores items separately with
freshness dates and stale flags.

## HTTP safety

`src/research/http_client.py` enforces:

- Only `http` and `https` schemes.
- No credentials in URLs.
- No loopback, private, link-local, multicast, reserved or unspecified IPs.
- DNS resolution is checked before the request and redirects are re-validated.
- robots.txt is respected when enabled (default).
- Per-host delay and bounded response size.
- Cache with TTL to avoid repeated requests.

These rules apply to every connector and to user-supplied website/rules URLs.
The research layer will refuse to fetch a local or private address even if a
model or user asks it to.

## Reliability and freshness

- Each `SearchResult` carries a source type and a reliability weight.
- Problems and solutions retain URLs and retrieval dates.
- Continuous Intelligence marks items older than `stale_after_days` as stale.
- The report includes a provenance section and freshness notes.
- If a source fails, the failure is logged and shown in the refresh history;
  the system does not silently substitute invented data.

## Rate limits and outages

- GitHub unauthenticated search is limited to a small number of requests per
  minute. Set `GITHUB_TOKEN` in `.env` for heavier use.
- arXiv, OpenAlex and Crossref are generally tolerant but may throttle.
- RSS feeds and websites may move, block crawlers or require JavaScript.
- DuckDuckGo's Instant Answer API is not a full web index and returns nothing
  for many specific queries; the connector treats that as a normal empty result.

## Model limits

- One shared model is used for all five agents.
- Recommended: `qwen2.5:7b` for 6 GB VRAM at 4-bit; `qwen2.5:3b` as fallback.
- Longer prompts and strict schemas can exceed small context windows. The client
  uses bounded evidence, `num_ctx=8192` by default and retries invalid JSON.
- If the model cannot produce valid output after retries, the run fails honestly.
- The model never gets to waive a deterministic gate.

## Privacy and cost

- No paid AI API is used or required.
- Prompts, evidence and results stay on the local machine.
- Public HTTP requests necessarily reveal the request to the source (URL, user
  agent, IP), as any browser would.
- `GITHUB_TOKEN` is read from the environment/`.env` and is never displayed in
  the UI.
- Logs may contain URLs and error messages, but not the token.

## Storage guard-rail

- Default budget: 30 GB. It is a **guard-rail**, not an allocation.
- Before a model download, HackathonIQ estimates size, checks the budget and
  free disk space, and refuses if either is insufficient.
- The UI warns as usage approaches the configured threshold.
- Cache cleanup only touches `data/cache` and only files older than the chosen
  age. It never deletes models, reports, the database, logs or personal files.
- The app never scans or modifies files outside its own `data/` directory.

## Ethical and quality constraints

- No fake judges, sponsors, statistics or URLs.
- Absence of evidence is reported as uncertainty, not as proof of novelty.
- A candidate can be rejected even if it sounds impressive.
- The system may return no winner. This is a valid, documented outcome.
