"""Alertes emploi reçues par e-mail (LinkedIn, Indeed, APEC, Welcome to the Jungle, Hellowork,
Choisir le service public…). Le collecteur lit UNIQUEMENT le dossier/libellé indiqué
(par défaut « Alertes emploi »), en lecture seule, sans marquer les messages comme lus.

Secrets : EMAIL_ADDRESS, EMAIL_APP_PASSWORD (mot de passe d'application Gmail).
"""
from __future__ import annotations

import email
import hashlib
import imaplib
import re
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from ..models import Offer
from ..utils import clean_text
from .base import Context, Source

# Reconnaissance des liens d'offre par site. id = groupe 1 de la regex.
SITES = [
    ("LinkedIn", re.compile(r"linkedin\.com/(?:comm/)?jobs/view/(\d+)")),
    ("Indeed", re.compile(r"indeed\.[a-z.]+/(?:rc/clk|viewjob|pagead/clk|m/viewjob)\?[^\"']*?\bjk=([0-9a-f]+)")),
    ("Indeed", re.compile(r"cts\.indeed\.com/[^\s\"']+")),
    ("APEC", re.compile(r"apec\.fr/[^\s\"']*detail-offre/([0-9A-Z]+)")),
    ("Welcome to the Jungle", re.compile(r"welcometothejungle\.com/[a-z]{2}/companies/[^/]+/jobs/([^/?#\"']+)")),
    ("Hellowork", re.compile(r"hellowork\.com/fr-fr/emplois/(\d+)\.html")),
    ("Choisir le service public", re.compile(r"choisirleservicepublic\.gouv\.fr/offre-emploi/([^/?#\"']+)")),
    ("France Travail", re.compile(r"francetravail\.fr/offres/recherche/detail/([0-9A-Z]+)")),
    ("Jobteaser", re.compile(r"jobteaser\.com/[a-z]{2}/job-offers/([^/?#\"']+)")),
    ("Cadremploi", re.compile(r"cadremploi\.fr/emploi/detail_offre\?offreId=(\d+)")),
]
SENDERS = {  # domaine de l'expéditeur → site (sert de repli pour les liens non reconnus)
    "linkedin.com": "LinkedIn", "indeed.com": "Indeed", "indeed.fr": "Indeed", "apec.fr": "APEC",
    "welcometothejungle.com": "Welcome to the Jungle", "hellowork.com": "Hellowork",
    "choisirleservicepublic.gouv.fr": "Choisir le service public", "francetravail.fr": "France Travail",
}
SKIP_TEXT = re.compile(r"(désinscri|desinscri|unsubscribe|se désabonner|préférences|preferences|voir toutes|see all|"
                       r"modifier (l'|cette )?alerte|gérer|manage|aide|help|confidentialit|privacy|télécharger l'app|"
                       r"voir plus d'offres|afficher plus|postuler maintenant|apply now|^voir l'offre$|^view job$)", re.I)
GENERIC_JOB_HREF = re.compile(r"(job|emploi|offre|career|carriere|recrutement|poste|vacanc)", re.I)
CONTRACT_RE = re.compile(r"\b(CDI|CDD|Intérim|Freelance|Stage|Alternance|Temps plein|Temps partiel|Full[- ]time|Contract)\b", re.I)


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _html_of(msg: email.message.Message) -> str:
    html, text = "", ""
    for part in msg.walk() if msg.is_multipart() else [msg]:
        ctype = part.get_content_type()
        if part.get_content_maintype() == "multipart" or part.get("Content-Disposition", "").startswith("attachment"):
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if ctype == "text/html" and not html:
            html = body
        elif ctype == "text/plain" and not text:
            text = body
    if html:
        return html
    # Texte brut : on fabrique des liens pour réutiliser le même extracteur
    return "<br>".join(re.sub(r"(https?://\S+)", r'<a href="\1">\1</a>', l) for l in text.splitlines())


def _match_site(href: str) -> tuple[str, str] | None:
    for name, rx in SITES:
        m = rx.search(href)
        if m:
            return name, (m.group(1) if m.groups() else hashlib.sha1(href.encode()).hexdigest()[:12])
    return None


def _unwrap(href: str) -> str:
    """Certains mails emballent le lien dans une redirection ?url=… : on récupère la cible si elle est lisible."""
    q = parse_qs(urlparse(href).query)
    for key in ("url", "u", "redirect", "target", "dest"):
        if q.get(key) and q[key][0].startswith("http"):
            return q[key][0]
    return href


def _context_lines(a, title: str) -> list[str]:
    """Texte du bloc qui entoure le lien : entreprise, lieu, contrat."""
    node = a
    for _ in range(6):
        if node.parent is None:
            break
        node = node.parent
        lines = [l for l in (clean_text(s) for s in node.get_text("\n").split("\n")) if l]
        if len(lines) >= 3 or node.name in ("tr", "td", "table", "li"):
            break
    return [l for l in lines if l != title and not SKIP_TEXT.search(l)][:6] if node is not a else []


NOISE_LINE = re.compile(r"(connection|connexion|relation|actively recruiting|recrute activement|alum|ancien[s]? élève|"
                        r"candidature simplifiée|easy apply|promoted|promu|sponsoris|il y a \d|\d+ (day|jour|hour|heure)s? ago|"
                        r"\d+ candidat|applicants?|nouveau|new$|top applicant|vous correspondez|be an early applicant)", re.I)
SALARY_RE = re.compile(r"(\d[\d\s.,]*\s?(k|K)?\s?€|€\s?\d|\d+\s?K\s?€?\s?[-–]|/\s?(an|year|yr|mois|month))")


def _split_card(lines: list[str]) -> tuple[str, str, str, str]:
    """Lignes d'une carte d'offre → (entreprise, lieu, contrat, salaire)."""
    org = loc = contract = salary = ""
    for l in lines:
        if NOISE_LINE.search(l):
            # « Banque de France · Paris Actively recruiting » : on coupe le bruit en fin de ligne
            l = NOISE_LINE.split(l)[0].strip(" ·-") if " · " in l else ""
            if not l:
                continue
        if not salary and SALARY_RE.search(l) and len(l) < 60:
            salary = l
            continue
        if not contract and CONTRACT_RE.search(l) and len(l) < 40:
            contract = CONTRACT_RE.search(l)[0]
            if CONTRACT_RE.fullmatch(l.strip()):
                continue
        if " · " in l and not org:
            parts = [x.strip() for x in l.split(" · ") if x.strip()]
            org = parts[0]
            loc = parts[1] if len(parts) > 1 else loc
            if len(parts) > 2 and not salary and SALARY_RE.search(parts[2]):
                salary = parts[2]
            continue
        if not org and len(l) <= 80:
            org = l
        elif not loc and len(l) <= 80:
            loc = l
    loc = SALARY_RE.split(loc)[0].strip(" ·-") if loc else loc
    return org, loc, contract, salary


def parse_alert(html: str, sender_site: str, received: str | None) -> list[Offer]:
    soup = BeautifulSoup(html, "html.parser")
    out: dict[str, Offer] = {}
    for a in soup.find_all("a", href=True):
        href = _unwrap(a["href"].strip())
        inner = [l for l in (clean_text(x) for x in a.get_text("\n").split("\n")) if l]
        if not inner:
            continue  # logos, boutons-images
        title = inner[0] if len(inner) > 1 else clean_text(a.get_text(" "))
        match = _match_site(href)
        if not match:
            if not (sender_site and GENERIC_JOB_HREF.search(href) and len(title) >= 12):
                continue
            match = (sender_site, hashlib.sha1(href.split("?")[0].encode()).hexdigest()[:12])
        site, jid = match
        if len(title) < 6 or SKIP_TEXT.search(title):
            continue
        key = f"{site}:{jid}"
        if key in out:
            continue
        # Le lien contient parfois toute la carte (LinkedIn) ; sinon on lit le bloc qui l'entoure.
        card = inner[1:] if len(inner) > 1 else _context_lines(a, title)
        card = [l for l in card if l != title and not SKIP_TEXT.search(l)]
        org, location, contract, salary = _split_card(card)
        if org == title:
            org = ""
        out[key] = Offer(
            source="email", source_id=hashlib.sha1(key.encode()).hexdigest()[:16],
            title=title, url=href, org=org, location=location, contract=contract, salary=salary,
            description=" · ".join(card)[:400], published=received, via=site,
        )
    return list(out.values())


class EmailAlerts(Source):
    name = "email"
    label = "Alertes e-mail"
    homepage = "https://mail.google.com"
    secrets = ("EMAIL_ADDRESS", "EMAIL_APP_PASSWORD")

    def fetch(self, ctx: Context) -> list[Offer]:
        host = ctx.settings.get("imap_host", "imap.gmail.com")
        folder = ctx.settings.get("folder", "Alertes emploi")
        days = int(ctx.settings.get("days", max(ctx.since_days, 3)))
        limit = int(ctx.settings.get("max_messages", 300))
        imap = imaplib.IMAP4_SSL(host)
        try:
            try:
                imap.login(self.secret("EMAIL_ADDRESS"), self.secret("EMAIL_APP_PASSWORD").replace(" ", ""))
            except imaplib.IMAP4.error as exc:
                raise RuntimeError("connexion refusée : vérifie EMAIL_ADDRESS et le mot de passe d'application (et que l'IMAP est activé dans Gmail)") from exc
            status, _ = imap.select(f'"{folder}"', readonly=True)
            if status != "OK":
                raise RuntimeError(f"dossier « {folder} » introuvable : crée le libellé dans Gmail (même nom, sans accent)")
            since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
            status, data = imap.search(None, "SINCE", since)
            ids = (data[0] or b"").split()[-limit:]
            offers: dict[str, Offer] = {}
            n_mail = 0
            for mid in ids:
                status, parts = imap.fetch(mid, "(BODY.PEEK[])")
                raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
                if not raw:
                    continue
                msg = email.message_from_bytes(raw)
                n_mail += 1
                sender = parseaddr(_decode(msg.get("From")))[1].lower()
                domain = ".".join(sender.split("@")[-1].split(".")[-2:])
                try:
                    received = parsedate_to_datetime(msg.get("Date")).date().isoformat()
                except Exception:
                    received = None
                found = parse_alert(_html_of(msg), SENDERS.get(domain, ""), received)
                if not found:
                    ctx.warn(f"aucune offre reconnue dans « {_decode(msg.get('Subject'))[:60]} » ({domain})")
                for o in found:
                    offers.setdefault(o.source_id, o)
            if not n_mail:
                ctx.warn(f"aucun message dans « {folder} » depuis {days} jours")
            return list(offers.values())
        finally:
            try:
                imap.logout()
            except Exception:
                pass
