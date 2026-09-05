import csv
import re
from pathlib import Path
from urllib.parse import urlparse

# Codebook manuel (METHODOLOGY §2.4) : mapping versionné domaine -> catégorie,
# issu de l'annotation à la main du 2026-09-05. Il a priorité sur les listes
# ci-dessous, qui restent la règle par défaut pour les domaines non annotés.
CODEBOOK_PATH = Path(__file__).with_name("domain_codebook.csv")


def _load_codebook(path: Path = CODEBOOK_PATH) -> tuple[dict, dict]:
    """Retourne (domaine -> catégorie, domaine -> sous-type)."""
    cats, subs = {}, {}
    if not path.exists():
        return cats, subs
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            domain = (row.get("domain") or "").strip().lower()
            category = (row.get("category") or "").strip()
            if domain and category:
                cats[domain] = category
                if row.get("subtype"):
                    subs[domain] = row["subtype"].strip()
    return cats, subs


CODEBOOK, CODEBOOK_SUBTYPES = _load_codebook()

# Alias → domaine canonique (un seul domaine par entité pour éviter le double comptage)
DOMAIN_ALIASES = {
    "x.com": "twitter.com",
    "mobile.twitter.com": "twitter.com",
    "youtu.be": "youtube.com",
    "m.youtube.com": "youtube.com",
    "redd.it": "reddit.com",
    "nyti.ms": "nytimes.com",
    "bbc.co.uk": "bbc.com",
    "fb.com": "facebook.com",
    "gab.ai": "gab.com",
    "telegram.org": "t.me",
    "discord.gg": "discord.com",
}

LEGACY_MAINSTREAM = {
    "cnn.com", "nytimes.com", "bbc.com", "theguardian.com",
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
    "dailywire.com", "zerohedge.com", "infowars.com",
    "thepostmillennial.com", "lifezette.com", "westernjournal.com",
    "americanthinker.com", "frontpagemag.com", "newsmax.com",
    "oann.com", "theblaze.com", "townhall.com", "nationalreview.com",
    "washingtontimes.com", "dailymail.co.uk", "express.co.uk",
    "unherd.com", "quillette.com", "spiked-online.com",
}

STATE_FUNDED = {
    "rt.com", "sputniknews.com", "tass.com", "xinhuanet.com",
    "cgtn.com", "globaltimes.cn", "farsnews.ir", "presstv.ir",
    "koreantimes.com", "trtworld.com", "china.org.cn",
    "france24.com",
}

SOCIAL_PLATFORMS = {
    "twitter.com", "reddit.com", "youtube.com",
    "tiktok.com", "instagram.com", "facebook.com",
    "linkedin.com", "t.me", "discord.com",
    "twitch.tv", "rumble.com", "odysee.com",
    "bitchute.com", "gab.com", "parler.com",
    "mewe.com", "vk.com", "truthsocial.com",
}

INSTITUTIONAL = {
    "wikipedia.org", "wikidata.org", "wikimedia.org",
}

# Clés canoniques (snake_case) utilisées partout : stats JSON, CSV, viz
CATEGORY_KEYS = [
    "mainstream",
    "alternative",
    "state_funded",
    "social_media",
    "institutional",
    "archive",
    "other",
]

CATEGORY_LABELS = {
    "mainstream": "Mainstream",
    "alternative": "Alternative",
    "state_funded": "State-controlled",
    "social_media": "Social platform",
    "institutional": "Institutional",
    "archive": "Archive / file host",
    "other": "Unclassified",
}

# Regex partagée d'extraction d'URLs dans le HTML des posts
URL_REGEX = re.compile(r"https?://(?:[a-zA-Z0-9.-]+)(?:/[^\s<>\"']*)?")


def normalize_domain(url_or_domain: str) -> str:
    """Accepte une URL complète OU un domaine nu, retourne le domaine canonique."""
    value = url_or_domain.strip()
    if "://" in value:
        domain = urlparse(value).netloc
    else:
        # urlparse("youtube.com").netloc == "" — traiter le domaine nu directement
        domain = value.split("/", 1)[0]
    domain = domain.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return DOMAIN_ALIASES.get(domain, domain)


def _in_set(domain: str, domain_set: set[str]) -> bool:
    """Match exact ou par suffixe de sous-domaine (en.wikipedia.org → wikipedia.org)."""
    if domain in domain_set:
        return True
    parts = domain.split(".")
    for i in range(1, len(parts) - 1):
        if ".".join(parts[i:]) in domain_set:
            return True
    return False


def source_subtype(domain: str) -> str:
    """Sous-type annoté (ex. 'osint') ou chaîne vide. Sert aux sous-analyses."""
    return CODEBOOK_SUBTYPES.get(domain, "")


def classify_source(domain: str) -> str:
    """Retourne une clé de CATEGORY_KEYS.

    Le codebook manuel est consulté en premier : il corrige les domaines que les
    listes par défaut ne connaissent pas (presse britannique, australienne,
    israélienne, ukrainienne) et applique la règle de financement retenue lors de
    l'annotation. State-funded reste testé avant Alternative (RT, TASS…).
    """
    if domain in CODEBOOK:
        return CODEBOOK[domain]
    if _in_set(domain, STATE_FUNDED):
        return "state_funded"
    if _in_set(domain, LEGACY_MAINSTREAM):
        return "mainstream"
    if _in_set(domain, ALTERNATIVE_MEDIA):
        return "alternative"
    if _in_set(domain, SOCIAL_PLATFORMS):
        return "social_media"
    tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
    if tld in ("gov", "mil", "edu"):
        return "institutional"
    if _in_set(domain, INSTITUTIONAL):
        return "institutional"
    return "other"


def extract_domains(html_content: str) -> list[str]:
    """Extrait les domaines externes normalisés (dédupliqués) du HTML d'un post."""
    if not html_content:
        return []
    html_content = html_content.replace("<wbr>", "")
    domains = []
    seen = set()
    for match in URL_REGEX.finditer(html_content):
        domain = normalize_domain(match.group(0))
        if not domain or "4chan" in domain:
            continue
        if domain in seen:
            continue
        seen.add(domain)
        domains.append(domain)
    return domains
