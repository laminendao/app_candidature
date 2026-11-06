"""Point d'entrée : python -m collector [--offline] [--only source1,source2]

1. Lit config/sources.yml et tous les profils de profiles/<id>/profile.yml
2. Interroge chaque source active une seule fois avec l'union des requêtes des profils
3. Dédoublonne, puis calcule un score par profil
4. Écrit data/profiles/<id>/offres.json, meta.json, data/profiles.json et data/status.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

from .models import Offer
from .scoring import Scorer
from .sources import ALL, Context, MissingSecret
from .utils import Http, today_iso

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PROFILES = ROOT / "profiles"
CONFIG = ROOT / "config" / "sources.yml"

log = logging.getLogger("collector")

MANUAL_SCORE = {"hi": 80, "mid": 55, "lo": 35}


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def load_profiles() -> list[dict]:
    profiles = []
    for d in sorted(PROFILES.iterdir()):
        f = d / "profile.yml"
        if d.is_dir() and not d.name.startswith("_") and f.exists():
            p = load_yaml(f)
            p["id"] = d.name
            p["_dir"] = d
            profiles.append(p)
    return profiles


# --------------------------------------------------------------------------- collecte
def collect(config: dict, profiles: list[dict], only: set[str] | None) -> tuple[list[Offer], list[dict]]:
    queries: list[str] = []
    for p in profiles:
        for q in (p.get("search", {}) or {}).get("queries", []):
            if q.lower() not in (x.lower() for x in queries):
                queries.append(q)

    since = int(config.get("since_days", 7))
    http = Http(delay=float(config.get("delay_seconds", 1.0)))
    pool: list[Offer] = []
    status: list[dict] = []

    for name, settings in (config.get("sources") or {}).items():
        settings = settings or {}
        if only and name not in only:
            continue
        cls = ALL.get(name)
        entry = {"id": name, "label": cls.label if cls else name, "homepage": getattr(cls, "homepage", ""),
                 "enabled": bool(settings.get("enabled", True)), "state": "", "count": 0, "message": "", "warnings": []}
        if not cls:
            entry.update(state="error", message="source inconnue dans config/sources.yml")
        elif not entry["enabled"]:
            entry.update(state="disabled", message="désactivée dans config/sources.yml")
        else:
            src = cls()
            ctx = Context(queries=settings.get("queries") or queries, since_days=since, settings=settings, http=http)
            t0 = time.monotonic()
            try:
                src.check_secrets()
                offers = src.fetch(ctx)
                pool += offers
                entry.update(state="warning" if ctx.warnings else "ok", count=len(offers))
            except MissingSecret as exc:
                entry.update(state="skipped", message=f"secret manquant : {exc}")
            except PermissionError as exc:
                entry.update(state="blocked", message=str(exc))
            except Exception as exc:  # une source en panne ne bloque jamais les autres
                log.exception("source %s", name)
                entry.update(state="error", message=f"{type(exc).__name__} : {exc}"[:300])
            entry["warnings"] = ctx.warnings[:10]
            entry["seconds"] = round(time.monotonic() - t0, 1)
        log.info("%-16s %-8s %4d offres %s", name, entry["state"], entry["count"], entry["message"])
        status.append(entry)
    return pool, status


def dedupe(pool: list[Offer], priority: list[str]) -> tuple[list[Offer], dict[str, list[dict]]]:
    """Une offre par empreinte ; garde la source prioritaire, liste les autres dans also_on."""
    rank = {s: i for i, s in enumerate(priority)}
    groups: dict[str, list[Offer]] = {}
    for o in pool:
        if o.title and o.url:
            groups.setdefault(o.fingerprint, []).append(o)
    kept, also = [], {}
    for items in groups.values():
        items.sort(key=lambda o: (rank.get(o.source.split("-")[0], 99), -len(o.description or "")))
        best = items[0]
        kept.append(best)
        others = [{"source": o.source, "url": o.url} for o in items[1:] if o.url != best.url]
        if others:
            also[best.uid] = others
    return kept, also


# --------------------------------------------------------------------------- profils
def build_profile(profile: dict, offers: list[Offer], also: dict, status: list[dict], labels: dict) -> dict:
    scorer = Scorer(profile)
    today = today_iso()
    min_score = int(profile.get("min_score", 30))
    retention = int(profile.get("retention_days", 30))
    out_dir = DATA / "profiles" / profile["id"]
    previous = {o["uid"]: o for o in read_json(out_dir / "offres.json", {}).get("offres", [])}
    failed = {s["id"] for s in status if s["state"] in ("error", "skipped", "blocked")}

    current: dict[str, dict] = {}
    for o in offers:
        s = scorer.score(o)
        if s.excluded or s.score < min_score:
            continue
        d = o.to_dict()
        d.update(score=s.score, fit=s.fit, category=s.category, reasons=s.reasons,
                 source_label=labels.get(o.source.split("-")[0], o.source), also_on=also.get(o.uid, []),
                 active=True, last_seen=today, first_seen=previous.get(o.uid, {}).get("first_seen", today))
        current[d["uid"]] = d

    # Offres saisies à la main dans profiles/<id>/manual.json
    for m in read_json(profile["_dir"] / "manual.json", []):
        uid = f"manuel:{m['id']}"
        d = {"uid": uid, "source": "manuel", "source_id": m["id"], "source_label": "Sélection manuelle",
             "title": m.get("title", ""), "url": m.get("url", ""), "org": m.get("org", ""),
             "location": m.get("location", ""), "department": "", "contract": m.get("contract", ""),
             "description": "", "published": m.get("published"), "deadline": m.get("deadline"),
             "salary": "", "via": "", "extra": {"contact": m["contact"]} if m.get("contact") else {},
             "score": MANUAL_SCORE.get(m.get("fit", "mid"), 55), "fit": m.get("fit", "mid"),
             "category": m.get("category", "autre"), "reasons": [], "why": m.get("why", ""),
             "also_on": [], "active": True, "last_seen": today,
             "first_seen": previous.get(uid, {}).get("first_seen", today)}
        current[uid] = d

    # Offres vues lors d'un passage précédent mais absentes aujourd'hui
    cutoff = (date.fromisoformat(today) - timedelta(days=retention)).isoformat()
    stale_deadline = (date.fromisoformat(today) - timedelta(days=14)).isoformat()
    for uid, old in previous.items():
        if uid in current or old.get("source") == "manuel":
            continue
        if old.get("deadline") and old["deadline"] < stale_deadline:
            continue
        if old.get("source", "").split("-")[0] in failed:
            current[uid] = old  # la source a échoué : on ne conclut rien
        elif old.get("last_seen", "") >= cutoff:
            current[uid] = {**old, "active": False}

    items = sorted(current.values(), key=lambda d: (d["score"], d.get("published") or ""), reverse=True)
    write_json(out_dir / "offres.json", {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                         "profile": profile["id"], "count": len(items), "offres": items})
    meta = {
        "id": profile["id"], "name": profile.get("name", profile["id"]),
        "categories": [{"id": c["id"], "label": c.get("label", c["id"])} for c in profile.get("categories", [])] + [{"id": "autre", "label": "Autres"}],
        "echeances": profile.get("echeances", []), "liens": profile.get("liens", []),
        "min_score": min_score, "fit": profile.get("fit", {}),
    }
    write_json(out_dir / "meta.json", meta)
    return {"id": profile["id"], "name": meta["name"], "count": len(items),
            "new": sum(1 for d in items if d["first_seen"] == today and d["source"] != "manuel")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Collecte des offres d'emploi")
    ap.add_argument("--offline", action="store_true", help="ne contacte aucune source (recalcule les scores et les fichiers)")
    ap.add_argument("--only", help="liste de sources séparées par des virgules")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    config = load_yaml(CONFIG)
    profiles = load_profiles()
    if not profiles:
        log.error("aucun profil dans profiles/")
        return 1

    if args.offline:
        pool, status = [], read_json(DATA / "status.json", {}).get("sources", [])
    else:
        pool, status = collect(config, profiles, set(args.only.split(",")) if args.only else None)

    labels = {name: cls.label for name, cls in ALL.items()}
    offers, also = dedupe(pool, config.get("priority", list(ALL)))
    summary = [build_profile(p, offers, also, status, labels) for p in profiles]

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not args.offline:
        write_json(DATA / "status.json", {"generated": now, "raw": len(pool), "unique": len(offers), "sources": status})
    write_json(DATA / "profiles.json", {"generated": now, "profiles": summary})
    for s in summary:
        log.info("profil %-12s %4d offres (%d nouvelles)", s["id"], s["count"], s["new"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
