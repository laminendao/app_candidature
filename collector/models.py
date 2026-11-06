from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field

from .utils import normalize


@dataclass
class Offer:
    """Une offre telle que renvoyée par une source, avant le score."""

    source: str              # identifiant de la source (ex. "france_travail")
    source_id: str           # identifiant de l'offre chez la source
    title: str
    url: str
    org: str = ""
    location: str = ""
    department: str = ""     # code département (ex. "91") si connu
    contract: str = ""
    description: str = ""
    published: str | None = None   # AAAA-MM-JJ
    deadline: str | None = None    # AAAA-MM-JJ
    salary: str = ""
    via: str = ""            # site d'origine quand la source est un agrégateur
    extra: dict = field(default_factory=dict)

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.source_id}"

    @property
    def fingerprint(self) -> str:
        """Empreinte pour repérer la même offre publiée sur plusieurs sources."""
        noise = {"h", "f", "x", "nb", "hf", "fh", "m", "w", "d"}  # « H/F », « F/H/X », « m/w/d »…
        words = [w for w in re.findall(r"[a-z0-9]+", normalize(self.title)) if w not in noise]
        org = re.findall(r"[a-z0-9]+", normalize(self.org))
        key = " ".join(words) + "|" + " ".join(org)
        return hashlib.sha1(key.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["uid"] = self.uid
        d["description"] = (self.description or "")[:900]
        return d
