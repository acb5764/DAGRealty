import { MongoClient } from "mongodb";

// The public site's origin (GitHub Pages). Local dev servers (any
// http://localhost:*) are also allowed so `python3 -m http.server` works
// against this API without a separate mock.
const PROD_ORIGIN = "https://acb5764.github.io";

// Only these fields ever leave this Worker. The entire `admin` sub-object
// (internal notes, featured/hidden flags, manual overrides), `source`,
// `first_seen_at`, `last_scrape_run_id`, `is_active_on_source`, and raw
// `_source_photo_urls`/`r2_key_*` never get queried here at all -- belt and
// suspenders against a future field being added to `listings` that
// shouldn't go public.
const PUBLIC_FIELDS = [
  "mls_number", "status", "list_price", "street_number", "address", "city",
  "state", "zip", "region", "county", "property_type", "house_style",
  "bedrooms", "full_baths", "three_quarter_baths", "half_baths",
  "total_baths", "total_sqft", "basement", "walkout_basement",
  "fireplaces_count", "exterior", "roof_type", "ac_type", "heating_type",
  "year_built", "zoning", "parking", "garage_spaces", "driveway",
  "elementary_school", "middle_school", "high_school", "included",
  "not_included", "water_type", "sewer_type", "property_features",
  "mobile_home", "tax_year", "total_taxes", "flood_zone", "acreage",
  "frontage_feet", "depth_feet", "public_comments", "amenities", "rooms",
  "virtual_tour_url", "updated_at",
];

function toPublicListing(doc, origin) {
  const out = {};
  for (const key of PUBLIC_FIELDS) {
    if (key in doc) out[key] = doc[key];
  }
  // `featured` is the one piece of admin.* safe to surface publicly (it just
  // drives the homepage highlight) -- everything else under admin (hidden,
  // internal_notes, manual_overrides, status_override) stays server-side.
  out.featured = Boolean(doc.admin && doc.admin.featured);
  out.photos = (doc.photos || []).map((p) => ({
    seq: p.seq,
    is_primary: p.is_primary,
    thumb_url: `${origin}/photos/${p.r2_key_thumb}`,
    full_url: `${origin}/photos/${p.r2_key_full}`,
  }));
  return out;
}

function isAllowedOrigin(origin) {
  if (!origin) return false;
  if (origin === PROD_ORIGIN) return true;
  try {
    return new URL(origin).hostname === "localhost";
  } catch {
    return false;
  }
}

function corsHeaders(origin) {
  const headers = {
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    Vary: "Origin",
  };
  if (isAllowedOrigin(origin)) headers["Access-Control-Allow-Origin"] = origin;
  return headers;
}

async function withListings(env, fn) {
  // A fresh connection per request, closed when done -- see EMM's
  // worker/src/index.js for the reasoning (Workers isolates aren't a
  // reliable place to keep a pooled TCP socket alive between invocations,
  // and this endpoint's traffic is far too low for that tradeoff to matter).
  // No directConnection here -- unlike EMM's URI, ours is an SRV-form Atlas
  // string (mongodb+srv://), which resolves to multiple hosts and is
  // incompatible with directConnection (confirmed via `wrangler tail`:
  // "MongoAPIError: SRV URI does not support directConnection").
  const client = await MongoClient.connect(env.MONGODB_URI, {
    maxPoolSize: 1,
    minPoolSize: 0,
    serverSelectionTimeoutMS: 5000,
  });
  try {
    const db = client.db(env.MONGODB_DB || "dagrealty");
    return await fn(db.collection("listings"));
  } finally {
    await client.close().catch(() => {});
  }
}

async function handleListings(request, env, headers, requestOrigin) {
  const docs = await withListings(env, (listings) =>
    listings.find({ "admin.hidden": { $ne: true } }).toArray()
  );
  docs.sort((a, b) => (a.list_price ?? 0) - (b.list_price ?? 0));

  return new Response(
    JSON.stringify({
      updated: new Date().toISOString(),
      listings: docs.map((d) => toPublicListing(d, requestOrigin)),
    }),
    {
      headers: {
        ...headers,
        "Content-Type": "application/json",
        "Cache-Control": "public, max-age=30",
      },
    }
  );
}

async function handleListingDetail(mlsNumber, env, headers, requestOrigin) {
  const doc = await withListings(env, (listings) =>
    listings.findOne({ _id: mlsNumber, "admin.hidden": { $ne: true } })
  );
  if (!doc) {
    return new Response(JSON.stringify({ error: "listing not found" }), {
      status: 404,
      headers: { ...headers, "Content-Type": "application/json" },
    });
  }
  return new Response(JSON.stringify(toPublicListing(doc, requestOrigin)), {
    headers: {
      ...headers,
      "Content-Type": "application/json",
      "Cache-Control": "public, max-age=30",
    },
  });
}

async function handlePhoto(key, env, headers) {
  const object = await env.PHOTOS_BUCKET.get(key);
  if (!object) {
    return new Response("not found", { status: 404, headers });
  }
  return new Response(object.body, {
    headers: {
      ...headers,
      "Content-Type": object.httpMetadata?.contentType || "image/jpeg",
      "Cache-Control": "public, max-age=31536000, immutable",
    },
  });
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const headers = corsHeaders(origin);
    const url = new URL(request.url);
    const requestOrigin = `${url.protocol}//${url.host}`;

    if (request.method === "OPTIONS") {
      return new Response(null, { headers });
    }
    if (request.method !== "GET") {
      return new Response("Method not allowed", { status: 405, headers });
    }

    try {
      const photoMatch = url.pathname.match(/^\/photos\/(.+)$/);
      if (photoMatch) {
        return await handlePhoto(decodeURIComponent(photoMatch[1]), env, headers);
      }

      const detailMatch = url.pathname.match(/^\/listings\/([^/]+)$/);
      if (detailMatch) {
        return await handleListingDetail(decodeURIComponent(detailMatch[1]), env, headers, requestOrigin);
      }

      if (url.pathname === "/listings") {
        return await handleListings(request, env, headers, requestOrigin);
      }

      return new Response("not found", { status: 404, headers });
    } catch (err) {
      console.error(err);
      return new Response(JSON.stringify({ error: "listings unavailable" }), {
        status: 502,
        headers: { ...headers, "Content-Type": "application/json" },
      });
    }
  },
};
