# Rust 1.95 matches block/buzz's rust-toolchain.toml; trixie matches the
# runtime image below, so the binaries are built against the glibc they run on.
# (They turn out to need no libssl at runtime — buzz-acp and the buzz CLI use
# rustls — but the toolchain still needs libssl-dev to build the workspace.)
FROM rust:1.95-trixie AS buzz-builder

ARG BUZZ_REF=047533c56c2a2d03f23ef3edb990e58405767aac
RUN apt-get update \
    && apt-get install -y --no-install-recommends git pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --filter=blob:none https://github.com/block/buzz.git /src/buzz \
    && git -C /src/buzz checkout --detach "${BUZZ_REF}"
WORKDIR /src/buzz
RUN cargo build --locked --release -p buzz-acp -p buzz-cli

FROM ghcr.io/getumbrel/hermes-agent-umbrel:v2026.7.20@sha256:d1579f49c4827321c3da72508ad12065a763c18bdd7dae227b120feb4fb230cb

ARG BUZZ_REF=047533c56c2a2d03f23ef3edb990e58405767aac
LABEL org.opencontainers.image.title="Buzz Hermes Agent" \
      org.opencontainers.image.description="Umbrel Hermes Agent connected to Buzz through the stock buzz-acp bridge" \
      org.opencontainers.image.source="https://github.com/jbforge/jbforge-app-store" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="0.1.1" \
      io.jbforge.buzz-ref="${BUZZ_REF}" \
      io.jbforge.hermes-ref="v2026.7.20"

COPY --from=buzz-builder /src/buzz/target/release/buzz-acp /usr/local/bin/buzz-acp
COPY --from=buzz-builder /src/buzz/target/release/buzz /usr/local/bin/buzz
COPY --chmod=0755 entrypoint.py /usr/local/bin/buzz-hermes-entrypoint

ENV BUZZ_ACP_AGENT_COMMAND=hermes \
    BUZZ_ACP_AGENT_ARGS=acp \
    BUZZ_ACP_RESPOND_TO=owner-only \
    BUZZ_ACP_RELAY_OBSERVER=true \
    HERMES_ACP_SKIP_CONFIGURED_MCP=1
