from __future__ import annotations

from ..models import Offer
from ..utils import clean_text
from .base import Context, Source

SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/fr/search/{page}"


class Adzuna(Source):
    """Agrégateur Adzuna (offre gratuite : 250 appels par jour)."""

    name = "adzuna"
    label = "Adzuna"
    homepage = "https://www.adzuna.fr"
    secrets = ("ADZUNA_APP_ID", "ADZUNA_APP_KEY")

    def fetch(self, ctx: Context) -> list[Offer]:
        app_id, app_key = self.secret("ADZUNA_APP_ID"), self.secret("ADZUNA_APP_KEY")
        per_page = int(ctx.settings.get("results_per_page", 50))
        max_pages = int(ctx.settings.get("max_pages", 2))
        budget = int(ctx.settings.get("max_calls", 120))
        exclude = ctx.settings.get("exclude", "stage stagiaire alternance alternant apprenti")
        calls = 0
        offers: dict[str, Offer] = {}

        for query in ctx.queries:
            for page in range(1, max_pages + 1):
                if calls >= budget:
                    ctx.warn(f"budget de {budget} appels atteint, requêtes restantes ignorées")
                    return list(offers.values())
                params = {
                    "app_id": app_id, "app_key": app_key,
                    "what_phrase": query, "what_exclude": exclude,
                    "results_per_page": per_page, "max_days_old": ctx.since_days,
                    "sort_by": "date", "content-type": "application/json",
                }
                r = ctx.http.get(SEARCH_URL.format(page=page), params=params)
                calls += 1
                if r.status_code in (401, 403):
                    raise RuntimeError(f"clé refusée ({r.status_code}) : vérifie ADZUNA_APP_ID et ADZUNA_APP_KEY")
                if r.status_code != 200:
                    ctx.warn(f"« {query} » page {page} : réponse {r.status_code}")
                    break
                results = r.json().get("results", [])
                for item in results:
                    o = self._map(item)
                    offers[o.source_id] = o
                if len(results) < per_page:
                    break
        return list(offers.values())

    @staticmethod
    def _map(item: dict) -> Offer:
        salary = ""
        if item.get("salary_min"):
            lo, hi = item.get("salary_min"), item.get("salary_max")
            salary = f"{int(lo):,} – {int(hi):,} €".replace(",", " ") if hi and hi != lo else f"{int(lo):,} €".replace(",", " ")
        contract = " ".join(filter(None, [item.get("contract_type"), item.get("contract_time")]))
        contract = {"permanent": "CDI", "contract": "CDD", "full_time": "temps plein", "part_time": "temps partiel"}.get(contract, contract.replace("permanent", "CDI").replace("contract", "CDD").replace("full_time", "temps plein").replace("part_time", "temps partiel"))
        return Offer(
            source="adzuna",
            source_id=str(item.get("id")),
            title=clean_text(item.get("title")),
            url=item.get("redirect_url", ""),
            org=clean_text((item.get("company") or {}).get("display_name")),
            location=clean_text((item.get("location") or {}).get("display_name")),
            contract=contract,
            description=clean_text(item.get("description")),
            published=(item.get("created") or "")[:10] or None,
            salary=salary,
        )
