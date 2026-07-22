# The Informational Diet of /pol/

**Longitudinal study**: tracking the external sources cited on 4chan's /pol/ board over several weeks.

Each day, we scrape all active threads on /pol/, extract every external URL shared, classify the source, measure the sentiment of the post, and track how the community's information consumption evolves over time.

## Methodology

| Step | Tool / Method | Output |
|---|---|---|
| 1. Daily scrape | `4TCT` via 4chan API | `data/saves/YYYY_MM_DD/threads/pol/*.json` |
| 2. Merge to JSONL | `convert_4tct_to_jsonl.py` | `data/pol_YYYY_MM_DD.jsonl` |
| 3. Extract + classify URLs | `pipeline.py` (regex + domain mapping) | Per-post: domain, category, sentiment |
| 4. Sentiment scoring | `cardiffnlp/twitter-roberta-base-sentiment-latest` | Compound score (-1 to +1) |
| 5. Aggregate | `pipeline.py` | `results/*_stats.json` per day |
| 6. Time series | `longitudinal.py` | Trends: source category share over time |
| 7. Visualize | `viz.py` | Figures + animated timelines |

## Source classification

Each cited domain is classified into one of 5 categories:

- **Mainstream legacy media** — CNN, NYT, BBC, Reuters, CBC, Le Monde...
- **Alternative / right-wing media** — Breitbart, Epoch Times, Rebel News, Fox News...
- **State-funded / affiliated** — RT, Xinhua, CGTN, TASS...
- **Social media / platforms** — Twitter/X, YouTube, Reddit, Telegram, TikTok...
- **Institutional / reference** — Wikipedia, .gov, .edu...

## Usage

### 1. Collect (run once per day)

```bash
cd 4TCT && python src/requester.py -b pol
# Let it run until all active threads are captured, then Ctrl+C
```

### 2. Convert to JSONL

```bash
python convert_4tct_to_jsonl.py
# Outputs: data/pol_YYYY_MM_DD.jsonl
```

### 3. Analyze

```bash
python pipeline.py data/pol_YYYY_MM_DD.jsonl --output results/YYYY_MM_DD
```

### 4. Track over time

```bash
python longitudinal.py --datadir data --out results/longitudinal
```

### 5. Visualize

```bash
python viz.py results/YYYY_MM_DD_stats.json --outdir figures/daily
python viz.py results/longitudinal_stats.json --outdir figures/longitudinal --longitudinal
```

## Research questions

- **H1**: /pol/ cites significantly more alternative/social media sources than mainstream legacy media.
- **H2**: Sentiment expressed toward mainstream media citations is more negative than toward alternative sources.
- **H3**: This citation structure differs drastically from official Canadian political discourse.
- **H4 (longitudinal)**: Source preferences shift in response to real-world political events.

## Repository structure

```
├── 4TCT/                          # 4chan Text Collection Tool (submodule)
├── pipeline.py                    # URL extraction + classification + sentiment
├── viz.py                         # Figure generation
├── longitudinal.py                # Time-series analysis across days
├── convert_4tct_to_jsonl.py       # Convert 4TCT per-thread JSON → flat JSONL
├── requirements.txt               # Python dependencies
├── data/                          # Raw JSONL files (gitignored)
└── results/                       # Stats + figures (gitignored)
```
