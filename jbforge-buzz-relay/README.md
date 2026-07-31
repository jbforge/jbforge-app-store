# Buzz Relay

Runs the [Buzz](https://github.com/block/buzz) relay on umbrelOS: the Rust
relay, Postgres, Redis, MinIO, a host-aware nginx gateway, and an admin
dashboard with a one-click full backup.

A Buzz community *is* its relay, so this app holds all of it — messages,
channels, members, workflows, git repos, media.

## Connecting

Open Buzz Desktop, choose "Join an existing community", and enter the relay
URL — by default `ws://umbrel.local:8482`.

The relay binds its community to exactly one host. To publish it under a
different name (a Tailscale MagicDNS name, a domain behind a reverse proxy),
set `APP_JBFORGE_BUZZ_RELAY_URL` in `app-data/jbforge-buzz-relay/user.env`
**before first start** — changing it later re-seeds a new, empty community.
Requests arriving on any other host get redirected to the canonical URL.

## Admin dashboard

`http://umbrel.local:8484` — username `admin`, password = this app's Umbrel
password. If you don't have it, read
`app-data/jbforge-buzz-relay/data/admin/credentials.txt`; the gateway writes
the value it used there on every start. Override it with `BUZZ_ADMIN_PASSWORD`
in `user.env`.

It shows:

- relay version, uptime, Postgres pool, stored/rejected event counts
- per-community messages, people, agents, channels, git repos, media, live
  connections and subscriptions
- events by kind
- the relay's own moderation reports and feedback (`/reports`, `/feedback`)
- **Download full backup**

The stats come from the relay's `/_status` and Prometheus `/metrics`
endpoints, which are container-internal; the gateway exposes them on the admin
port only.

It runs on its own port so the relay port keeps the unauthenticated WebSocket
surface Buzz Desktop needs. Basic auth over plain HTTP is only as private as
the network carrying it — keep the box on your LAN or Tailscale.

## Backup

"Download full backup" streams one `.tar.gz`:

| Path | What |
|---|---|
| `postgres.dump` | `pg_dump -Fc` of the whole relay database — every community |
| `minio/` | the media object store |
| `git/` | the relay's git data |
| `identity.env` | relay signing key + git-hook secret — **secret** |
| `RESTORE.md` | restore steps |

`identity.env` is the part people lose. Restore the database onto a fresh
install without it and the relay derives a new key from that install's
`APP_SEED`: same messages, different community, and no client reconnects.

Umbrel's own app backup copies a live Postgres data directory in place, which
is not a consistent snapshot. Use this instead.

The dump is assembled before the download starts, so the browser waits a
moment first. It runs against the live relay — no downtime.

## Notes

- The relay runs in open mode: anyone who can reach the port with a Nostr key
  can join. Keep it on your LAN/Tailscale, or enable the pubkey allowlist /
  closed relay mode via env if you expose it.
- The relay signing key derives from this install's app seed, so the community
  identity is stable across restarts and updates. Override it with
  `BUZZ_RELAY_PRIVATE_KEY` (and `BUZZ_GIT_HOOK_HMAC_SECRET`) in `user.env` to
  carry an existing community onto this install.
- The relay image is pinned by digest. Buzz versions the relay separately from
  Buzz Desktop via `relay-v*` tags, and the desktop version number does not
  correspond to a relay build.

## user.env

| Variable | Default |
|---|---|
| `APP_JBFORGE_BUZZ_RELAY_URL` | `ws://<device>:8482` |
| `APP_JBFORGE_BUZZ_RELAY_MEDIA_URL` | canonical public URL + `/media` |
| `BUZZ_RELAY_PRIVATE_KEY` | derived from `APP_SEED` |
| `BUZZ_GIT_HOOK_HMAC_SECRET` | `<APP_SEED>-git-hook` |
| `BUZZ_ADMIN_PORT` | `8484` |
| `BUZZ_ADMIN_PASSWORD` | this app's `APP_PASSWORD` |
| `BUZZ_ADMIN_HOST` | `buzz-admin.internal` (internal only; not a DNS name) |
