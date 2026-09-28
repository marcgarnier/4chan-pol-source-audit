# Article — *The Informational Diet of /pol/*

Source LaTeX de l'article, prêt pour soumission arXiv.

## Contenu

| Fichier | Rôle |
|---|---|
| `main.tex` | Source complet, autonome |
| `fig_main.png` | Figure 1 — parts de citations (IC de Wilson) et courbe de Lorenz |
| `main.pdf` | Rendu compilé (10 pages) |
| `main.docx` | Version Word, pour relecture ou soumission en .docx |
| `make_docx.py` | Convertisseur LaTeX vers Word |

## Compilation

```
pdflatex main.tex
pdflatex main.tex
```

Deux passes suffisent. **Pas de BibTeX** : la bibliographie est un
environnement `thebibliography` en dur, précisément pour qu'arXiv n'ait
besoin d'aucun fichier `.bbl` externe. Paquets requis, tous standards :
`geometry`, `graphicx`, `booktabs`, `amsmath`, `amssymb`, `url`, `natbib`,
`hyperref`, `caption`.

## Soumission arXiv

Téléverser `main.tex`, `fig_main.png` et `fig3_lorenz.png` (le `.pdf` n'est
pas à envoyer, arXiv compile lui-même). Catégories suggérées :
**cs.CY** (Computers and Society) en primaire, **cs.SI** (Social and
Information Networks) en croisée.

## À faire avant de soumettre

1. **Renseigner l'affiliation.** Le bloc auteur ne contient qu'un courriel.
2. **Vérifier chaque référence contre la source primaire** — année exacte,
   volume, pages, DOI. La liste provient de `METHODOLOGY.md`, qui porte
   elle-même l'avertissement de ne pas s'y fier en aveugle. Elle n'a pas
   été vérifiée bibliographiquement.
3. **Lire la section Limitations.** Elle énonce sans détour que la mesure de
   sentiment n'est pas validée sur ce domaine et que le codage des sources
   est mono-axe. Ce sont des choix de transparence assumés ; si tu préfères
   d'abord combler ces manques, ils sont à traiter avant soumission, pas
   après.

## Régénérer les chiffres

Tous les nombres de l'article sortent de `analysis.py`, à la racine du dépôt :

```
python analysis.py        # tables, results/analysis.json, figures
```

Le sentiment ne fait pas partie de l'analyse publiée (voir §3.4 de l'article).
`sentiment_db.py` et `analysis.py --with-sentiment` restent disponibles pour qui
reprendrait ce volet après une validation annotée.

Les figures produites dans `figures_real/` sont à recopier ici si elles
changent.

## Version Word

```
python make_docx.py
```

Le lecteur LaTeX de pandoc ignore `\citet` et `\citep` faute de base
bibliographique, ce qui **supprime silencieusement les appels de citation** et
laisse des phrases amputées. `make_docx.py` lit les `\bibitem[Auteurs(Année)]`
du document et développe les appels en texte avant de passer la main à pandoc,
de sorte que la bibliographie de `main.tex` reste la source unique. Ne pas
convertir avec `pandoc` seul.

Requiert pandoc (`winget install --id JohnMacFarlane.Pandoc`).
