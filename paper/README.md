# Article — *The Informational Diet of /pol/*

Source LaTeX de l'article, prêt pour soumission arXiv.

## Contenu

| Fichier | Rôle |
|---|---|
| `main.tex` | Source complet, autonome |
| `fig_main.png` | Figure 1 — parts de citations (IC de Wilson) et tonalité (IC 95 % de la moyenne) |
| `fig3_lorenz.png` | Figure 2 — courbe de Lorenz de la concentration |
| `main.pdf` | Rendu compilé (9 pages) |

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
python sentiment_db.py    # remplit le sentiment dans pol.db
python analysis.py        # tables, results/analysis.json, figures
```

Les figures produites dans `figures_real/` sont à recopier ici si elles
changent.
