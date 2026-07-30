# Only the authenticated reverse proxy joins Umbrel's shared app network.
export APP_JBFORGE_BUZZ_AGENT_PROXY_IP="10.21.63.4"

_agent_user_env="${UMBREL_ROOT:-/home/umbrel/umbrel}/app-data/jbforge-buzz-agent/user.env"
[ -f "${_agent_user_env}" ] && . "${_agent_user_env}"

# Buzz identity and relay admission. BUZZ_AUTH_TAG is optional only when the
# agent identity is already a direct relay member.
export APP_JBFORGE_BUZZ_AGENT_RELAY_URL="${BUZZ_RELAY_URL:-}"
export APP_JBFORGE_BUZZ_AGENT_PRIVATE_KEY="${BUZZ_PRIVATE_KEY:-}"
export APP_JBFORGE_BUZZ_AGENT_AUTH_TAG="${BUZZ_AUTH_TAG:-}"
export APP_JBFORGE_BUZZ_AGENT_OWNER="${BUZZ_ACP_AGENT_OWNER:-}"
export APP_JBFORGE_BUZZ_AGENT_API_TOKEN="${BUZZ_API_TOKEN:-}"

# Host mapping for relay names this container cannot resolve. Umbrel containers
# inherit the host's /etc/resolv.conf nameservers, which on a stock install are
# public resolvers — so a Tailscale MagicDNS relay URL (*.ts.net) fails with
# "failed to lookup address information" and the bridge never connects. Set
# BUZZ_RELAY_HOST_MAP="relay.host.name:100.x.y.z" in user.env (the IP is
# `tailscale ip -4` on this machine). The default is an unused placeholder
# because compose rejects an empty extra_hosts entry.
export APP_JBFORGE_BUZZ_AGENT_RELAY_HOST_MAP="${BUZZ_RELAY_HOST_MAP:-buzz-relay.invalid:127.0.0.1}"

export APP_JBFORGE_BUZZ_AGENT_RESPOND_TO="${BUZZ_ACP_RESPOND_TO:-owner-only}"
export APP_JBFORGE_BUZZ_AGENT_RESPOND_TO_ALLOWLIST="${BUZZ_ACP_RESPOND_TO_ALLOWLIST:-}"
export APP_JBFORGE_BUZZ_AGENT_SYSTEM_PROMPT="${BUZZ_ACP_SYSTEM_PROMPT:-}"
export APP_JBFORGE_BUZZ_AGENT_HEARTBEAT_INTERVAL="${BUZZ_ACP_HEARTBEAT_INTERVAL:-0}"
