# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A static real-estate listings site for David A Gardner (Apex Realty Group, Huntingdon PA), replacing his legacy listings page hosted on USAMLS (`usamls.net/dgrealestate`). Hosted on GitHub Pages, so the site itself is deliberately **no build step, no framework, no dependencies** — plain HTML/CSS/JS served as-is. The two exceptions: `worker/` (a Cloudflare Worker, own `package.json`, deployed via `wrangler`) proxies public listing data out of MongoDB, and `scraper/` + `tools/mongo-tools/` (Python) keep that Mongo data in sync with the source MLS listings and let the owner manage it via Claude Code.

## Running locally

No build/lint/test tooling for the site itself:

```bash
python3 -m http.server 8000
# then browse http://localhost:8000/
```

Click through nav, filters/sort on `listings.html`, and a few `listing.html?mls=...` detail pages after any frontend change — there's no test suite to catch regressions.

## Architecture

**MongoDB is the source of truth for listings; nothing is committed to git.** A scheduled scraper (`scraper/`, run via GitHub Actions cron — see `.github/workflows/scrape.yml`) pulls listing + detail data from the USAMLS office-listings pages and upserts into the `listings` collection (db `dagrealty`), recording bookkeeping in `scrape_runs`. The same scraper code can be invoked on-demand for a single listing or a full resync via the `dagrealty-mongo` MCP server (`tools/mongo-tools/`) — see "MCP admin tools" below. A small Cloudflare Worker (`worker/`) is the only thing with public-facing DB credentials (a separate, least-privilege, read-only Atlas user scoped to `listings`): it queries `listings`, strips each doc down to a hardcoded `PUBLIC_FIELDS` allowlist (the entire `admin` sub-object — internal notes, featured/hidden flags, manual overrides — is never queried by the public Worker), and serves JSON over HTTPS with CORS locked to the production GitHub Pages origin (plus `localhost` for dev). `js/listings.js` and `js/listing-detail.js` fetch that Worker URL via a `LISTINGS_API_URL` constant at the top of each file.

**Photos are re-hosted, never hotlinked.** USAMLS serves photos via signed/session-style URLs (`getPhoto.asp?...&k=...`) that are not stable long-term. `scraper/photos.py` downloads, resizes (thumb ~400px + full ~1600px JPEG via Pillow), and uploads each photo to a Cloudflare R2 bucket; listing docs store only R2 object keys, and the Worker proxies them at `/photos/:key` with long-lived immutable caching.

**Off-market detection.** Each scrape run records every `mls_number` it saw. Listings not seen in the latest run get `is_active_on_source = false` rather than being deleted, so the owner can review via the `list_removed_listings` MCP tool before anything disappears from the public site.

**Manual overrides live in `admin`, never in the scraped fields directly.** If a scraped field is wrong or needs a manual correction between scrapes, use `set_manual_override` rather than hand-editing the scraped value — the next scrape would otherwise silently overwrite a hand edit made directly on a public field.

**GitHub Pages subpath means relative paths only.** The site deploys at `<username>.github.io/DAGRealty`, not domain root, so every `href`/`src` must be relative with no leading slash.

**Theming is dark-by-default with a manual light override**, driven by a `data-theme` attribute on `<html>` and CSS custom properties in `css/style.css`. Because there's no shared `<head>`, every page duplicates the small inline FOUC-prevention script that sets `data-theme` before the stylesheet loads — copy it from an existing page when adding a new one.

**Shared chrome via Web Components.** `js/components.js` defines `<site-header>`/`<site-footer>` custom elements used as plain tags on every page.

## MCP admin tools (`dagrealty-mongo`)

Run via `uv run tools/mongo-tools/server.py`, registered in `.mcp.json`. This is internal tooling for the site owner only — never exposed publicly, separate from the public Worker's read-only DB user. Tools: `list_listings`, `get_listing`, `resync_listing`, `resync_all_listings`, `set_manual_override`, `clear_manual_override`, `set_featured`, `set_hidden`, `set_internal_note`, `mark_status`, `reupload_listing_photos`, `list_scrape_runs`, `get_scrape_run`, `list_removed_listings`.

## Known TODOs

Search for `TODO`/`REPLACE_WITH` — placeholder `LISTINGS_API_URL` in `js/listings.js`, `js/listing-detail.js`, and `js/home.js` until the Worker is deployed and its URL is known (see `worker/README.md`); a placeholder `REPLACE_WITH_CONTACT_EMAIL` mailto in `contact.html` — no real public business email for David was available on the source USAMLS page (only phone numbers), so don't invent one — confirm the real address with the client before launch.
