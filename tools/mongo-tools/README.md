# dagrealty-mongo MCP server

Internal admin tooling for managing DAGRealty listings in MongoDB. Never exposed publicly — separate from the read-only DB user given to the Cloudflare Worker (`worker/`).

## Setup

```bash
cp tools/mongo-tools/.env.example tools/mongo-tools/.env
# edit tools/mongo-tools/.env with the full-access Atlas admin connection string
```

Registered for Claude Code in the repo-root `.mcp.json` as `dagrealty-mongo`, launched on demand via `uv run tools/mongo-tools/server.py` — no separate install step.

## Tools

- `list_listings(status?, property_type?, city?, min_price?, max_price?, min_beds?)` / `get_listing(mls_number)` — browse/inspect (includes admin fields).
- `resync_listing(mls_number)` / `resync_all_listings()` — on-demand rescrape, same code path as the nightly GitHub Actions cron (`scraper/run.py`).
- `reupload_listing_photos(mls_number)` — force re-download/resize/re-upload photos for one listing (`scraper/photos.py --force`).
- `set_manual_override(mls_number, field, value)` / `clear_manual_override(mls_number, field)` — hand-correct a scraped field; survives future scrapes until cleared.
- `set_featured` / `set_hidden` / `set_internal_note` / `mark_status` — admin-only metadata, never touched by the scraper.
- `list_scrape_runs(limit?)` / `get_scrape_run(run_id)` — scrape health/history.
- `list_removed_listings()` — listings that dropped off the source MLS on the last scrape, for review before they disappear from the public site.
