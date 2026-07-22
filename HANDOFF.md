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
