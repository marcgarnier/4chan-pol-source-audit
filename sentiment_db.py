"""Calcule le sentiment RoBERTa des posts citant une source et l'écrit dans pol.db.

`build_db.py` charge les citations mais laisse les colonnes de sentiment vides ;
`pipeline.py` calcule le sentiment mais n'écrit que des CSV/JSON. Les deux voies
n'étaient pas raccordées : ce script comble le trou en remplissant
`citations.compound / neg_score / neu_score / pos_score`.

Le sentiment est celui du **post citant**, pas de la page citée — c'est la
mesure définie dans METHODOLOGY.md. Un post citant plusieurs domaines donne donc
la même valeur à chacune de ses citations, et le texte n'est analysé qu'une fois.

Idempotent et reprenable : seules les lignes encore NULL sont traitées, et la
base est commitée par lots — une interruption ne perd que le lot en cours.

    python sentiment_db.py                  # complète les citations manquantes
    python sentiment_db.py --recompute      # recalcule tout
    python sentiment_db.py --limit 200      # essai rapide
"""
import argparse
import sqlite3

from tqdm import tqdm

from pipeline import SentimentAnalyzer

DEFAULT_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"


def pending_posts(conn, recompute: bool = False, limit: int | None = None):
    """Posts citant au moins une source dont le sentiment reste à calculer.

    Un post cité plusieurs fois (plusieurs domaines) n'apparaît qu'une fois :
    inutile de repasser le même texte dans le modèle.
    """
    where = "" if recompute else "WHERE c.compound IS NULL"
    sql = f"""
        SELECT DISTINCT p.post_no, p.com_text
        FROM citations c
        JOIN posts p ON p.post_no = c.post_no
        {where}
        ORDER BY p.post_no
    """
    params = ()
    if limit:
        sql += " LIMIT ?"
        params = (limit,)
    return conn.execute(sql, params).fetchall()


def coverage(conn) -> tuple[int, int]:
    """(citations avec sentiment, total citations)."""
    return conn.execute("SELECT COUNT(compound), COUNT(*) FROM citations").fetchone()


def run(db_path: str, batch_size: int, commit_every: int,
        recompute: bool, limit: int | None, model: str):
    conn = sqlite3.connect(db_path)

    filled_before, total = coverage(conn)
    rows = pending_posts(conn, recompute, limit)
    if not rows:
        print(f"Rien à faire : {filled_before}/{total} citations ont déjà un sentiment.")
        conn.close()
        return

    print(f"Base : {db_path}")
    print(f"  citations : {filled_before}/{total} déjà renseignées")
    print(f"  posts à analyser : {len(rows)}")

    analyzer = SentimentAnalyzer(model)
    print(f"  modèle : {model} sur {analyzer.device}")

    for start in tqdm(range(0, len(rows), commit_every), desc="Sentiment", unit=" lot"):
        chunk = rows[start : start + commit_every]
        scores = analyzer.predict([text or "" for _, text in chunk], batch_size=batch_size)
        conn.executemany(
            """UPDATE citations
                  SET compound = ?, neg_score = ?, neu_score = ?, pos_score = ?
                WHERE post_no = ?""",
            [
                (s["compound"], s["neg_score"], s["neu_score"], s["pos_score"], post_no)
                for (post_no, _), s in zip(chunk, scores)
            ],
        )
        conn.commit()

    filled_after, total = coverage(conn)
    mean = conn.execute("SELECT AVG(compound) FROM citations WHERE compound IS NOT NULL").fetchone()[0]
    conn.close()

    print(f"  + {filled_after - filled_before} citations renseignées")
    print(f"  Total : {filled_after}/{total} citations avec sentiment (moyenne {mean:.3f})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Remplit les colonnes de sentiment de la table citations (idempotent)"
    )
    ap.add_argument("--db", default="pol.db", help="Fichier SQLite (défaut : pol.db)")
    ap.add_argument("--batch-size", type=int, default=64, help="Taille de lot du modèle")
    ap.add_argument("--commit-every", type=int, default=512,
                    help="Nombre de posts entre deux commits (granularité de reprise)")
    ap.add_argument("--recompute", action="store_true",
                    help="Recalcule aussi les citations déjà renseignées")
    ap.add_argument("--limit", type=int, help="N'analyse que N posts (essai rapide)")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="Modèle HuggingFace")
    args = ap.parse_args()

    run(args.db, args.batch_size, args.commit_every,
        args.recompute, args.limit, args.model)
