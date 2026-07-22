import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup
from tqdm import tqdm

from source_classifier import normalize_domain, classify_source, CATEGORY_NAMES


TOPIC_KEYWORDS = {
    "Geopolitics / War": [
        "war", "ukraine", "russia", "israel", "palestine", "gaza",
        "military", "iran", "taiwan", "china", "conflict", "nato",
    ],
    "Elections / Politics": [
        "election", "vote", "trump", "biden", "candidate",
        "democrat", "republican", "harris", "president",
    ],
    "Economy / Finance": [
        "inflation", "economy", "stock", "market", "tax",
        "money", "crypto", "job", "recession", "budget",
    ],
    "Identity / Society": [
        "immigrant", "border", "race", "woke", "lgbt",
        "transgender", "crime", "police", "migrant", "gender",
    ],
}

DEFAULT_TOPIC = "Other / Misc"

SOURCE_CATEGORIES = ["Mainstream", "Alternative", "State-funded", "Social Media", "Institutional", "Other"]


def classify_topic(text: str) -> str:
    text_lower = text.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return topic
    return DEFAULT_TOPIC


URL_REGEX = re.compile(
    r"https?://(?:[a-zA-Z0-9.-]+)(?:/[^\s<>\"']*)?"
)


def parse_external_urls(html_content: str) -> list[str]:
    if not html_content:
        return []
    html_content = re.sub(r"<wbr>", "", html_content)
    domains = []
    seen = set()

    for match in URL_REGEX.finditer(html_content):
        url = match.group(0)
        domain = normalize_domain(url)
        if not domain:
            continue
        if "4chan.org" in domain or "boards.4chan" in domain:
            continue
        if domain in seen:
            continue
        seen.add(domain)
        domains.append(domain)

    return domains


def process(jsonl_path: str):
    print(f"Lecture de : {jsonl_path}")
    op_topics = {}
    all_posts = []

    # Passe 1 : identifier les OPs et leur sujet
    with open(jsonl_path, "r") as f:
        for line in tqdm(f, desc="Passe 1 — OPs", unit=" posts"):
            line = line.strip()
            if not line:
                continue
            try:
                post = json.loads(line)
            except json.JSONDecodeError:
                continue
            all_posts.append(post)
            if post.get("resto") == 0:
                semantic_url = post.get("semantic_url", "") or ""
                sub = post.get("sub", "") or ""
                op_text = f"{semantic_url} {sub}".strip()
                topic = classify_topic(op_text) if op_text else DEFAULT_TOPIC
                op_topics[post["no"]] = topic

    print(f"  OPs trouvés : {len(op_topics)}")
    print(f"  Posts totaux : {len(all_posts)}")

    # Stats par sujet
    topic_post_count = defaultdict(int)
    topic_link_count = defaultdict(int)
    matrix = defaultdict(lambda: defaultdict(int))

    # Passe 2 : parser les liens, croiser avec le sujet
    for post in tqdm(all_posts, desc="Passe 2 — Liens", unit=" posts"):
        post_no = post.get("no")
        resto = post.get("resto")

        # Déterminer le sujet du post
        if resto == 0:
            topic = op_topics.get(post_no, DEFAULT_TOPIC)
        else:
            topic = op_topics.get(resto, DEFAULT_TOPIC)

        topic_post_count[topic] += 1

        com = post.get("com", "")
        domains = parse_external_urls(com)
        if domains:
            topic_link_count[topic] += 1
            for domain in domains:
                cat = classify_source(domain)
                matrix[topic][cat] += 1

    # Affichage console
    print()
    print("=" * 90)
    print(f"{'Sujet':<25} {'Posts':>8} {'Avec lien':>10} {'Taux src.':>9}", end="")
    for cat in SOURCE_CATEGORIES:
        print(f" {cat:>14}", end="")
    print()
    print("=" * 90)

    topic_order = list(TOPIC_KEYWORDS.keys()) + [DEFAULT_TOPIC]
    for topic in topic_order:
        total = topic_post_count.get(topic, 0)
        linked = topic_link_count.get(topic, 0)
        sourcing_rate = linked / total * 100 if total > 0 else 0.0
        row_cats = matrix.get(topic, {})
        cat_total = sum(row_cats.values()) or 1

        print(f"{topic:<25} {total:>8} {linked:>10} {sourcing_rate:>7.1f}%", end="")
        for cat in SOURCE_CATEGORIES:
            pct = row_cats.get(cat, 0) / cat_total * 100
            print(f" {pct:>13.1f}%", end="")
        print()

    print()
    print(f"TOTAL{'':<19} {sum(topic_post_count.values()):>8} {sum(topic_link_count.values()):>10}", end="")
    total_all = sum(topic_post_count.values()) or 1
    print(f" {sum(topic_link_count.values())/total_all*100:>7.1f}%")

    return matrix, topic_post_count, topic_link_count


def plot_topic_source_matrix(matrix: dict, output_dir: str = "outputs"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    colors = {
        "Mainstream": "#4C72B0",
        "Alternative": "#DD8452",
        "State-funded": "#C44E52",
        "Social Media": "#55A868",
        "Institutional": "#8172B2",
        "Other": "#8C8C8C",
    }

    topic_order = list(TOPIC_KEYWORDS.keys()) + [DEFAULT_TOPIC]
    cats = ["Mainstream", "Alternative", "State-funded", "Social Media", "Institutional", "Other"]

    labels = []
    percentages = []
    for topic in topic_order:
        if topic not in matrix or sum(matrix[topic].values()) == 0:
            continue
        labels.append(topic)
        row = matrix[topic]
        total = sum(row.values())
        percentages.append([row.get(c, 0) / total * 100 for c in cats])

    if not percentages:
        print("Aucune donnée à plotter.")
        return

    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(labels))
    bottom = np.zeros(len(labels))

    for i, cat in enumerate(cats):
        vals = [p[i] for p in percentages]
        ax.bar(x, vals, bottom=bottom, label=cat,
               color=colors.get(cat, "#8C8C8C"), width=0.6, edgecolor="white")
        bottom += np.array(vals)

    ax.set_xlabel("Thread topic", fontsize=12)
    ax.set_ylabel("Share of cited sources (%)", fontsize=12)
    ax.set_title("Source category by thread topic on /pol/", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=10)
    ax.legend(loc="upper right", fontsize=10, framealpha=0.9)
    ax.set_ylim(0, 105)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    out_path = Path(output_dir) / "topic_source_matrix.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Graphique sauvegardé : {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python topic_source_matrix.py <fichier.jsonl> [--plot]")
        sys.exit(1)

    jsonl_path = sys.argv[1]
    matrix, topic_post_count, topic_link_count = process(jsonl_path)

    if "--plot" in sys.argv:
        plot_topic_source_matrix(matrix)
