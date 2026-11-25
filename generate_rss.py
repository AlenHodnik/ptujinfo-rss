
import requests
import re
import html
from pathlib import Path
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from urllib.parse import urljoin

BASE_URL = "https://ptujinfo.com"
SOURCE_URL = BASE_URL + "/dnevni-pregled"
FEED_URL = "https://alenhodnik.github.io/ptujinfo-rss/rss.xml"
OUTPUT = Path(__file__).resolve().parent / "rss.xml"
MAX_ITEMS = 50

response = requests.get(SOURCE_URL, timeout=30)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

# Pridobivanje fotografij
images = {}

for a in soup.select('a[href^="/novica/"]'):
    img = a.select_one("img[src]")
    if img:
        images[a["href"]] = urljoin(BASE_URL, img["src"])

# Pridobivanje novic
articles = []
seen = set()

for a in soup.select('h3 a[href^="/novica/"]'):
    href = a["href"]
    title = a.get_text(" ", strip=True)

    match = re.search(r"/(\d+)/?$", href)

    if not match or not title:
        continue

    article_id = match.group(1)

    if article_id in seen:
        continue

    seen.add(article_id)

    articles.append({
        "id": article_id,
        "title": title,
        "url": urljoin(BASE_URL, href),
        "image": images.get(href),
        "category": href.split("/")[2]
    })

    if len(articles) >= MAX_ITEMS:
        break

# Ob napaki ne prepisemo obstojecega RSS
if not articles:
    raise RuntimeError("Ni najdenih novic!")

# Generiranje RSS
fg = FeedGenerator()
fg.id(BASE_URL)
fg.title("Ptujinfo - Zadnje novice")
fg.link(href=BASE_URL, rel="alternate")
fg.link(href=FEED_URL, rel="self")
fg.description("Zadnje novice portala Ptujinfo.com")
fg.language("sl")
fg.ttl(10)

for article in articles:
    fe = fg.add_entry(order="append")
    fe.id(article["url"])
    fe.title(article["title"])
    fe.link(href=article["url"])
    fe.category(term=article["category"])

    description = ""

    if article["image"]:
        description += (
            f'<img src="{html.escape(article["image"])}" />'
        )

    description += (
        f'<p>{html.escape(article["title"])}</p>'
        f'<p><a href="{html.escape(article["url"])}">'
        'Preberi celotno novico</a></p>'
    )

    fe.description(description)

# Odstranimo spremenljive casovne oznake,
# da se RSS ne spreminja brez novih podatkov.
from lxml import etree

root = etree.fromstring(fg.rss_str())

for node in root.xpath("/rss/channel/lastBuildDate"):
    node.getparent().remove(node)

data = etree.tostring(
    root,
    encoding="UTF-8",
    xml_declaration=True,
    pretty_print=True
)

if OUTPUT.exists() and OUTPUT.read_bytes() == data:
    print("Ni sprememb.")
else:
    temp = OUTPUT.with_suffix(".tmp")
    temp.write_bytes(data)
    temp.replace(OUTPUT)
    print("RSS posodobljen.")

print(f"Stevilo novic: {len(articles)}")

for article in articles[:5]:
    print(f" - {article['title']}")
