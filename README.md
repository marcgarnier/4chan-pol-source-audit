# The Informational Diet of /pol/

A data-driven audit of the news sources cited on 4chan's /pol/ board.

What does the /pol/ community actually read and share? This project scrapes /pol/ periodically, extracts every external URL posted, classifies each source into a media category, and measures the sentiment of the surrounding discussion. The goal is to produce reproducible, quantitative evidence about the information ecosystem of one of the internet's most influential political spaces.

## Pipeline

| Step | Tool | Output |
|---|---|---|
| 1. Scrape | `4TCT` via 4chan API | `data/saves/YYYY_MM_DD/threads/pol/*.json` |
| 2. Merge | `convert_4tct_to_jsonl.py` | `data/pol_YYYY_MM_DD.jsonl` |
| 3. Extract + classify URLs | `source_classifier.py` | Normalized domain → 5 categories |
| 4. Aggregate stats | `pipeline.py` | Per-domain and per-category stats + sentiment |
| 5. Topic cross-analysis | `topic_source_matrix.py` | Source categories × thread topic matrix |
| 6. Visualize | `viz.py` | Publication-ready figures |

## Source categories

Sources are classified into five categories (see `source_classifier.py`):

| Category | Examples |
|---|---|
| **Mainstream** | CNN, NYT, BBC, Reuters, CBC, The Guardian, Bloomberg |
| **Alternative** | Breitbart, Fox News, Epoch Times, Rebel News, Zero Hedge |
| **State-funded** | RT, Xinhua, CGTN, TASS, France 24 |
| **Social Media** | Twitter/X, YouTube, Reddit, Telegram, TikTok, Rumble |
| **Institutional** | Wikipedia, .gov, .mil, .edu domains |

## Scripts

| Script | Description |
|---|---|
| `source_classifier.py` | Shared module: `normalize_domain(url)` and `classify_source(domain)` |
| `pipeline.py` | Full extraction + RoBERTa sentiment analysis + aggregated stats |
| `topic_source_matrix.py` | Cross-tabulates source categories by thread topic (geopolitics, elections, economy, identity) |
| `viz.py` | Generates bar charts, scatter plots, pie charts, comparison tables |
| `convert_4tct_to_jsonl.py` | Converts 4TCT per-thread JSON into flat JSONL |
| `export_sheet.py` | Exports consolidated stats to Excel (.xlsx) |

## Usage

### 1. Scrape /pol/

```bash
cd 4TCT && python src/requester.py -b pol
# Let it run for a few minutes, then Ctrl+C
```

### 2. Convert to JSONL

```bash
python convert_4tct_to_jsonl.py
# Creates data/pol_YYYY_MM_DD.jsonl for each day's scrape
```

### 3. Run the full pipeline

```bash
# Aggregate all scraped sessions
python pipeline.py data/*.jsonl --output results/aggregated

# Cross source categories with thread topics
python topic_source_matrix.py data/*.jsonl --plot
```

### 4. Visualize

```bash
python viz.py results/aggregated_stats.json --outdir figures
```

### 5. Export to Excel

```bash
python export_sheet.py results/aggregated_stats.json results/aggregated_posts.csv -o consolidated_stats.xlsx
```

## Research questions

- **H1**: /pol/ cites more alternative and social media sources than mainstream legacy media.
- **H2**: Sentiment toward mainstream media sources is more negative than toward alternative sources.
- **H3**: Source preferences vary systematically by thread topic (geopolitics vs. domestic politics vs. identity debates).

## Repository structure

```
├── 4TCT/                          # 4chan Text Collection Tool (cloned separately)
├── source_classifier.py           # Domain normalization and source classification
├── pipeline.py                    # URL extraction + sentiment analysis + stats
├── topic_source_matrix.py         # Topic × source category cross-tabulation
├── viz.py                         # Figure generation
├── convert_4tct_to_jsonl.py       # Thread JSON → flat JSONL converter
├── export_sheet.py                # Excel export
├── requirements.txt               # Python dependencies
├── data/                          # Raw JSONL files (gitignored)
└── results/                       # Stats + figures (gitignored)
```

## Requirements

- Python 3.8+
- See `requirements.txt` for dependencies (torch, transformers, beautifulsoup4, matplotlib, openpyxl, etc.)
