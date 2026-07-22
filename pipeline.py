import json
import csv
import html
import re
from pathlib import Path
from collections import Counter, defaultdict
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from tqdm import tqdm
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import numpy as np


DOMAIN_MAPPING = {
    "twitter.com": "x_twitter",
    "x.com": "x_twitter",
    "bbc.com": "bbc",
    "bbc.co.uk": "bbc",
    "theguardian.com": "guardian",
    "youtu.be": "youtube",
    "reddit.com": "reddit",
    "redd.it": "reddit",
    "nytimes.com": "nytimes",
    "nyti.ms": "nytimes",
}

LEGACY_MAINSTREAM = {
    "cnn.com", "nytimes.com", "bbc.com", "bbc.co.uk", "theguardian.com",
    "washingtonpost.com", "reuters.com", "apnews.com", "npr.org",
    "cbc.ca", "lemonde.fr", "lefigaro.fr", "elmundo.es", "elpais.com",
    "spiegel.de", "zeit.de", "corriere.it", "repubblica.it",
    "bloomberg.com", "wsj.com", "economist.com", "ft.com",
    "time.com", "newsweek.com", "theatlantic.com", "newyorker.com",
    "abcnews.go.com", "cbsnews.com", "nbcnews.com",
    "globalnews.ca", "ctvnews.ca", "thestar.com", "globeandmail.com",
}

ALTERNATIVE_MEDIA = {
    "breitbart.com", "epochtimes.com", "rebelnews.com", "foxnews.com",
    "dailywire.com", "zerohedge.com", "infowars.com", "truthsocial.com",
    "thepostmillennial.com", "lifezette.com", "westernjournal.com",
    "americanthinker.com", "frontpagemag.com", "newsmax.com",
    "oann.com", "theblaze.com", "townhall.com", "nationalreview.com",
    "washingtontimes.com", "dailymail.co.uk", "express.co.uk",
    "rt.com", "sputniknews.com", "tass.com",
    "unherd.com", "quillette.com", "spiked-online.com",
}

STATE_FUNDED = {
    "rt.com", "sputniknews.com", "tass.com", "xinhuanet.com",
    "cgtn.com", "globaltimes.cn", "farsnews.ir", "presstv.ir",
    "koreantimes.com", "trtworld.com", "china.org.cn",
    "france24.com",
}

SOCIAL_PLATFORMS = {
    "twitter.com", "x.com", "reddit.com", "redd.it", "youtube.com",
    "youtu.be", "tiktok.com", "instagram.com", "facebook.com",
    "fb.com", "linkedin.com", "t.me", "telegram.org", "discord.com",
    "discord.gg", "twitch.tv", "rumble.com", "odysee.com",
    "bitchute.com", "gab.com", "gab.ai", "parler.com",
    "mewe.com", "vk.com", "truthsocial.com",
}

INSTITUTIONAL = {
    "wikipedia.org", "wikidata.org", "wikimedia.org",
    "gov", "mil", "edu",
}


def normalize_domain(domain: str) -> str:
    domain = domain.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    domain = DOMAIN_MAPPING.get(domain, domain)
    return domain


def classify_source(domain: str) -> str:
    if domain in LEGACY_MAINSTREAM:
        return "mainstream"
    if domain in STATE_FUNDED:
        return "state_funded"
    if domain in ALTERNATIVE_MEDIA:
        return "alternative"
    if domain in SOCIAL_PLATFORMS:
        return "social_media"
    tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
    if tld in ("gov", "mil", "edu"):
        return "institutional"
    if domain in INSTITUTIONAL:
        return "institutional"
    return "other"


def extract_domains_from_post(post: dict) -> list[dict]:
    html_content = post.get("com", "")
    if not html_content:
        return []
    entries = []
    soup = BeautifulSoup(html_content, "html.parser")
    for link in soup.find_all("a"):
        href = link.get("href")
        if not href:
            continue
        parsed = urlparse(href)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        if not domain:
            continue
        if "4chan.org" in domain or "boards.4chan" in domain:
            continue
        normalized = normalize_domain(domain)
        entries.append({
            "raw_domain": domain,
            "domain": normalized,
            "category": classify_source(normalized),
            "url": href,
        })
    return entries


def clean_text(raw_html: str) -> str:
    text = BeautifulSoup(raw_html, "html.parser").get_text(separator=" ")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class SentimentAnalyzer:
    def __init__(self, model_name: str = "cardiffnlp/twitter-roberta-base-sentiment-latest"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name).to(self.device)
        self.model.eval()

    def predict(self, texts: list[str], batch_size: int = 64) -> list[dict]:
        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            encoded = self.tokenizer(
                batch, padding=True, truncation=True, max_length=128, return_tensors="pt"
            ).to(self.device)
            with torch.no_grad():
                logits = self.model(**encoded).logits
            probs = torch.softmax(logits, dim=-1).cpu().numpy()
            for prob in probs:
                negative, neutral, positive = prob
                score = -1.0 * negative + 0.0 * neutral + 1.0 * positive
                results.append({
                    "neg_score": float(negative),
                    "neu_score": float(neutral),
                    "pos_score": float(positive),
                    "compound": float(score),
                })
        return results


class ResearchPipeline:
    def __init__(self, sentiment_model: str = "cardiffnlp/twitter-roberta-base-sentiment-latest"):
        self.sentiment = SentimentAnalyzer(sentiment_model)
        self.domain_counter = Counter()
        self.category_counter = Counter()
        self.domain_sentiments = defaultdict(list)
        self.category_sentiments = defaultdict(list)
        self.post_records = []

    def load_and_parse(self, jsonl_path: str, sample: int | None = None):
        posts = []
        with open(jsonl_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    posts.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if sample:
            posts = posts[:sample]
        return posts

    def extract_urls_batch(self, posts: list[dict]) -> list[dict]:
        records = []
        for post in tqdm(posts, desc="Extracting URLs"):
            text = clean_text(post.get("com", ""))
            domains = extract_domains_from_post(post)
            if not domains:
                continue
            main_domain = domains[0]
            records.append({
                "post_id": post.get("no"),
                "text": text,
                "domains": domains,
                "primary_domain": main_domain["domain"],
                "primary_category": main_domain["category"],
            })
        return records

    def compute_sentiment(self, records: list[dict]):
        texts = [r["text"] for r in records]
        sentiments = self.sentiment.predict(texts)
        for rec, sent in zip(records, sentiments):
            rec["sentiment"] = sent
            self.domain_counter[rec["primary_domain"]] += 1
            self.category_counter[rec["primary_category"]] += 1
            self.domain_sentiments[rec["primary_domain"]].append(sent["compound"])
            self.category_sentiments[rec["primary_category"]].append(sent["compound"])
        self.post_records = records

    def summary_stats(self) -> dict:
        def summarize(scores: list[float]) -> dict:
            arr = np.array(scores)
            return {
                "count": int(len(arr)),
                "mean_sentiment": float(np.mean(arr)),
                "std_sentiment": float(np.std(arr)),
                "negativity_ratio": float(np.mean(arr < -0.2)),
            }

        domains_top = self.domain_counter.most_common(50)
        domain_stats = {}
        for d, c in domains_top:
            scores = self.domain_sentiments.get(d, [])
            if scores:
                domain_stats[d] = summarize(scores)

        category_stats = {}
        for cat in ("mainstream", "alternative", "social_media", "state_funded", "institutional", "other"):
            scores = self.category_sentiments.get(cat, [])
            if scores:
                category_stats[cat] = summarize(scores)

        return {
            "total_posts_with_links": len(self.post_records),
            "total_domains_seen": len(self.domain_counter),
            "top_domains": domain_stats,
            "categories": category_stats,
        }

    def export_csv(self, path: str):
        fieldnames = [
            "post_id", "primary_domain", "primary_category",
            "compound", "neg_score", "neu_score", "pos_score",
            "text_preview",
        ]
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for rec in self.post_records:
                sent = rec.get("sentiment", {})
                writer.writerow({
                    "post_id": rec["post_id"],
                    "primary_domain": rec["primary_domain"],
                    "primary_category": rec["primary_category"],
                    "compound": sent.get("compound"),
                    "neg_score": sent.get("neg_score"),
                    "neu_score": sent.get("neu_score"),
                    "pos_score": sent.get("pos_score"),
                    "text_preview": rec["text"][:200],
                })

    def export_stats_json(self, path: str):
        with open(path, "w") as f:
            json.dump(self.summary_stats(), f, indent=2)

    def run(self, jsonl_path: str, output_prefix: str = "results", sample: int | None = None):
        posts = self.load_and_parse(jsonl_path, sample=sample)
        records = self.extract_urls_batch(posts)
        self.compute_sentiment(records)
        self.export_csv(f"{output_prefix}_posts.csv")
        self.export_stats_json(f"{output_prefix}_stats.json")
        return self.summary_stats()


def compare_corpora(pol_stats: dict, canadian_stats: dict) -> dict:
    pol_cats = pol_stats.get("categories", {})
    can_cats = canadian_stats.get("categories", {})
    all_cats = set(pol_cats) | set(can_cats)
    comparison = {}
    for cat in sorted(all_cats):
        p = pol_cats.get(cat, {})
        c = can_cats.get(cat, {})
        p_total = pol_stats.get("total_posts_with_links", 1)
        c_total = canadian_stats.get("total_posts_with_links", 1)
        comparison[cat] = {
            "pol_count": p.get("count", 0),
            "pol_pct": round(p.get("count", 0) / p_total * 100, 1),
            "pol_mean_sentiment": p.get("mean_sentiment"),
            "canada_count": c.get("count", 0),
            "canada_pct": round(c.get("count", 0) / c_total * 100, 1),
            "canada_mean_sentiment": c.get("mean_sentiment"),
        }
    return comparison


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="4chan /pol/ source audit pipeline")
    parser.add_argument("input", help="Path to 4TCT JSONL file")
    parser.add_argument("--output", default="results", help="Output prefix")
    parser.add_argument("--sample", type=int, help="Sample N posts (for testing)")
    parser.add_argument("--compare", help="Path to Canadian corpus JSONL for comparison")
    args = parser.parse_args()

    pipe = ResearchPipeline()
    stats = pipe.run(args.input, args.output, sample=args.sample)
    print(json.dumps(stats, indent=2))

    if args.compare:
        pipe2 = ResearchPipeline()
        can_stats = pipe2.run(args.compare, "canada_results", sample=args.sample)
        comparison = compare_corpora(stats, can_stats)
        print("\n=== COMPARISON TABLE ===")
        print(json.dumps(comparison, indent=2))
        with open(f"{args.output}_comparison.json", "w") as f:
            json.dump(comparison, f, indent=2)
