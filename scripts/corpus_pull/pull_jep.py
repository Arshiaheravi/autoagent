"""Java JEP (JDK Enhancement Proposal) puller — STUB.

Source: https://openjdk.org/jeps/
Each JEP has Goal + Non-Goals + Motivation + Description.

Tag rows with platform="jep".
"""

JEPS_URL = "https://openjdk.org/jeps/"


def pull(out_path: str, *, limit: int | None = None, **kwargs) -> int:
    raise NotImplementedError(
        f"pull_jep stub — implement against {JEPS_URL}. "
        "Index page lists all JEPs by number — scrape each.")


__all__ = ["pull", "JEPS_URL"]
