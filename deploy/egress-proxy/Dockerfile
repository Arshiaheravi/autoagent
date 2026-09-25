# Allowlist egress proxy — the only route off the tenant --internal network.
# Default-deny tinyproxy that permits CONNECT to api.anthropic.com:443 and nothing
# else (no cloud metadata, no control plane, no siblings). Runs non-root.
FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends tinyproxy \
    && rm -rf /var/lib/apt/lists/*

COPY tinyproxy.conf /etc/tinyproxy/tinyproxy.conf
COPY filter /etc/tinyproxy/filter

# tinyproxy needs to read its config + write nothing persistent; run unprivileged.
RUN chown -R 10001:10001 /etc/tinyproxy
USER 10001:10001
EXPOSE 8888

# Foreground so Docker supervises it.
CMD ["tinyproxy", "-d", "-c", "/etc/tinyproxy/tinyproxy.conf"]
