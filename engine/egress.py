#!/usr/bin/env python3
"""Egress control for untrusted tenants (the network launch gate).

Bare bridge networking lets a tenant's session reach cloud metadata
(169.254.169.254 → IAM creds), the Postgres control plane, and sibling
containers. The fix is two-layer:

  1. Run the tenant container on a Docker ``--internal`` network — it has NO
     route off-host, so metadata / control plane / the public internet are all
     unreachable *directly*. This is the load-bearing guarantee (proven in
     test_egress.py against real Docker).
  2. Attach a dual-homed **allowlist proxy** (deploy/egress-proxy) to both the
     internal network and an external one. The tenant's HTTPS_PROXY points at it;
     it permits ONLY api.anthropic.com and denies everything else. That's the one
     hole punched through the wall, and it's allowlisted.

This module builds the Docker plumbing (network + proxy) as pure argv builders so
they're unit-testable, plus docker-gated helpers that actually run them.
"""
import os
import subprocess

DEFAULT_INTERNAL_NET = "autoagent-tenants-internal"
DEFAULT_EXTERNAL_NET = "autoagent-egress-external"
DEFAULT_PROXY_IMAGE = "autoagent-egress-proxy:latest"
DEFAULT_PROXY_PORT = 8888


def proxy_container_name(net: str = DEFAULT_INTERNAL_NET) -> str:
    return f"egress-proxy-{net}"


def proxy_url(host: str = None, port: int = DEFAULT_PROXY_PORT) -> str:
    """HTTPS_PROXY value the tenant container uses. Host defaults to the proxy
    container's name, resolvable over the shared internal Docker network."""
    return f"http://{host or proxy_container_name()}:{port}"


# ── pure argv builders (unit-testable, no side effects) ─────────────────────

def create_internal_network_argv(name: str = DEFAULT_INTERNAL_NET) -> list:
    # --internal => no gateway to the host/outside; containers reach only peers.
    return ["docker", "network", "create", "--internal", name]


def create_external_network_argv(name: str = DEFAULT_EXTERNAL_NET) -> list:
    return ["docker", "network", "create", name]


def remove_network_argv(name: str) -> list:
    return ["docker", "network", "rm", name]


def build_proxy_run_argv(*, internal_net: str = DEFAULT_INTERNAL_NET,
                         external_net: str = DEFAULT_EXTERNAL_NET,
                         image: str = DEFAULT_PROXY_IMAGE,
                         port: int = DEFAULT_PROXY_PORT) -> list:
    """Run the allowlist proxy on the internal network (reachable by tenants) with
    a non-root, cap-dropped, read-only container. A second `docker network connect`
    (see ensure_egress) gives it the external leg."""
    name = proxy_container_name(internal_net)
    return [
        "docker", "run", "-d", "--name", name,
        "--network", internal_net,
        "--user", "10001:10001",
        "--read-only", "--tmpfs", "/tmp",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--restart", "unless-stopped",
        image,
    ]


def connect_external_argv(external_net: str = DEFAULT_EXTERNAL_NET,
                          internal_net: str = DEFAULT_INTERNAL_NET) -> list:
    return ["docker", "network", "connect", external_net,
            proxy_container_name(internal_net)]


# ── docker-gated execution ──────────────────────────────────────────────────

def _docker_available() -> bool:
    from shutil import which
    if not which("docker"):
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True,
                              timeout=15).returncode == 0
    except Exception:
        return False


def _run_ok(argv: list) -> bool:
    try:
        return subprocess.run(argv, capture_output=True, timeout=60).returncode == 0
    except Exception:
        return False


def ensure_egress(*, internal_net: str = DEFAULT_INTERNAL_NET,
                  external_net: str = DEFAULT_EXTERNAL_NET,
                  image: str = None) -> str:
    """Idempotently create the networks + start the allowlist proxy. Returns the
    HTTPS_PROXY url a tenant should use. Raises if Docker isn't available."""
    if not _docker_available():
        raise RuntimeError("docker unavailable — cannot provision the egress proxy")
    image = image or os.environ.get("AUTOAGENT_EGRESS_PROXY_IMAGE", DEFAULT_PROXY_IMAGE)
    # `docker network create` fails if it already exists — that's fine (idempotent).
    _run_ok(create_internal_network_argv(internal_net))
    _run_ok(create_external_network_argv(external_net))
    _run_ok(build_proxy_run_argv(internal_net=internal_net,
                                 external_net=external_net, image=image))
    _run_ok(connect_external_argv(external_net, internal_net))
    return proxy_url()
