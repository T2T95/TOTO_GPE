from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import ssl


# Storage layout (relative to project_root = back/):
# - back/config/dns/blocklist.txt
# - back/config/dns/allowlist.txt
# - back/generated/dns/dnsmasq_blocklist.conf


def _cfg_dir(root: Path) -> Path:
    return root / "config" / "dns"


def _gen_dir(root: Path) -> Path:
    return root / "generated" / "dns"


def ensure_dns_storage(root: Path) -> None:
    _cfg_dir(root).mkdir(parents=True, exist_ok=True)
    _gen_dir(root).mkdir(parents=True, exist_ok=True)


def _normalized_domain(domain: str) -> str:
    d = (domain or "").strip().lower().strip('.')
    return d


_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def _is_valid_domain(domain: str) -> bool:
    d = _normalized_domain(domain)
    if not d or "/" in d or " " in d:
        return False
    if len(d) > 253:
        return False
    parts = d.split('.')
    if len(parts) < 2:
        return False
    return all(_LABEL_RE.match(p) is not None for p in parts)


def _read_list(path: Path) -> set[str]:
    items: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            d = _normalized_domain(line)
            if d and _is_valid_domain(d):
                items.add(d)
    return items


def _write_list(path: Path, items: Iterable[str]) -> None:
    ordered = sorted({_normalized_domain(x) for x in items if _is_valid_domain(x)})
    path.write_text("\n".join(ordered) + ("\n" if ordered else ""), encoding="utf-8")


def blocklist_path(root: Path) -> Path:
    return _cfg_dir(root) / "blocklist.txt"


def allowlist_path(root: Path) -> Path:
    return _cfg_dir(root) / "allowlist.txt"


def load_blocklist(root: Path) -> set[str]:
    return _read_list(blocklist_path(root))


def load_allowlist(root: Path) -> set[str]:
    return _read_list(allowlist_path(root))


def add_to_blocklist(root: Path, domain: str) -> Tuple[bool, str]:
    d = _normalized_domain(domain)
    if not _is_valid_domain(d):
        return False, f"Domaine invalide: {domain!r}"
    bl = load_blocklist(root)
    if d in bl:
        return True, f"Déjà présent dans la blocklist: {d}"
    bl.add(d)
    ensure_dns_storage(root)
    _write_list(blocklist_path(root), bl)
    return True, f"Ajouté à la blocklist: {d}"


def remove_from_blocklist(root: Path, domain: str) -> Tuple[bool, str]:
    d = _normalized_domain(domain)
    bl = load_blocklist(root)
    if d not in bl:
        return False, f"Absent de la blocklist: {d}"
    bl.remove(d)
    _write_list(blocklist_path(root), bl)
    return True, f"Retiré de la blocklist: {d}"


def is_domain_blocked(root: Path, domain: str) -> bool:
    d = _normalized_domain(domain)
    if not _is_valid_domain(d):
        return False
    bl = load_blocklist(root)
    al = load_allowlist(root)
    # Allowlist surpasse blocklist
    if d in al:
        return False
    # Vérifie suffixes: si xyz.evil.com et blocklist contient evil.com -> bloqué
    parts = d.split('.')
    for i in range(len(parts) - 1):
        cand = '.'.join(parts[i:])
        if cand in bl and cand not in al:
            return True
    return d in bl and d not in al


def generate_dnsmasq_blocklist(root: Path) -> Path:
    ensure_dns_storage(root)
    bl = load_blocklist(root)
    al = load_allowlist(root)
    # Retirer les domaines explicitement autorisés
    effective = sorted({d for d in bl if d not in al})

    lines = []
    # dnsmasq: address=/domain/0.0.0.0 bloque domaine + sous-domaines
    for d in effective:
        lines.append(f"address=/{d}/0.0.0.0")
        # Optionnel: IPv6
        lines.append(f"address=/{d}/::")

    out = _gen_dir(root) / "dnsmasq_blocklist.conf"
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return out


def _parse_domains_from_text(text: str) -> set[str]:
    domains: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        # dnsmasq format: address=/domain/0.0.0.0 or /::
        if line.startswith("address=/"):
            try:
                part = line.split("/", 2)[1]
                d = _normalized_domain(part)
                if _is_valid_domain(d):
                    domains.add(d)
                    continue
            except Exception:
                pass
        # hosts format: 0.0.0.0 domain or 127.0.0.1 domain
        tokens = line.split()
        if len(tokens) >= 2 and tokens[0] in {"0.0.0.0", "127.0.0.1", "::"}:
            d = _normalized_domain(tokens[1])
            if _is_valid_domain(d):
                domains.add(d)
                continue
        # plain domain per line
        d = _normalized_domain(line)
        if _is_valid_domain(d):
            domains.add(d)
    return domains


def import_domains_from_text(root: Path, text: str) -> Tuple[int, int]:
    """Importe des domaines depuis un texte et fusionne dans blocklist.

    Retourne (ajoutés, total_après).
    """
    ensure_dns_storage(root)
    current = load_blocklist(root)
    to_add = _parse_domains_from_text(text)
    before = len(current)
    current |= to_add
    _write_list(blocklist_path(root), current)
    return (len(current) - before, len(current))


def import_from_url(root: Path, url: str, timeout: int = 25) -> Tuple[bool, str, Tuple[int, int] | None]:
    """Télécharge une liste et l'importe dans la blocklist.

    Renvoie (ok, message, (ajoutés, total)) si ok.
    """
    ctx = None
    try:
        ctx = ssl.create_default_context()
    except Exception:
        ctx = None
    req = Request(url, headers={"User-Agent": "Elhomeshield/0.1"})
    try:
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            if resp.status and resp.status >= 400:
                return False, f"HTTP {resp.status} sur {url}", None
            text = resp.read().decode("utf-8", errors="ignore")
    except HTTPError as e:
        return False, f"HTTPError {e.code} sur {url}", None
    except URLError as e:
        return False, f"URLError: {e.reason}", None
    except Exception as e:
        return False, f"Erreur téléchargement: {e}", None

    added, total = import_domains_from_text(root, text)
    return True, f"Import réussi depuis {url} (ajoutés: {added}, total: {total})", (added, total)


def hagezi_profiles() -> dict:
    """Quelques profils Hagezi pratiques (format domaines).

    On accepte aussi d'autres URLs custom côté CLI.
    """
    base = "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains"
    return {
        "light": f"{base}/light.txt",
        "normal": f"{base}/normal.txt",
        "pro": f"{base}/pro.txt",
        "ultimate": f"{base}/ultimate.txt",
    }


__all__ = [
    "ensure_dns_storage",
    "load_blocklist",
    "load_allowlist",
    "add_to_blocklist",
    "remove_from_blocklist",
    "is_domain_blocked",
    "generate_dnsmasq_blocklist",
    "import_from_url",
    "import_domains_from_text",
    "hagezi_profiles",
]
