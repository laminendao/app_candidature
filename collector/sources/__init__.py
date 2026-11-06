"""Registre des sources. Pour ajouter une source : écrire une classe dérivée de Source,
l'ajouter à ALL ci-dessous, puis l'activer dans config/sources.yml."""
from .adzuna import Adzuna
from .base import Context, MissingSecret, Source
from .cnrs import Cnrs
from .email_alerts import EmailAlerts
from .france_travail import FranceTravail
from .html_sites import Cesi, Hellowork, Inria, Sfds
from .rss import GenericRss

ALL: dict[str, type[Source]] = {cls.name: cls for cls in (FranceTravail, Adzuna, Cnrs, Inria, Hellowork, Sfds, Cesi, GenericRss, EmailAlerts)}

__all__ = ["ALL", "Context", "MissingSecret", "Source"]
