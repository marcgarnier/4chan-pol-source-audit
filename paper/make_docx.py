"""Convertit main.tex en .docx via pandoc, en résolvant les citations natbib.

Le lecteur LaTeX de pandoc ignore `\\citet` et `\\citep` quand aucune base
bibliographique ne lui est fournie, ce qui supprime silencieusement les appels
de citation et laisse des phrases amputées (« Research on /pol/ began as a
measurement problem. assembled roughly 8M posts... »).

Plutôt que de maintenir un .bib parallèle, qui dériverait de la bibliographie du
document, ce script lit les `\\bibitem[Auteurs(Année)]{clé}` déjà présents dans
main.tex et développe les appels en texte avant de passer la main à pandoc. La
bibliographie du document reste la source unique.

    python make_docx.py                 # produit main.docx
    python make_docx.py --out autre.docx
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent

# \bibitem[Hine et al.(2017)]{hine2017}
BIBITEM = re.compile(r"\\bibitem\[([^\]]*)\]\{([^}]+)\}")
LABEL = re.compile(r"^(.*?)\((\d{4}[a-z]?)\)\s*$")


def load_entries(tex: str) -> dict[str, tuple[str, str]]:
    """clé -> (auteurs, année), lus depuis les étiquettes natbib du document."""
    entries = {}
    for label, key in BIBITEM.findall(tex):
        m = LABEL.match(label.strip())
        if m:
            entries[key] = (m.group(1).strip(), m.group(2))
        else:  # étiquette non standard : on la garde telle quelle
            entries[key] = (label.strip(), "")
    return entries


def expand_citations(tex: str, entries: dict[str, tuple[str, str]]) -> tuple[str, list[str]]:
    """Développe \\citet et \\citep en texte, à la manière de natbib author-year."""
    missing = []

    def resolve(keys: str):
        out = []
        for key in (k.strip() for k in keys.split(",")):
            if key not in entries:
                missing.append(key)
                out.append((key, ""))
            else:
                out.append(entries[key])
        return out

    def link(key, text):
        """Lien interne vers l'entrée de bibliographie (signet Word, ancre PDF)."""
        return f"\\hyperlink{{ref-{key}}}{{{text}}}"

    def keys_of(group):
        return [k.strip() for k in group.split(",")]

    def do_citet(m):
        parts, keys = resolve(m.group(1)), keys_of(m.group(1))
        return "; ".join(link(k, f"{a} ({y})" if y else a)
                         for k, (a, y) in zip(keys, parts))

    def do_citep(m):
        parts, keys = resolve(m.group(1)), keys_of(m.group(1))
        inner = "; ".join(link(k, f"{a}, {y}" if y else a)
                          for k, (a, y) in zip(keys, parts))
        return f"({inner})"

    tex = re.sub(r"\\citet\{([^}]+)\}", do_citet, tex)
    tex = re.sub(r"\\citep\{([^}]+)\}", do_citep, tex)

    # Pose l'ancre au début de chaque entrée de bibliographie.
    tex = BIBITEM.sub(
        lambda m: f"\\bibitem[{m.group(1)}]{{{m.group(2)}}}\\hypertarget{{ref-{m.group(2)}}}{{}}",
        tex,
    )
    return tex, missing


def find_pandoc() -> str:
    from shutil import which
    for candidate in ("pandoc",
                      str(Path.home() / "AppData/Local/Pandoc/pandoc.exe"),
                      r"C:\Program Files\Pandoc\pandoc.exe"):
        found = which(candidate) or (candidate if Path(candidate).exists() else None)
        if found:
            return found
    sys.exit("pandoc introuvable : winget install --id JohnMacFarlane.Pandoc")


def main(src: Path, out: Path):
    tex = src.read_text(encoding="utf-8")
    entries = load_entries(tex)
    if not entries:
        sys.exit("Aucun \\bibitem trouvé : vérifier la bibliographie de main.tex.")

    expanded, missing = expand_citations(tex, entries)
    n_cites = len(re.findall(r"\\cite[tp]\{", tex))

    # pandoc résout les chemins relatifs depuis le répertoire du fichier source
    with tempfile.NamedTemporaryFile("w", suffix=".tex", dir=src.parent,
                                     delete=False, encoding="utf-8") as f:
        tmp = Path(f.name)
        f.write(expanded)
    try:
        subprocess.run([find_pandoc(), tmp.name, "-f", "latex", "-t", "docx",
                        "--resource-path", str(src.parent), "-o", str(out.resolve())],
                       cwd=src.parent, check=True)
    finally:
        tmp.unlink(missing_ok=True)

    print(f"Références lues       : {len(entries)}")
    print(f"Appels de citation    : {n_cites} développés")
    if missing:
        print(f"  ATTENTION clés sans bibitem : {sorted(set(missing))}")
    print(f"Écrit                 : {out} ({out.stat().st_size // 1024} Ko)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="main.tex -> .docx avec citations résolues")
    ap.add_argument("--src", default=str(HERE / "main.tex"))
    ap.add_argument("--out", default=str(HERE / "main.docx"))
    args = ap.parse_args()
    main(Path(args.src), Path(args.out))
