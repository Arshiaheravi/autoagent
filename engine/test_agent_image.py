"""End-to-end smoke test of the built agent image through the real ContainerRunner.

Verifies the full execution path a tenant session takes: the image runs the claude
CLI as a non-root user, the engine is importable (hooks resolve), the engine code
is NOT tenant-writable, and the mounted volume IS writable.

Requires the image to be built first:
    docker build -f deploy/Dockerfile.agent -t autoagent-agent:smoke .
Skips cleanly when Docker or the image is unavailable.
"""
import os
import shutil
import subprocess
import tempfile

import pytest

import sandbox

IMAGE = os.environ.get("AUTOAGENT_AGENT_IMAGE", "autoagent-agent:smoke")


def _image_ready() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "image", "inspect", IMAGE],
                              capture_output=True, timeout=20).returncode == 0
    except Exception:
        return False


@pytest.mark.skipif(not _image_ready(),
                    reason=f"agent image {IMAGE} not built (see module docstring)")
def test_agent_image_runs_a_confined_session():
    vol = tempfile.mkdtemp()
    try:
        probe = (
            'echo UID=$(id -u); '
            'claude --version >/dev/null 2>&1 && echo CLAUDE_OK || echo CLAUDE_FAIL; '
            'python3 -c "import tenant; print(\'ENGINE_OK\')" 2>&1 | tail -1; '
            '(echo x > /opt/autoagent/engine/hack 2>/dev/null && echo ENGINE_WRITABLE || echo ENGINE_READONLY); '
            '(echo w > /workspace/w.txt 2>/dev/null && echo WORKSPACE_WRITABLE || echo WORKSPACE_RO)'
        )
        spec = sandbox.SandboxSpec(image=IMAGE, volume=vol, tenant_id="smoke",
                                   network="none", entrypoint="sh")
        argv, kwargs = sandbox.ContainerRunner(spec).wrap(
            ["-c", probe], "/ignored", {"ANTHROPIC_API_KEY": "x"})
        out = subprocess.run(argv, capture_output=True, text=True,
                             timeout=120, env=kwargs["env"]).stdout
        assert "UID=10001" in out, out            # non-root
        assert "CLAUDE_OK" in out, out            # claude CLI present + runs
        assert "ENGINE_OK" in out, out            # engine importable via PYTHONPATH
        assert "ENGINE_READONLY" in out, out      # session can't rewrite engine
        assert "WORKSPACE_WRITABLE" in out, out   # tenant volume writable
    finally:
        shutil.rmtree(vol, ignore_errors=True)
