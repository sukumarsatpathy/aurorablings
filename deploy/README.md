# Aurora Blings Production Deployment (Ubuntu)

This deployment setup uses release-based rollout with fast rollback:

```text
/srv/aurorablings/
  releases/<timestamp-sha>/
  current -> releases/<timestamp-sha>
  shared/
    .env
    media/
    logs/
    run/
    static/
    venv/
```

## 1) One-time server bootstrap

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx redis-server postgresql postgresql-contrib certbot python3-certbot-nginx
sudo mkdir -p /srv/aurorablings
sudo chown -R $USER:www-data /srv/aurorablings

bash deploy/scripts/bootstrap_server.sh
```

Populate `/srv/aurorablings/shared/.env` with production values.

## 2) Systemd services

Copy and enable services:

```bash
sudo cp deploy/systemd/aurorablings-gunicorn.service /etc/systemd/system/
sudo cp deploy/systemd/aurorablings-celery-worker.service /etc/systemd/system/
sudo cp deploy/systemd/aurorablings-celery-beat.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable aurorablings-gunicorn aurorablings-celery-worker aurorablings-celery-beat
sudo systemctl start aurorablings-gunicorn aurorablings-celery-worker aurorablings-celery-beat
```

## 3) Nginx

Use `deploy/nginx/aurorablings.conf.template` as `/etc/nginx/sites-available/aurorablings.conf`.

```bash
sudo ln -s /etc/nginx/sites-available/aurorablings.conf /etc/nginx/sites-enabled/aurorablings.conf
sudo nginx -t
sudo systemctl reload nginx
```

Django serves static/media only in debug mode. In production, Nginx serves:
- `/static/` -> `/srv/aurorablings/shared/static/`
- `/media/` -> `/srv/aurorablings/shared/media/`

## 4) SSL with Certbot

```bash
sudo certbot --nginx -d aurorablings.com -d www.aurorablings.com -d api.aurorablings.com
sudo certbot renew --dry-run
```

Auto-renew timer is installed by package:

```bash
systemctl list-timers | grep certbot
```

If needed, create a deploy hook (`/etc/letsencrypt/renewal-hooks/deploy/nginx-reload.sh`):

```bash
#!/usr/bin/env bash
systemctl reload nginx
```

## 5) Release deployment command

```bash
APP_ROOT=/srv/aurorablings \
RELEASE_ID=$(date +"%Y%m%d%H%M%S")-manual \
ARTIFACT_PATH=/tmp/aurorablings-release.tgz \
WEB_BASE_URL=https://aurorablings.com \
API_BASE_URL=https://api.aurorablings.com \
bash deploy/scripts/deploy_release.sh \
  --app-root "$APP_ROOT" \
  --release-id "$RELEASE_ID" \
  --artifact "$ARTIFACT_PATH" \
  --web-base-url "$WEB_BASE_URL" \
  --api-base-url "$API_BASE_URL" \
  --keep-releases 3
```

What this does:
1. Extracts artifact into `/srv/aurorablings/releases/<release-id>`
2. Links shared `.env`
3. Installs backend dependencies into shared venv
4. Runs migrations + collectstatic
5. Runs preflight health checks against temporary gunicorn instance
6. Switches `current` symlink only after preflight success
7. Restarts gunicorn/celery, reloads nginx
8. Runs smoke health checks
9. Keeps last 3 releases

## 6) Rollback

List releases:

```bash
ls -1dt /srv/aurorablings/releases/*
```

Rollback to previous:

```bash
bash deploy/scripts/rollback.sh
```

Rollback to specific release:

```bash
bash deploy/scripts/rollback.sh 20260330101010-ab12cd3
```

## 7) Health checks and smoke checks

Health endpoints:
- `/health/server`
- `/health/db`
- `/health/cache`
- `/health/payment`

Run manually:

```bash
WEB_BASE_URL=https://aurorablings.com API_BASE_URL=https://api.aurorablings.com bash deploy/scripts/health_check.sh full
API_BASE_URL=http://127.0.0.1:18100 bash deploy/scripts/health_check.sh api-only
```

Smoke checks cover:
- Homepage
- Admin login page
- Product listing API
- Checkout/init endpoint behavior (must not 500)
- Health endpoints

## 8) GitHub Actions environments

Workflow file: `.github/workflows/deploy.yml`
- `develop` -> `staging` environment deploy
- `main` -> `production` environment deploy (use manual approval rule in GitHub environment)
- Concurrency lock prevents overlapping deploys per branch

Set environment secrets (staging + production):
- `*_SSH_KEY`
- `*_HOST`
- `*_USER`
- `*_APP_ROOT`
- `*_WEB_BASE_URL`
- `*_API_BASE_URL`

## 9) Staging vs production notes

Use separate servers and `.env` values:
- staging: sandbox payment keys, staging domains, optional lower workers
- production: live payment keys, strict hosts, secure cookies, SSL-only

Always deploy to staging first, validate checkout/webhooks, then promote to production.

## 10) Migration safety guidance

For rollback-safe releases:
- prefer additive DB migrations
- avoid destructive schema changes in same deploy
- deploy code that tolerates both old/new schema during transitions