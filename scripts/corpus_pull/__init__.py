"""Per-source adapters that pull external decision corpora and emit
canonical-schema JSON for `scripts/ingest_council_corpus.py`.

Each adapter exposes:

    def pull(out_path: str, *, limit: int | None = None, **kwargs) -> int:
        '''Fetch from the source, normalize, write canonical-schema JSON.
        Return row count written.'''

Stubs raise NotImplementedError with the source URL in the message.
"""

__all__ = [
    "pull_adrs",
    "pull_anthropic_agents",
    "pull_tc39",
    "pull_pep",
    "pull_rust_rfcs",
    "pull_jep",
    "pull_postmortems",
]
