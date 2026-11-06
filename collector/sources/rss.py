from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET

from ..models import Offer
from ..utils import clean_text, parse_date
from .base import Context, Source


def parse_feed(xml_text: str) -> list[dict]:
    """Lit un flux RSS 2.0 ou Atom et renvoie des entrées {title, link, description, date}."""
    root = ET.fromstring(xml_text.encode() if isinstance(xml_text, str) else xml_text)
    entries = []
    for item in root.iter():
        tag = item.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        def get(*names):
            # Attention : un Element sans enfant est « faux », d'où le test explicite à None.
            for name in names:
                for c in item:
                    if c.tag.split("}")[-1] == name:
                        return c
            return None

        link_el = get("link")
        link = ""
        if link_el is not None:
            link = (link_el.text or link_el.get("href") or "").strip()
        desc_el = get("description", "summary", "content")
        date_el = get("pubDate", "published", "updated", "date")
        title_el = get("title")
        entries.append({
            "title": clean_text(title_el.text if title_el is not None else ""),
            "link": link,
            "description": clean_text(desc_el.text if desc_el is not None else ""),
            "date": parse_date(date_el.text if date_el is not None else None),
        })
    return entries


DEADLINE_RE = re.compile(r"date limite[^0-9]{0,40}(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+\w+\s+\d{4})", re.I)


def entry_to_offer(source: str, e: dict, org: str = "", location: str = "") -> Offer:
    sid = hashlib.sha1((e["link"] or e["title"]).encode()).hexdigest()[:16]
    m = DEADLINE_RE.search(e["description"])
    return Offer(
        source=source, source_id=sid, title=e["title"], url=e["link"], org=org,
        location=location, description=e["description"], published=e["date"],
        deadline=parse_date(m[1]) if m else None,
    )


class GenericRss(Source):
    """N'importe quel flux RSS/Atom déclaré dans config/sources.yml (clé « feeds »)."""

    name = "rss"
    label = "Flux RSS"

    def fetch(self, ctx: Context) -> list[Offer]:
        offers: list[Offer] = []
        for feed in ctx.settings.get("feeds", []):
            try:
                r = ctx.http.get(feed["url"])
                r.raise_for_status()
                for e in parse_feed(r.text):
                    offers.append(entry_to_offer(f"rss-{feed.get('id', 'flux')}", e, feed.get("org", ""), feed.get("location", "")))
            except Exception as exc:  # un flux en erreur ne bloque pas les autres
                ctx.warn(f"{feed.get('id', feed['url'])} : {exc}")
        return offers
