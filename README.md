# The Informational Diet of /pol/

A factual audit of external sources cited on 4chan's political board.

## Pipeline

1. **Collect** — `4TCT` (4chan Text Collection Tool) scrapes /pol/ via the 4chan API
2. **Parse** — `pipeline.py` extracts external URLs from post HTML, normalizes domains, classifies sources (mainstream / alternative / social media / state-funded / institutional)
3. **Sentiment** — `cardiffnlp/twitter-roberta-base-sentiment-latest` scores the text surrounding each cited link
4. **Visualize** — `viz.py` produces bar charts, scatter plots, pie charts, and comparison tables

## Usage

```bash
# Collect data
cd 4TCT && python src/requester.py -b pol

# Analyze
python pipeline.py 4TCT/data/posts.jsonl --output results

# Visualize
python viz.py results_stats.json --outdir figures
```

## Output

- `results_posts.csv` — per-post sentiment and source data
- `results_stats.json` — aggregated statistics by domain and category
- `figures/` — publication-ready PNG figures
