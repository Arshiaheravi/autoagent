#!/usr/bin/env python3
"""Session execution sandbox (Fork A: container-per-tenant).

A tenant's session runs ``claude -p`` which executes bash, writes files, and runs
git in the tenant's workspace — arbitrary code execution. On shared self-serve
infra that MUST be confined so a tenant's session can never touch the host or
another tenant's volume. This module is the seam: the engine's one spawn site
hands a runner the ``(argv, cwd, env)`` it would have Popen'd, and the runner
returns the argv + Popen kwargs to actually launch.

- ``LocalRunner`` — today's behaviour, byte-identical: run on the host. The
  single-tenant default; nothing changes unless a tenant opts into a sandbox.
- ``ContainerRunner`` — wrap the command in ``docker run`` with the tenant's
  volume mounted, only whitelisted env injected (BYOK key), a non-root user,
  read-only root FS, dropped caps, and memory/cpu/pid limits.

Fork A is container-*per-tenant* (one long-lived container + volume); production
will ``docker exec`` into that container. ``docker run --rm`` here is the same
isolation contract with an ephemeral container — the security flags are what
matter, and they are identical either way.
"""
import os
from dataclasses import dataclass, field
from typing import Optional

# Env vars allowed to cross into the sandbox from the host child-env. Everything
# else (the operator's shell, other tenants' anything) is left at the boundary.
DEFAULT_ENV_WHITELIST = ("ANTHROPIC_API_KEY",)

DEFAULT_WORKDIR = "/workspace"
DEFAULT_MEMORY = "2g"
DEFAULT_CPUS = "2"
DEFAULT_PIDS_LIMIT = 512
DEFAULT_USER = "10001:10001"     # non-root; never run a tenant session as root
# Sessions need the Anthropic API, so the default is bridge egress. WARNING: bare
# bridge lets a tenant's session code reach cloud metadata (169.254.169.254 → IAM
# creds), the Postgres control plane, and sibling containers. Untrusted signups
# are NOT safe on bridge — before opening self-serve, route API traffic through an
# allowlisted egress proxy (or a dedicated network that blocks link-local +
# RFC1918 + the control-plane range) and set network to that. This is a launch
# gate tracked in docs/SELF_SERVE_ISOLATION_ARCHITECTURE.md, not a code toggle.
DEFAULT_NETWORK = "bridge"


@dataclass
class SandboxSpec:
    """Everything the container runner needs to confine one tenant's session."""
    image: str
    volume: str                       # docker named volume OR host path -> workdir
    tenant_id: str = "default"
    workdir: str = DEFAULT_WORKDIR
    memory: str = DEFAULT_MEMORY
    cpus: str = DEFAULT_CPUS
    pids_limit: int = DEFAULT_PIDS_LIMIT
    user: str = DEFAULT_USER
    network: str = DEFAULT_NETWORK
    env_whitelist: tuple = DEFAULT_ENV_WHITELIST
    entrypoint: Optional[str] = None  # override image entrypoint when needed
    extra_run_args: list = field(default_factory=list)
    proxy_url: Optional[str] = None   # untrusted tenants egress ONLY via this proxy
    no_proxy: str = "localhost,127.0.0.1"


class LocalRunner:
    """Run the session directly on the host — the single-tenant default."""

    def wrap(self, argv: list, cwd: str, env: dict):
        return list(argv), {"cwd": cwd, "env": env}


class ContainerRunner:
    """Run the session inside the tenant's container (Fork A)."""

    def __init__(self, spec: SandboxSpec):
        self.spec = spec

    def _nonsecret_env(self) -> dict:
        """Non-secret tenant vars the engine needs INSIDE the sandbox (pointing at
        the mounted volume). Safe to place inline in argv."""
        s = self.spec
        env = {
            "AUTOAGENT_TENANT_ID": s.tenant_id,
            "AUTOAGENT_HOME": f"{s.workdir}/.autoagent",
        }
        if s.proxy_url:
            # Force all egress through the allowlist proxy. On an --internal network
            # there's no other route out anyway; these make the CLI use the proxy.
            for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
                env[k] = s.proxy_url
            env["NO_PROXY"] = s.no_proxy
            env["no_proxy"] = s.no_proxy
        return env

    def _secret_env(self, env: dict) -> dict:
        """The whitelisted SECRET values (e.g. the BYOK key). These must never
        appear in argv (the host process table); they ride the docker CLI's own
        environment and are forwarded name-only."""
        return {k: env[k] for k in self.spec.env_whitelist
                if k in env and env[k] is not None}

    def build_docker_argv(self, argv: list, env: dict) -> list:
        s = self.spec
        docker = [
            "docker", "run", "--rm", "-i",
            "--network", s.network,
            "--memory", s.memory,
            "--cpus", s.cpus,
            "--pids-limit", str(s.pids_limit),
            "--user", s.user,
            "--read-only",                      # root FS immutable; writes go to the volume
            "--tmpfs", "/tmp",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "-v", f"{s.volume}:{s.workdir}",
            "-w", s.workdir,
        ]
        for k, v in self._nonsecret_env().items():
            docker += ["-e", f"{k}={v}"]        # non-secret: inline is fine
        for k in self._secret_env(env):
            docker += ["-e", k]                 # name-only: value comes from CLI env
        if s.entrypoint is not None:
            docker += ["--entrypoint", s.entrypoint]
        docker += list(s.extra_run_args)
        docker.append(s.image)
        docker += list(argv)
        return docker

    def wrap(self, argv: list, cwd: str, env: dict):
        # cwd is irrelevant on the host (the container's -w sets the working dir).
        # The container env is ONLY what -e forwards. Secret values are passed to
        # the docker CLI via its environment (so name-only `-e KEY` forwards them)
        # rather than argv, keeping them out of the host process table.
        cli_env = {**os.environ, **self._secret_env(env)}
        return self.build_docker_argv(argv, env), {"cwd": None, "env": cli_env}


def get_runner(ctx):
    """Select the runner for a project/tenant from its config.

    ``config["sandbox"] == "container"`` opts into Fork A; anything else (the
    default) stays on the host. Kept deliberately explicit so a misconfig fails
    to a *more* isolated state is impossible — you never get a container by
    accident, and you never lose the host default silently.
    """
    cfg = getattr(ctx, "config", {}) or {}
    if cfg.get("sandbox") != "container":
        return LocalRunner()
    image = cfg.get("sandbox_image") or os.environ.get("AUTOAGENT_SANDBOX_IMAGE")
    if not image:
        raise RuntimeError(
            "sandbox=container requires 'sandbox_image' in config or "
            "AUTOAGENT_SANDBOX_IMAGE — refusing to launch an unconfigured sandbox."
        )
    from tenant import current_tenant
    t = current_tenant()
    volume = cfg.get("sandbox_volume") or str(t.data_root)
    spec = SandboxSpec(
        image=image,
        volume=volume,
        tenant_id=t.tenant_id,
        memory=str(cfg.get("sandbox_memory", DEFAULT_MEMORY)),
        cpus=str(cfg.get("sandbox_cpus", DEFAULT_CPUS)),
        pids_limit=int(cfg.get("sandbox_pids_limit", DEFAULT_PIDS_LIMIT)),
        network=cfg.get("sandbox_network", DEFAULT_NETWORK),
        proxy_url=cfg.get("sandbox_proxy_url"),
    )
    return ContainerRunner(spec)
