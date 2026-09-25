"""Python PEP puller — STUB.

Source: https://peps.python.org/
Each PEP has structured Abstract + Motivation + Rationale + Decision.
Accepted PEPs = HIGH confidence, Withdrawn/Rejected = LOW.

Tag rows with platform="pep".
"""

PEPS_URL = "https://peps.python.org/"


def pull(out_path: str, *, limit: int | None = None, **kwargs) -> int:
    raise NotImplementedError(
        f"pull_pep stub — implement against {PEPS_URL}. "
        "Use the JSON index at https://peps.python.org/api/peps.json")


__all__ = ["pull", "PEPS_URL"]
