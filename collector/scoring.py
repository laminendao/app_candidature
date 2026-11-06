"""Score de pertinence d'une offre pour un profil. Tout est piloté par profile.yml."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from .models import Offer
from .utils import normalize

DEFAULT_CATEGORY_POINTS = 35


@lru_cache(maxsize=4096)
def _pattern(term: str) -> re.Pattern:
    t = re.escape(normalize(term)).replace(r"\ ", r"[\s\-']+")
    return re.compile(rf"(?<![a-z0-9]){t}(?![a-z0-9])")


def has_any(text: str, terms) -> str | None:
    for term in terms or []:
        if _pattern(term).search(text):
            return term
    return None


@dataclass
class Scored:
    score: int
    fit: str
    category: str
    reasons: list[str]
    excluded: str | None = None


class Scorer:
    def __init__(self, profile: dict):
        self.p = profile
        self.categories = profile.get("categories", [])
        self.skills = profile.get("skills", [])
        self.penalties = profile.get("penalties", [])
        self.exclude = profile.get("exclude_title", [])
        self.exclude_text = profile.get("exclude_text", [])
        loc = profile.get("locations", {}) or {}
        self.loc_bonus = int(loc.get("bonus", 0))
        self.loc_deps = {str(d) for d in loc.get("departements", [])}
        self.loc_terms = loc.get("terms", [])
        fit = profile.get("fit", {}) or {}
        self.fit_hi, self.fit_mid = int(fit.get("hi", 65)), int(fit.get("mid", 45))

    def category_of(self, title_n: str) -> dict | None:
        for cat in self.categories:
            if has_any(title_n, cat.get("keywords")):
                return cat
        return None

    def score(self, offer: Offer) -> Scored:
        title = normalize(offer.title)
        body = normalize(" ".join([offer.title, offer.org, offer.description, offer.contract]))

        bad = has_any(title, self.exclude) or has_any(body, self.exclude_text)
        if bad:
            return Scored(0, "lo", "", [], excluded=bad)

        reasons: list[str] = []
        total = 0
        cat = self.category_of(title)
        if cat:
            total += int(cat.get("points", DEFAULT_CATEGORY_POINTS))

        for skill in self.skills:
            terms = skill.get("terms", [])
            w = int(skill.get("weight", 5))
            if has_any(title, terms):
                total += round(w * 1.5)
                reasons.append(skill["label"])
            elif has_any(body, terms):
                total += w
                reasons.append(skill["label"])

        # Une catégorie peut exiger au moins une compétence (ex. un postdoc doit toucher à la statistique ou au ML)
        if cat and cat.get("requires") and not set(cat["requires"]) & set(reasons):
            return Scored(0, "lo", cat["id"], reasons, excluded="hors thématique")

        for pen in self.penalties:
            hit = has_any(title, pen.get("terms")) if pen.get("title_only", True) else has_any(body, pen.get("terms"))
            if hit:
                total += int(pen.get("weight", -10))

        if self.loc_bonus:
            loc_text = normalize(offer.location)
            if (offer.department and offer.department in self.loc_deps) or has_any(loc_text, self.loc_terms):
                total += self.loc_bonus
                reasons.append("zone géographique")

        total = max(0, min(100, total))
        fit = "hi" if total >= self.fit_hi else "mid" if total >= self.fit_mid else "lo"
        return Scored(total, fit, cat["id"] if cat else "autre", reasons)
