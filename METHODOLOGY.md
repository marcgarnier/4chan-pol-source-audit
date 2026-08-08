# Methodology

Design and justification for *The Informational Diet of /pol/*. This document
specifies (1) how source categories are constructed from **external, citable
typologies** rather than ad-hoc judgment, (2) the statistical analysis plan, and
(3) known threats to validity and their mitigations. It is the reference for the
technical paper's *Methods* section.

> **Note on references.** Author–year citations point to the reference list at
> the bottom. Verify every entry (exact year, venue, DOI) against the primary
> source before submission — do not trust this list blind.

---

## 1. Study design

- **Object.** Which external sources the /pol/ community cites, and the tone of
  the discussion surrounding each citation.
- **Unit of analysis.** The *citation event* — one external domain appearing in
  one post. Posts may contain several; each domain is counted once per post
  (deduplicated within a post).
- **Sampling frame.** Live threads on /pol/ captured via the 4chan JSON API
  (through 4TCT) over a bounded collection window. This is a **snapshot** design,
  not a longitudinal one: conclusions hold for the collection window, not for
  /pol/ in general or across time.
- **Current corpus (as of 2026-07-24).** 752 threads, 30,821 posts, 819 posts
  with ≥1 external link (2.7%), 1,135 citation events, 283 unique domains.

---

## 2. Source category construction

### 2.1 The core problem: three axes, not one

The original five-way scheme (Mainstream / Alternative / State-funded / Social
Media / Institutional) silently collapsed **three orthogonal dimensions**, which
is why cases like *Fox News*, *France 24* and *BBC* were impossible to place
consistently:

| Axis | Question | Example values |
|---|---|---|
| **Medium type** | What kind of object is it? | News outlet · social platform · reference work · file host / archive |
| **Editorial orientation** | Where does it sit politically? | left · center-left · center · center-right · right |
| **Ownership / control** | Who controls editorial output? | independent · public-funded-independent · state-controlled |

A single source carries a value on *each* axis (e.g. RT = `news / right /
state-controlled`; BBC = `news / center-left / public-funded-independent`;
France 24 = `news / center / public-funded-independent`). Forcing these into one
mutually-exclusive label is the root of the France 24 vs. BBC inconsistency.

**Design decision.** Code every domain on all three axes independently, using
external typologies for each, then analyze axes separately. Category-level
reporting (the headline "share by category") is derived from the *medium type*
axis, with orientation and control reported as cross-cuts.

### 2.2 External typologies (source of truth)

To make classification **reproducible and non-subjective**, each axis is mapped
to a published rating system rather than author intuition:

| Axis | Primary source | Fallback / cross-check |
|---|---|---|
| Editorial orientation (bias) | **AllSides Media Bias Ratings** (AllSides 2024) | **Ad Fontes Media** bias score (Otero 2021) |
| Factual reliability | **Media Bias/Fact Check (MBFC)** factuality rating | **NewsGuard** score (where available) |
| Ownership / state control | **RSF** ownership data (*Media Ownership Monitor* / World Press Freedom Index, RSF 2024) | Peer-reviewed state-media lists (e.g. Nechushtai & Lewis 2019; academic coding of state-controlled outlets) |
| Medium type | Rule-based (URL/domain structure) — see §2.3 | manual review of top-N domains |

Rationale for choosing rating aggregators: AllSides, MBFC and Ad Fontes are the
labels most widely used as ground truth in computational-social-science work on
news reliability and partisanship (e.g. Bozarth et al. 2020; Robertson et al.
2018 use comparable third-party labels), which makes results comparable to prior
literature and shifts the "why is X here?" burden onto a citable external
authority.

### 2.3 Medium-type coding rules

Deterministic, applied in `source_classifier.py`:

1. **Reference / institutional** — Wikipedia/Wikimedia family; TLDs `.gov`,
   `.mil`, `.edu` (matched by domain suffix so `en.wikipedia.org` resolves).
2. **Social platform** — curated set of platforms (YouTube, X/Twitter, Reddit,
   Telegram, TikTok, Rumble, BitChute, Gab, …), with mobile/short aliases
   normalized to a canonical domain (`youtu.be`, `m.youtube.com` → `youtube.com`).
3. **News outlet** — present in an external rating database (AllSides / MBFC /
   Ad Fontes). Bias and control axes are then attached from those databases.
4. **File host / archive** — a distinct type that must be broken out of "Other"
   (see §4.4): catbox.moe, rentry.org, archive.today, 4plebs, litter.catbox, …
5. **Unclassified ("Other")** — everything else, reported transparently, not
   treated as a meaningful category.

### 2.4 Reproducibility of the coding

- **Codebook.** Every axis value and its external source is recorded per domain
  in a versioned mapping table, so the classification can be regenerated and
  audited.
- **Inter-annotator agreement.** For domains not covered by an external database
  (a non-trivial share on /pol/, which cites obscure sites), two coders annotate
  independently and agreement is quantified with **Cohen's κ** (Cohen 1960) or
  **Krippendorff's α** (Krippendorff 2018); target ≥ 0.80, interpreted per
  Landis & Koch (1977). Disagreements are adjudicated and the codebook updated.
- **Coverage reporting.** The paper reports what fraction of citation events
  were labeled by external databases vs. manual coding vs. left unclassified.

---

## 3. Analysis plan

### 3.1 Descriptive (feasible now, n ≈ 819)

- **Category shares** with **95% confidence intervals**. Use the **Wilson score
  interval** (Wilson 1927) for proportions — it behaves correctly for small or
  extreme cells, unlike the normal approximation. Categories whose n is too
  small for inference (currently Alternative n=6, State-controlled n=1) are
  reported as "negligible, n insufficient for inference", which is itself a
  finding: /pol/ almost never cites the legacy or state press.
- **Concentration / diversity of sourcing.** Quantify "YouTube dominates" (340 /
  1,135 ≈ 30% of all citations) with the **Herfindahl–Hirschman Index** and the
  **Gini coefficient** over the domain distribution; a Lorenz curve visualizes
  informational concentration. This directly measures the *diversity* of /pol/'s
  information diet.

### 3.2 Inferential (sentiment ~ category)

- **Omnibus test.** Whether the discussion tone differs across categories:
  **Kruskal–Wallis** (Kruskal & Wallis 1952) — non-parametric, appropriate given
  the non-normal, bounded sentiment distribution — rather than one-way ANOVA.
- **Post-hoc.** Pairwise **Dunn** tests with **Holm correction** (Holm 1979) for
  multiple comparisons.
- **Effect sizes, always.** Report **ε²**/**η²** and pairwise **Cliff's delta**
  (Cliff 1993), not p-values alone: with large n everything becomes
  "significant", so effect size carries the substantive claim.
- **Adjusted model.** A regression `sentiment ~ category + topic + post_length`
  to isolate the category effect from confounds (thread topic, verbosity).

### 3.3 Structural

- **Co-citation network.** Domains co-occurring within a thread → weighted
  co-occurrence graph; community detection (e.g. Louvain) surfaces sourcing
  "ecosystems" (which sources travel together).

---

## 4. Sentiment measurement and its validation

### 4.1 Model

`cardiffnlp/twitter-roberta-base-sentiment-latest` (Barbieri et al. 2020,
TweetEval; Loureiro et al. 2022, TimeLMs). Three-way (neg/neu/pos) softmax,
collapsed to a compound score in [−1, +1].

### 4.2 The proxy caveat (a validity threat, not a footnote)

The score is computed over the **entire post**, so it measures the **tone of the
discourse surrounding a citation**, *not* the author's attitude toward the cited
source. "CNN is garbage, here's proof" yields a negative score attached to CNN,
even though the poster endorses the link. The paper must either (a) frame the
metric explicitly as *ambient discourse tone*, or (b) upgrade to
**target-dependent / stance detection** (Mohammad et al. 2016; aspect-based
sentiment, Pontiki et al. 2016), which identifies the opinion *target* — a
harder task with no off-the-shelf model for 4chan text.

### 4.3 Domain-shift validation (required before any sentiment claim)

RoBERTa was trained on Twitter, never on /pol/'s slang, irony, and toxicity →
systematic measurement error. Mitigation: **hand-annotate a random sample of
100–200 posts**, report model–human agreement (κ / correlation). Sentiment
results are not interpretable without this validation step.

### 4.4 The "Other" category is not neutral

At ~35–45% of citations, "Other" is the largest bucket and currently
meaningless. Breaking out **file hosts and archives** (catbox.moe, rentry.org,
archive.today, 4plebs) is not cleanup — it *is* a sourcing behavior: routing
around moderation and preserving deleted content. This deserves its own
sub-analysis.

---

## 5. Threats to validity

### 5.1 Survivorship / deletion bias — the primary threat

**This is the study's most serious limitation and must be stated prominently, not
buried in a table.** The corpus is built by polling *live* threads through the
4chan JSON API (via 4TCT) on a fixed cadence. Two mechanisms remove content
before it can be captured, and both are **non-random in the direction of the
phenomenon under study**:

1. **Moderator deletion.** /pol/'s most extreme content is disproportionately
   removed by moderation. What survives long enough to be scraped is a *filtered*
   view — systematically less extreme than what was actually posted. An audit of
   the board's information diet therefore **undercounts precisely the behavior it
   claims to measure.**
2. **Capture-cadence gaps.** Threads that are born *and* die between two polling
   cycles are never seen at all. This is a stronger problem than archive
   incompleteness (e.g. 4plebs): we do not even rely on an archive — fast-moving
   threads simply never enter the frame.

**Scope of the damage differs by estimand — this bounds, but does not excuse, the
problem:**

- **Source-distribution estimates** (e.g. "54% of citations are social
  platforms") are *relatively* robust: deletion would have to be **correlated
  with the category of the cited source** to bias these proportions, which is
  plausibly a weak effect.
- **Sentiment / tone estimates** are *directly* exposed: deletion correlates
  strongly with the extremity of discourse, which is exactly what the sentiment
  score captures. Any sentiment claim inherits this bias at full strength.

**Mitigations (partial — this cannot be fully corrected):**

- **Quantify the loss.** Compare consecutive scrapes of the same threads to
  measure the rate at which posts/threads disappear, and report it as a figure.
  This converts a qualitative caveat into a measured quantity.
- **Reframe every claim.** The corpus represents the **surviving, publicly
  visible discourse** of /pol/ over the collection window — not "/pol/ discourse"
  in general. All conclusions are scoped accordingly.
- **Acknowledge the irreducible residual.** No sampling design over live 4chan
  data eliminates this; it is a structural feature of the medium.

### 5.2 Threats summary

| Threat | Nature | Mitigation |
|---|---|---|
| **Survivorship / deletion bias** | **Sampling bias (non-random, aligned with the phenomenon)** | **See §5.1 — quantify loss rate, reframe as "surviving discourse", scope all claims; hits sentiment far harder than source distribution** |
| Sentiment ≠ stance toward source | Construct validity | Reframe as ambient tone, or do stance detection (§4.2) |
| Model domain shift (Twitter → /pol/) | Measurement error | Human-annotated validation sample (§4.3) |
| Subjective category coding | Construct validity | Anchor to external typologies (§2.2); double-code residual domains, report Krippendorff's α / Cohen's κ ≥ 0.80 (§2.4) |
| Temporal representativeness | External validity | Collection window ≠ /pol/ in general; scope all claims to the window |
| Rating-database bias | Instrument validity | AllSides/MBFC labels are themselves contested (Bozarth et al. 2020); report which database, use ≥2 as cross-check, publish disagreements |
| Small cells | Statistical power | No inference on categories with insufficient n; report as descriptive only |
| Bot / spam / raids | Data quality | 4chan has no accounts; flag coordinated link-spam bursts before aggregating |

---

## References

*Verify all entries against primary sources before use.*

- AllSides. (2024). *AllSides Media Bias Ratings*. https://www.allsides.com/media-bias
- Barbieri, F., Camacho-Collados, J., Neves, L., & Espinosa-Anke, L. (2020). *TweetEval: Unified Benchmark and Comparative Evaluation for Tweet Classification*. Findings of EMNLP 2020.
- Bozarth, L., Saraf, A., & Budak, C. (2020). *Higher Ground? How Groundtruth Labeling Impacts Our Understanding of Fake News about the 2016 U.S. Presidential Nominees*. ICWSM 2020.
- Cliff, N. (1993). *Dominance statistics: Ordinal analyses to answer ordinal questions*. Psychological Bulletin, 114(3).
- Cohen, J. (1960). *A coefficient of agreement for nominal scales*. Educational and Psychological Measurement, 20(1).
- Hine, G. E., Onaolapo, J., De Cristofaro, E., Kourtellis, N., Leontiadis, I., Samaras, R., Stringhini, G., & Blackburn, J. (2017). *Kek, Cucks, and God Emperor Machine Learning: A Measurement Study of 4chan's Politically Incorrect Board*. ICWSM 2017.
- Holm, S. (1979). *A simple sequentially rejective multiple test procedure*. Scandinavian Journal of Statistics, 6(2).
- Krippendorff, K. (2018). *Content Analysis: An Introduction to Its Methodology* (4th ed.). SAGE.
- Kruskal, W. H., & Wallis, W. A. (1952). *Use of ranks in one-criterion variance analysis*. Journal of the American Statistical Association, 47(260).
- Landis, J. R., & Koch, G. G. (1977). *The measurement of observer agreement for categorical data*. Biometrics, 33(1).
- Loureiro, D., Barbieri, F., Neves, L., Espinosa-Anke, L., & Camacho-Collados, J. (2022). *TimeLMs: Diachronic Language Models from Twitter*. ACL 2022 (Demo).
- Media Bias/Fact Check. *MBFC methodology and ratings*. https://mediabiasfactcheck.com/
- Mohammad, S., Kiritchenko, S., Sobhani, P., Zhu, X., & Cherry, C. (2016). *SemEval-2016 Task 6: Detecting Stance in Tweets*. SemEval 2016.
- Nechushtai, E., & Lewis, S. C. (2019). *What kind of news gatekeepers do we want machines to be?* (on algorithmic and institutional gatekeeping; for state/independent framing). Computers in Human Behavior, 90.
- Otero, V. (2021). *Ad Fontes Media Bias Chart methodology*. Ad Fontes Media. https://adfontesmedia.com/
- Papasavva, A., Zannettou, S., De Cristofaro, E., Stringhini, G., & Blackburn, J. (2020). *Raiders of the Lost Kek: 3.5 Years of Augmented 4chan Posts from the Politically Incorrect Board*. ICWSM 2020.
- Pontiki, M., Galanis, D., Papageorgiou, H., et al. (2016). *SemEval-2016 Task 5: Aspect-Based Sentiment Analysis*. SemEval 2016.
- Reporters Without Borders (RSF). (2024). *World Press Freedom Index* and *Media Ownership Monitor*. https://rsf.org/
- Robertson, R. E., Jiang, S., Joseph, K., Friedland, L., Lazer, D., & Wilson, C. (2018). *Auditing Partisan Audience Bias within Google Search*. CSCW 2018.
- Wilson, E. B. (1927). *Probable inference, the law of succession, and statistical inference*. Journal of the American Statistical Association, 22(158).
