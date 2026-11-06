from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..models import Offer
from ..utils import clean_text, department_from_postcode
from .base import Context, Source

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
PAGE = 150
MAX_INDEX = 1149  # l'API refuse les plages au-delà


class FranceTravail(Source):
    """API officielle « Offres d'emploi v2 ». Couvre tous les secteurs, partenaires compris."""

    name = "france_travail"
    label = "France Travail"
    homepage = "https://candidat.francetravail.fr/offres/recherche"
    secrets = ("FRANCE_TRAVAIL_CLIENT_ID", "FRANCE_TRAVAIL_CLIENT_SECRET")

    SCOPES = ("api_offresdemploiv2 o2dsoffre", "api_offresdemploiv2")

    def _token(self, ctx: Context) -> str:
        errors = []
        for scope in self.SCOPES:
            r = ctx.http.post(TOKEN_URL, data={
                "grant_type": "client_credentials",
                "client_id": self.secret("FRANCE_TRAVAIL_CLIENT_ID"),
                "client_secret": self.secret("FRANCE_TRAVAIL_CLIENT_SECRET"),
                "scope": scope,
            }, headers={"Content-Type": "application/x-www-form-urlencoded"})
            if r.status_code == 200:
                try:
                    return r.json()["access_token"]
                except (ValueError, KeyError):
                    pass
            try:
                body = r.json()
                detail = " – ".join(x for x in (body.get("error"), body.get("error_description")) if x)
            except ValueError:
                detail = r.text[:120]
            errors.append(f"{r.status_code} {detail}".strip())
        hint = {
            "invalid_client": "identifiant ou clé secrète incorrects (vérifie les secrets GitHub, sans espace)",
            "invalid_scope": "l'application n'est pas abonnée à l'API « Offres d'emploi v2 » sur francetravail.io",
        }
        why = next((h for k, h in hint.items() if any(k in e for e in errors)), "vérifie les identifiants et l'abonnement à l'API Offres d'emploi v2")
        raise RuntimeError(f"authentification refusée ({' / '.join(errors)}) : {why}")

    def fetch(self, ctx: Context) -> list[Offer]:
        token = self._token(ctx)
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        now = datetime.now(timezone.utc).replace(microsecond=0)
        since = now - timedelta(days=ctx.since_days)
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        departements = ctx.settings.get("departements") or [None]
        offers: dict[str, Offer] = {}

        for query in ctx.queries:
            words = ",".join(w for w in query.replace("'", " ").split() if len(w) >= 2)
            for dep in departements:
                start = 0
                while start <= MAX_INDEX - 1:
                    end = min(start + PAGE - 1, MAX_INDEX)
                    params = {
                        "motsCles": words,
                        "minCreationDate": since.strftime(fmt),
                        "maxCreationDate": now.strftime(fmt),
                        "range": f"{start}-{end}",
                    }
                    if dep:
                        params["departement"] = dep
                    r = ctx.http.get(SEARCH_URL, params=params, headers=headers)
                    if r.status_code == 204:
                        break
                    if r.status_code not in (200, 206):
                        ctx.warn(f"« {query} » : réponse {r.status_code}")
                        break
                    results = r.json().get("resultats", [])
                    for item in results:
                        o = self._map(item)
                        offers[o.source_id] = o
                    if len(results) < PAGE or end >= MAX_INDEX:
                        break
                    start += PAGE
        return list(offers.values())

    @staticmethod
    def _map(item: dict) -> Offer:
        lieu = item.get("lieuTravail") or {}
        origine = item.get("origineOffre") or {}
        partenaires = origine.get("partenaires") or []
        oid = str(item.get("id"))
        url = origine.get("urlOrigine") or f"https://candidat.francetravail.fr/offres/recherche/detail/{oid}"
        return Offer(
            source="france_travail",
            source_id=oid,
            title=clean_text(item.get("intitule")),
            url=url,
            org=clean_text((item.get("entreprise") or {}).get("nom")),
            location=clean_text(lieu.get("libelle")),
            department=department_from_postcode(lieu.get("codePostal")),
            contract=clean_text(item.get("typeContratLibelle") or item.get("typeContrat")),
            description=clean_text(item.get("description")),
            published=(item.get("dateCreation") or "")[:10] or None,
            salary=clean_text((item.get("salaire") or {}).get("libelle")),
            via=", ".join(p.get("nom", "") for p in partenaires if p.get("nom")),
        )
