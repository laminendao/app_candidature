from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..models import Offer
from ..utils import Http


class MissingSecret(Exception):
    """Une clé d'API nécessaire n'est pas configurée."""


@dataclass
class Context:
    """Ce que le collecteur transmet à chaque source."""

    queries: list[str]            # union des requêtes de tous les profils
    since_days: int               # ancienneté maximale des offres recherchées
    settings: dict                # réglages propres à la source (config/sources.yml)
    http: Http
    warnings: list[str] = field(default_factory=list)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


class Source:
    """Classe de base. Une source = un module qui renvoie une liste d'Offer."""

    name: str = ""          # identifiant technique, utilisé dans config/sources.yml
    label: str = ""         # nom affiché dans l'appli
    homepage: str = ""
    secrets: tuple[str, ...] = ()   # variables d'environnement requises

    def secret(self, key: str) -> str:
        value = os.environ.get(key, "").strip()
        if not value:
            raise MissingSecret(key)
        return value

    def check_secrets(self) -> None:
        for key in self.secrets:
            self.secret(key)

    def fetch(self, ctx: Context) -> list[Offer]:  # pragma: no cover - interface
        raise NotImplementedError
