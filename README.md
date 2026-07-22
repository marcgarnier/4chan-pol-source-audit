# The Informational Diet of /pol/

What sources does 4chan's /pol/ actually cite? A data-driven audit.

Scrape /pol/ multiple times over several weeks to accumulate volume, extract every external URL shared, classify the source type, and measure the sentiment of the surrounding post.

## Pipeline

| Step | Tool | Output |
|---|---|---|
| 1. Scrape | `4TCT` via 4chan API | `data/saves/YYYY_MM_DD/threads/pol/*.json` |
| 2. Merge | `convert_4tct_to_jsonl.py` | `data/pol_YYYY_MM_DD.jsonl` |
| 3. Consolidate | `python pipeline.py data/*.jsonl` | Single aggregate stats |
| 4. Classify | Domain mapping → 5 categories | Per-post: domain, category, sentiment |
| 5. Visualize | `viz.py` | Figures |

## Source classification

- **Mainstream legacy media** — CNN, NYT, BBC, Reuters, CBC...
- **Alternative / right-wing media** — Breitbart, Epoch Times, Fox News...
- **State-funded / affiliated** — RT, Xinhua, CGTN, TASS...
- **Social media / platforms** — Twitter/X, YouTube, Reddit, Telegram...
- **Institutional / reference** — Wikipedia, .gov, .edu...

## Usage

### 1. Scrape (une fois par session)

```bash
cd 4TCT && python src/requester.py -b pol
# Ctrl+C après quelques minutes
```

### 2. Convertir

```bash
python convert_4tct_to_jsonl.py
# Crée data/pol_YYYY_MM_DD.jsonl pour chaque jour
```

### 3. Tout analyser d'un coup

```bash
python pipeline.py data/*.jsonl --output results/aggregated
```

### 4. Visualiser

```bash
python viz.py results/aggregated_stats.json --outdir figures
```

## Repo structure

```
├── 4TCT/                          # Scraper (cloné)
├── pipeline.py                    # Extraction URLs + classification + sentiment
├── viz.py                         # Figures
├── convert_4tct_to_jsonl.py       # 4TCT → JSONL
├── data/                          # JSONL bruts (ignorés par git)
└── results/                       # Stats + figures (ignorés par git)
```
