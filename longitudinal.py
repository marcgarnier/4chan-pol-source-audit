import json
import csv
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from source_classifier import classify_source, extract_domains

CATEGORY_COLORS = {
    "mainstream": "#4C72B0",
    "alternative": "#DD8452",
    "social_media": "#55A868",
    "state_funded": "#C44E52",
    "institutional": "#8172B2",
    "other": "#8C8C8C",
}

CATEGORY_LABELS = {
    "mainstream": "Mainstream",
    "alternative": "Alternative",
    "social_media": "Social Media",
    "state_funded": "State-funded",
    "institutional": "Institutional",
    "other": "Other",
}


def run_all(data_dir: str = "data", results_dir: str = "results/longitudinal"):
    data_path = Path(data_dir)
    res_path = Path(results_dir)
    res_path.mkdir(parents=True, exist_ok=True)

    jsonl_files = sorted(data_path.glob("pol_*.jsonl"))
    if not jsonl_files:
        print("No data files found in data/")
        return

    dates = []
    domain_counts = []
    category_counts = []
    post_counts = []

    for f in jsonl_files:
        date_str = f.stem.replace("pol_", "")
        dates.append(date_str)

        dom_counter = defaultdict(int)
        cat_counter = defaultdict(int)
        n_posts = 0

        with open(f) as fh:
            for line in fh:
                post = json.loads(line)
                n_posts += 1
                for domain in extract_domains(post.get("com", "")):
                    dom_counter[domain] += 1
                    cat_counter[classify_source(domain)] += 1

        total = sum(cat_counter.values()) or 1
        category_counts.append({k: v / total for k, v in cat_counter.items()})
        domain_counts.append(dom_counter)
        post_counts.append(n_posts)

    _plot_category_timeline(dates, category_counts, res_path)
    _export_table(dates, category_counts, post_counts, res_path)
    _save_aggregated_stats(dates, category_counts, domain_counts, res_path)
    print(f"Longitudinal analysis saved to {res_path}")


def _plot_category_timeline(dates, category_counts, out_dir):
    fig, ax = plt.subplots(figsize=(12, 6))
    cats = ["mainstream", "alternative", "social_media", "state_funded", "institutional", "other"]
    x = np.arange(len(dates))

    bottom = np.zeros(len(dates))
    for cat in cats:
        values = [d.get(cat, 0) * 100 for d in category_counts]
        if not any(v > 0 for v in values):
            continue
        ax.bar(x, values, bottom=bottom, label=CATEGORY_LABELS.get(cat, cat),
               color=CATEGORY_COLORS.get(cat, "#8C8C8C"), width=0.7)
        bottom += np.array(values)

    ax.set_xlabel("Date")
    ax.set_ylabel("Share of citations (%)")
    ax.set_title("Source Category Share on /pol/ Over Time")
    ax.set_xticks(x)
    ax.set_xticklabels(dates, rotation=45, ha="right", fontsize=8)
    ax.legend(loc="upper left", fontsize=9)
    ax.set_ylim(0, 105)
    fig.tight_layout()
    fig.savefig(out_dir / "category_timeline.png", dpi=200)
    plt.close(fig)
    print(f"Saved {out_dir / 'category_timeline.png'}")


def _export_table(dates, category_counts, post_counts, out_dir):
    cats = ["mainstream", "alternative", "social_media", "state_funded", "institutional", "other"]
    path = out_dir / "daily_categories.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date"] + [CATEGORY_LABELS.get(c, c) for c in cats] + ["total_posts"])
        for i, date in enumerate(dates):
            row = [date] + [f"{category_counts[i].get(c, 0) * 100:.1f}%" for c in cats] + [post_counts[i]]
            w.writerow(row)
    print(f"Saved {path}")


def _save_aggregated_stats(dates, category_counts, domain_counts, out_dir):
    cats = ["mainstream", "alternative", "social_media", "state_funded", "institutional", "other"]
    aggregated = {}
    for cat in cats:
        vals = [d.get(cat, 0) for d in category_counts]
        aggregated[cat] = {
            "mean_share": float(np.mean(vals)) if vals else 0,
            "max_share": float(np.max(vals)) if vals else 0,
            "min_share": float(np.min(vals)) if vals else 0,
        }
    all_domains = defaultdict(int)
    for dc in domain_counts:
        for d, c in dc.items():
            all_domains[d] += c
    top_domains = sorted(all_domains.items(), key=lambda x: -x[1])[:30]
    aggregated["top_domains_overall"] = [{"domain": d, "count": c} for d, c in top_domains]
    aggregated["dates"] = dates

    with open(out_dir / "aggregated_stats.json", "w") as f:
        json.dump(aggregated, f, indent=2)
    print(f"Saved {out_dir / 'aggregated_stats.json'}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--datadir", default="data")
    parser.add_argument("--out", default="results/longitudinal")
    args = parser.parse_args()
    run_all(args.datadir, args.out)
