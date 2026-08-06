"""Charge les posts /pol/ scrapés (4TCT) dans une base SQLite.

Idempotent : relancer le script ajoute uniquement les nouveaux posts/citations,
les existants sont ignorés (pas de doublon). Lit directement les JSON bruts de
4TCT, aucune conversion préalable nécessaire.

    python3 build_db.py                 # ajoute tout data/saves -> pol.db
    python3 build_db.py --db autre.db   # cible une autre base
"""
import json
import sqlite3
import argparse
from pathlib import Path

import warnings
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
import html as html_mod
import re

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

from source_classifier import extract_domains, classify_source, URL_REGEX
from topic_source_matrix import classify_topic

SAVES_DIR = Path("4TCT/data/saves")

SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    thread_no     INTEGER PRIMARY KEY,
    board         TEXT NOT NULL DEFAULT 'pol',
    semantic_url  TEXT,
    subject       TEXT,
    topic         TEXT,
    capture_date  TEXT,
    replies       INTEGER,
    images        INTEGER
);
CREATE TABLE IF NOT EXISTS posts (
    post_no       INTEGER PRIMARY KEY,
    thread_no     INTEGER REFERENCES threads(thread_no),
    resto         INTEGER,
    time          INTEGER,
    country       TEXT,
    com_html      TEXT,
    com_text      TEXT,
    capture_date  TEXT
);
CREATE TABLE IF NOT EXISTS domains (
    domain    TEXT PRIMARY KEY,
    category  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS citations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    post_no     INTEGER REFERENCES posts(post_no),
    domain      TEXT REFERENCES domains(domain),
    url         TEXT,
    compound    REAL,
    neg_score   REAL,
    neu_score   REAL,
    pos_score   REAL,
    UNIQUE(post_no, domain)
);
CREATE INDEX IF NOT EXISTS idx_cit_domain   ON citations(domain);
CREATE INDEX IF NOT EXISTS idx_cit_post     ON citations(post_no);
CREATE INDEX IF NOT EXISTS idx_posts_thread ON posts(thread_no);
CREATE INDEX IF NOT EXISTS idx_dom_category ON domains(category);
"""


def clean_text(raw_html: str) -> str:
    text = BeautifulSoup(raw_html or "", "html.parser").get_text(separator=" ")
    text = html_mod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def first_url_for_domain(com_html: str, target: str) -> str:
    """Retrouve l'URL brute correspondant à un domaine normalisé."""
    for m in URL_REGEX.finditer(com_html.replace("<wbr>", "")):
        from source_classifier import normalize_domain
        if normalize_domain(m.group(0)) == target:
            return m.group(0)
    return ""


def iter_threads(saves_dir: Path):
    for day_dir in sorted(saves_dir.iterdir()):
        pol = day_dir / "threads" / "pol"
        if not pol.is_dir():
            continue
        for jf in sorted(pol.glob("*.json")):
            try:
                data = json.load(open(jf))
            except Exception:
                continue
            posts = data if isinstance(data, list) else data.get("posts", [])
            if posts:
                yield day_dir.name, posts


def build(db_path: str, saves_dir: Path):
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    cur = conn.cursor()

    n_threads = n_posts = n_citations = 0
    before = cur.execute("SELECT COUNT(*) FROM posts").fetchone()[0]

    for capture_date, posts in iter_threads(saves_dir):
        op = posts[0]
        thread_no = op.get("no")
        # Thread : topic depuis semantic_url + sub de l'OP
        op_text = f"{op.get('semantic_url','') or ''} {op.get('sub','') or ''}".strip()
        cur.execute(
            """INSERT OR IGNORE INTO threads
               (thread_no, semantic_url, subject, topic, capture_date, replies, images)
               VALUES (?,?,?,?,?,?,?)""",
            (thread_no, op.get("semantic_url"), op.get("sub"),
             classify_topic(op_text) if op_text else "Other / Misc",
             capture_date, op.get("replies"), op.get("images")),
        )
        n_threads += cur.rowcount

        for post in posts:
            post_no = post.get("no")
            com = post.get("com", "") or ""
            cur.execute(
                """INSERT OR IGNORE INTO posts
                   (post_no, thread_no, resto, time, country, com_html, com_text, capture_date)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (post_no, thread_no, post.get("resto"), post.get("time"),
                 post.get("country"), com, clean_text(com), capture_date),
            )
            n_posts += cur.rowcount

            for domain in extract_domains(com):
                cur.execute("INSERT OR IGNORE INTO domains (domain, category) VALUES (?,?)",
                            (domain, classify_source(domain)))
                cur.execute(
                    "INSERT OR IGNORE INTO citations (post_no, domain, url) VALUES (?,?,?)",
                    (post_no, domain, first_url_for_domain(com, domain)),
                )
                n_citations += cur.rowcount

    conn.commit()
    after = cur.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    total_cit = cur.execute("SELECT COUNT(*) FROM citations").fetchone()[0]
    total_thr = cur.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
    conn.close()

    print(f"Base : {db_path}")
    print(f"  + {n_threads} nouveaux threads, + {n_posts} nouveaux posts, + {n_citations} nouvelles citations")
    print(f"  Totaux : {total_thr} threads, {after} posts (avant : {before}), {total_cit} citations")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Charge les posts /pol/ scrapés dans SQLite (idempotent)")
    ap.add_argument("--db", default="pol.db", help="Fichier SQLite (défaut : pol.db)")
    ap.add_argument("--saves", default=str(SAVES_DIR), help="Répertoire 4TCT/data/saves")
    args = ap.parse_args()
    build(args.db, Path(args.saves))
