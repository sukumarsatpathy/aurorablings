#!/usr/bin/env bash
# Run from the repo root. Pushing to main triggers .github/workflows/deploy.yml,
# which builds, packages and deploys to production. Read before running.
set -euo pipefail

cd "$(dirname "$0")"

# 1. Clear the stale lock left behind by a sandboxed git status.
rm -f .git/index.lock

# 2. Sanity-check what is about to ship.
git status
git diff --stat

# 3. Verify the frontend build locally FIRST. CI gates on this
#    (deploy.yml line 55, no `|| true`), so a failure here is a failed
#    deploy. This is the one check that could not run in the sandbox.
( cd frontend && npm run build )

# 4. Stage and commit.
git add -A
git commit -m "perf(banners): fix starved LCP banner, add AVIF alongside WebP

The three promo banners were serving raw 2400-2600px masters: their
image_small/medium/large derivatives were never generated, so the srcSet in
PromoBannerCard collapsed to a single candidate pointing at the full-size
image. 7.3 MB of banner payload on mobile against a ~390px slot.

Backend:
- add backfill_banner_variants management command (dry-run by default;
  --apply re-encodes masters and deletes originals, so it refuses to start
  without Pillow and warns when the AVIF encoder is missing)
- add AVIF generation to core/image_optimization.py at its own quality
  default (50, not WebP's 74 -- the scales are not comparable and reusing
  the WebP number produced larger files)
- add image_avif_{small,medium,large} to PromoBanner + migration 0005
- guard should_generate so a build without an AVIF encoder does not
  re-encode masters on every single save
- iterate a shared BANNER_IMAGE_FIELDS tuple in the cleanup signals so new
  formats cannot leak orphaned files into MEDIA_ROOT
- pin Pillow>=11.3.0, the floor for native AVIF

Frontend:
- prioritise the real LCP element: drop loading=lazy, set fetchpriority=high
  on the first promo banner
- exclude that card from the GSAP entrance tween; an opacity:0 start defers
  the LCP paint
- remove the index.html preload of banner-1200.webp, which is only
  DualPromoBanner's below-the-fold fallback and competed with the real LCP
  request on every route
- correct sizes: the grid collapses at 1024px, not 768px, and the widest
  cell is ~700px rather than the 1200px previously declared
- serve AVIF via <picture> ahead of the WebP img, never in place of it;
  AVIF is ~94-95% supported and the gap skews to in-app browsers"

# 5. Push. This deploys.
git push origin main
