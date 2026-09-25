"""Sandbox runner (Fork A) — unit contract + a real-container isolation proof.

Unit tests need no Docker. The integration test actually launches a container and
proves a tenant session can't see the host or cross the env boundary; it skips
when Docker or the probe image is unavailable.
"""
import os
import shutil
import subprocess
import types

import pytest

import sandbox
from sandbox import ContainerRunner, LocalRunner, SandboxSpec, get_runner


def _ctx(config):
    return types.SimpleNamespace(config=config, name="proj")


# ── unit: runner selection ──────────────────────────────────────────────────

def test_default_is_local_runner():
    assert isinstance(get_runner(_ctx({})), LocalRunner)
    assert isinstance(get_runner(_ctx({"sandbox": "host"})), LocalRunner)


def test_container_requires_image(monkeypatch):
    monkeypatch.delenv("AUTOAGENT_SANDBOX_IMAGE", raising=False)
    with pytest.raises(RuntimeError):
        get_runner(_ctx({"sandbox": "container"}))


def test_container_runner_selected_with_image(monkeypatch):
    monkeypatch.setenv("AUTOAGENT_TENANT_ID", "acme")
    r = get_runner(_ctx({"sandbox": "container", "sandbox_image": "img:1"}))
    assert isinstance(r, ContainerRunner)
    assert r.spec.image == "img:1"
    assert r.spec.tenant_id == "acme"


# ── unit: local runner is byte-identical to today ───────────────────────────

def test_local_runner_is_passthrough():
    argv = ["claude", "-p", "hi"]
    out_argv, kwargs = LocalRunner().wrap(argv, "/repo", {"ANTHROPIC_API_KEY": "k"})
    assert out_argv == argv
    assert kwargs == {"cwd": "/repo", "env": {"ANTHROPIC_API_KEY": "k"}}


# ── unit: container argv + env whitelist ────────────────────────────────────

def test_docker_argv_has_isolation_flags():
    spec = SandboxSpec(image="agent:1", volume="/vol", tenant_id="acme")
    argv = ContainerRunner(spec).build_docker_argv(["claude", "-p", "x"], {})
    s = " ".join(argv)
    for flag in ("--read-only", "--cap-drop ALL", "--security-opt no-new-privileges",
                 "--pids-limit 512", "--user 10001:10001", "--memory 2g", "--cpus 2"):
        assert flag in s
    assert "-v /vol:/workspace" in s
    assert "-w /workspace" in s
    # image precedes the inner command, which is appended last
    assert argv.index("agent:1") < argv.index("claude")
    assert argv[-3:] == ["claude", "-p", "x"]


def test_env_whitelist_blocks_host_leak():
    spec = SandboxSpec(image="agent:1", volume="/vol", tenant_id="acme")
    argv = ContainerRunner(spec).build_docker_argv(
        ["claude"],
        {"ANTHROPIC_API_KEY": "sekret", "AWS_SECRET_ACCESS_KEY": "leak", "PATH": "/x"},
    )
    joined = " ".join(argv)
    assert "-e ANTHROPIC_API_KEY" in joined   # forwarded by NAME
    assert "sekret" not in joined             # secret VALUE never in argv/process table
    assert "AWS_SECRET_ACCESS_KEY" not in joined   # non-whitelisted never crosses
    assert "leak" not in joined
    assert "-e AUTOAGENT_TENANT_ID=acme" in joined
    assert "-e AUTOAGENT_HOME=/workspace/.autoagent" in joined


def test_secret_value_leaves_argv_for_cli_env():
    spec = SandboxSpec(image="agent:1", volume="/vol")
    argv, kwargs = ContainerRunner(spec).wrap(["claude"], "/host/repo",
                                              {"ANTHROPIC_API_KEY": "sk-distinct-val"})
    assert kwargs["cwd"] is None
    assert "sk-distinct-val" not in " ".join(argv)              # value not in argv
    assert kwargs["env"]["ANTHROPIC_API_KEY"] == "sk-distinct-val"  # handed to docker CLI env
    assert argv[0:2] == ["docker", "run"]


# ── integration: prove isolation against a real container ───────────────────

TEST_IMAGE = os.environ.get("AUTOAGENT_SANDBOX_TEST_IMAGE", "kalilinux/kali-rolling:latest")


def _docker_ready(image: str) -> bool:
    if not shutil.which("docker"):
        return False
    try:
        r = subprocess.run(["docker", "image", "inspect", image],
                            capture_output=True, timeout=20)
        return r.returncode == 0
    except Exception:
        return False


@pytest.mark.skipif(not _docker_ready(TEST_IMAGE),
                    reason=f"docker or probe image {TEST_IMAGE} unavailable")
def test_container_cannot_see_host_or_cross_env(tmp_path):
    vol = tmp_path / "tenant_vol"
    vol.mkdir()
    (vol / "marker.txt").write_text("OWN_VOLUME")
    host_secret = tmp_path / "HOST_SECRET.txt"
    host_secret.write_text("host-only")

    spec = SandboxSpec(image=TEST_IMAGE, volume=str(vol), tenant_id="acme",
                       network="none", entrypoint="sh")
    probe = (
        'echo UID=$(id -u); '
        'echo KEY=$ANTHROPIC_API_KEY; '
        'echo LEAK=${LEAK_TEST:-NONE}; '
        'echo TENANT=$AUTOAGENT_TENANT_ID; '
        '(cat /workspace/marker.txt >/dev/null 2>&1 && echo MARK_OK || echo MARK_FAIL); '
        f'(cat {host_secret} >/dev/null 2>&1 && echo LEAKED_HOST || echo NO_HOST)'
    )
    child_env = {"ANTHROPIC_API_KEY": "sekret", "LEAK_TEST": "shouldnotcross"}
    argv, kwargs = ContainerRunner(spec).wrap(["-c", probe], "/ignored", child_env)
    # The secret rides the docker CLI env (kwargs["env"]), not argv.
    assert "sekret" not in " ".join(argv)
    r = subprocess.run(argv, capture_output=True, text=True, timeout=90, env=kwargs["env"])
    out = r.stdout
    assert "UID=10001" in out, out          # non-root
    assert "KEY=sekret" in out, out         # whitelisted key injected
    assert "LEAK=NONE" in out, out          # host env did NOT cross
    assert "TENANT=acme" in out, out        # tenant var set inside sandbox
    assert "MARK_OK" in out, out            # can read its own volume
    assert "NO_HOST" in out, out            # cannot read a host-only file by abspath
    assert "LEAKED_HOST" not in out, out
