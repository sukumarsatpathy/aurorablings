#!/usr/bin/env bash
#
# Aurora Blings — fresh server bootstrap
#
# Prepares a bare Ubuntu 24.04 box for the GitHub Actions deploy. Everything
# here is what deploy_release.sh ASSUMES already exists and does not create:
# Docker, the directory tree, the external Postgres volume, the shared .env,
# swap, and TLS certificates.
#
# Idempotent: safe to re-run. Nothing here destroys data.
#
# Usage (as root on the new server):
#     bash bootstrap_server.sh                 # everything except certs
#     bash bootstrap_server.sh --with-certs    # also issue Let's Encrypt certs
#
# IMPORTANT: --with-certs requires DNS for aurorablings.com to already point at
# THIS server. Let's Encrypt validates over HTTP on port 80; if DNS still points
# at the old box, issuance fails. Move DNS first.

set -euo pipefail

APP_ROOT="/srv/aurora"
SHARED="${APP_ROOT}/shared"
DOMAIN="aurorablings.com"
CERT_EMAIL="${CERT_EMAIL:-sukumarsatpathy@gmail.com}"
WITH_CERTS="false"
[[ "${1:-}" == "--with-certs" ]] && WITH_CERTS="true"

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!!  %s\033[0m\n' "$*"; }

[[ $EUID -eq 0 ]] || { echo "Run as root."; exit 1; }

# ── 1. Docker ────────────────────────────────────────────────────────────────
# Docker's own apt repo, not Ubuntu's docker.io package — the latter lags badly
# and ships a compose version that predates the compose-plugin syntax used here.
if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker Engine"
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
                         docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
else
  log "Docker already installed: $(docker --version)"
fi

# ── 2. Swap ──────────────────────────────────────────────────────────────────
# On a small box this is the difference between degrading and OOM-killing a
# container. Free, and this server has the disk for it.
if ! swapon --show | grep -q '/swapfile'; then
  log "Creating 2G swapfile"
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl -w vm.swappiness=10 >/dev/null
  grep -q 'vm.swappiness' /etc/sysctl.conf || echo 'vm.swappiness=10' >> /etc/sysctl.conf
fi

# Redis warns about this on every start: without overcommit, a background save
# fork can fail under memory pressure -- and on a box this size, it will.
if [[ "$(sysctl -n vm.overcommit_memory)" != "1" ]]; then
  log "Enabling vm.overcommit_memory for Redis"
  sysctl -w vm.overcommit_memory=1 >/dev/null
  grep -q 'vm.overcommit_memory' /etc/sysctl.conf || echo 'vm.overcommit_memory=1' >> /etc/sysctl.conf
else
  log "Swap already present"
fi

# ── 3. Directory tree ────────────────────────────────────────────────────────
# deploy_release.sh creates most of these itself, but certbot's directories and
# the .env must exist before the first deploy, so create the lot here.
log "Creating ${APP_ROOT} tree"
mkdir -p "${APP_ROOT}/releases" \
         "${SHARED}"/{media,static,logs,logs/nginx,run,tmp} \
         "${SHARED}"/certbot/{conf,www}

# ── 4. External Docker resources ─────────────────────────────────────────────
# docker-compose.prod.yml declares BOTH of these `external: true`, so Compose
# will not create them and the deploy fails with an unhelpful error if missing.
log "Ensuring external volume and network"
docker volume inspect aurora_postgres_data >/dev/null 2>&1 \
  || docker volume create aurora_postgres_data
docker network inspect aurora_network >/dev/null 2>&1 \
  || docker network create aurora_network

# ── 5. Sizing profile, chosen from actual RAM ────────────────────────────────
TOTAL_MB=$(free -m | awk '/^Mem:/{print $2}')
log "Detected ${TOTAL_MB} MB RAM"
if [[ ${TOTAL_MB} -ge 1800 ]]; then
  PROFILE="B (2 vCPU / 2 GB)"
  read -r -d '' SIZING <<'EOF' || true
GUNICORN_WORKERS=2
GUNICORN_THREADS=4
CELERY_POOL=prefork
CELERY_CONCURRENCY=1
PG_MAX_CONNECTIONS=40
PG_SHARED_BUFFERS=256MB
PG_EFFECTIVE_CACHE_SIZE=768MB
PG_WORK_MEM=8MB
PG_MAINTENANCE_WORK_MEM=64MB
PG_AUTOVACUUM_MAX_WORKERS=2
PG_MAX_WAL_SIZE=1GB
PG_MIN_WAL_SIZE=256MB
PG_RANDOM_PAGE_COST=1.1
PG_EFFECTIVE_IO_CONCURRENCY=200
EOF
else
  PROFILE="A (1 vCPU / 1 GB — built-in defaults)"
  SIZING="# Profile A: compose defaults already match this box. Nothing to set."
fi
echo "    Selected profile ${PROFILE}"

# ── 6. .env skeleton ─────────────────────────────────────────────────────────
# deploy_release.sh hard-fails without this file. Secrets are GENERATED fresh,
# not copied: the old DJANGO_SECRET_KEY and POSTGRES_PASSWORD are published in
# the public repo's git history. A rebuild is the one moment rotating them is
# free -- the database volume is empty, so there is no existing role whose
# password has to match.
if [[ -f "${SHARED}/.env" ]]; then
  warn "${SHARED}/.env already exists — leaving it alone."
  warn "Sizing block for profile ${PROFILE} written to ${SHARED}/sizing.env instead."
  printf '%s\n' "${SIZING}" > "${SHARED}/sizing.env"
else
  log "Writing ${SHARED}/.env with freshly generated secrets"
  DJANGO_KEY=$(python3 -c 'import secrets,string; print("".join(secrets.choice(string.ascii_letters+string.digits+"!@#$%^&*(-_=+)") for _ in range(64)))')
  PG_PASS=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
  cat > "${SHARED}/.env" <<EOF
# ─── Aurora Blings production environment ───────────────────────────────
# Generated by bootstrap_server.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)
#
# SECRETS BELOW ARE NEWLY GENERATED. Do not paste the old values back in:
# the previous DJANGO_SECRET_KEY and POSTGRES_PASSWORD are in the public
# repo's git history and can forge JWTs for any user.
#
# BACK THIS FILE UP SOMEWHERE ENCRYPTED. It is not in git and not in any
# backup script -- backup_prod.sh does not capture it.

DJANGO_SETTINGS_MODULE=config.settings.prod
DJANGO_SECRET_KEY=${DJANGO_KEY}
DJANGO_DEBUG=False
# localhost/127.0.0.1 are required, not optional: the container healthcheck
# curls http://localhost:8000/, so the Host header is "localhost". Django
# answers a Host outside this list with 400, curl -f reads 400 as failure, and
# the container never reports healthy -- the deploy then hangs on "backend
# Waiting" and eventually fails, with nothing in the logs to explain why.
# "backend" is the compose service name, used by the Celery health checks
# (HEALTH_API_BASE_URL=http://backend:8000/api).
DJANGO_ALLOWED_HOSTS=${DOMAIN},www.${DOMAIN},localhost,127.0.0.1,backend
DJANGO_CSRF_TRUSTED_ORIGINS=https://${DOMAIN},https://www.${DOMAIN}
CORS_ALLOWED_ORIGINS=https://${DOMAIN},https://www.${DOMAIN}
BACKEND_URL=https://${DOMAIN}

POSTGRES_DB=aurora_db
POSTGRES_USER=aurora_user
POSTGRES_PASSWORD=${PG_PASS}

REDIS_URL=redis://redis:6379/1
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# ─── Email: NOT configured here ─────────────────────────────────────────
# Deliberately omitted. This project does not send mail through Django's
# EMAIL_* settings: apps/notifications/services/senders/smtp_sender.py calls
# get_connection() with backend, host, username and password passed
# explicitly, read from the "notification.smtp" AppSetting (falling back to
# the EmailSettings model). Both are edited from the admin UI, and both
# override anything set here.
#
# Configure SMTP at:  /admin/notifications  ->  provider settings
# Brevo is the intended provider (the domain publishes brevo1/brevo2
# _domainkey CNAMEs): host smtp-relay.brevo.com, port 587, username = the
# Brevo SMTP login, password = a generated SMTP key.
#
# If mail is not sending, the cause is almost always that the SMTP settings
# row is disabled or incomplete -- smtp_sender raises "SMTP provider is
# disabled in settings" / "SMTP configuration is incomplete". It is not
# EMAIL_BACKEND.
DEFAULT_FROM_EMAIL=Aurora Blings <noreply@${DOMAIN}>
ADMINS_EMAIL=

# Payments: Razorpay is the live gateway. Empty means checkout cannot complete.
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=

# Shipping
NIMBUSPOST_API_KEY=
NIMBUSPOST_WEBHOOK_SECRET=

# ─── Optional ───────────────────────────────────────────────────────────
ENABLE_DJANGO_ADMIN=False
TURNSTILE_ENABLED=False

# ─── Server sizing — profile ${PROFILE} ─────────────────────────────────
# See deploy/server-sizing.env.sample. These are SIZING knobs only; they do
# not affect the Celery beat schedule or health monitoring.
${SIZING}
EOF
  chmod 640 "${SHARED}/.env"
fi

# ── 7. TLS certificates ──────────────────────────────────────────────────────
# nginx.prod.conf's 443 block references the cert files directly, so nginx
# REFUSES TO START without them and the whole deploy fails. Certs must exist
# before the first deploy, not after.
if [[ "${WITH_CERTS}" == "true" ]]; then
  if [[ -f "${SHARED}/certbot/conf/live/${DOMAIN}/fullchain.pem" ]]; then
    log "Certificates already present for ${DOMAIN}"
  else
    log "Issuing Let's Encrypt certificates (standalone, port 80)"
    # Check EVERY name in the request, not just the apex. Let's Encrypt
    # validates each SAN independently, so one stale record fails the whole
    # order. A name resolving to MORE than one address is the dangerous case:
    # the old record was added-to rather than replaced, validation picks an
    # address at random, and issuance fails intermittently.
    MYIP=$(curl -fsS https://api.ipify.org || echo "unknown")
    DNS_OK=true
    for NAME in "${DOMAIN}" "www.${DOMAIN}"; do
      mapfile -t ADDRS < <(getent ahostsv4 "${NAME}" | awk '{print $1}' | sort -u)
      if [[ ${#ADDRS[@]} -eq 0 ]]; then
        warn "${NAME}: no A record at all."
        DNS_OK=false
      elif [[ ${#ADDRS[@]} -gt 1 ]]; then
        warn "${NAME}: resolves to MULTIPLE addresses (${ADDRS[*]})."
        warn "  Delete the stale A record(s); leave exactly one pointing here."
        DNS_OK=false
      elif [[ "${ADDRS[0]}" != "${MYIP}" ]]; then
        warn "${NAME}: resolves to ${ADDRS[0]}, this server is ${MYIP}."
        DNS_OK=false
      else
        echo "    ${NAME} -> ${ADDRS[0]}  OK"
      fi
    done
    if [[ "${DNS_OK}" != "true" ]]; then
      warn "Refusing to request a certificate: it would fail and consume a"
      warn "Let's Encrypt rate-limit slot (5 failures per hostname per hour)."
      exit 1
    fi
    docker run --rm -p 80:80 \
      -v "${SHARED}/certbot/conf:/etc/letsencrypt" \
      -v "${SHARED}/certbot/www:/var/www/certbot" \
      certbot/certbot certonly --standalone \
        -d "${DOMAIN}" -d "www.${DOMAIN}" \
        --email "${CERT_EMAIL}" --agree-tos --no-eff-email --non-interactive
  fi
else
  warn "Skipping certificates (--with-certs not given)."
  warn "nginx will NOT start without them. Move DNS, then re-run with --with-certs."
fi

# ── 8. Certificate auto-renewal ──────────────────────────────────────────────
# Issuance above uses --standalone, which needs port 80 to itself. Renewal
# cannot: nginx owns port 80 by then. nginx.prod.conf already serves
# /.well-known/acme-challenge/ from /var/www/certbot (the same directory
# mounted here), so renewal uses --webroot and needs no downtime.
#
# Without this the certificate simply expires and the site goes down on a date
# nobody has in their calendar. certbot's own message after issuance says
# renewal is not configured; this is what configures it.
log "Installing certificate renewal"
cat > /usr/local/bin/aurora-renew-certs.sh <<'RENEW'
#!/usr/bin/env bash
set -euo pipefail
SHARED="/srv/aurora/shared"

docker run --rm \
  -v "${SHARED}/certbot/conf:/etc/letsencrypt" \
  -v "${SHARED}/certbot/www:/var/www/certbot" \
  certbot/certbot renew --webroot -w /var/www/certbot --quiet

# Reload nginx so it picks up a renewed certificate. The compose project name
# is timestamped per release, so match on the service name rather than a fixed
# container name. No-op when nothing renewed.
NGINX=$(docker ps -qf "name=nginx_proxy" | head -1)
if [[ -n "${NGINX}" ]]; then
  docker exec "${NGINX}" nginx -s reload || true
fi
RENEW
chmod +x /usr/local/bin/aurora-renew-certs.sh

# Twice daily is Let's Encrypt's own recommendation: renewal only acts inside
# the last 30 days, so most runs do nothing, and two chances a day means a
# transient failure is not fatal.
CRON_LINE="17 3,15 * * * /usr/local/bin/aurora-renew-certs.sh >> /var/log/aurora-certbot.log 2>&1"
( crontab -l 2>/dev/null | grep -v 'aurora-renew-certs' ; echo "${CRON_LINE}" ) | crontab -
echo "    renewal cron installed (03:17 and 15:17 daily)"

# ── Done ─────────────────────────────────────────────────────────────────────
cat <<EOF

$(log "Bootstrap complete")

  Docker      $(docker --version | cut -d, -f1)
  RAM         ${TOTAL_MB} MB  ->  sizing profile ${PROFILE}
  Swap        $(swapon --show=NAME --noheadings | tr '\n' ' ')
  Volume      aurora_postgres_data
  Network     aurora_network
  Env file    ${SHARED}/.env
  Certs       $([[ -f "${SHARED}/certbot/conf/live/${DOMAIN}/fullchain.pem" ]] && echo present || echo "MISSING — nginx will not start")

NEXT, in this order:

  1. Fill in the blank secrets in ${SHARED}/.env (Razorpay, shipping).
     Email is configured in the ADMIN UI, not here -- see the comments in .env.
     If sizing.env was written instead of .env, append it:
         cat ${SHARED}/sizing.env >> ${SHARED}/.env
  2. Back up ${SHARED}/.env somewhere encrypted. Nothing else has a copy.
  3. If certs are MISSING above: move DNS here, then re-run with --with-certs.
  4. Add your CI public key to /root/.ssh/authorized_keys.
  5. Set the four GitHub secrets (PROD_HOST = this server's IP).
  6. Merge the infra branch to main so Actions deploys.
  7. Restore the database and media (see the recovery runbook).
  8. Only after key auth works: disable password SSH login.

EOF
