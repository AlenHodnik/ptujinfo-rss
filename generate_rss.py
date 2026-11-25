
import requests
import re
import html
from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from urllib.parse import urljoin
from lxml import etree

BASE_URL = "https://ptujinfo.com"
SOURCE_URL = BASE_URL + "/dnevni-pregled"
FEED_URL = "https://alenhodnik.github.io/ptujinfo-rss/rss.xml"
OUTPUT = Path(__file__).resolve().parent / "rss.xml"
MAX_ITEMS = 50

# Pridobivanje spletne strani
response = requests.get(SOURCE_URL, timeout=30)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

articles = []
seen = set()

# Pridobivanje podatkov posameznega clanka
for card in soup.select("article"):

    a = card.select_one('h3 a[href^="/novica/"]')

    if not a:
        continue

    href = a["href"]
    title = a.get_text(" ", strip=True)

    match = re.search(r"/(\d+)/?$", href)

    if not match or not title:
        continue

    article_id = match.group(1)

    if article_id in seen:
        continue

    seen.add(article_id)

    # Fotografija
    img = card.select_one("picture img[src]")
    image = urljoin(BASE_URL, img["src"]) if img else None

    # Povzetek
    summary_tag = card.select_one("h5")
    summary = (
        summary_tag.get_text(" ", strip=True)
        if summary_tag else ""
    )

    # Datum in ura objave
    time_tag = card.select_one(
        'time[itemprop="datePublished"][datetime]'
    )

    published = None

    if time_tag:
        try:
            published = datetime.fromisoformat(
                time_tag["datetime"]
            )
            if published.tzinfo is None:
                published = None
        except ValueError:
            pass

    # Avtor
    author_tag = card.select_one(
        'span[itemprop="author"] a'
    )

    author = (
        author_tag.get_text(" ", strip=True)
        if author_tag else ""
    )

    articles.append({
        "id": article_id,
        "title": title,
        "url": urljoin(BASE_URL, href),
        "image": image,
        "summary": summary,
        "published": published,
        "author": author,
        "category": href.split("/")[2]
    })

# Ob napaki ohranimo obstojeci RSS
if not articles:
    raise RuntimeError("Ni najdenih novic!")

# Razvrscanje od najnovejse do najstarejse
articles.sort(
    key=lambda a: (
        a["published"]
        or datetime.min.replace(tzinfo=timezone.utc)
    ),
    reverse=True
)

articles = articles[:MAX_ITEMS]

# Generiranje RSS
fg = FeedGenerator()
fg.load_extension("dc")

fg.id(BASE_URL)
fg.title("Ptujinfo - Zadnje novice")
fg.link(href=BASE_URL, rel="alternate")
fg.link(href=FEED_URL, rel="self")
fg.description("Zadnje novice portala Ptujinfo.com")
fg.language("sl")
fg.ttl(10)

fg.logo(
    BASE_URL
    + "/themes/custom/infotheme/images/favicons/ptuj.png"
)

for article in articles:

    fe = fg.add_entry(order="append")

    # Ohranimo obstojeci GUID zaradi Feedlyja
    fe.id(article["url"])
    fe.title(article["title"])
    fe.link(href=article["url"])
    fe.category(term=article["category"])

    # Dejanski datum objave
    if article["published"]:
        fe.pubDate(article["published"])

    # Avtor
    if article["author"]:
        fe.dc.dc_creator(article["author"])

    # Fotografija in povzetek
    description = ""

    if article["image"]:
        description += (
            f'<p><img src="{html.escape(article["image"])}"'
            ' style="max-width:100%;height:auto;" /></p>'
        )

    description += (
        f'<p>{html.escape(article["summary"] or article["title"])}</p>'
    )

    description += (
        f'<p><a href="{html.escape(article["url"])}">'
        'Preberi celotno novico na Ptujinfo</a></p>'
    )

    fe.description(description)

# Odstranimo samodejno generirane casovne oznake
root = etree.fromstring(fg.rss_str())

for node in root.xpath("/rss/channel/lastBuildDate"):
    node.getparent().remove(node)

data = etree.tostring(
    root,
    encoding="UTF-8",
    xml_declaration=True,
    pretty_print=True
)

# Datoteko posodobimo samo ob spremembah
if OUTPUT.exists() and OUTPUT.read_bytes() == data:
    print("Ni sprememb.")
else:
    temp = OUTPUT.with_suffix(".tmp")
    temp.write_bytes(data)
    temp.replace(OUTPUT)
    print("RSS posodobljen.")

print(f"Stevilo novic: {len(articles)}")

for article in articles[:5]:
    print(
        f" - {article['published']} | "
        f"{article['title']}"
    )
