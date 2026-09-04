"""Génère le classeur d'annotation manuelle des domaines non classés.

Le classificateur automatique laisse 47 % des citations en « other », et une
part non négligeable sont en réalité des médias qu'il ne connaît pas (presse
britannique, australienne, israélienne, ukrainienne). Ce script sort les N
domaines non classés les plus cités dans un .xlsx à remplir à la main.

La colonne `auto_suggestion` n'est renseignée que là où une règle
**déterministe** s'applique (hébergeur/archive connu, TLD .gov/.mil/.edu,
plateforme connue). Tout le reste est laissé vide : c'est précisément là que
le jugement humain est nécessaire et que la règle automatique a échoué.

    python make_annotation_sheet.py                # top 200
    python make_annotation_sheet.py --top 100      # plus court
"""
import argparse
import sqlite3
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

CATEGORIES = [
    "mainstream", "alternative", "state_funded",
    "social_media", "institutional", "archive", "other",
]

DEFINITIONS = [
    ("mainstream", "Média d'information établi, commercial ou indépendant.",
     "dailymail.com, independent.co.uk, nypost.com, forbes.com"),
    ("alternative", "Média d'information partisan ou alternatif, hors presse établie.",
     "unz.com, noticer.news, substack d'opinion"),
    ("state_funded", "Diffuseur public ou contrôlé/financé par un État.",
     "abc.net.au, pbs.org, aljazeera.com, rt.com"),
    ("social_media", "Plateforme sociale, y compris les façades et miroirs.",
     "xcancel.com, nitter.net, imgur.com, flickr.com"),
    ("institutional", "Référence, gouvernement, université, recherche, ONG.",
     "nature.com, arxiv.org, pewresearch.org, icrc.org"),
    ("archive", "Hébergeur de fichiers, pastebin, archive web.",
     "files.catbox.moe, rentry.org, archive.today, archive.4plebs.org"),
    ("other", "Rien de ce qui précède : traceur, carte, outil, boutique, site perso.",
     "marinetraffic.com, flightradar24.com, tampermonkey.net"),
]

QUESTIONS = [
    "Les agrégateurs (msn.com, yahoo.com, finance.yahoo.com, news.google) : "
    "« mainstream » ou « other » ? Ils redistribuent sans produire.",
    "Al Jazeera : « state_funded » comme RT, ou « mainstream » ? "
    "Financé par le Qatar mais rédaction distincte. Le choix doit être le même "
    "que pour la BBC et l'ABC australienne — dis lequel.",
    "Substack et blogs personnels d'opinion : « alternative » ou « other » ?",
    "Sites de campagne (donaldjtrump.com, united24media.com) : "
    "« other » ou une catégorie propre « partisan/campagne » ?",
    "Les cartes de guerre en direct (liveuamap, deepstatemap, tzevaadom) : "
    "« other », ou méritent-elles leur propre catégorie « OSINT/tracker » ? "
    "Elles pèsent lourd dans ce corpus.",
]

# Règles déterministes — les seules que je me permets de pré-remplir.
ARCHIVE_HOSTS = (
    "catbox.moe", "rentry.org", "archive.today", "archive.ph", "archive.is",
    "archive.md", "archive.org", "4plebs.org", "desuarchive.org", "warosu.org",
    "pastebin.com", "ghostarchive.org", "pastes.io", "pastejustit.com",
    "cloakbin.com", "write.as", "mega.nz",
)
PLATFORM_HOSTS = (
    "nitter.net", "nitter.poast.org", "xcancel.com", "imgur.com", "flickr.com",
    "streamable.com", "vocaroo.com", "voca.ro", "odysee.com",
)
INSTITUTIONAL_TLDS = (".gov", ".mil", ".edu")


def auto_suggest(domain: str) -> str:
    if any(domain == h or domain.endswith("." + h) for h in ARCHIVE_HOSTS):
        return "archive"
    if any(domain == h or domain.endswith("." + h) for h in PLATFORM_HOSTS):
        return "social_media"
    if any(domain.endswith(t) for t in INSTITUTIONAL_TLDS):
        return "institutional"
    return ""


def fetch(db: str, top: int):
    conn = sqlite3.connect(db)
    total_other = conn.execute(
        "SELECT COUNT(*) FROM citations ci JOIN domains d USING(domain) "
        "WHERE d.category='other'").fetchone()[0]
    rows = conn.execute("""
        SELECT ci.domain, COUNT(*) AS n,
               MAX(CASE WHEN ci.url <> '' THEN ci.url END) AS example
          FROM citations ci JOIN domains d USING(domain)
         WHERE d.category = 'other'
      GROUP BY ci.domain
      ORDER BY n DESC
         LIMIT ?
    """, (top,)).fetchall()
    conn.close()
    return rows, total_other


def build(db: str, top: int, out: str):
    rows, total_other = fetch(db, top)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "À annoter"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", start_color="1F4E79")
    todo_fill = PatternFill("solid", start_color="FFF2CC")

    headers = ["rang", "domaine", "citations", "% cumulé du bucket",
               "exemple d'URL", "auto (règle sûre)", "CATÉGORIE", "notes"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    running = 0
    for i, (domain, n, example) in enumerate(rows, 1):
        running += n
        auto = auto_suggest(domain)
        url = (example or "")[:95]
        ws.append([i, domain, n, round(running / total_other * 100, 1),
                   url, auto, auto, ""])
        ws.cell(row=i + 1, column=7).fill = todo_fill

    dv = DataValidation(
        type="list",
        formula1='"' + ",".join(CATEGORIES) + '"',
        allow_blank=True,
        showDropDown=False,
        errorTitle="Catégorie inconnue",
        error="Choisis une valeur dans la liste déroulante.",
    )
    ws.add_data_validation(dv)
    dv.add(f"G2:G{len(rows) + 1}")

    for col, width in zip("ABCDEFGH", (6, 34, 11, 18, 60, 18, 18, 40)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:H{len(rows) + 1}"

    # ---- feuille de garde ----
    g = wb.create_sheet("Guide", 0)
    g.column_dimensions["A"].width = 18
    g.column_dimensions["B"].width = 68
    g.column_dimensions["C"].width = 52

    def line(a="", b="", c="", bold=False, fill=False):
        g.append([a, b, c])
        r = g.max_row
        if bold:
            for col in "ABC":
                g[f"{col}{r}"].font = Font(bold=True)
        if fill:
            for col in "ABC":
                g[f"{col}{r}"].fill = header_fill
                g[f"{col}{r}"].font = header_font

    line("Comment remplir", "", "", fill=True)
    line("", "Une seule colonne à remplir : CATÉGORIE (colonne G, fond jaune), "
             "avec la liste déroulante.")
    line("", "La colonne F ne contient une valeur que si une règle déterministe "
             "s'applique (archive, plateforme, TLD .gov/.mil/.edu). Elle est "
             "recopiée en G pour te faire gagner du temps — corrige-la si elle "
             "a tort.")
    line("", "Les lignes sont triées par nombre de citations. La colonne D dit "
             "quelle part du bucket « non classé » tu as couverte en t'arrêtant "
             "à cette ligne. Tu peux t'arrêter quand tu veux.")
    line("", "La colonne « notes » est libre : sers-t'en pour les cas où tu "
             "hésites, je les traiterai à part.")
    line()
    line("Catégories", "Définition", "Exemples", bold=True)
    for name, definition, examples in DEFINITIONS:
        line(name, definition, examples)
    line()
    line("Décisions à trancher", "", "", fill=True)
    line("", "Ces cas reviennent souvent et doivent être tranchés une fois pour "
             "toutes, sinon le codage devient incohérent :")
    for q in QUESTIONS:
        line("", q)
    line()
    line("Portée", "", "", fill=True)
    line("", f"{len(rows)} domaines proposés, soit "
             f"{round(sum(r[1] for r in rows) / total_other * 100, 1)}% des "
             f"{total_other:,} citations aujourd'hui non classées.")
    line("", "Les domaines cités une seule fois (904 sur 1 248) sont hors de "
             "cette liste : leur coder tous coûterait cher pour peu d'effet, et "
             "l'article déclarera le résidu comme tel.")

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)

    covered = sum(r[1] for r in rows)
    print(f"Classeur créé : {out}")
    print(f"  {len(rows)} domaines à annoter")
    print(f"  couvrent {covered:,}/{total_other:,} citations non classées "
          f"({covered/total_other*100:.1f}% du bucket)")
    print(f"  pré-remplis par règle sûre : "
          f"{sum(1 for d, _, _ in rows if auto_suggest(d))}")
    print(f"  à trancher à la main : "
          f"{sum(1 for d, _, _ in rows if not auto_suggest(d))}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Génère le classeur d'annotation")
    ap.add_argument("--db", default="pol.db")
    ap.add_argument("--top", type=int, default=200)
    ap.add_argument("--out", default="annotation_domaines.xlsx")
    args = ap.parse_args()
    build(args.db, args.top, args.out)
