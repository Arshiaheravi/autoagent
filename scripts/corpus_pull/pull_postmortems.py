"""Post-mortem library puller — STUB.

Source: https://github.com/danluu/post-mortems
Curated index of ~2k high-quality public post-mortems. Each link
points to the original company's incident write-up.

For council corpus: post-mortems become synthetic "verdicts" where
  - question  = "what went wrong with X?"
  - synthesis = root cause + remediation
  - winner    = the fix that worked
  - confidence = HIGH (post-mortems are post-hoc; outcomes are real)

Tag rows with platform="postmortems".
"""

POSTMORTEMS_INDEX_URL = "https://github.com/danluu/post-mortems"


def pull(out_path: str, *, limit: int | None = None, **kwargs) -> int:
    raise NotImplementedError(
        f"pull_postmortems stub — implement against {POSTMORTEMS_INDEX_URL}. "
        "Two-stage: parse README.md for links, then scrape each linked "
        "incident page.")


__all__ = ["pull", "POSTMORTEMS_INDEX_URL"]
