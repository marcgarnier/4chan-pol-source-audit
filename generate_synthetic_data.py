import json
import random

random.seed(42)

DOMAINS_BY_CATEGORY = {
    "mainstream": [
        ("cnn.com", "/2026/07/politics/article"),
        ("nytimes.com", "/2026/07/us/politics"),
        ("bbc.com", "/news/world"),
        ("bbc.co.uk", "/news/uk"),
        ("theguardian.com", "/world/2026/jul"),
        ("reuters.com", "/world/us"),
        ("cbc.ca", "/news/politics"),
        ("bloomberg.com", "/news/articles"),
        ("wsj.com", "/news/politics"),
        ("washingtonpost.com", "/politics"),
    ],
    "alternative": [
        ("breitbart.com", "/politics/2026"),
        ("foxnews.com", "/politics"),
        ("epochtimes.com", "/us/politics"),
        ("rebelnews.com", "/canada"),
        ("zerohedge.com", "/political"),
        ("dailywire.com", "/news"),
        ("newsmax.com", "/politics"),
        ("thepostmillennial.com", "/news"),
        ("washingtontimes.com", "/news"),
        ("dailymail.co.uk", "/news/article"),
    ],
    "social_media": [
        ("twitter.com", "/user/status/123456"),
        ("x.com", "/user/status/789012"),
        ("reddit.com", "/r/politics/comments/"),
        ("youtube.com", "/watch?v=abc123"),
        ("tiktok.com", "/@user/video/123"),
        ("rumble.com", "/video/abc"),
        ("gab.com", "/groups/politics"),
        ("truthsocial.com", "/@user/123"),
    ],
    "state_funded": [
        ("rt.com", "/news/2026"),
        ("tass.com", "/world/2026"),
        ("xinhuanet.com", "/english/2026-07"),
        ("cgtn.com", "/world/2026"),
        ("france24.com", "/en/americas"),
    ],
    "institutional": [
        ("wikipedia.org", "/wiki/Politics"),
        ("state.gov", "/press/2026"),
        ("congress.gov", "/bill/119th"),
    ],
}

TEMPLATES_POSITIVE = [
    "Based and redpilled. {link} finally tells the truth about what's happening.",
    "Even {link} is starting to wake up to reality. Interesting times.",
    "This is exactly what I've been saying for months. {link}",
    "Spread this far and wide. {link} Real journalism still exists.",
    "Unbelievable footage. Watch before it gets taken down. {link}",
    "Based take from {link}. They're one of the few honest outlets left.",
    "This thread is pure gold. {link}",
    "Finally someone says it out loud. {link}",
]

TEMPLATES_NEUTRAL = [
    "Interesting development. {link}",
    "Thoughts on this? {link}",
    "What do you guys think about this? {link}",
    "FYI: {link}",
    "Discussion thread. {link}",
    "{link} - relevant to current situation.",
    "Saw this and thought of /pol/. {link}",
    "New article on the situation. {link}",
]

TEMPLATES_NEGATIVE = [
    "More propaganda from {link}. They never learn.",
    "LOL {link} is literally fake news at this point.",
    "Disgusting. {link} should be ashamed of themselves.",
    "Can't believe anyone still trusts {link} after all their lies.",
    "This is straight up brainwashing. {link}",
    "Remember when {link} used to be credible? Yeah, me neither.",
    "The gaslighting from {link} is unreal. {link}",
    "Thread: why {link} is the enemy of the people. {link}",
    "Shillposting from {link} as usual. Don't fall for it.",
    "Absolutely shameful reporting by {link}. {link}",
]

def generate_post(post_num: int) -> dict:
    cat = random.choices(
        ["mainstream", "alternative", "social_media", "state_funded", "institutional"],
        weights=[25, 35, 20, 12, 8],
        k=1
    )[0]
    domain, path = random.choice(DOMAINS_BY_CATEGORY[cat])
    url = f"https://www.{domain}{path}"

    if domain in ("twitter.com", "x.com"):
        url = f"https://{domain}{path}"

    if random.random() < 0.5:
        cat2 = random.choices(
            ["mainstream", "alternative", "social_media", "state_funded", "institutional"],
            weights=[25, 35, 20, 12, 8],
            k=1
        )[0]
        domain2, path2 = random.choice(DOMAINS_BY_CATEGORY[cat2])
        url2 = f"https://www.{domain2}{path2}"
        if domain2 in ("twitter.com", "x.com"):
            url2 = f"https://{domain2}{path2}"
    else:
        url2 = None

    sentiment = random.random()
    if cat in ("mainstream", "state_funded"):
        if sentiment < 0.70:
            templates = TEMPLATES_NEGATIVE
        elif sentiment < 0.90:
            templates = TEMPLATES_NEUTRAL
        else:
            templates = TEMPLATES_POSITIVE
    elif cat in ("alternative",):
        if sentiment < 0.15:
            templates = TEMPLATES_NEGATIVE
        elif sentiment < 0.40:
            templates = TEMPLATES_NEUTRAL
        else:
            templates = TEMPLATES_POSITIVE
    else:
        if sentiment < 0.40:
            templates = TEMPLATES_NEGATIVE
        elif sentiment < 0.70:
            templates = TEMPLATES_NEUTRAL
        else:
            templates = TEMPLATES_POSITIVE

    template = random.choice(templates)
    if random.random() < 0.5:
        text = template.replace("{link}", f'<a href="{url}" class="link">{domain}</a>')
    else:
        text = template.replace("{link}", f'<a href="{url}" class="link">{domain}</a>')

    if url2 and random.random() < 0.3:
        text += f' Also relevant: <a href="{url2}" class="link">{domain2}</a>'

    text = text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("&lt;a href=", '<a href=').replace("&gt;", '>')
    text = text.replace('class=&quot;link&quot;', 'class="link"')

    text += "<br><br><span class=\"quote\">&gt;be me<br>&gt;reading /pol/ again</span>"

    post = {
        "no": post_num,
        "now": f"2026-04-{random.randint(1,30):02d} {random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}",
        "name": random.choice(["Anonymous", "John", "basedgod", "Patriot", "Normie", "Anon"]),
        "com": text,
        "sub": random.choice(["", "Thoughts?", "Based", "Interesting times", "Wake up people"]),
        "replies": random.randint(0, 200),
        "images": random.randint(0, 5),
    }
    return post

NUM_POSTS = 5000

with open("synthetic_4tct.jsonl", "w") as f:
    for i in range(NUM_POSTS):
        post = generate_post(i + 1)
        f.write(json.dumps(post) + "\n")

print(f"Generated {NUM_POSTS} synthetic posts to synthetic_4tct.jsonl")
