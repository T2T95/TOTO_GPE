from __future__ import annotations

import json
import re
from datetime import datetime, time
from pathlib import Path
from typing import Dict, List, Tuple

from ..dns.services import load_blocklist, load_allowlist


def _cfg_dir(root: Path) -> Path:
    return root / "config" / "parental"


def _gen_dir(root: Path) -> Path:
    return root / "generated" / "dns"


def ensure_parental_storage(root: Path) -> None:
    d = _cfg_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    # categories.json
    cats = d / "categories.json"
    if not cats.exists():
        cats.write_text(json.dumps({"adult": [], "social": [], "gaming": []}, indent=2) + "\n", encoding="utf-8")
    # settings.json
    settings = d / "settings.json"
    if not settings.exists():
        settings.write_text(json.dumps({"active_categories": ["adult"], "schedule": {"enabled": False, "range": "22:00-06:00"}}, indent=2) + "\n", encoding="utf-8")


def _cats_path(root: Path) -> Path:
    return _cfg_dir(root) / "categories.json"


def _settings_path(root: Path) -> Path:
    return _cfg_dir(root) / "settings.json"


def list_categories(root: Path) -> Dict[str, List[str]]:
    try:
        return json.loads(_cats_path(root).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_categories(root: Path, cats: Dict[str, List[str]]) -> None:
    _cats_path(root).write_text(json.dumps(cats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _normalize_domain(d: str) -> str:
    d = (d or "").strip().lower().strip('.')
    return d


_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def _valid_domain(d: str) -> bool:
    if not d:
        return False
    parts = d.split('.')
    if len(parts) < 2:
        return False
    return all(_LABEL_RE.match(p) for p in parts)


def add_domain_to_category(root: Path, category: str, domain: str) -> Tuple[bool, str]:
    cats = list_categories(root)
    if category not in cats:
        cats[category] = []
    d = _normalize_domain(domain)
    if not _valid_domain(d):
        return False, f"Domaine invalide: {domain!r}"
    if d in cats[category]:
        return True, f"Deja present: {d}"
    cats[category].append(d)
    _save_categories(root, cats)
    return True, f"Ajoute: {d}"


def remove_domain_from_category(root: Path, category: str, domain: str) -> Tuple[bool, str]:
    cats = list_categories(root)
    d = _normalize_domain(domain)
    if category not in cats or d not in cats[category]:
        return False, f"Absent: {d}"
    cats[category] = [x for x in cats[category] if x != d]
    _save_categories(root, cats)
    return True, f"Retire: {d}"


def get_active_categories(root: Path) -> List[str]:
    try:
        s = json.loads(_settings_path(root).read_text(encoding="utf-8"))
        return list(s.get("active_categories") or [])
    except Exception:
        return []


def set_active_categories(root: Path, cats: List[str]) -> Tuple[bool, str]:
    s = _load_settings(root)
    available = set(list_categories(root).keys())
    filt = [c for c in cats if c in available]
    s["active_categories"] = filt
    _save_settings(root, s)
    return True, f"Actives: {', '.join(filt) if filt else '(aucune)'}"


def get_schedule(root: Path) -> Dict:
    return _load_settings(root).get("schedule", {"enabled": False, "range": "22:00-06:00"})


def set_schedule_enabled(root: Path, enabled: bool) -> None:
    s = _load_settings(root)
    s.setdefault("schedule", {})["enabled"] = bool(enabled)
    _save_settings(root, s)


def set_schedule_range(root: Path, rng: str) -> Tuple[bool, str]:
    if not _parse_range(rng):
        return False, "Format invalide. Ex: 22:00-06:00"
    s = _load_settings(root)
    s.setdefault("schedule", {})["range"] = rng
    _save_settings(root, s)
    return True, f"Plage enregistree: {rng}"


def _load_settings(root: Path) -> Dict:
    try:
        return json.loads(_settings_path(root).read_text(encoding="utf-8"))
    except Exception:
        return {"active_categories": [], "schedule": {"enabled": False, "range": "22:00-06:00"}}


def _save_settings(root: Path, s: Dict) -> None:
    _settings_path(root).write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _parse_range(rng: str) -> Tuple[time, time] | None:
    try:
        a, b = [x.strip() for x in rng.split("-")]
        h1, m1 = [int(x) for x in a.split(":")]
        h2, m2 = [int(x) for x in b.split(":")]
        return time(h1, m1), time(h2, m2)
    except Exception:
        return None


def _is_quiet_now(s: Dict) -> bool:
    sched = s.get("schedule") or {}
    if not sched.get("enabled"):
        return True  # si desactive, considerer actif tout le temps
    rng = sched.get("range") or "22:00-06:00"
    parsed = _parse_range(rng)
    if not parsed:
        return True
    t1, t2 = parsed
    now = datetime.now().time()
    if t1 <= t2:
        return t1 <= now <= t2
    else:
        # chevauche minuit
        return now >= t1 or now <= t2


def _write_dnsmasq_conf(root: Path, domains: List[str]) -> Path:
    lines: List[str] = []
    for d in sorted(set(domains)):
        lines.append(f"address=/{d}/0.0.0.0")
        lines.append(f"address=/{d}/::")
    out = _gen_dir(root) / "dnsmasq_blocklist.conf"
    # Fusionner avec la blocklist existante (DNS services) pour conserver base
    # Charger base et allowlist, recalculer dans ce fichier unique
    base = load_blocklist(root)
    allow = load_allowlist(root)
    effective = sorted({x for x in (set(base) | set(domains)) if x not in allow})
    lines = []
    for d in effective:
        lines.append(f"address=/{d}/0.0.0.0")
        lines.append(f"address=/{d}/::")
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return out


def apply_parental_to_dns(root: Path) -> Path:
    ensure_parental_storage(root)
    cats = list_categories(root)
    s = _load_settings(root)
    if not _is_quiet_now(s):
        # en dehors des horaires, ne rien ajouter
        return _write_dnsmasq_conf(root, [])
    active = s.get("active_categories") or []
    doms: List[str] = []
    for c in active:
        doms.extend(cats.get(c, []))
    return _write_dnsmasq_conf(root, doms)


__all__ = [
    "ensure_parental_storage",
    "list_categories",
    "add_domain_to_category",
    "remove_domain_from_category",
    "set_active_categories",
    "get_active_categories",
    "get_schedule",
    "set_schedule_enabled",
    "set_schedule_range",
    "apply_parental_to_dns",
]
