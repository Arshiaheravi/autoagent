"""Lint guards for the agent sandbox image — hardening the image must not lose."""
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_DOCKERFILE = _ROOT / "deploy" / "Dockerfile.agent"
_DOCKERIGNORE = _ROOT / ".dockerignore"


@pytest.fixture(scope="module")
def dockerfile_text():
    if not _DOCKERFILE.exists():
        pytest.skip("agent Dockerfile not present")
    return _DOCKERFILE.read_text(encoding="utf-8")


def test_runs_as_non_root(dockerfile_text):
    assert "USER 10001" in dockerfile_text        # matches sandbox --user default


def test_base_image_is_pinned_not_latest(dockerfile_text):
    from_lines = [l for l in dockerfile_text.splitlines() if l.strip().startswith("FROM ")]
    assert from_lines, "no FROM line"
    for l in from_lines:
        assert ":" in l, f"unpinned base image: {l}"
        assert not l.strip().endswith(":latest"), f"floating :latest base: {l}"


def test_no_secret_baked_in(dockerfile_text):
    # Only instruction lines matter — a comment explaining runtime -e injection is
    # fine; a baked ENV/ARG value is not. Strip comments, then look for secrets.
    instr = "\n".join(l for l in dockerfile_text.splitlines()
                      if l.strip() and not l.strip().startswith("#")).lower()
    for needle in ("anthropic_api_key", "autoagent_vault_key", "sk-ant", "byok_anthropic"):
        assert needle not in instr, f"secret-ish token baked into image: {needle}"


def test_engine_dir_not_tenant_writable(dockerfile_text):
    # /opt/autoagent (engine on PYTHONPATH) must stay root-owned — a session must
    # not be able to rewrite the code it runs under.
    for line in dockerfile_text.splitlines():
        if "chown" in line:
            assert "/opt/autoagent" not in line, f"engine chowned to tenant: {line}"


def test_home_is_on_the_writable_volume(dockerfile_text):
    # Root FS is --read-only at run time, so HOME must live under /workspace.
    assert "HOME=/workspace" in dockerfile_text


def test_dockerignore_excludes_sensitive_paths():
    if not _DOCKERIGNORE.exists():
        pytest.skip(".dockerignore not present")
    text = _DOCKERIGNORE.read_text(encoding="utf-8")
    for needle in ("config.json", ".autoagent", "vault", ".git", "*.enc", "tenants.json"):
        assert needle in text, f".dockerignore missing exclusion: {needle}"
