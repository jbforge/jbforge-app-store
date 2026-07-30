# Buzz Agent for Umbrel

This app runs [Hermes Agent](https://github.com/NousResearch/hermes-agent) behind
Buzz's stock `buzz-acp` bridge:

```text
Buzz relay <-- WebSocket --> buzz-acp <-- ACP stdio --> Hermes Agent
```

The agent connects outbound, so the Umbrel does not need an inbound port for
agent traffic. The app's port serves the full Hermes dashboard behind Umbrel
authentication.

## Before installation

In Buzz Desktop, create a dedicated Hermes agent owned by you. Keep **Who can
talk to this agent** set to **Owner only**. Record the deployment values:

- community relay WebSocket URL;
- dedicated agent private key (`nsec` or hex; never reuse a human key);
- owner public key (64-character hex);
- owner-signed NIP-OA auth tag, unless the agent is a direct relay member.

Add the agent identity to only the Buzz channels where it should work.

## Configure the app

Open the app after installation. Its Umbrel-authenticated setup page asks for:

```dotenv
BUZZ_RELAY_URL="wss://community.example.com"
BUZZ_PRIVATE_KEY="nsec1..."
BUZZ_AUTH_TAG='["auth", "..."]'
BUZZ_ACP_AGENT_OWNER="64-character-owner-pubkey-hex"
```

`BUZZ_AUTH_TAG` may be omitted only when the dedicated agent key is already a
direct relay member. If the relay separately requires a bearer token, add
`BUZZ_API_TOKEN`.

Select **Open Hermes** to choose a model/provider and authenticate it through
the Hermes dashboard. The setup page stores Buzz credentials mode-0600 in
`data/hermes/buzz-acp.env` — its own file, not Hermes' `.env`, so the dashboard
saving a provider credential can never race it away — and it never returns
stored secrets to the browser. As a host-admin fallback, the Buzz variables can
instead be set in `app-data/jbforge-buzz-agent/user.env`; the setup page's
values take precedence over those.

The app persists Hermes configuration, credentials, skills, memory, sessions,
and state under `app-data/jbforge-buzz-agent/data/hermes/`. Its tool workspace is
`app-data/jbforge-buzz-agent/workspace/`.

Saving from the setup page restarts the bridge in place; restart the app after
editing `user.env` by hand. The container runs `hermes acp --check` before
connecting to Buzz and retries rather than exiting, so a failed check shows up
in the app logs with the setup page still reachable.

## Safer defaults

- `BUZZ_ACP_RESPOND_TO=owner-only` is the default. Hermes ACP can use shell and
  file tools unattended; do not expose it to arbitrary channel authors.
- To admit a small team, set `BUZZ_ACP_RESPOND_TO=allowlist` and
  `BUZZ_ACP_RESPOND_TO_ALLOWLIST` to comma-separated 64-character pubkeys.
- Relay observer activity is enabled so the owner can see live agent activity
  in Buzz Desktop.
- All Hermes state and the workspace survive app/container restarts.
- Revoking the agent in Buzz is the security boundary. Stop/uninstall the
  Umbrel app only after relay revocation has succeeded.

## Image provenance

`ghcr.io/jbforge/buzz-hermes-agent:0.1.0` is built by this repository's GitHub
Actions workflow from:

- Buzz `047533c56c2a2d03f23ef3edb990e58405767aac` (`buzz-acp` and `buzz` CLI);
- Umbrel's digest-pinned Hermes Agent `v2026.7.20` image with its ACP extra.

The workflow publishes native `linux/amd64` and `linux/arm64` images with SBOM
and provenance attestations.
