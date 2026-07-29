# JBForge App Store

An [Umbrel](https://umbrel.com) community app store.

## Install

In umbrelOS: **App Store → ⋯ → Community App Stores**, then add:

```
https://github.com/jbforge/jbforge-app-store
```

## Apps

| App | What it is |
|-----|------------|
| [Buzz Relay](jbforge-buzz-relay) | Self-hosted relay for [Buzz](https://github.com/block/buzz), Block's agent-first team workspace. Full stack: relay (Rust) + Postgres + Redis + MinIO + host-aware nginx gateway. |

## Buzz Relay

A Buzz community *is* its relay — install this and the community lives on your
hardware, with its identity derived from the install's app seed so it survives
restarts, updates, and backups.

**Connect:** Buzz desktop app → *Join an existing community* → `ws://umbrel.local:8482`

### Publishing under a different host

The relay binds its community to exactly one canonical host. Requests arriving
under any other host are redirected there by the bundled gateway. If you want
the community published under a Tailscale MagicDNS name or a real domain, set it
**before first start** — changing it later re-seeds a new, empty community:

```sh
# ~/umbrel/app-data/jbforge-buzz-relay/user.env
APP_JBFORGE_BUZZ_RELAY_URL="wss://your-host.example.ts.net"
APP_JBFORGE_BUZZ_RELAY_MEDIA_URL="https://your-host.example.ts.net/media"
```

### Carrying an existing community onto this install

The relay signing key *is* the community identity. A fresh install derives it
from `${APP_SEED}`, which is unique per install — so a plain reinstall, or a
move from another app id, would start an empty community. To bring an existing
one along, pin the key in the same `user.env` and restore the app's data
directory alongside it:

```sh
# ~/umbrel/app-data/jbforge-buzz-relay/user.env
BUZZ_RELAY_PRIVATE_KEY="<the old install's key>"
BUZZ_GIT_HOOK_HMAC_SECRET="<the old install's git-hook secret>"
```

Then copy the old `app-data/<old-app-id>/data/` tree (postgres, redis, minio,
git) into `app-data/jbforge-buzz-relay/data/` before starting the app. The
internal service passwords are the Umbrel-convention hardcoded values in
`docker-compose.yml`, so a copied Postgres volume keeps working as-is.

### Relay version

The app tracks `ghcr.io/block/buzz:main` — Buzz has no stable release tags yet.
Umbrel only pulls that image on install and on app update, **not** on restart,
so an app whose version has not changed in a while is running an older relay
build than upstream `main`.

## License

Packaging in this repository is MIT. Buzz itself is licensed by
[Block](https://github.com/block/buzz).
