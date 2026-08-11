A modern replacement for David A Gardner's (Apex Realty Group, Huntingdon PA) listings page, currently hosted on the legacy USAMLS platform. Hosted on GitHub Pages, backed by MongoDB Atlas, with listing data kept in sync via a scheduled scraper and managed internally through an MCP server. See `CLAUDE.md` for the full architecture.

## Local dev

```bash
python3 -m http.server 8000
# then browse http://localhost:8000/
```

## One-time setup

1. **MongoDB Atlas** — create database `dagrealty` with two DB users: a full-access admin user (for the scraper + MCP server) and a separate read-only user scoped to the `listings` collection (for the public Worker, see below).
2. **Cloudflare R2** — enable R2 on the Cloudflare account (Dashboard → R2, one-time), then `wrangler r2 bucket create dagrealty` and create an S3-compatible API token (Dashboard → R2 → Manage API Tokens) for the scraper's photo uploads.
3. **Cloudflare Worker** — `cd worker && npm install && wrangler secret put MONGODB_URI` (paste the **read-only** connection string) `&& wrangler deploy`. Copy the deployed `*.workers.dev` URL into `LISTINGS_API_URL` in `js/listings.js` and `js/listing-detail.js`.
4. **GitHub Actions secrets** (repo Settings → Secrets and variables → Actions) for `.github/workflows/scrape.yml`:
   - Secrets: `MONGODB_URI` (admin connection string), `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`
   - Variables (optional, default shown): `MONGODB_DB=dagrealty`, `R2_BUCKET=dagrealty`
5. **Local `.env` files** (gitignored) — copy `tools/mongo-tools/.env.example` to `tools/mongo-tools/.env` and `scraper/.env.example` to `scraper/.env`, filling in the admin `MONGODB_URI` and (for `scraper/.env`) the R2 credentials, so `resync_listing`/`resync_all_listings`/`reupload_listing_photos` work locally via Claude Code.
6. **GitHub Pages** — Settings → Pages → deploy from `main` branch, root. `.nojekyll` is already present.
