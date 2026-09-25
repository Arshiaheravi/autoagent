#!/usr/bin/env python3
"""Tenant — the isolation unit for multi-tenant deployments.

Single source of truth for *which* tenant this process serves and *where* its
data lives. Everything that today hardcodes ``~/.autoagent`` (the filesystem
root and the control DB) derives from a Tenant instead, so the same engine runs
unchanged whether it's:

  - single-tenant (the default): one implicit ``default`` tenant whose data_root
    is ``~/.autoagent`` — identical to today's behaviour.
  - self-serve (Fork A: container-per-tenant): one Tenant per customer. The
    container just sets ``AUTOAGENT_TENANT_ID`` + ``AUTOAGENT_HOME`` (its mounted
    volume) and the whole engine scopes to that tenant automatically.

``tenant_id`` is the scoping key for shared control-plane rows once the control
DB moves to Postgres + RLS (Fork B). ``data_root`` is the per-tenant filesystem
boundary the container volume provides.
"""
import os
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TENANT_ID = "default"

# A tenant_id is used in filesystem paths, container names, and DB scoping, so it
# must be tightly constrained — no path traversal, no shell/Docker metacharacters.
# Start alphanumeric, then [a-z0-9_-], max 64. This is the SSoT for the rule.
_TENANT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


def is_valid_tenant_id(tenant_id) -> bool:
    return isinstance(tenant_id, str) and bool(_TENANT_ID_RE.match(tenant_id))


def require_valid_tenant_id(tenant_id) -> str:
    if not is_valid_tenant_id(tenant_id):
        raise ValueError(f"invalid tenant_id: {tenant_id!r} "
                         "(must match ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$)")
    return tenant_id

# Env vars that select the tenant. AUTOAGENT_HOME already exists (registry has
# always honoured it); AUTOAGENT_TENANT_ID is new and defaults to "default" so
# nothing changes for single-tenant installs.
ENV_TENANT_ID = "AUTOAGENT_TENANT_ID"
ENV_DATA_ROOT = "AUTOAGENT_HOME"


def _default_data_root() -> Path:
    return Path(os.environ.get(ENV_DATA_ROOT, Path.home() / ".autoagent"))


@dataclass(frozen=True)
class Tenant:
    """One isolated tenant: an id + the filesystem root that holds its state."""
    tenant_id: str
    data_root: Path

    @property
    def db_path(self) -> Path:
        """Control DB for this tenant (SQLite today, one Postgres row-scope later)."""
        return self.data_root / "agency.db"

    @property
    def projects_dir(self) -> Path:
        return self.data_root / "projects"

    @classmethod
    def default(cls) -> "Tenant":
        """The implicit single-tenant install rooted at ~/.autoagent."""
        return cls(DEFAULT_TENANT_ID, _default_data_root())


def current_tenant() -> Tenant:
    """The tenant this process serves, resolved from the environment.

    Back-compat: with neither env var set, this is the single ``default`` tenant
    at ``~/.autoagent`` — exactly today's layout. A per-tenant container overrides
    both env vars at launch; nothing else in the engine needs to know.
    """
    return Tenant(
        tenant_id=os.environ.get(ENV_TENANT_ID, DEFAULT_TENANT_ID),
        data_root=_default_data_root(),
    )
