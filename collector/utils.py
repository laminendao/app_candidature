from __future__ import annotations

import html
import logging
import re
import time
import unicodedata
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from urllib import robotparser
from urllib.parse import urlparse

import requests

log = logging.getLogger("collector")

USER_AGENT = "suivi-candidatures-bot/1.0 (+https://github.com/; collecte quotidienne d'offres d'emploi)"

MONTHS_FR = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
    "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
}


def normalize(text: str | None) -> str:
    """Minuscules, sans accents, espaces simples."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().replace("’", "'").split())


def clean_text(text: str | None) -> str:
    """Retire le HTML résiduel et compacte les espaces."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(text))
    return " ".join(html.unescape(text).split())


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize(text)).strip("-")


def department_from_postcode(code: str | None) -> str:
    if not code:
        return ""
    code = str(code).strip()
    if code.startswith("97") and len(code) >= 3:
        return code[:3]
    if code.startswith("20"):  # Corse
        return "2A" if code[:3] < "202" else "2B"
    return code[:2] if len(code) >= 2 and code[:2].isdigit() else ""


def parse_date(value: str | None) -> str | None:
    """Accepte ISO, RFC 822, JJ/MM/AAAA et « 9 octobre 2026 ». Renvoie AAAA-MM-JJ."""
    if not value:
        return None
    value = str(value).strip()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        return f"{m[1]}-{m[2]}-{m[3]}"
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if m:
        return _safe_date(int(m[3]), int(m[2]), int(m[1]))
    m = re.search(r"(\d{1,2})(?:er)?\s+([a-zA-Zéûèô]+)\s+(\d{4})", value)
    if m:
        month = MONTHS_FR.get(normalize(m[2]))
        if month:
            return _safe_date(int(m[3]), month, int(m[1]))
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return None


def _safe_date(y: int, m: int, d: int) -> str | None:
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def today_iso() -> str:
    return datetime.now().date().isoformat()


class Http:
    """Session HTTP polie : User-Agent explicite, délai entre requêtes, respect de robots.txt."""

    def __init__(self, delay: float = 1.0, timeout: int = 30):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"})
        self.delay = delay
        self.timeout = timeout
        self._last: dict[str, float] = {}
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        parts = urlparse(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            rp = robotparser.RobotFileParser()
            try:
                r = self.session.get(base + "/robots.txt", timeout=self.timeout)
                if r.status_code >= 400:
                    self._robots[base] = None  # pas de robots.txt : tout est permis
                else:
                    rp.parse(r.text.splitlines())
                    self._robots[base] = rp
            except requests.RequestException:
                self._robots[base] = None
        rp = self._robots[base]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    def _wait(self, url: str) -> None:
        host = urlparse(url).netloc
        elapsed = time.monotonic() - self._last.get(host, 0)
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last[host] = time.monotonic()

    def get(self, url: str, *, check_robots: bool = False, retries: int = 2, **kw) -> requests.Response:
        if check_robots and not self.allowed(url):
            raise PermissionError(f"robots.txt interdit la collecte de {url}")
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            self._wait(url)
            try:
                r = self.session.get(url, timeout=self.timeout, **kw)
                if r.status_code in (429, 502, 503, 504) and attempt < retries:
                    time.sleep(3 * (attempt + 1))
                    continue
                return r
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(2 * (attempt + 1))
        raise last_exc or RuntimeError(f"échec GET {url}")

    def post(self, url: str, **kw) -> requests.Response:
        self._wait(url)
        return self.session.post(url, timeout=self.timeout, **kw)
