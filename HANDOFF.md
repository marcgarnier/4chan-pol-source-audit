# Compte rendu de correction — 22 juillet 2026

Audit + correctifs appliqués par Claude Code (session du 22/07/2026), à destination de l'IA/du dev qui reprend ce projet. **Tout le code a été vérifié en exécution réelle sur `pol_data.jsonl` après correction.**

## Contexte

Les résultats commités (`pol_results_*.csv/json`) avaient été générés par une version antérieure du code. Le code présent dans le repo était **cassé** : le relancer aurait produit ~100 % de domaines vides classés "Other". Trois bugs se combinaient.

## Bugs corrigés

### 1. `normalize_domain()` recevait un domaine nu mais attendait une URL
`pipeline.py` extrayait le domaine puis le passait à `normalize_domain()`, qui faisait `urlparse(domain).netloc` → chaîne vide (`urlparse("youtube.com").netloc == ""`).
**Fix** : `normalize_domain()` (source_classifier.py) accepte désormais URL complète OU domaine nu.

### 2. Les alias normalisés n'appartenaient à aucune catégorie
L'ancien `DOMAIN_MAPPING` produisait des alias artificiels (`youtu.be`→`youtube`, `x.com`→`x_twitter`, `nyti.ms`→`nytimes`) absents des sets de classification → classés "Other" et comptés comme des domaines distincts (ex. dans l'ancien CSV : `youtube.com` = 31 citations "social_media" ET `youtube` = 12 citations "other").
**Fix** : remplacé par `DOMAIN_ALIASES` qui normalise vers le **domaine canonique réel** (`youtu.be`→`youtube.com`, `x.com`→`twitter.com`, `bbc.co.uk`→`bbc.com`, etc.). Plus de double comptage.

### 3. Mismatch de casse entre classification et stats
`classify_source()` retournait `"Mainstream"`, `"Social Media"` (Title Case) alors que `pipeline.summary_stats()` et tout `viz.py` cherchaient `"mainstream"`, `"social_media"` → la section `categories` des stats sortait vide.
**Fix** : `classify_source()` retourne des clés snake_case, définies dans `CATEGORY_KEYS`. Les labels d'affichage sont dans `CATEGORY_LABELS`. `CATEGORY_NAMES` (Title Case) n'existe plus.

### 4. Sous-domaines jamais reconnus
`en.wikipedia.org` ≠ `wikipedia.org` (match exact) → les 7 citations Wikipedia étaient "Other".
**Fix** : `_in_set()` fait un match par suffixe de sous-domaine.

### 5. `NameError` dans pipeline.py
`sys.exit(1)` sans `import sys`. **Fix** : import ajouté.

### 6. Classifieur dupliqué et divergent dans longitudinal.py
`longitudinal.py` avait sa propre copie `classify_domain()` avec des règles **différentes** (bitchute/rumble/odysee y étaient "alternative" au lieu de "social_media"). **Fix** : supprimé, importe `source_classifier`.

### 7. Divers
- Regex URL + extraction dédupliquées : fonction partagée `extract_domains()` dans `source_classifier.py`, utilisée par pipeline, topic_source_matrix (`parse_external_urls` en est un alias) et longitudinal.
- Code mort supprimé dans `viz.py` (calculs de `colors` jamais utilisés, boucle no-op).
- Colonne `total_posts` du CSV longitudinal maintenant remplie.
- RT/Sputnik/TASS retirés du set Alternative (ils sont State-funded, testé en premier) ; truthsocial retiré d'Alternative (reste Social).

## Architecture après correction

`source_classifier.py` est la **source de vérité unique** : `normalize_domain()`, `classify_source()`, `extract_domains()`, `URL_REGEX`, `CATEGORY_KEYS`, `CATEGORY_LABELS`, les sets de domaines. **Aucun autre fichier ne doit redéfinir de logique de classification.**

## Résultats régénérés (vérifiés)

Pipeline relancé sur `pol_data.jsonl` (6 931 posts, 124 avec liens externes) :

| Catégorie | Avant (buggé) | Après |
|---|---|---|
| mainstream | 1 | 4 |
| alternative | 1 | 1 |
| social_media | 40 | 64 |
| state_funded | 0 | 0 |
| institutional | 3 | 10 |
| other | 79 | 45 |

`pol_results_posts.csv`, `pol_results_stats.json`, `figures_real/`, `outputs/topic_source_matrix.png` et `results/longitudinal/` ont été régénérés. **Toute figure/stat produite avant ce correctif est invalide.** Note : `data/pol_2026_07_22.jsonl` est une copie de `pol_data.jsonl` créée pour respecter le layout attendu par `longitudinal.py`.

## Points restants (non traités, à toi de jouer)

1. **Sentiment ≠ opinion sur la source** : le score RoBERTa porte sur le post entier, pas sur l'attitude envers la source citée. Un post hostile citant CNN pour s'en moquer compte comme "sentiment de CNN". À documenter comme limite, ou passer à une analyse de stance.
2. **Troncature à 128 tokens** dans `SentimentAnalyzer.predict()`.
3. **Classification thématique fragile** (`topic_source_matrix.py`) : mots-clés sur `semantic_url + sub` de l'OP uniquement, first-match dans l'ordre du dict ("trump china war" → Geopolitics). Résultat actuel : 73 % des posts en "Other / Misc", "Economy" à 0 — la grille de mots-clés est trop étroite.
4. **Choix éditoriaux à justifier dans le README** : Fox News en "Alternative", France 24 en "State-funded" mais pas BBC/CBC (aussi à financement public). Un reviewer attaquera ça en premier.
5. **Corpus canadien manquant** : `compare_corpora()` et le README promettent une comparaison /pol/ vs corpus canadien ; aucun corpus dans le repo.
6. **Données synthétiques** : `generate_synthetic_data.py` existe ; s'assurer qu'aucune figure "réelle" n'est générée depuis du synthétique (nommer les outputs explicitement).
7. **Hygiène du repo** : `consolidated_stats.xlsx`, `scraper.log`, `.DS_Store`, `__pycache__` probablement à gitignorer ; `pol_data.jsonl` (3,2 Mo) à terme vers un stockage de données.
8. **Échantillon minuscule** : 124 posts avec liens sur une seule journée — aucune conclusion statistique possible ; laisser tourner le scraper 4TCT plusieurs semaines avant d'interpréter quoi que ce soit.

---

# Compte rendu — 4 septembre 2026

Session Claude Code. Point de départ : le dépôt était au commit `8ad7a4a`, la copie de travail synchronisée depuis un Mac, et **aucun script ne pouvait tourner sur cette machine Windows** (Python absent, seul le stub Microsoft Store était dans le PATH).

## Environnement mis en place

Python 3.12.10 (winget, scope utilisateur) + venv `.venv/` à la racine du projet. Torch installé en **build CPU** (`--index-url https://download.pytorch.org/whl/cpu`) : la RTX 5070 Ti de la machine est en architecture Blackwell (sm_120) et demanderait des wheels CUDA 12.8+, pour un gain nul sur ce volume — l'inférence complète prend ~6 min sur CPU.

    python -m venv .venv
    .venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
    .venv/Scripts/python -m pip install -r requirements.txt

## Bug corrigé : encodage dépendant de la locale

Sur Windows, `open()` prend la codepage locale (`cp1252` ici) et non UTF-8. Les 19 `open()` du projet étaient tous sans `encoding=`.

Le point de rupture est l'**écriture**, pas la lecture : ~0,5 % des posts /pol/ (33 sur un échantillon de 6 299 posts du 22/07) contiennent des caractères hors cp1252 — CJK, emoji, tirets typographiques — et `export_csv()` levait `UnicodeEncodeError` sur `text_preview`. Le pipeline ne tournait qu'avec `PYTHONUTF8=1` forcé dans l'environnement.

La lecture survivait par accident : `convert_4tct_to_jsonl.py` écrit avec `json.dumps(ensure_ascii=True)`, donc les JSONL intermédiaires sont en ASCII pur. Ne pas s'y fier — les JSON bruts de 4TCT, eux, sont en UTF-8.

macOS et Linux étant en UTF-8 par défaut, le bug était invisible sur la machine d'origine. **Corrigé** : les 19 appels passent désormais `encoding="utf-8"` explicitement. Vérifié en conditions réelles — les cinq scripts tournent sans `PYTHONUTF8` sur une machine en `cp1252`.

## Raccord SQLite ↔ sentiment : `sentiment_db.py`

`build_db.py` chargeait les citations en laissant `compound / neg_score / neu_score / pos_score` à NULL, et `pipeline.py` calcule le sentiment mais n'écrit que des CSV/JSON. Les deux voies n'étaient pas raccordées : **les 10 078 citations de `pol.db` étaient intégralement sans sentiment.**

`sentiment_db.py` comble ce trou. Il réutilise `SentimentAnalyzer` de `pipeline.py` — pas de second modèle, pas de logique dupliquée (cf. le bug n° 6 de la session du 22/07). Un post citant plusieurs domaines n'est analysé qu'une fois et sa valeur est propagée à toutes ses citations. Idempotent et reprenable : seules les lignes NULL sont traitées, commit tous les 512 posts.

    python sentiment_db.py                  # complète les citations manquantes
    python sentiment_db.py --recompute      # recalcule tout
    python sentiment_db.py --limit 200      # essai rapide

## Corpus : de 1 à 24 jours

`4TCT/data/saves/` contenait **24 journées** de scrape (22/07 → 04/09/2026, 6 594 captures de threads) mais seules 6 avaient été converties en JSONL, et les résultats publiés reposaient sur `pol_data.jsonl` — un fichier d'une seule journée. `pol.db`, elle, était déjà à jour sur les 24 jours.

Tout a été régénéré (`convert_4tct_to_jsonl.py`, `pipeline.py`, `topic_source_matrix.py`, `longitudinal.py`, `viz.py`, `export_sheet.py`) :

| | Avant | Après |
|---|---|---|
| Posts source | 6 931 | 278 706 |
| Posts avec liens | 1 637 | 7 107 |
| Domaines distincts | 331 | 1 170 |
| Points longitudinaux | 1 | 24 |

**Toute figure ou statistique antérieure au 4 septembre 2026 est périmée.**

## Sentiment par catégorie (n = 7 107)

| Catégorie | n | Sentiment moyen | Ratio négatif |
|---|---:|---:|---:|
| State-funded | 13 | −0,507 | 92 % |
| Mainstream | 271 | −0,350 | 66 % |
| Institutional | 567 | −0,296 | 54 % |
| Other | 2 633 | −0,254 | 53 % |
| Alternative | 19 | −0,236 | 53 % |
| Social Media | 3 604 | −0,208 | 42 % |

L'hypothèse centrale — le mainstream reçoit un traitement plus négatif que les sources alternatives — **tient sur le corpus complet** (−0,350 contre −0,236). Mais avec n = 19 pour Alternative et n = 13 pour State-funded, ces deux lignes ne supportent aucun test statistique.

### Biais découvert : `pipeline.py` ne compte qu'un domaine par post

Une fois `pol.db` renseignée, les mêmes chiffres calculés en SQL ne concordent pas avec ceux du pipeline. Cause : `extract_urls_batch()` retient `domains[0]` — le **premier** domaine du post — et jette les suivants. 11 % des posts (782 sur 7 107) citent plusieurs domaines, et la perte est très inégale selon la catégorie :

| Catégorie | `pipeline.py` | `pol.db` | Écart |
|---|---:|---:|---:|
| other | 2 633 | 4 753 | ×1,8 |
| social_media | 3 604 | 4 066 | ×1,1 |
| institutional | 567 | 789 | ×1,4 |
| mainstream | 271 | 386 | ×1,4 |
| alternative | 19 | **69** | **×3,6** |
| state_funded | 13 | 15 | ×1,2 |
| **Total** | 7 107 | 10 078 | |

Les sources alternatives sont les plus pénalisées : elles apparaissent typiquement en second lien, après un lien YouTube ou Twitter qui capte la place de `primary_domain`. Le pipeline sous-estimait donc structurellement la catégorie la plus décisive pour l'hypothèse du projet.

Chiffres corrigés, calculés sur la base (n = 10 078) :

| Catégorie | n | Sentiment moyen | Ratio négatif |
|---|---:|---:|---:|
| State-funded | 15 | −0,430 | 87 % |
| Mainstream | 386 | −0,346 | 66 % |
| Alternative | 69 | −0,275 | 62 % |
| Institutional | 789 | −0,225 | 45 % |
| Other | 4 753 | −0,209 | 47 % |
| Social Media | 4 066 | −0,179 | 39 % |

La direction de l'hypothèse tient toujours, mais **l'écart mainstream/alternative se réduit de 0,114 à 0,071** et Alternative passe de la 5ᵉ à la 3ᵉ place du classement. **Ce sont ces chiffres-là qu'il faut citer, pas ceux du pipeline.** Corriger `pipeline.py` pour émettre une ligne par couple (post, domaine) — ou, mieux, faire de `pol.db` la source unique des statistiques.

## Points restants — mise à jour de la liste du 22/07

Résolus : **n° 7** (hygiène du repo — `.venv/` et les fichiers AppleDouble `._*` ajoutés au `.gitignore` ; le reste était déjà couvert).

Atténué : **n° 8** (échantillon) — on passe de 124 à 7 107 posts avec liens. Mais le taux de citation n'est que de **2,5 %** des posts, donc les catégories rares le restent : agréger plus de jours ne suffira pas pour Alternative et State-funded. Il faut élargir les listes de domaines de `source_classifier.py`.

Aggravé : **n° 3** (classification thématique) — « Other / Misc » passe de 73 % à **76,2 %** (212 493 posts sur 278 706) sur le corpus élargi. La grille de mots-clés ne tient pas l'échelle. `Economy / Finance` remonte de 0 à 25 liens seulement. À refaire avant toute publication.

Inchangés : **n° 1** (sentiment ≠ stance), **n° 2** (troncature à 128 tokens), **n° 4** (choix éditoriaux à justifier : Fox News en Alternative, France 24 en State-funded mais pas BBC/CBC), **n° 5** (corpus canadien absent), **n° 6** (données synthétiques).

Nouveau : **`pipeline.py` ne compte qu'un domaine par post** (voir plus haut). C'est le point le plus urgent — il fausse la catégorie Alternative d'un facteur 3,6 et affaiblit la mesure centrale du projet.

Nouveau : **`pipeline.py` et `pol.db` restent deux voies parallèles.** `sentiment_db.py` raccorde le sentiment, mais le pipeline continue de lire les JSONL et d'écrire ses propres CSV/JSON sans jamais consulter la base. À terme, faire de SQLite la source unique et ne garder les JSONL que comme format d'échange — ce qui règlerait le point précédent par construction.
