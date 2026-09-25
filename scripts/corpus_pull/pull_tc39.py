"""TC39 (JavaScript) RFC / proposal puller — STUB.

Source: https://github.com/tc39/proposals
Each stage-3/4 proposal has a README.md with motivation + design.
Stage-0/1/2 rejected proposals also valuable (negative signal).

Tag rows with platform="tc39".
"""

TC39_URL = "https://github.com/tc39/proposals"


def pull(out_path: str, *, limit: int | None = None, **kwargs) -> int:
    raise NotImplementedError(
        f"pull_tc39 stub — implement against {TC39_URL}. "
        "Each proposal dir has a README.md with rationale.")


__all__ = ["pull", "TC39_URL"]
