#!/usr/bin/env python3
"""knowledge_db — SQLite FTS5 index over memory/knowledge.md RULE entries.

Markdown remains the source of truth (human-readable, append-only audit trail).
This module mirrors RULE entries into an FTS5-backed SQLite DB so the agent can
search 300+ rules by topic instead of reading the full markdown tail every session.

Public functions:
    rebuild()                      — parse knowledge.md → populate rules table
    search(query, limit=5)         — full-text search, returns list[dict]
    recent(limit=10)               — most-recently-appended rules
    append(rule_text, source="manual") — append to markdown AND DB
    ensure_fresh()                 — rebuild if markdown mtime > DB mtime

DB schema: memory/knowledge.db (FTS5 virtual table).
"""
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_MD = ROOT / "memory" / "knowledge.md"
KNOWLEDGE_DB = ROOT / "memory" / "knowledge.db"

RULE_RE = re.compile(
    r"^RULE:\s*(?:\[(?P<date>[^\]]+)\]\s*)?(?P<text>.+?)(?:\s*\(Source:\s*(?P<source>[^)]+)\))?\s*$"
)


def _conn() -> sqlite3.Connection:
    KNOWLEDGE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(KNOWLEDGE_DB))
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS rules USING fts5("
        "date, rule_text, source, added_at, "
        "tokenize = 'porter unicode61')"
    )
    return conn


def _parse_rules_md(text: str) -> list[dict]:
    out: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("RULE:"):
            continue
        m = RULE_RE.match(line)
        if not m:
            continue
        out.append({
            "date": (m.group("date") or "").strip(),
            "rule_text": m.group("text").strip(),
            "source": (m.group("source") or "").strip(),
        })
    return out


def rebuild() -> int:
    """Re-parse knowledge.md and replace the rules table. Returns row count."""
    if not KNOWLEDGE_MD.exists():
        return 0
    rules = _parse_rules_md(KNOWLEDGE_MD.read_text(encoding="utf-8"))
    conn = _conn()
    try:
        conn.execute("DELETE FROM rules")
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        conn.executemany(
            "INSERT INTO rules(date, rule_text, source, added_at) VALUES(?,?,?,?)",
            [(r["date"], r["rule_text"], r["source"], now) for r in rules],
        )
        conn.commit()
        return len(rules)
    finally:
        conn.close()


def ensure_fresh() -> None:
    """Rebuild DB if markdown is newer than DB."""
    if not KNOWLEDGE_MD.exists():
        return
    if not KNOWLEDGE_DB.exists():
        rebuild()
        return
    if KNOWLEDGE_MD.stat().st_mtime > KNOWLEDGE_DB.stat().st_mtime:
        rebuild()


def search(query: str, limit: int = 5) -> list[dict]:
    ensure_fresh()
    conn = _conn()
    try:
        escaped = query.replace('"', '""')
        fts_q = f'"{escaped}"'
        cur = conn.execute(
            "SELECT date, rule_text, source FROM rules "
            "WHERE rules MATCH ? ORDER BY rank LIMIT ?",
            (fts_q, limit),
        )
        return [
            {"date": r[0], "rule_text": r[1], "source": r[2]}
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def recent(limit: int = 10) -> list[dict]:
    ensure_fresh()
    conn = _conn()
    try:
        cur = conn.execute(
            "SELECT date, rule_text, source FROM rules "
            "ORDER BY rowid DESC LIMIT ?",
            (limit,),
        )
        return [
            {"date": r[0], "rule_text": r[1], "source": r[2]}
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def append(rule_text: str, source: str = "manual", date_str: Optional[str] = None) -> None:
    """Append to knowledge.md AND rules table. Preserves audit trail."""
    date_str = date_str or datetime.utcnow().strftime("%Y-%m-%d")
    md_line = f"RULE: [{date_str}] {rule_text.strip()}"
    if source:
        md_line += f" (Source: {source})"
    with KNOWLEDGE_MD.open("a", encoding="utf-8") as f:
        f.write("\n" + md_line + "\n")
    conn = _conn()
    try:
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        conn.execute(
            "INSERT INTO rules(date, rule_text, source, added_at) VALUES(?,?,?,?)",
            (date_str, rule_text.strip(), source, now),
        )
        conn.commit()
    finally:
        conn.close()


def _format_hits(hits: list[dict]) -> str:
    if not hits:
        return "(no matches)"
    lines = []
    for h in hits:
        src = f" (Source: {h['source']})" if h["source"] else ""
        d = f"[{h['date']}] " if h["date"] else ""
        lines.append(f"- {d}{h['rule_text']}{src}")
    return "\n".join(lines)


def _cli():
    import argparse
    p = argparse.ArgumentParser(description="knowledge_db CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("search"); sp.add_argument("query"); sp.add_argument("--limit", type=int, default=5)
    sp = sub.add_parser("recent"); sp.add_argument("--limit", type=int, default=10)
    sp = sub.add_parser("add"); sp.add_argument("rule_text"); sp.add_argument("--source", default="manual")
    sub.add_parser("rebuild")
    sub.add_parser("count")
    args = p.parse_args()
    if args.cmd == "search":
        print(_format_hits(search(args.query, args.limit)))
    elif args.cmd == "recent":
        print(_format_hits(recent(args.limit)))
    elif args.cmd == "add":
        append(args.rule_text, source=args.source)
        print("appended")
    elif args.cmd == "rebuild":
        n = rebuild()
        print(f"indexed {n} rules")
    elif args.cmd == "count":
        ensure_fresh()
        conn = _conn()
        try:
            n = conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
        finally:
            conn.close()
        print(n)


if __name__ == "__main__":
    _cli()
