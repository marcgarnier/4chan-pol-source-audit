import json
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#333333",
    "axes.labelcolor": "#333333",
    "axes.titlesize": 14,
    "axes.labelsize": 11,
    "xtick.color": "#333333",
    "ytick.color": "#333333",
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial"],
})


CATEGORY_COLORS = {
    "mainstream": "#4C72B0",
    "alternative": "#DD8452",
    "social_media": "#55A868",
    "state_funded": "#C44E52",
    "institutional": "#8172B2",
    "other": "#8C8C8C",
}

CATEGORY_LABELS = {
    "mainstream": "Mainstream Legacy Media",
    "alternative": "Alternative / Right-wing Media",
    "social_media": "Social Media / Platforms",
    "state_funded": "State-funded / Affiliated",
    "institutional": "Institutional / Reference",
    "other": "Other",
}


def load_stats(stats_path: str) -> dict:
    with open(stats_path) as f:
        return json.load(f)


def load_csv_post_data(csv_path: str) -> list[dict]:
    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["compound"] = float(row["compound"]) if row["compound"] else 0.0
            rows.append(row)
    return rows


def fig1_top_domains_bar(stats: dict, top_n: int = 20, save_path: str = "fig1_top_domains.png"):
    top = list(stats.get("top_domains", {}).items())[:top_n]
    if not top:
        print("No domain data to plot")
        return
    domains = [d for d, _ in top]
    counts = [s["count"] for _, s in top]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(range(len(domains)), counts, color="#4C72B0", edgecolor="white", height=0.7)
    ax.set_yticks(range(len(domains)))
    ax.set_yticklabels(domains, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Number of citations")
    ax.set_title("Top 20 External Domains Cited on /pol/")
    for bar, count in zip(bars, counts):
        ax.text(bar.get_width() + max(counts) * 0.005, bar.get_y() + bar.get_height() / 2,
                str(count), va="center", fontsize=8)
    ax.set_xlim(0, max(counts) * 1.15)
    fig.tight_layout()
    fig.savefig(save_path, dpi=200)
    plt.close(fig)
    print(f"Saved {save_path}")


def fig1b_category_pie(stats: dict, save_path: str = "fig1b_category_pie.png"):
    cats = stats.get("categories", {})
    labels = []
    sizes = []
    colors = []
    for cat_key in ("mainstream", "alternative", "social_media", "state_funded", "institutional", "other"):
        if cat_key in cats:
            labels.append(CATEGORY_LABELS.get(cat_key, cat_key))
            sizes.append(cats[cat_key]["count"])
            colors.append(CATEGORY_COLORS.get(cat_key, "#8C8C8C"))
    if not sizes:
        return
    fig, ax = plt.subplots(figsize=(8, 8))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=None, autopct="%1.1f%%", startangle=140,
        colors=colors, wedgeprops={"edgecolor": "white", "linewidth": 1},
        pctdistance=0.85,
    )
    for t in autotexts:
        t.set_fontsize(9)
    ax.legend(wedges, labels, title="Source category", loc="center left",
              bbox_to_anchor=(1, 0, 0.5, 1), fontsize=9)
    ax.set_title("Distribution of Cited Sources by Category on /pol/")
    fig.tight_layout()
    fig.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {save_path}")


def fig2_sentiment_scatter(stats: dict, save_path: str = "fig2_sentiment_scatter.png"):
    top = list(stats.get("top_domains", {}).items())[:30]
    if not top:
        return
    domains = []
    means = []
    stds = []
    counts = []
    for d, s in top:
        domains.append(d)
        means.append(s["mean_sentiment"])
        stds.append(s["std_sentiment"])
        counts.append(s["count"])

    fig, ax = plt.subplots(figsize=(12, 7))
    sizes = [max(c / max(counts) * 800, 30) for c in counts]
    scatter = ax.scatter(means, stds, s=sizes, c="#4C72B0", alpha=0.7, edgecolors="#333", linewidth=0.5)

    for i, d in enumerate(domains):
        ax.annotate(d, (means[i], stds[i]), fontsize=6.5, alpha=0.8,
                    ha="center", va="bottom" if i % 2 == 0 else "top",
                    textcoords="offset points", xytext=(0, 4 if i % 2 == 0 else -4))

    ax.axvline(0, color="#999", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.set_xlabel("Mean sentiment score (-1 = negative, +1 = positive)")
    ax.set_ylabel("Standard deviation of sentiment")
    ax.set_title("Sentiment Distribution by Domain (size ∝ citation volume)")

    kw = dict(prop="sizes", num=5, fmt="{x:.0f}", color="#555", alpha=0.7)
    ax.legend(*scatter.legend_elements(**kw), loc="upper right", title="Citations", fontsize=8)
    fig.tight_layout()
    fig.savefig(save_path, dpi=200)
    plt.close(fig)
    print(f"Saved {save_path}")


def fig2b_category_sentiment_bars(stats: dict, save_path: str = "fig2b_category_sentiment.png"):
    cats = stats.get("categories", {})
    ordered_keys = ["mainstream", "alternative", "social_media", "state_funded", "institutional", "other"]
    labels = []
    means = []
    stds = []
    colors = []
    for k in ordered_keys:
        if k in cats:
            labels.append(CATEGORY_LABELS.get(k, k))
            means.append(cats[k]["mean_sentiment"])
            stds.append(cats[k]["std_sentiment"])
            colors.append(CATEGORY_COLORS.get(k, "#8C8C8C"))
    if not means:
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(labels))
    bars = ax.bar(x, means, yerr=stds, capsize=5, color=colors, edgecolor="white", width=0.6)
    ax.axhline(0, color="#333", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=9)
    ax.set_ylabel("Mean sentiment score")
    ax.set_title("Mean Sentiment by Source Category on /pol/")
    for bar, m in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + (0.02 if m >= 0 else -0.07),
                f"{m:.3f}", ha="center", va="bottom" if m >= 0 else "top", fontsize=8)

    fig.tight_layout()
    fig.savefig(save_path, dpi=200)
    plt.close(fig)
    print(f"Saved {save_path}")


def fig3_comparison_bars(comparison_path: str, save_path: str = "fig3_comparison.png"):
    with open(comparison_path) as f:
        comp = json.load(f)
    ordered_keys = ["mainstream", "alternative", "social_media", "state_funded", "institutional", "other"]
    labels = []
    pol_pcts = []
    can_pcts = []
    colors = []
    for k in ordered_keys:
        if k in comp:
            labels.append(CATEGORY_LABELS.get(k, k))
            pol_pcts.append(comp[k]["pol_pct"])
            can_pcts.append(comp[k]["canada_pct"])
            colors.append(CATEGORY_COLORS.get(k, "#8C8C8C"))
    if not labels:
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(labels))
    width = 0.35
    bars1 = ax.bar(x - width / 2, pol_pcts, width, label="/pol/", color="#C44E52", edgecolor="white")
    bars2 = ax.bar(x + width / 2, can_pcts, width, label="Canadian political corpus", color="#4C72B0", edgecolor="white")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=9)
    ax.set_ylabel("Share of citations (%)")
    ax.set_title("Source Category Comparison: /pol/ vs Canadian Political Corpus")
    ax.legend(fontsize=10)
    for bar in bars1:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.5, f"{h:.1f}%",
                    ha="center", va="bottom", fontsize=7)
    for bar in bars2:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.5, f"{h:.1f}%",
                    ha="center", va="bottom", fontsize=7)
    fig.tight_layout()
    fig.savefig(save_path, dpi=200)
    plt.close(fig)
    print(f"Saved {save_path}")


def fig3_table(comparison_path: str, save_path: str = "fig3_table.png"):
    with open(comparison_path) as f:
        comp = json.load(f)
    ordered_keys = ["mainstream", "alternative", "social_media", "state_funded", "institutional", "other"]
    rows = []
    for k in ordered_keys:
        if k in comp:
            rows.append([
                CATEGORY_LABELS.get(k, k),
                f"{comp[k]['pol_pct']}%",
                f"{comp[k]['pol_count']}",
                f"{comp[k]['pol_mean_sentiment']:.3f}" if comp[k].get("pol_mean_sentiment") is not None else "N/A",
                f"{comp[k]['canada_pct']}%",
                f"{comp[k]['canada_count']}",
                f"{comp[k]['canada_mean_sentiment']:.3f}" if comp[k].get("canada_mean_sentiment") is not None else "N/A",
            ])
    headers = ["Category", "/pol/ %", "/pol/ count", "/pol/ sentiment",
               "Canada %", "Canada count", "Canada sentiment"]
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.axis("off")
    table = ax.table(cellText=rows, colLabels=headers, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.5)
    for (r, c), cell in table.get_celld().items():
        if r == 0:
            cell.set_facecolor("#333333")
            cell.set_text_props(color="white", weight="bold")
        elif r % 2 == 0:
            cell.set_facecolor("#f5f5f5")
    fig.tight_layout()
    fig.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {save_path}")


def generate_all(stats_path: str, csv_path: str | None = None,
                 comparison_path: str | None = None, output_dir: str = "."):
    stats = load_stats(stats_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    fig1_top_domains_bar(stats, save_path=str(out / "fig1_top_domains.png"))
    fig1b_category_pie(stats, save_path=str(out / "fig1b_category_pie.png"))
    fig2_sentiment_scatter(stats, save_path=str(out / "fig2_sentiment_scatter.png"))
    fig2b_category_sentiment_bars(stats, save_path=str(out / "fig2b_category_sentiment.png"))

    if comparison_path:
        fig3_comparison_bars(comparison_path, save_path=str(out / "fig3_comparison.png"))
        fig3_table(comparison_path, save_path=str(out / "fig3_table.png"))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate infographics from pipeline stats")
    parser.add_argument("stats", help="Path to stats JSON (from pipeline)")
    parser.add_argument("--csv", help="Path to posts CSV (for per-post plots)")
    parser.add_argument("--compare", help="Path to comparison JSON")
    parser.add_argument("--outdir", default="figures", help="Output directory")
    args = parser.parse_args()
    generate_all(args.stats, args.csv, args.compare, args.outdir)
