"""Tests hors-ligne : extracteurs, API simulées, score et passage complet.
Lancer : python -m unittest discover -s tests -v"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from collector import main as M
from collector.models import Offer
from collector.scoring import Scorer
from collector.sources import ALL, Context
from collector.sources.rss import parse_feed
from collector.utils import Http, parse_date

FIX = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(self, status=200, text="", data=None):
        self.status_code, self.text, self._data = status, text, data

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def ctx(settings=None, queries=("data analyst",)):
    return Context(queries=list(queries), since_days=7, settings=settings or {}, http=Http(delay=0))


class UtilsTest(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(parse_date("Publiée le 19/10/2026 10:34."), "2026-10-19")
        self.assertEqual(parse_date("Publié le 9 octobre 2026 Paris"), "2026-10-09")
        self.assertEqual(parse_date("1er décembre 2026"), "2026-12-01")
        self.assertEqual(parse_date("Thu, 05 Nov 2026 09:00:00 GMT"), "2026-11-05")
        self.assertEqual(parse_date("2026-11-30T00:00:00Z"), "2026-11-30")


class ParsersTest(unittest.TestCase):
    def test_rss(self):
        entries = parse_feed((FIX / "cnrs.xml").read_text())
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["date"], "2026-11-04")
        self.assertIn("Ingénieur", entries[0]["title"])

    def test_inria(self):
        offers = ALL["inria"]().parse((FIX / "inria.html").read_text(), "https://jobs.inria.fr/public/classic/fr/offres")
        self.assertEqual(len(offers), 2)
        o = offers[0]
        self.assertEqual(o.source_id, "2026-10351")
        self.assertEqual(o.location, "Sophia Antipolis")
        self.assertEqual(o.deadline, "2026-11-30")
        self.assertTrue(o.url.startswith("https://jobs.inria.fr/"))

    def test_hellowork(self):
        offers = ALL["hellowork"]().parse((FIX / "hellowork.html").read_text(), "https://www.hellowork.com/fr-fr/emploi/x.html")
        self.assertEqual(len(offers), 2)
        self.assertEqual(offers[0].title, "Data Analyst H/F")
        self.assertEqual(offers[0].org, "Bouygues Construction")
        self.assertEqual(offers[0].contract, "CDI")

    def test_sfds(self):
        offers = ALL["sfds"]().parse((FIX / "sfds.html").read_text(), "https://www.sfds.asso.fr/fr/n/506/")
        self.assertEqual(len(offers), 1)  # le stage est écarté
        o = offers[0]
        self.assertTrue(o.title.startswith("Chargé d"))
        self.assertEqual(o.org, "ONIRIS VetAgroBio Nantes")
        self.assertEqual(o.published, "2026-10-14")
        self.assertEqual(o.extra.get("contact"), "contact@oniris.fr")

    def test_cesi(self):
        offers = ALL["cesi"]().parse((FIX / "cesi.html").read_text(), "https://lineact.cesi.fr/recrutement/")
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].published, "2026-09-17")
        self.assertEqual(offers[0].contract, "CDI")


class ApiTest(unittest.TestCase):
    def test_france_travail(self):
        src = ALL["france_travail"]()
        c = ctx()
        token = FakeResponse(200, data={"access_token": "t"})
        page = FakeResponse(206, data={"resultats": [{
            "id": "191ABC", "intitule": "Data analyst (H/F)", "description": "Analyse <b>SQL</b>",
            "dateCreation": "2026-11-05T08:00:00.000Z", "lieuTravail": {"libelle": "91 - LES ULIS", "codePostal": "91940"},
            "entreprise": {"nom": "Eiffage"}, "typeContratLibelle": "CDI",
            "origineOffre": {"urlOrigine": "https://candidat.francetravail.fr/offres/recherche/detail/191ABC", "partenaires": [{"nom": "HELLOWORK"}]},
        }]})
        with mock.patch.dict("os.environ", {"FRANCE_TRAVAIL_CLIENT_ID": "a", "FRANCE_TRAVAIL_CLIENT_SECRET": "b"}), \
             mock.patch.object(c.http, "post", return_value=token), \
             mock.patch.object(c.http, "get", return_value=page) as g:
            offers = src.fetch(c)
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].department, "91")
        self.assertEqual(offers[0].via, "HELLOWORK")
        self.assertEqual(offers[0].description, "Analyse SQL")
        self.assertEqual(g.call_args.kwargs["params"]["motsCles"], "data,analyst")

    def test_adzuna(self):
        src = ALL["adzuna"]()
        c = ctx(settings={"max_pages": 1})
        page = FakeResponse(200, data={"results": [{
            "id": 42, "title": "<strong>Data</strong> Scientist", "redirect_url": "https://adzuna.fr/x",
            "company": {"display_name": "SNCF"}, "location": {"display_name": "Saint-Denis"},
            "contract_type": "permanent", "created": "2026-11-04T10:00:00Z", "salary_min": 45000, "salary_max": 55000,
            "description": "maintenance prédictive",
        }]})
        with mock.patch.dict("os.environ", {"ADZUNA_APP_ID": "a", "ADZUNA_APP_KEY": "b"}), \
             mock.patch.object(c.http, "get", return_value=page):
            offers = src.fetch(c)
        self.assertEqual(offers[0].title, "Data Scientist")
        self.assertEqual(offers[0].contract, "CDI")
        self.assertEqual(offers[0].salary, "45 000 – 55 000 €")


class ScoringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scorer = Scorer(M.load_yaml(M.PROFILES / "lamine" / "profile.yml"))

    def s(self, title, desc="", loc="", dep=""):
        return self.scorer.score(Offer("t", "1", title, "https://x", description=desc, location=loc, department=dep))

    def test_strong_match(self):
        r = self.s("Ingénieur Data Science – Maintenance prédictive ferroviaire", "séries temporelles, python, fiabilité")
        self.assertEqual(r.category, "ds")
        self.assertEqual(r.fit, "hi")

    def test_btp_data_analyst_is_kept(self):
        r = self.s("Data Analyst H/F", "Groupe BTP, SQL, Power BI, statistiques", "Nanterre", "92")
        self.assertEqual(r.category, "da")
        self.assertGreaterEqual(r.score, 35)

    def test_lycee(self):
        r = self.s("Enseignant(e) de mathématiques (Oise)", "lycée, mathématiques")
        self.assertEqual(r.category, "ens_sec")

    def test_exclusions(self):
        self.assertIsNotNone(self.s("Stage Data Scientist").excluded)
        self.assertIsNotNone(self.s("Alternance data analyst").excluded)
        # « apprentissage automatique » ne doit pas être pris pour de l'alternance
        self.assertIsNone(self.s("Ingénieur apprentissage automatique").excluded)

    def test_irrelevant_is_low(self):
        self.assertLess(self.s("Technicien de laboratoire en biologie moléculaire").score, 35)


class PipelineTest(unittest.TestCase):
    """Passage complet avec des sources simulées, dans un dossier temporaire."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(M.PROFILES, self.tmp / "profiles")
        self.patches = [mock.patch.object(M, "DATA", self.tmp / "data"), mock.patch.object(M, "PROFILES", self.tmp / "profiles")]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp)

    def test_run(self):
        pool = [
            Offer("france_travail", "1", "Data Analyst H/F", "https://ft/1", org="Vinci", department="92", description="SQL statistiques"),
            Offer("adzuna", "9", "Data analyst (H/F)", "https://az/9", org="Vinci"),       # doublon
            Offer("cnrs", "2", "Technicien en biologie", "https://cnrs/2", org="CNRS"),   # hors profil
        ]
        status = [{"id": "france_travail", "state": "ok"}, {"id": "adzuna", "state": "ok"}, {"id": "cnrs", "state": "ok"}]
        with mock.patch.object(M, "collect", return_value=(pool, status)), mock.patch.object(M, "load_yaml", wraps=M.load_yaml):
            self.assertEqual(M.main([]), 0)
        data = json.loads((self.tmp / "data/profiles/lamine/offres.json").read_text())
        uids = {o["uid"] for o in data["offres"]}
        self.assertIn("france_travail:1", uids)
        self.assertNotIn("adzuna:9", uids)          # dédoublonné
        self.assertNotIn("cnrs:2", uids)            # score trop bas
        self.assertEqual(sum(1 for o in data["offres"] if o["source"] == "manuel"), 13)
        ft = next(o for o in data["offres"] if o["uid"] == "france_travail:1")
        self.assertEqual(ft["also_on"][0]["source"], "adzuna")
        meta = json.loads((self.tmp / "data/profiles/lamine/meta.json").read_text())
        self.assertTrue(meta["echeances"])
        profiles = json.loads((self.tmp / "data/profiles.json").read_text())
        self.assertEqual([p["id"] for p in profiles["profiles"]], ["lamine"])  # _modele ignoré

        # Deuxième passage sans l'offre : elle reste, grisée, avec sa date de première vue
        with mock.patch.object(M, "collect", return_value=([], status)):
            M.main([])
        data2 = json.loads((self.tmp / "data/profiles/lamine/offres.json").read_text())
        old = next(o for o in data2["offres"] if o["uid"] == "france_travail:1")
        self.assertFalse(old["active"])
        self.assertEqual(old["first_seen"], ft["first_seen"])


if __name__ == "__main__":
    unittest.main()
