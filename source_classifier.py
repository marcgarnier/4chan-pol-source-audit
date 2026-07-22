from urllib.parse import urlparse

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

CATEGORY_NAMES = [
    "Mainstream",
    "Alternative",
    "State-funded",
    "Social Media",
    "Institutional",
]


def normalize_domain(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    domain = DOMAIN_MAPPING.get(domain, domain)
    return domain


def classify_source(domain: str) -> str:
    if domain in LEGACY_MAINSTREAM:
        return "Mainstream"
    if domain in STATE_FUNDED:
        return "State-funded"
    if domain in ALTERNATIVE_MEDIA:
        return "Alternative"
    if domain in SOCIAL_PLATFORMS:
        return "Social Media"
    tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
    if tld in ("gov", "mil", "edu"):
        return "Institutional"
    if domain in INSTITUTIONAL:
        return "Institutional"
    return "Other"
