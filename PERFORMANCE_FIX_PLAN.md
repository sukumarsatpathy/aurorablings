# Aurora Blings — Performance Work: As-Built Record

Supersedes the original plan. All 14 changes are implemented; this documents
what actually shipped, which differs from the plan in several places that
matter.

**Read the "Where this diverged from the plan" section before trusting any
older copy of this document.** Three of the planned changes would have broken
production if implemented as written.

**Nothing here has been verified by a build or a running server.** The analysis
environment could not run `npm run build` (node_modules was installed on macOS;
the native rollup/esbuild binaries do not execute under Linux) or boot Django.
Verification was static analysis plus logic simulation. See "Before you ship".

---

## Status

| # | Change | Status | Diverged from plan |
|---|---|---|---|
| 1 | `CONN_MAX_AGE` on the DB config | done | — |
| 2 | React Query defaults | done | — |
| 3 | Gunicorn threaded workers | done | yes — worker count also lowered |
| 4 | Serve responsive image derivatives | done (backend) | yes — see below |
| 5 | Fix hover image prefetch | done | — |
| 6 | Convert 1.7 MB homepage PNG | done | — |
| 7 | Lazy-load routes | done | yes — scope widened |
| 8 | Vite manual chunking | done | — |
| 9 | Fix `price_range` N+1 | done | yes — prefetch left unfiltered |
| 10 | Remove per-product stock queries | done | **yes — materially** |
| 11 | Replace `image_count` annotation | partial | indexes not added |
| 12 | Remove duplicate GTM bootstrap | done | — |
| 13 | Scope Lenis to storefront | done | — |
| 14 | Un-hide the hero | done | — |

Two changes were added that were not in the plan at all:

- `backfill_media_variants` management command (Change 4 is inert without it)
- ownership fix in `scripts/restore_local.sh`

---

## Where this diverged from the plan

### The original report was wrong about the image pipeline

The first report claimed there was no server-side image processing and
recommended building one. That was incorrect. `ProductMedia.save()`
(`backend/apps/catalog/models.py:298`) already compresses to max 1800px and
generates `image_small` / `image_medium` / `image_large` via
`core/image_optimization.py`.

The real defect was narrower: the derivatives were generated, stored, and
cleaned up on delete — but `ProductListSerializer` returned the full-size
master anyway, so no product grid ever used them. That is what Change 4 fixes.

### Change 10 would have broken add-to-cart

The plan said to remove `total_stock`, `variant_count` and `stock_summary` from
the public `ProductListSerializer` and move them to a staff-only subclass.

`total_stock` is read by the storefront:

- `DealProductCard.tsx` — six call sites, driving in-stock state and the
  quantity cap on add-to-cart
- `NewArrivalsSection.tsx:135` — falls back to it for `stock_quantity`
- `DealProductSerializer` **extends** `ProductListSerializer`, so the deals
  endpoint inherits whatever the base class exposes

Removing it would have made every deal product read as out of stock.

**What shipped instead:** `total_stock` stays on the public serializer and is
now fed by a `Subquery` annotation (`warehouse_stock_total`) applied in both
`get_product_list()` and `get_deal_products()`. Same 40 queries eliminated, no
API change. Only `stock_summary` moved to the new `AdminProductListSerializer`
— grep confirmed nothing outside `pages/admin/ProductManagement.tsx` reads it,
and it was exposing per-SKU inventory levels to anonymous visitors.

The annotation returns `NULL` (not `0`) when a product has no warehouse rows,
which is the same signal the old `.exists()` check produced, so the fallback to
`variant.stock_quantity` still fires in exactly the same cases. Verified across
all four branches.

### Change 9: the prefetch was left unfiltered

The plan said to narrow the variants prefetch to
`ProductVariant.objects.filter(is_active=True)`.

`get_default_variant` ends with `variants[0]` as a last-resort fallback, which
returns an *inactive* variant when a product has no active ones. Filtering the
prefetch would empty the list in that case and return `None` instead — so a
product whose variants are all inactive would silently lose its price in the
admin listing.

**What shipped:** `price_range` reads `.all()` and filters in Python. That
removes the N+1 with provably identical output, and the cost of loading
inactive variants is negligible.

### Change 3: worker count also had to change

The plan only switched `worker_class` to `gthread` with 4 threads. But
`GUNICORN_WORKERS` is set nowhere in the deploy config, so it defaulted to
`(cores * 2) + 1`. Combined with 4 threads and the now-persistent connections
from Change 1, an 8-core box would reserve 36 Postgres connections against a
default `max_connections` of 100.

**What shipped:** the worker formula is now `cores + 1`, which is the right
shape for threaded workers anyway.

| | before | after |
|---|---|---|
| 2 cores | 5 concurrent | 12 concurrent, 12 conns |
| 4 cores | 9 concurrent | 20 concurrent, 20 conns |
| 8 cores | 17 concurrent | 36 concurrent, 36 conns |

Check `SHOW max_connections;` before deploying on 8+ cores or a small managed
instance.

### Change 7: scope widened, and three pages would have crashed

The plan covered the 24 admin pages. Also lazy-loaded: `DashboardLayout`, the
whole account area, and `ProductDetailPage` (in addition to the planned
`CheckoutPage`, `ProductListingPage`, `CartPage`). 34 lazy routes total.

More importantly, an export-style audit before writing any code found three
pages where the plan's blanket `.then(m => ({ default: m.X }))` wrapper would
have produced a runtime "Element type is invalid" that TypeScript does not
catch:

- `GTMSettings` — `.jsx` file with a `.d.ts` shim, **default** export
- `TrackingSettings` — same
- `Settings.tsx` — a one-line barrel, `export { SettingsPage as Settings }`

All 34 imports were verified against their actual export style.

### Change 11: indexes not added

The `image_count` annotation was converted from `Count("media", distinct=True)`
to a `Subquery`, as planned. The composite index on
`("-is_featured", "-created_at")` was **not** added — the plan itself said to
confirm with `EXPLAIN ANALYZE` first, and that was not possible here. With a
small catalog Postgres may reasonably prefer a sequential scan. Revisit if the
listing slows as the table grows.

### Change 4: srcset is not yet wired into the product cards

The backend emits `primary_image_srcset` / `hover_image_srcset` and the types
exist. The card components were left alone: `ListCardImage` holds images as a
deduped `string[]` that a hover carousel cycles by index, so consuming srcset
means restructuring to `{src, srcset}[]` and touching the dedupe plus the
hover-media fetch path. That is a refactor with real regression risk.

It is also mostly unnecessary — `primary_image` now resolves to the 768px
rendition server-side, so the byte saving already lands. A comment at the call
site in `ProductListingPage.tsx` explains this.

Note the hover-media fetch (`ProductListingPage.tsx` ~line 217) still reads
`item.image`, the full-size master. Worth changing to `item.image_medium` when
that refactor happens.

---

## Bugs found along the way

Four real defects surfaced that were not on the original list:

**1. Hover images have never worked.** `get_hover_image` reads `media[1]`, but
the prefetch was filtered to `is_primary=True`, so the list could never hold
more than one row. The frontend read the field and silently got `null`. Fixed
by ordering the prefetch `("-is_primary", "sort_order")` instead of filtering.

**2. Wrong srcset widths (mine).** The first implementation hardcoded
400/800/1600. `generate_responsive_variants` actually renders at
**480/768/1200**. Browsers trust the `w` descriptor when selecting a candidate,
so this would have silently picked wrong files. Worse, `core/image_optimization.py`
already exported a `build_srcset()` helper using the correct constants — the
serializer now calls it, so the two cannot drift.

**3. `__in=[None]` matches nothing (mine).** The backfill command's first draft
used `Q(image_small__in=["", None])`. Django *drops* the `None` and compiles it
to `IN ('')`, so it would have matched only empty-string rows and skipped every
NULL one — precisely the legacy rows the command exists to fix. Now uses
explicit `isnull=True | field=""`.

**4. `restore_local.sh` left media unwritable.** It uses `docker cp`, which
preserves the host uid (501 on macOS), so the restored `media/products` tree
ended up owned by 501 while the container runs as `django` (uid 101). The app
only notices when `upload_to="products/%Y/%m/"` needs to create a directory for
a *new* month — so it looks fine for weeks, then uploads start failing on the
1st with nothing in the changelog to explain it. Script now chowns after
copying.

---

## Operational notes

### The backfill is required, and it is destructive

Change 4 is **inert** until derivatives exist. A dry run against production
data found **222 rows** missing them — effectively the whole catalog, because
migration `0010` added the fields after those products were uploaded.

`ProductMedia.save()` does not only add derivatives. It re-encodes the master
through `compress_image()` to WebP under a new filename, and the `pre_save`
signal then deletes the old file because the name changed. So each row:

- loses its original `.jpg` / `.png`
- gains a re-encoded `.webp` (lossy-on-lossy)
- gains three derivative files

Not reversible from the application.

```bash
# back up first
sudo tar czf ~/media-backup-$(date +%F).tar.gz -C /srv/aurora/shared media

# trial pass, then the rest
docker compose -f docker-compose.prod.yml exec backend \
  python manage.py backfill_media_variants --apply --limit 5
docker compose -f docker-compose.prod.yml exec backend \
  python manage.py backfill_media_variants --apply --batch-size 50
```

Use `exec`, not `run` — `run` fires `entrypoint.sh`, and the backend service
sets `RUN_COLLECTSTATIC=true`, so a one-off would trigger
`collectstatic --clear` for no reason.

The command is baked into the image (`COPY . /app/`), so **it does not exist in
the prod container until the image is rebuilt and pushed.** Dev bind-mounts
`./backend:/app`, so it works there immediately.

### Analytics will dip slightly

Change 12 defers GTM to `requestIdleCallback`, so it initialises up to ~1s
later and some very-fast-bounce sessions go unrecorded. Correct trade — a tag
manager must not sit on the critical rendering path — but tell whoever watches
those numbers before they read it as a regression.

---

## Before you ship

Nothing below was run in the analysis environment.

**Frontend — the real gate.** A lazy-loading mistake surfaces as a blank route
at runtime, not a build error:

```bash
cd frontend && npm run build
```

Then log in as admin and click through all 24 admin routes with the network tab
open. Each should pull its own chunk. Confirm `/admin/gtm-settings` still
enforces `RequireStaffOnly`.

Optional but worth it:

```bash
npm i -D rollup-plugin-visualizer
ANALYZE=1 npm run build
```

No admin page, `recharts`, `lexical`, or `@dnd-kit` should appear in the entry
chunk. (Static import-graph analysis says they do not — 68 eager modules
reached, none touching those vendors — but confirm against a real build.)

**Backend — query counts.** Add this test; it is the thing that stops Phase 4
silently regressing later:

```python
from django.test.utils import CaptureQueriesContext
from django.db import connection

def test_product_list_query_count(self):
    # create ~20 products with variants and media in setUp
    with CaptureQueriesContext(connection) as ctx:
        self.client.get("/api/v1/products/")
    self.assertLess(len(ctx.captured_queries), 10)
```

Simulation of a 20-product page put it at **83 queries before, 3 after** (base
SELECT + media prefetch + variants prefetch). Expect a handful more in reality
from pagination and auth.

Also smoke-test, since these are the paths the divergences touch:

- deals carousel — in-stock badges and add-to-cart quantity caps still correct
- admin product list — `stock_summary` column still populated
- product grid — hover image now actually swaps (new behaviour, previously dead)

**Baseline first.** Capture before/after so the effect is provable:

```bash
npx lighthouse https://aurorablings.com --output=json --output-path=./baseline-home.json
npx lighthouse https://aurorablings.com/products/ --output=json --output-path=./baseline-plp.json
```

Record LCP, TBT, Speed Index, total transfer size.

## Rough expectations

| Phase | Metric | Expected |
|---|---|---|
| 1 | API p50 latency | −10 to −30 ms/request |
| 2 | Product grid image bytes | −80 to −90% (after backfill) |
| 3 | Initial JS transfer | −60 to −70% |
| 4 | `/api/v1/products/` response time | −60 to −80% |
| 5 | LCP on homepage | −0.5 to −1.5 s |

Estimates from reading the code, not measurements. The Phase 4 number is the
best-supported (query counts are countable); the Phase 3 number is the least,
since it was never compiled.

---

## Files changed

**Backend**

- `config/settings/base.py` — `CONN_MAX_AGE`, `CONN_HEALTH_CHECKS`
- `config/gunicorn.conf.py` — `gthread`, 4 threads, worker count lowered
- `apps/catalog/models.py` — `price_range` reads the prefetch cache
- `apps/catalog/serializers.py` — derivative URLs + srcset, hover fix,
  `total_stock` via annotation, new `AdminProductListSerializer`
- `apps/catalog/selectors.py` — ordered media prefetch, `_image_count_subquery`,
  `_warehouse_stock_subquery`, both applied to list and deals
- `apps/catalog/views.py` — staff/public serializer split on `list()`
- `apps/catalog/management/commands/backfill_media_variants.py` — new

**Frontend**

- `src/lib/queryClient.ts` — real defaults
- `src/App.tsx` — 34 lazy routes, two Suspense boundaries, `RouteFallback`,
  `useLenis` removed
- `src/components/layouts/MainLayout.tsx` — owns `useLenis` now
- `src/hooks/useLenis.ts` — velocity write dead-zone
- `src/pages/storefront/HomePage.tsx` — hero scroll-reveal removed
- `src/components/storefront/CategoryShowcase/CategoryShowcase.tsx` — WebP + srcset
- `src/assets/bg-img.webp`, `bg-img-640.webp` — new (1689 KB → 115 KB / 63 KB)
- `src/types/product.ts` — srcset field types
- `src/pages/storefront/ProductListingPage.tsx` — deferral note
- `index.html` — inline GTM script removed, preload hoisted
- `src/main.tsx` — GTM deferred to idle
- `vite.config.ts` — manual chunks

**Scripts**

- `scripts/restore_local.sh` — chown after `docker cp`

---

# Lighthouse 73 → 100 push: Phases 1–3 (as-built, 2026-07-21)

Baseline after the original 14 changes: mobile 73 (FCP 3.4s, LCP 4.3s, SI 6.4s,
TBT 70ms, CLS 0). Everything below attacks the remaining problem: a CSR SPA
paints nothing until HTML → CSS → JS → API → image completes.

## Phase 1 — critical path trims

- **Critical CSS inlined at build** — `frontend/scripts/inline-critical.mjs`
  (Beasties, new devDependency) runs as part of `npm run build`. Inlines
  above-the-fold rules into `dist/index.html`; full stylesheets demoted to
  `media="print"` swap + `<noscript>` fallback. Hashed CSS files unchanged, so
  immutable caching still holds.
- **Cache lifetimes** — `aurorablings.conf.template`: `/assets/` now 1y
  immutable with hard 404 (no SPA fallback), `index.html` `no-cache`.
  `frontend.conf`: `no-cache` on the SPA fallback. `nginx.prod.conf` already
  had `/assets/` right.
- **Forced reflow** — `useLenis` defers Lenis + ScrollTrigger init past first
  paint (double rAF → `requestIdleCallback`, 1.5s cap). Native scroll in the
  gap; only `MainLayout` consumes the hook.
- **Image delivery** — no code change; pipeline already emits AVIF/WebP
  derivatives. Operational: run `backfill_banner_variants` and
  `backfill_media_variants` after deploy.

## Phase 2 — break the LCP request chain (SSI bootstrap)

`index.html` now carries
`<!--#include virtual="/api/v1/banners/bootstrap-fragment/?uri=$request_uri" -->`.
nginx (`ssi on; ssi_silent_errors on;` in both configs; docker proxy also
forces `Accept-Encoding ""` so SSI can parse upstream HTML) resolves it as a
subrequest to the new `backend/apps/banners/bootstrap.py` view, which returns
(Redis-cached 5 min, two variants, invalidated with the banner cache in
`tasks.py`):

- a `<link rel="preload" as="image">` for the **top-left** banner — the LCP
  card on every breakpoint; selection is by `position`, NOT `order` — AVIF
  srcset when all three derivatives exist, WebP otherwise, homepage only
  (`?uri=` guard);
- `window.__BOOT__` with the active banners + public settings, consumed by
  `usePromoBanners`, `settingsService.getPublic` (feeds useBranding /
  useCurrency), and the GTM bootstrap in `main.tsx` via `src/services/boot.ts`.

Failure mode: backend down → include silently vanishes → SPA fetches the APIs
exactly as before. Deploy order between backend/frontend/nginx is irrelevant.

## Phase 3 — pre-hydration hero shell

A plain inline script inside `#root` (index.html) renders the top-left banner
card from `window.__BOOT__` synchronously during HTML parse — before the
module bundle is even requested. FCP/LCP now happen at HTML+image speed.
Geometry mirrors the module CSS (220px rows ≤1024px; 1.3fr column / 456px on
desktop) via hand-written `ab-shell-*` classes that Beasties and CSS modules
can't touch. React's first commit replaces the subtree; same image URL, so the
swap repaints from cache. `MainLayout` skips its entrance fade exactly once
when `__SHELL_PAINTED__` is set, so hydration doesn't hide content the visitor
is already reading. Non-home routes and dev mode: script no-ops.

## Verified

- Frontend: clean Linux install + `tsc -b` + `vite build` + Beasties step all
  pass; SSI directive and shell survive the build.
- jsdom end-to-end: fragment spliced where nginx would put it → `__BOOT__`
  parsed, AVIF preload targets top-left, shell renders inside `#root` with
  correct bg/priority, no shell on `/product/x`.
- Backend: `py_compile` + logic simulation of `_preload_tag` /
  `_script_safe_json` (escaping verified against `</script>` injection).
- NOT verified: a running Django (env can't boot it) or a real Lighthouse run.

## Before you ship

1. `npm install` (new devDependency: beasties), then `npm run build` — expect
   "inline-critical: critical CSS inlined into dist/index.html".
2. Deploy backend (no migrations) + frontend; copy nginx config; reload nginx.
3. Run both backfill commands if any banner/product predates the AVIF fields.
4. Smoke: `curl -s https://aurorablings.com/ | grep -c __BOOT__` → 1; preload
   tag present on `/`, absent on a product URL; hero visible with JS disabled
   modulo fonts.
5. Re-run Lighthouse mobile + desktop; expected mobile high-80s→95+,
   desktop ~100. Residual gap, if any, will be font loading or third-party
   tags — measure before touching anything else.
