from __future__ import annotations

from ..models import Offer
from .base import Context, Source
from .rss import entry_to_offer, parse_feed

FEED_URL = "https://emploi.cnrs.fr/Rss/Offres.ashx?BassinEmploi={bassin}"


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
                offers += [entry_to_offer(self.name, e, "CNRS", label) for e in entries]
            except Exception as exc:
                ctx.warn(f"bassin {bassin} : {exc}")
        if not ok:
            raise RuntimeError("aucun flux CNRS lisible")
        return offers
