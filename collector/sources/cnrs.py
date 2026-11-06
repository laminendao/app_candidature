from __future__ import annotations

from ..models import Offer
from .base import Context, Source
from .rss import entry_to_offer, parse_feed

import re

PREFIX_RE = re.compile(r"^Offre d'emploi\s+(.{0,60}?)\s*:\s*", re.I)
FEED_URL ="https://emploi.cnrs.fr/Rss/Offres.ashx?BassinEmploi={bassin}"


class Cnrs(Source):
    """Flux RSS du portail emploi du CNRS, un flux par bassin d'emploi (région)."""

    name = "cnrs"
    label = "CNRS"
    homepage = "https://emploi.cnrs.fr/Offres/Recherche.aspx"

    def fetch(self, ctx: Context) -> list[Offer]:
        offers: list[Offer] = []
        ok = 0
        bassins = ctx.settings.get("bassins", ["ile-de-france"])
        for bassin in bassins:
            try:
                r = ctx.http.get(FEED_URL.format(bassin=bassin))
                r.raise_for_status()
                entries = parse_feed(r.text)
                ok += 1
                label = bassin.replace("-", " ").title()
                for e in entries:
                    o = entry_to_offer(self.name, e, "CNRS", label)
                    # « Offre d'emploi Chercheur en contrat CDD : Post-doctorat… » → contrat + intitulé
                    m = PREFIX_RE.match(o.title)
                    if m:
                        o.contract = m[1].strip()
                        o.title = o.title[m.end():].strip()
                    offers.append(o)
            except Exception as exc:
                ctx.warn(f"bassin {bassin} : {exc}")
        if not ok:
            raise RuntimeError("aucun flux CNRS lisible")
        return offers
