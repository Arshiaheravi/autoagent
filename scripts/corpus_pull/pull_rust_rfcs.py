"""Rust RFC puller — STUB.

Source: https://github.com/rust-lang/rfcs
Accepted RFCs in /text/, rejected in PR-closed history.
Both shapes are valuable (positive + negative signal).

Tag rows with platform="rust-rfc".
"""

RUST_RFCS_URL = "https://github.com/rust-lang/rfcs"


def pull(out_path: str, *, limit: int | None = None, **kwargs) -> int:
    raise NotImplementedError(
        f"pull_rust_rfcs stub — implement against {RUST_RFCS_URL}. "
        "Accepted RFCs live in text/; rejected ones in closed PRs.")


__all__ = ["pull", "RUST_RFCS_URL"]
