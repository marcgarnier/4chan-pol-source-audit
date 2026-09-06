"""Analyses statistiques du corpus /pol/, telles que spécifiées dans METHODOLOGY.md.

Produit tous les chiffres cités dans l'article : parts de catégories avec
intervalles de Wilson (§3.1), concentration HHI/Gini (§3.1), structure du réseau
de co-citation et assortativité par orientation (§3.3), sous-analyse du cluster
OSINT, et mesure du taux de disparition des posts (§5.1).

**Le sentiment est exclu de l'analyse publiée.** Le modèle n'a jamais été validé
sur du texte /pol/ : l'ironie y est lue au premier degré, les insultes de
registre sont comptées comme de l'hostilité, 42 % des posts cités dépassent la
troncature à 128 tokens, et le score porte sur le post entier plutôt que sur
l'attitude envers la source citée. Publier une mesure invalidée aurait fondé la
conclusion sur un instrument non calibré. Le code reste accessible derrière
`--with-sentiment` pour qui reprendrait le travail après validation annotée.

Lit `pol.db` — la base est la source de vérité.

    python analysis.py                    # tables + results/analysis.json
    python analysis.py --no-figures       # sans les figures
    python analysis.py --with-sentiment   # rejoue les tests exclus
"""
import argparse
import json
import math
import sqlite3
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy import stats

CATEGORY_LABELS = {
    "mainstream": "Mainstream",
    "alternative": "Alternative",
    "state_funded": "State-controlled",
    "social_media": "Social platform",
    "institutional": "Institutional",
    "archive": "Archive / file host",
    "other": "Unclassified",
}

# Les archives ont désormais leur propre catégorie dans le codebook. La
# sous-analyse porte sur le cluster OSINT (cartes de guerre, traceurs AIS/ADS-B),
# annoté en sous-type lors du codage manuel : ~700 citations que la catégorie
# "other" masquait.


# --------------------------------------------------------------------------
# Statistiques élémentaires
# --------------------------------------------------------------------------

def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalle de score de Wilson (1927) — correct pour les cellules extrêmes."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def gini(counts) -> float:
    """Coefficient de Gini sur la distribution des citations par domaine."""
    x = np.sort(np.asarray(counts, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return 0.0
    return float((2 * np.sum((np.arange(1, n + 1)) * x)) / (n * x.sum()) - (n + 1) / n)


def hhi(counts) -> float:
    """Indice de Herfindahl-Hirschman, normalisé dans [0, 1]."""
    x = np.asarray(counts, dtype=float)
    if x.sum() == 0:
        return 0.0
    shares = x / x.sum()
    h = float(np.sum(shares**2))
    n = len(x)
    return h if n <= 1 else (h - 1 / n) / (1 - 1 / n)


def cliffs_delta(a, b) -> float:
    """Cliff's delta via la statistique U de Mann-Whitney : delta = 2U/(n1*n2) - 1."""
    a, b = np.asarray(a), np.asarray(b)
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    u = stats.mannwhitneyu(a, b, alternative="two-sided").statistic
    return float(2 * u / (len(a) * len(b)) - 1)


def interpret_delta(d: float) -> str:
    """Seuils de Romano et al. (2006), la convention usuelle pour Cliff's delta."""
    ad = abs(d)
    if ad < 0.147:
        return "negligible"
    if ad < 0.33:
        return "small"
    if ad < 0.474:
        return "medium"
    return "large"


def dunn_holm(groups: dict[str, np.ndarray]) -> list[dict]:
    """Test post-hoc de Dunn (rangs communs, correction de ties) + descente de Holm."""
    names = list(groups)
    all_vals = np.concatenate([groups[k] for k in names])
    ranks = stats.rankdata(all_vals)
    N = len(all_vals)

    mean_ranks, sizes, off = {}, {}, 0
    for k in names:
        n_k = len(groups[k])
        mean_ranks[k] = float(np.mean(ranks[off : off + n_k]))
        sizes[k] = n_k
        off += n_k

    # correction pour ex aequo
    _, tie_counts = np.unique(all_vals, return_counts=True)
    tie_term = float(np.sum(tie_counts**3 - tie_counts))
    sigma_base = (N * (N + 1) / 12) - tie_term / (12 * (N - 1))

    raw = []
    for a, b in combinations(names, 2):
        se = math.sqrt(sigma_base * (1 / sizes[a] + 1 / sizes[b]))
        z = (mean_ranks[a] - mean_ranks[b]) / se if se > 0 else 0.0
        p = 2 * (1 - stats.norm.cdf(abs(z)))
        raw.append({"a": a, "b": b, "z": float(z), "p_raw": float(p),
                    "delta": cliffs_delta(groups[a], groups[b])})

    # Holm (1979) : descente séquentielle
    order = sorted(range(len(raw)), key=lambda i: raw[i]["p_raw"])
    m, running = len(raw), 0.0
    for rank, i in enumerate(order):
        adj = min(1.0, (m - rank) * raw[i]["p_raw"])
        running = max(running, adj)
        raw[i]["p_holm"] = running
        raw[i]["significant"] = running < 0.05
    for r in raw:
        r["magnitude"] = interpret_delta(r["delta"])
    return sorted(raw, key=lambda r: r["p_holm"])


# --------------------------------------------------------------------------
# Chargement
# --------------------------------------------------------------------------

def load(db_path: str):
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT ci.domain, d.category, ci.compound,
               LENGTH(p.com_text) AS post_len, p.thread_no, p.capture_date,
               COALESCE(t.topic, 'Other / Misc') AS topic
          FROM citations ci
          JOIN domains d USING(domain)
          JOIN posts   p ON p.post_no = ci.post_no
     LEFT JOIN threads t ON t.thread_no = p.thread_no
    """).fetchall()
    meta = {
        "threads": conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0],
        "posts": conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
        "posts_with_links": conn.execute(
            "SELECT COUNT(DISTINCT post_no) FROM citations").fetchone()[0],
        "citations": conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0],
        "domains": conn.execute("SELECT COUNT(*) FROM domains").fetchone()[0],
        "days": conn.execute("SELECT COUNT(DISTINCT capture_date) FROM posts").fetchone()[0],
        "window": conn.execute(
            "SELECT MIN(capture_date), MAX(capture_date) FROM posts").fetchone(),
    }
    conn.close()
    return rows, meta


# --------------------------------------------------------------------------
# Blocs d'analyse
# --------------------------------------------------------------------------

def category_shares(rows, meta):
    counts = Counter(r[1] for r in rows)
    n = sum(counts.values())
    out = []
    for cat, k in counts.most_common():
        lo, hi = wilson_ci(k, n)
        out.append({
            "category": cat, "label": CATEGORY_LABELS.get(cat, cat),
            "n": k, "share": k / n, "ci_low": lo, "ci_high": hi,
        })
    return {"total_citations": n, "categories": out}


def concentration(rows):
    counts = Counter(r[0] for r in rows)
    vals = list(counts.values())
    total = sum(vals)
    ranked = counts.most_common()
    cum = np.cumsum([c for _, c in ranked]) / total
    return {
        "unique_domains": len(counts),
        "gini": gini(vals),
        "hhi_normalized": hhi(vals),
        "top1_domain": ranked[0][0],
        "top1_share": ranked[0][1] / total,
        "top10_share": float(cum[min(9, len(cum) - 1)]),
        "top50_share": float(cum[min(49, len(cum) - 1)]),
        "domains_for_half": int(np.searchsorted(cum, 0.5) + 1),
        "singleton_domains": sum(1 for v in vals if v == 1),
        "top_domains": [{"domain": d, "n": c} for d, c in ranked[:20]],
    }


def sentiment_tests(rows):
    groups = defaultdict(list)
    for _, cat, comp, *_ in rows:
        groups[cat].append(comp)
    groups = {k: np.array(v) for k, v in groups.items()}

    h, p = stats.kruskal(*groups.values())
    n = sum(len(v) for v in groups.values())
    eps2 = float(h / (n - 1))
    return {
        "kruskal_h": float(h), "kruskal_p": float(p),
        "epsilon_squared": eps2,
        "n": n, "k_groups": len(groups),
        "posthoc": dunn_holm(groups),
    }


NEWS_CATEGORIES = ("mainstream", "alternative", "state_funded")


def news_block_test(rows):
    """Médias (toutes catégories) contre non-médias, et homogénéité interne du bloc.

    Le codage manuel fait apparaître que les trois catégories de médias ne se
    distinguent pas entre elles, mais se distinguent nettement du reste. C'est
    ce contraste-là, et non mainstream/alternatif, qui porte le signal.
    """
    news = np.array([r[2] for r in rows if r[1] in NEWS_CATEGORIES])
    rest = np.array([r[2] for r in rows if r[1] not in NEWS_CATEGORIES])
    u = stats.mannwhitneyu(news, rest, alternative="two-sided")

    within = [np.array([r[2] for r in rows if r[1] == cat]) for cat in NEWS_CATEGORIES]
    h, p_within = stats.kruskal(*within)

    return {
        "news_n": int(len(news)), "news_mean": float(news.mean()),
        "news_median": float(np.median(news)),
        "news_negativity": float((news < -0.2).mean()),
        "rest_n": int(len(rest)), "rest_mean": float(rest.mean()),
        "rest_median": float(np.median(rest)),
        "rest_negativity": float((rest < -0.2).mean()),
        "mannwhitney_p": float(u.pvalue),
        "cliffs_delta": cliffs_delta(news, rest),
        "mean_gap": float(news.mean() - rest.mean()),
        "within_news_kruskal_h": float(h),
        "within_news_p": float(p_within),
        "within_news_homogeneous": bool(p_within > 0.05),
    }


def adjusted_model(rows):
    """sentiment ~ catégorie + thème + log(longueur du post) — §3.2."""
    import pandas as pd
    import statsmodels.formula.api as smf

    df = pd.DataFrame(rows, columns=[
        "domain", "category", "compound", "post_len", "thread_no", "capture_date", "topic"])
    df["log_len"] = np.log1p(df["post_len"].fillna(0))
    # référence = social_media, la catégorie la plus fournie
    df["category"] = pd.Categorical(
        df["category"],
        categories=["social_media"] + [c for c in df["category"].unique() if c != "social_media"])
    model = smf.ols("compound ~ C(category) + C(topic) + log_len", data=df).fit(
        cov_type="cluster", cov_kwds={"groups": df["thread_no"]})
    return {
        "r_squared": float(model.rsquared),
        "n_obs": int(model.nobs),
        "n_clusters": int(df["thread_no"].nunique()),
        "coefficients": {
            name: {"beta": float(model.params[name]),
                   "se": float(model.bse[name]),
                   "p": float(model.pvalues[name])}
            for name in model.params.index
        },
        "summary_text": str(model.summary()),
    }


def other_breakdown(rows):
    """Sous-analyse du cluster OSINT à l'intérieur du bucket 'other'.

    Cartes de guerre en direct, traceurs AIS et ADS-B : un comportement de
    sourçage distinct, identifié lors du codage manuel (colonne subtype du
    codebook), que la catégorie fourre-tout masquait entièrement.
    """
    from source_classifier import source_subtype

    other = [r for r in rows if r[1] == "other"]
    osint = [r for r in other if source_subtype(r[0]) == "osint"]
    counts = Counter(r[0] for r in osint)
    vals = np.array([r[2] for r in osint]) if osint else np.array([])
    return {
        "other_total": len(other),
        "osint_citations": len(osint),
        "osint_share_of_other": len(osint) / len(other) if other else 0.0,
        "osint_share_of_all": len(osint) / len(rows),
        "osint_unique_domains": len(counts),
        "osint_mean_sentiment": float(vals.mean()) if len(vals) else float("nan"),
        "residual_other": len(other) - len(osint),
        "top_osint": [{"domain": d, "n": c} for d, c in counts.most_common(10)],
    }


def network_orientation(rows, min_weight=2):
    """Le réseau de co-citation trie-t-il les médias par orientation ?

    Remplace, sans modèle de langue, la question que le sentiment adressait :
    si /pol/ entretenait un « écosystème alternatif » distinct, les domaines
    alternatifs devraient se co-citer entre eux plutôt qu'avec la presse
    établie. Le test de regroupement préserve le degré : les domaines
    alternatifs étant peu cités, une permutation naïve des étiquettes leur
    prêterait une connectivité qu'ils n'ont pas.
    """
    import networkx as nx

    rng = np.random.default_rng(0)
    cat = {r[0]: r[1] for r in rows}
    by_thread = defaultdict(set)
    for domain, _, _, _, thread_no, _, _ in rows:
        by_thread[thread_no].add(domain)

    w = Counter()
    for domains in by_thread.values():
        if 2 <= len(domains) <= 40:
            for a, b in combinations(sorted(domains), 2):
                w[(a, b)] += 1
    g = nx.Graph()
    for (a, b), weight in w.items():
        if weight >= min_weight:
            g.add_edge(a, b, weight=weight)
    if g.number_of_nodes() == 0:
        return {}

    nx.set_node_attributes(g, {d: cat.get(d, "?") for d in g}, "category")
    sub = g.subgraph([n for n in g if cat.get(n) in NEWS_CATEGORIES]).copy()

    deg = dict(sub.degree())
    order = sorted(sub.nodes(), key=lambda n: deg[n])
    labels = [cat[n] for n in order]

    def alt_alt(lbl):
        m = dict(zip(order, lbl))
        return sum(1 for a, b in sub.edges() if m[a] == m[b] == "alternative")

    observed = alt_alt(labels)
    block = 5  # ne permuter qu'entre voisins de degré comparable
    null = []
    for _ in range(5000):
        perm = labels[:]
        for i in range(0, len(perm), block):
            chunk = perm[i : i + block]
            rng.shuffle(chunk)
            perm[i : i + block] = chunk
        null.append(alt_alt(perm))
    null = np.array(null)

    return {
        "full_assortativity": float(nx.attribute_assortativity_coefficient(g, "category")),
        "news_nodes": sub.number_of_nodes(),
        "news_edges": sub.number_of_edges(),
        "news_composition": dict(Counter(cat[n] for n in sub)),
        "news_assortativity": float(nx.attribute_assortativity_coefficient(sub, "category")),
        "alt_alt_observed": int(observed),
        "alt_alt_expected": float(null.mean()),
        "alt_alt_p": float((null >= observed).mean()),
        "mean_degree": {k: float(np.mean([deg[n] for n in sub if cat[n] == k]))
                        for k in NEWS_CATEGORIES if any(cat[n] == k for n in sub)},
    }


def cocitation(rows, min_weight=2):
    """§3.3 : graphe de co-occurrence des domaines dans un même thread + Louvain."""
    import networkx as nx

    cat = {r[0]: r[1] for r in rows}
    by_thread = defaultdict(set)
    for domain, _, _, _, thread_no, _, _ in rows:
        by_thread[thread_no].add(domain)

    w = Counter()
    for domains in by_thread.values():
        if 2 <= len(domains) <= 40:  # ignore les threads-catalogues aberrants
            for a, b in combinations(sorted(domains), 2):
                w[(a, b)] += 1

    g = nx.Graph()
    for (a, b), weight in w.items():
        if weight >= min_weight:
            g.add_edge(a, b, weight=weight)
    if g.number_of_nodes() == 0:
        return {"nodes": 0, "edges": 0, "communities": []}

    comms = nx.community.louvain_communities(g, weight="weight", seed=0)
    comms = sorted(comms, key=len, reverse=True)
    deg = dict(g.degree(weight="weight"))
    return {
        "nodes": g.number_of_nodes(),
        "edges": g.number_of_edges(),
        "density": float(nx.density(g)),
        "modularity": float(nx.community.modularity(g, comms, weight="weight")),
        "n_communities": len(comms),
        "communities": [
            {"size": len(c),
             "composition": dict(Counter(cat.get(d, "?") for d in c).most_common()),
             "members": sorted(c, key=lambda d: -deg[d])[:8]}
            for c in comms[:6]
        ],
    }


def deletion_rate(saves_dir="4TCT/data/saves"):
    """§5.1 : taux de disparition des posts entre deux captures d'un même thread."""
    by_thread = defaultdict(list)
    for day in sorted(Path(saves_dir).iterdir()):
        pol = day / "threads" / "pol"
        if not pol.is_dir():
            continue
        for jf in sorted(pol.glob("*.json")):
            stem = jf.name.split("_")[0]
            if stem.isdigit():
                by_thread[int(stem)].append((day.name, jf))

    pairs, disappeared, observed = [], 0, 0
    for thread_no, caps in by_thread.items():
        if len(caps) < 2:
            continue
        caps.sort()
        for (d1, f1), (d2, f2) in zip(caps, caps[1:]):
            try:
                p1 = json.load(open(f1, encoding="utf-8"))
                p2 = json.load(open(f2, encoding="utf-8"))
            except Exception:
                continue
            s1 = {p["no"] for p in (p1 if isinstance(p1, list) else p1.get("posts", []))}
            s2 = {p["no"] for p in (p2 if isinstance(p2, list) else p2.get("posts", []))}
            if not s1:
                continue
            gone = len(s1 - s2)
            pairs.append({"thread": thread_no, "from": d1, "to": d2,
                          "posts_first": len(s1), "disappeared": gone,
                          "rate": gone / len(s1)})
            disappeared += gone
            observed += len(s1)

    return {
        "thread_pairs": len(pairs),
        "posts_observed": observed,
        "posts_disappeared": disappeared,
        "pooled_rate": disappeared / observed if observed else 0.0,
        "pooled_ci": wilson_ci(disappeared, observed) if observed else (0.0, 0.0),
        "mean_per_thread_rate": float(np.mean([p["rate"] for p in pairs])) if pairs else 0.0,
        "threads_with_any_loss": sum(1 for p in pairs if p["disappeared"] > 0),
    }


def paper_figure(res, rows, path):
    """Figure principale : parts de citations (IC de Wilson) et concentration.

    Les deux panneaux portent le résultat descriptif de l'article — ce que /pol/
    cite, et à quel point c'est concentré — sans dépendre d'aucun modèle.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cats = sorted(res["shares"]["categories"], key=lambda r: -r["n"])
    labels = [c["label"] for c in cats]
    y = np.arange(len(cats))[::-1]
    news = {"mainstream", "alternative", "state_funded"}
    colors = ["#8c2d04" if c["category"] in news else "#1f4e79" for c in cats]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.8))

    share = np.array([c["share"] for c in cats]) * 100
    lo = share - np.array([c["ci_low"] for c in cats]) * 100
    hi = np.array([c["ci_high"] for c in cats]) * 100 - share
    ax1.barh(y, share, color=colors, height=0.62)
    ax1.errorbar(share, y, xerr=[lo, hi], fmt="none", ecolor="#333", capsize=3, lw=1)
    for yi, c in zip(y, cats):
        ax1.text(c["share"] * 100 + 1.5, yi, f"n={c['n']:,}", va="center", fontsize=8)
    ax1.set_yticks(y)
    ax1.set_yticklabels(labels, fontsize=9)
    ax1.set_xlabel("Share of citation events (%, 95% Wilson CI)")
    ax1.set_xlim(0, 58)
    ax1.set_title("(a) What /pol/ cites", loc="left", fontsize=10)
    ax1.text(0.97, 0.06, "news outlets in red\n(12.8% combined)", transform=ax1.transAxes,
             ha="right", fontsize=8, color="#8c2d04")

    counts = np.sort(np.array(list(Counter(r[0] for r in rows).values()), dtype=float))
    cum = np.concatenate([[0], np.cumsum(counts) / counts.sum()])
    x = np.linspace(0, 1, len(cum))
    ax2.plot([0, 1], [0, 1], "--", color="#999", lw=1, label="Perfect equality")
    ax2.plot(x, cum, color="#1f4e79", lw=2,
             label=f"Domains (Gini = {res['concentration']['gini']:.3f})")
    ax2.fill_between(x, cum, x, color="#1f4e79", alpha=0.12)
    ax2.set_xlabel("Cumulative share of unique domains")
    ax2.set_ylabel("Cumulative share of citations")
    ax2.legend(loc="upper left", frameon=False, fontsize=8)
    ax2.set_title("(b) How concentrated", loc="left", fontsize=10)

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300)
    plt.close(fig)
    print(f"Figure sauvegardée : {path}")


def lorenz_figure(rows, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    counts = np.sort(np.array(list(Counter(r[0] for r in rows).values()), dtype=float))
    cum = np.concatenate([[0], np.cumsum(counts) / counts.sum()])
    x = np.linspace(0, 1, len(cum))

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], "--", color="#999", lw=1, label="Perfect equality")
    ax.plot(x, cum, color="#1f4e79", lw=2, label=f"Domains (Gini = {gini(counts):.3f})")
    ax.fill_between(x, cum, x, color="#1f4e79", alpha=0.12)
    ax.set_xlabel("Cumulative share of unique domains")
    ax.set_ylabel("Cumulative share of citations")
    ax.set_title("Concentration of /pol/'s citation distribution")
    ax.legend(loc="upper left", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300)
    plt.close(fig)
    print(f"Figure sauvegardée : {path}")


# --------------------------------------------------------------------------

def main(db, out_json, make_figures, with_sentiment=False):
    rows, meta = load(db)
    if not rows:
        raise SystemExit("Aucune citation en base : lancer build_db.py d'abord.")

    res = {
        "corpus": meta,
        "shares": category_shares(rows, meta),
        "concentration": concentration(rows),
        "network_orientation": network_orientation(rows),
        "other_breakdown": other_breakdown(rows),
        "cocitation": cocitation(rows),
        "deletion": deletion_rate(),
    }

    # Le sentiment est exclu de l'analyse publiée : le modèle n'a jamais été
    # validé sur du texte /pol/ (ironie lue au premier degré, insultes de
    # registre comptées comme hostilité, 42 % des posts tronqués à 128 tokens)
    # et le score porte sur le post entier, pas sur l'attitude envers la source.
    # Le code reste disponible derrière --with-sentiment pour qui voudrait le
    # reprendre après une validation annotée.
    if with_sentiment:
        scored = [r for r in rows if r[2] is not None]
        if scored:
            res["sentiment"] = sentiment_tests(scored)
            res["news_block"] = news_block_test(scored)
            res["adjusted_model"] = adjusted_model(scored)

    c, s = res["corpus"], res["shares"]
    print(f"\nCorpus : {c['posts']:,} posts / {c['threads']:,} threads / "
          f"{c['citations']:,} citations / {c['domains']:,} domaines "
          f"/ {c['days']} jours ({c['window'][0]} -> {c['window'][1]})")

    print(f"\n{'Catégorie':22}{'n':>7}{'part':>9}{'IC 95% (Wilson)':>20}")
    for r in s["categories"]:
        ci = f"[{r['ci_low']*100:.1f}, {r['ci_high']*100:.1f}]"
        print(f"{r['label']:22}{r['n']:>7,}{r['share']*100:>8.1f}%{ci:>20}")

    cc = res["concentration"]
    print(f"\nConcentration : Gini={cc['gini']:.3f}  HHI*={cc['hhi_normalized']:.3f}  "
          f"top-1 ({cc['top1_domain']})={cc['top1_share']*100:.1f}%  "
          f"top-10={cc['top10_share']*100:.1f}%  "
          f"{cc['domains_for_half']} domaines = 50% des citations")

    no = res["network_orientation"]
    if no:
        print(f"\nOrientation dans le réseau de co-citation :")
        print(f"  sous-graphe médias : {no['news_nodes']} noeuds, {no['news_edges']} arêtes")
        print(f"  assortativité par orientation : {no['news_assortativity']:+.4f} "
              f"(graphe complet : {no['full_assortativity']:+.4f})")
        print(f"  arêtes alternative--alternative : observé={no['alt_alt_observed']}, "
              f"attendu={no['alt_alt_expected']:.2f} (degré préservé), "
              f"p={no['alt_alt_p']:.3f}")
        print("  degré moyen : " + ", ".join(f"{k}={v:.1f}" for k, v in no['mean_degree'].items()))

    if with_sentiment and "news_block" in res:
        nb = res["news_block"]
        print(f"\n[--with-sentiment, hors analyse publiée] médias {nb['news_mean']:+.3f} "
              f"vs {nb['rest_mean']:+.3f}, delta={nb['cliffs_delta']:+.3f}")

    ob, dl = res["other_breakdown"], res["deletion"]
    print(f"\nCluster OSINT : {ob['osint_citations']:,} citations "
          f"({ob['osint_share_of_all']*100:.1f}% du total, "
          f"{ob['osint_share_of_other']*100:.1f}% du bucket 'other', "
          f"{ob['osint_unique_domains']} domaines)")
    print(f"Co-citation : {res['cocitation']['nodes']} noeuds, "
          f"{res['cocitation']['edges']} arêtes, "
          f"modularité={res['cocitation']['modularity']:.3f}, "
          f"{res['cocitation']['n_communities']} communautés")
    print(f"Disparition de posts : {dl['posts_disappeared']:,}/{dl['posts_observed']:,} "
          f"= {dl['pooled_rate']*100:.1f}% "
          f"[{dl['pooled_ci'][0]*100:.1f}, {dl['pooled_ci'][1]*100:.1f}] "
          f"sur {dl['thread_pairs']} paires de captures")

    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    serializable = {k2: v for k2, v in res.items()}
    if "adjusted_model" in res:
        serializable["adjusted_model"] = {k2: v for k2, v in res["adjusted_model"].items()
                                          if k2 != "summary_text"}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)
    print(f"\nRésultats complets : {out_json}")

    if make_figures:
        paper_figure(res, rows, "figures_real/fig_main.png")
        lorenz_figure(rows, "figures_real/fig3_lorenz.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Analyses statistiques pour l'article")
    ap.add_argument("--db", default="pol.db")
    ap.add_argument("--out", default="results/analysis.json")
    ap.add_argument("--no-figures", action="store_true")
    ap.add_argument("--with-sentiment", action="store_true",
                    help="Rejoue les tests de sentiment exclus de l'analyse publiée")
    args = ap.parse_args()
    main(args.db, args.out, not args.no_figures, args.with_sentiment)
