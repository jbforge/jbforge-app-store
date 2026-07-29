# Static IPs on Umbrel's shared app network (10.21.0.0/16).
# Container-name DNS is unreliable here: bare service names collide across
# apps, and <app>_<service>_1 names contain underscores, which strict URL
# parsers (MinIO mc) reject. Official apps pin IPs — same pattern as bitcoin.
export APP_JBFORGE_BUZZ_RELAY_IP="10.21.62.2"
export APP_JBFORGE_BUZZ_RELAY_POSTGRES_IP="10.21.62.3"
export APP_JBFORGE_BUZZ_RELAY_REDIS_IP="10.21.62.4"
export APP_JBFORGE_BUZZ_RELAY_MINIO_IP="10.21.62.5"

# Relay URL override: drop a user.env next to the app's data dir to pin the
# community host (e.g. a Tailscale MagicDNS name). The relay binds its
# community to this host — changing it re-seeds a community for the new host.
_buzz_user_env="${UMBREL_ROOT:-/home/umbrel/umbrel}/app-data/jbforge-buzz-relay/user.env"
[ -f "${_buzz_user_env}" ] && . "${_buzz_user_env}"
export APP_JBFORGE_BUZZ_RELAY_URL="${APP_JBFORGE_BUZZ_RELAY_URL:-ws://${DEVICE_DOMAIN_NAME:-umbrel.local}:8482}"

# Relay identity. By default the signing key derives from ${APP_SEED}, Umbrel's
# deterministic per-install secret, so the community identity is stable across
# restarts and updates. Set BUZZ_RELAY_PRIVATE_KEY (and BUZZ_GIT_HOOK_HMAC_SECRET)
# in the same user.env to carry an existing community's identity onto this
# install — that is what makes migrating a live community here possible, since a
# different app id would otherwise get a different seed and seed a new community.
export APP_JBFORGE_BUZZ_RELAY_PRIVATE_KEY="${BUZZ_RELAY_PRIVATE_KEY:-${APP_SEED}}"
export APP_JBFORGE_BUZZ_RELAY_GIT_HOOK_SECRET="${BUZZ_GIT_HOOK_HMAC_SECRET:-${APP_SEED}-git-hook}"

# Gateway derivations: canonical host (no scheme/path) and the public
# browser-facing URL, used by the nginx gateway for host-based redirects.
export APP_JBFORGE_BUZZ_RELAY_GATEWAY_IP="10.21.62.6"
_buzz_canonical_host="$(printf %s "${APP_JBFORGE_BUZZ_RELAY_URL}" | sed -e 's|^wss://||' -e 's|^ws://||' -e 's|/.*$||')"
export APP_JBFORGE_BUZZ_RELAY_CANONICAL_HOST="${_buzz_canonical_host}"
case "${APP_JBFORGE_BUZZ_RELAY_URL}" in
  wss://*) export APP_JBFORGE_BUZZ_RELAY_PUBLIC_URL="https://${_buzz_canonical_host}" ;;
  *)       export APP_JBFORGE_BUZZ_RELAY_PUBLIC_URL="http://${_buzz_canonical_host}" ;;
esac

# Media base URL defaults to the canonical host, not DEVICE_DOMAIN_NAME: an
# install that only overrides the relay URL would otherwise hand out media links
# on a host the gateway immediately redirects away from. Still independently
# overridable in user.env for setups that serve media from elsewhere.
export APP_JBFORGE_BUZZ_RELAY_MEDIA_URL="${APP_JBFORGE_BUZZ_RELAY_MEDIA_URL:-${APP_JBFORGE_BUZZ_RELAY_PUBLIC_URL}/media}"
