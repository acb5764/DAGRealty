# dagrealty-listings-api (Cloudflare Worker)

The only thing with public-facing MongoDB access. Reads `listings`, strips each
doc down to the `PUBLIC_FIELDS` allowlist in `src/index.js` (the whole `admin`
sub-object never leaves this Worker), and proxies listing photos out of R2.

## Routes

- `GET /listings` — all non-hidden listings, sorted by price.
- `GET /listings/:mls_number` — one listing.
- `GET /photos/:key` — streams a photo object from the R2 bucket, immutably cached.

## One-time setup

```bash
npm install
wrangler login
wrangler r2 bucket create dagrealty   # if not already created
wrangler secret put MONGODB_URI              # paste the READ-ONLY, listings-scoped Atlas user
wrangler deploy
```

Deploy prints a `*.workers.dev` URL — paste it into `LISTINGS_API_URL` in
`js/listings.js` and `js/listing-detail.js`.

## Local dev

```bash
npm run dev
```

Note: `wrangler dev` needs `MONGODB_URI` available too — either `wrangler secret put` in dev mode when prompted, or a `.dev.vars` file (gitignored) with `MONGODB_URI=...`.
