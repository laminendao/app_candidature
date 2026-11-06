"""Sources lues depuis des pages HTML. Les extracteurs sont volontairement tolérants :
ils cherchent des motifs stables (forme des liens, libellés) plutôt que des classes CSS."""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..models import Offer
from ..utils import clean_text, parse_date, slugify
from .base import Context, Source

CONTRACT_RE = re.compile(r"\b(CDI|CDD|Intérim|Interim|Freelance|Indépendant|Stage|Alternance|Post-?doc\w*|Contrat de projet)\b", re.I)


def _lines(el) -> list[str]:
    return [l for l in (clean_text(s) for s in el.get_text("\n").split("\n")) if l]


def _card(a, max_up: int = 4):
    """Remonte depuis un lien jusqu'au bloc qui décrit l'offre (li, article ou div)."""
    node = a
    for _ in range(max_up):
        if node.parent is None:
            break
        node = node.parent
        if node.name in ("li", "article", "tr"):
            return node
    return node


# --------------------------------------------------------------------------- Inria
class Inria(Source):
    name = "inria"
    label = "Inria"
    homepage = "https://jobs.inria.fr/public/classic/fr/offres"
    LINK_RE = re.compile(r"/offres/(\d{4}-\d{4,6})/?(?:[?#].*)?$")

    def fetch(self, ctx: Context) -> list[Offer]:
        r = ctx.http.get(self.homepage, check_robots=True)
        r.raise_for_status()
        return self.parse(r.text, self.homepage)

    def parse(self, html: str, base: str) -> list[Offer]:
        soup = BeautifulSoup(html, "html.parser")
        offers: dict[str, Offer] = {}
        for a in soup.find_all("a", href=True):
            m = self.LINK_RE.search(a["href"])
            title = clean_text(a.get_text())
            if not m or not title or m[1] in offers:
                continue
            text = "\n".join(_lines(_card(a)))
            city = re.search(r"Ville\s*:\s*([^\n]+)", text)
            team = re.search(r"[ÉE]quipe Inria\s*:\s*([^\n]+)", text)
            dl = re.search(r"Date limite pour postuler\s*:\s*([^\n]+)", text)
            offers[m[1]] = Offer(
                source=self.name, source_id=m[1], title=title, url=urljoin(base, a["href"]),
                org="Inria" + (f" – équipe {team[1].strip()}" if team else ""),
                location=city[1].strip() if city else "",
                deadline=parse_date(dl[1]) if dl else None,
                description=text[:600],
            )
        return list(offers.values())


# --------------------------------------------------------------------------- Hellowork
class Hellowork(Source):
    name = "hellowork"
    label = "Hellowork"
    homepage = "https://www.hellowork.com/fr-fr/emploi.html"
    LINK_RE = re.compile(r"/fr-fr/emplois/(\d+)\.html")

    def fetch(self, ctx: Context) -> list[Offer]:
        queries = ctx.settings.get("queries") or ctx.queries
        regions = ctx.settings.get("regions") or [""]
        offers: dict[str, Offer] = {}
        found_pages = 0
        for q in queries:
            for region in regions:
                suffix = f"-region_{region}" if region else ""
                url = f"https://www.hellowork.com/fr-fr/emploi/metier_{slugify(q)}{suffix}.html"
                r = ctx.http.get(url, check_robots=True)
                if r.status_code == 404:
                    continue  # métier inconnu de Hellowork : normal
                if r.status_code != 200:
                    ctx.warn(f"{url} : réponse {r.status_code}")
                    continue
                found_pages += 1
                for o in self.parse(r.text, url):
                    offers.setdefault(o.source_id, o)
        if not found_pages:
            raise RuntimeError("aucune page de résultats Hellowork lisible")
        return list(offers.values())

    def parse(self, html: str, base: str) -> list[Offer]:
        soup = BeautifulSoup(html, "html.parser")
        out: dict[str, Offer] = {}
        for a in soup.find_all("a", href=True):
            m = self.LINK_RE.search(a["href"])
            if not m or m[1] in out:
                continue
            card = _card(a)
            lines = _lines(card)
            title = clean_text(a.get("title") or a.get("aria-label") or "") or (lines[0] if lines else "")
            if not title:
                continue
            rest = [l for l in lines if l != title and not l.lower().startswith(("voir l", "postuler", "nouveau"))]
            location = next((l for l in rest if re.search(r"\s-\s\d{2,3}$|\(\d{2}\)$", l)), "")
            contract = next((CONTRACT_RE.search(l)[0] for l in rest if CONTRACT_RE.search(l)), "")
            org = next((l for l in rest if l not in (location,) and not CONTRACT_RE.search(l) and not re.search(r"\d", l)), "")
            out[m[1]] = Offer(
                source=self.name, source_id=m[1], title=title, url=urljoin(base, a["href"]),
                org=org, location=location, contract=contract, description=" · ".join(rest)[:400],
            )
        return list(out.values())


# --------------------------------------------------------------------------- SFdS
class Sfds(Source):
    name = "sfds"
    label = "SFdS (Société française de statistique)"
    homepage = "https://www.sfds.asso.fr/fr/n/506-consulter_les_offres_demploi/"

    def fetch(self, ctx: Context) -> list[Offer]:
        r = ctx.http.get(self.homepage, check_robots=True)
        r.raise_for_status()
        return self.parse(r.text, self.homepage)

    def parse(self, html: str, base: str) -> list[Offer]:
        soup = BeautifulSoup(html, "html.parser")
        out: list[Offer] = []
        for i, table in enumerate(soup.find_all("table")):
            fields: dict[str, str] = {}
            link = ""
            inner: list[str] = []   # lignes à une seule cellule : titre, date, type/lieu
            for tr in table.find_all("tr"):
                cells = tr.find_all(["th", "td"])
                if len(cells) < 2:
                    t = clean_text(tr.get_text(" "))
                    if t:
                        inner.append(t)
                    continue
                key = clean_text(cells[0].get_text()).rstrip(" :")
                fields[key] = clean_text(cells[1].get_text(" "))
                if key.lower().startswith("en savoir plus"):
                    a = cells[1].find("a", href=True)
                    link = urljoin(base, a["href"]) if a else ""
            if not fields:
                continue
            # Le titre, la date de publication et le type/lieu sont soit dans le tableau
            # (lignes à une cellule), soit juste avant. On s'arrête à la fin du tableau précédent.
            before: list[str] = list(inner)
            if not any(t.startswith("Publiée le") for t in before):
                prev_table = table.find_previous("table")
                for el in table.find_all_previous(string=True, limit=60):
                    if prev_table is not None and el.find_parent("table") is prev_table:
                        break
                    t = clean_text(el)
                    if t:
                        before.insert(0, t)  # remet dans l'ordre de lecture
                before = before[-8:]
            known = {clean_text(v) for v in fields.values()}
            published = next((parse_date(t) for t in before if t.startswith("Publiée le")), None)
            meta = next((t for t in before if re.match(r"^(CDI|CDD|Postdoc|Stage|Thèse|Doctorat)\s*,", t, re.I)), "")
            title = next((t for t in before if not t.startswith(("Publiée le", "Référence")) and t != meta
                          and t not in known and "@" not in t and len(t) > 12), "")
            if not title or meta.lower().startswith(("stage", "thèse")):
                continue
            contact = fields.get("Contact", "")
            out.append(Offer(
                source=self.name, source_id=f"{published or 'x'}-{slugify(title)[:50]}",
                title=title, url=link or base,
                org=fields.get("Entreprise/Organisme", ""),
                location=meta.split(",", 1)[1].strip(" .") if "," in meta else "",
                contract=meta.split(",", 1)[0] if meta else "",
                description=" · ".join(f"{k} : {v}" for k, v in fields.items() if k not in ("Contact", "En savoir plus"))[:900],
                published=published,
                extra={"contact": contact} if contact else {},
            ))
        return out


# --------------------------------------------------------------------------- CESI
class Cesi(Source):
    name = "cesi"
    label = "CESI (école et LINEACT)"
    homepage = "https://lineact.cesi.fr/recrutement/"
    URLS = ("https://lineact.cesi.fr/recrutement/", "https://www.cesi.fr/recrutement/")

    def fetch(self, ctx: Context) -> list[Offer]:
        out: dict[str, Offer] = {}
        ok = 0
        for url in ctx.settings.get("urls", self.URLS):
            try:
                r = ctx.http.get(url, check_robots=True)
                r.raise_for_status()
                ok += 1
                for o in self.parse(r.text, url):
                    out.setdefault(o.source_id, o)
            except Exception as exc:
                ctx.warn(f"{url} : {exc}")
        if not ok:
            raise RuntimeError("aucune page CESI lisible")
        return list(out.values())

    def parse(self, html: str, base: str) -> list[Offer]:
        soup = BeautifulSoup(html, "html.parser")
        out: dict[str, Offer] = {}
        base_path = urlparse(base).path.rstrip("/")
        for a in soup.find_all("a", href=True):
            url = urljoin(base, a["href"]).split("#")[0]
            path = urlparse(url).path.rstrip("/")
            # Une offre = un lien vers une sous-page de /recrutement/ (pas la liste, ni un filtre, ni la candidature spontanée)
            if not path.startswith(base_path + "/") or path == base_path or "?" in a["href"] \
                    or "candidature-spontanee" in url or "/page/" in path or url in out:
                continue
            title = clean_text(a.get_text(" "))
            if len(title) < 15:
                continue
            h = a.find_parent(["h2", "h3", "h4"]) or a
            card = _card(h)
            text = " ".join(_lines(card))
            pub = re.search(r"Publié le\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4})\s*([^\n]*?)(?=\s*(?:Recherche|Enseignement|$)|\s{2})", text)
            contract = CONTRACT_RE.search(text)
            loc = re.search(r"-\s*(CDI|CDD)[^-]*-\s*([^()]+?)(?:\s*\(|$)", text)
            out[url] = Offer(
                source=self.name, source_id=slugify(url.rstrip("/").split("/")[-1])[:80],
                title=title, url=url,
                org="CESI LINEACT" if "lineact" in base else "CESI",
                location=(loc[2].strip() if loc else (pub[2].strip() if pub else "")),
                contract=contract[0] if contract else "",
                published=parse_date(pub[1]) if pub else None,
                description=text[:400],
            )
        return list(out.values())
