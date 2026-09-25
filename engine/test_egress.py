"""Egress gate — allowlist-proxy plumbing + a real-Docker network-isolation proof.

The load-bearing guarantee is that a tenant on a Docker --internal network has NO
route off-host (metadata / control plane / internet all unreachable). That is
proven against real Docker by contrast: the same TCP probe succeeds on bridge and
fails on --internal. Skips when Docker or outbound connectivity is unavailable.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

import egress
import sandbox

_ROOT = Path(__file__).resolve().parent.parent
TEST_IMAGE = "kalilinux/kali-rolling:latest"
TEST_NET = "aa-egress-proof-net"


# ── unit: argv builders + proxy url ─────────────────────────────────────────

def test_internal_network_argv_is_internal():
    assert egress.create_internal_network_argv("n") == \
        ["docker", "network", "create", "--internal", "n"]


def test_proxy_url_default_targets_proxy_container():
    assert egress.proxy_url() == f"http://{egress.proxy_container_name()}:8888"


def test_proxy_run_argv_is_hardened():
    argv = egress.build_proxy_run_argv(internal_net="n", image="img:1")
    s = " ".join(argv)
    for flag in ("--network n", "--user 10001:10001", "--read-only",
                 "--cap-drop ALL", "--security-opt no-new-privileges"):
        assert flag in s
    assert argv[-1] == "img:1"


def test_connect_external_argv():
    assert egress.connect_external_argv("ext", "int") == \
        ["docker", "network", "connect", "ext", egress.proxy_container_name("int")]


# ── unit: sandbox routes tenant egress through the proxy ─────────────────────

def test_sandbox_injects_proxy_env_when_set():
    spec = sandbox.SandboxSpec(image="a:1", volume="/v", tenant_id="acme",
                               proxy_url="http://egress:8888")
    argv = sandbox.ContainerRunner(spec).build_docker_argv(["claude"], {})
    joined = " ".join(argv)
    assert "-e HTTPS_PROXY=http://egress:8888" in joined
    assert "-e NO_PROXY=localhost,127.0.0.1" in joined


def test_sandbox_no_proxy_env_by_default():
    spec = sandbox.SandboxSpec(image="a:1", volume="/v", tenant_id="acme")
    joined = " ".join(sandbox.ContainerRunner(spec).build_docker_argv(["claude"], {}))
    assert "HTTPS_PROXY" not in joined


# ── unit: proxy image is default-deny + non-root ────────────────────────────

def test_proxy_config_is_default_deny():
    conf = (_ROOT / "deploy" / "egress-proxy" / "tinyproxy.conf").read_text()
    assert "FilterDefaultDeny Yes" in conf
    assert "ConnectPort 443" in conf          # no arbitrary-port CONNECT
    assert 'Filter "/etc/tinyproxy/filter"' in conf


def test_proxy_filter_allows_only_anthropic():
    flt = (_ROOT / "deploy" / "egress-proxy" / "filter").read_text().strip().splitlines()
    assert flt == [r"^api\.anthropic\.com$"]


def test_proxy_image_runs_non_root():
    df = (_ROOT / "deploy" / "egress-proxy" / "Dockerfile").read_text()
    assert "USER 10001" in df


# ── integration: prove --internal removes off-host egress ───────────────────

def _docker_ready() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        r = subprocess.run(["docker", "image", "inspect", TEST_IMAGE],
                           capture_output=True, timeout=20)
        return r.returncode == 0
    except Exception:
        return False


def _tcp_probe(network: str | None) -> str:
    """Try to open a TCP connection to 1.1.1.1:443 from a container. Returns the
    probe's stdout ('OPEN'/'CLOSED')."""
    net = ["--network", network] if network else []
    argv = ["docker", "run", "--rm", *net, TEST_IMAGE, "bash", "-c",
            "timeout 8 bash -c 'echo > /dev/tcp/1.1.1.1/443' 2>/dev/null && echo OPEN || echo CLOSED"]
    r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    return r.stdout.strip()


@pytest.mark.skipif(not _docker_ready(), reason="docker or probe image unavailable")
def test_internal_network_blocks_offhost_egress():
    # Baseline: on bridge the probe reaches the internet. If it can't (no outbound
    # in this environment), we can't prove the contrast — skip.
    if _tcp_probe(None) != "OPEN":
        pytest.skip("no outbound connectivity on bridge; cannot prove isolation contrast")
    subprocess.run(egress.create_internal_network_argv(TEST_NET),
                   capture_output=True, timeout=30)
    try:
        internal = _tcp_probe(TEST_NET)
    finally:
        subprocess.run(egress.remove_network_argv(TEST_NET),
                       capture_output=True, timeout=30)
    assert internal == "CLOSED", f"--internal network still reached the internet: {internal}"
