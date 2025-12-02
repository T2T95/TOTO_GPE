from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Tuple
import subprocess


def _cfg_dir(root: Path) -> Path:
    return root / "config" / "firewall"


def _gen_dir(root: Path) -> Path:
    return root / "generated" / "firewall"


def ensure_fw_storage(root: Path) -> None:
    _cfg_dir(root).mkdir(parents=True, exist_ok=True)
    _gen_dir(root).mkdir(parents=True, exist_ok=True)
    rules_path = _cfg_dir(root) / "rules.json"
    if not rules_path.exists():
        rules_path.write_text("[]\n", encoding="utf-8")


def _rules_path(root: Path) -> Path:
    return _cfg_dir(root) / "rules.json"


def list_rules(root: Path) -> List[Dict]:
    p = _rules_path(root)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_rules(root: Path, rules: List[Dict]) -> None:
    (_rules_path(root)).write_text(json.dumps(rules, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _prompt(txt: str, default: str = "") -> str:
    v = input(f"{txt} [{default}]: ").strip()
    return v or default


def add_rule_interactive(root: Path) -> Tuple[bool, str]:
    rules = list_rules(root)
    name = _prompt("Nom de la règle", "EHS rule")
    action = (_prompt("Action (allow/block)", "block").lower())
    if action not in {"allow", "block"}:
        return False, "Action invalide"
    direction = (_prompt("Direction (in/out)", "out").lower())
    if direction not in {"in", "out"}:
        return False, "Direction invalide"
    protocol = (_prompt("Protocole (tcp/udp/any)", "any").lower())
    if protocol not in {"tcp", "udp", "any"}:
        return False, "Protocole invalide"
    remote = _prompt("Remote IP/CIDR (any pour tout)", "any")
    localport = _prompt("Local port (any)", "any")
    remoteport = _prompt("Remote port (any)", "any")

    rule = {
        "name": name,
        "action": action,
        "direction": direction,
        "protocol": protocol,
        "remote": remote,
        "localport": localport,
        "remoteport": remoteport,
    }
    rules.append(rule)
    _save_rules(root, rules)
    return True, f"Règle ajoutée: {name}"


def remove_rule_by_index(root: Path, idx: int) -> Tuple[bool, str]:
    rules = list_rules(root)
    if idx < 0 or idx >= len(rules):
        return False, "Index hors bornes"
    r = rules.pop(idx)
    _save_rules(root, rules)
    return True, f"Règle supprimée: {r.get('name','')}"


def generate_windows_netsh(root: Path) -> Path:
    rules = list_rules(root)
    lines: List[str] = [
        "rem Elhomeshield firewall rules (Windows netsh)",
    ]
    for r in rules:
        dirflag = "in" if r.get("direction") == "in" else "out"
        action = "allow" if r.get("action") == "allow" else "block"
        proto = r.get("protocol", "any")
        remote = r.get("remote", "any")
        lport = r.get("localport", "any")
        rport = r.get("remoteport", "any")
        name = r.get("name", "EHS rule")
        parts = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name=\"{name}\"",
            f"dir={dirflag}",
            f"action={action}",
        ]
        if proto != "any":
            parts.append(f"protocol={proto}")
        if remote != "any":
            parts.append(f"remoteip={remote}")
        if lport != "any":
            parts.append(f"localport={lport}")
        if rport != "any":
            parts.append(f"remoteport={rport}")
        lines.append(" ".join(parts))

    out = _gen_dir(root) / "windows_apply.ps1"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def generate_linux_iptables(root: Path) -> Path:
    rules = list_rules(root)
    lines: List[str] = [
        "#!/usr/bin/env bash",
        "set -e",
        "# Elhomeshield firewall rules (iptables)",
    ]
    for r in rules:
        chain = "OUTPUT" if r.get("direction") != "in" else "INPUT"
        action = "ACCEPT" if r.get("action") == "allow" else "DROP"
        proto = r.get("protocol", "any")
        remote = r.get("remote", "any")
        lport = r.get("localport", "any")
        rport = r.get("remoteport", "any")
        cmd = ["iptables", "-A", chain]
        if proto != "any":
            cmd += ["-p", proto]
        if remote != "any":
            cmd += ["-d", remote] if chain == "OUTPUT" else ["-s", remote]
        if lport != "any" and proto in {"tcp", "udp"}:
            cmd += ["--sport", str(lport)]
        if rport != "any" and proto in {"tcp", "udp"}:
            cmd += ["--dport", str(rport)]
        cmd += ["-j", action]
        lines.append(" ".join(cmd))

    out = _gen_dir(root) / "linux_iptables.sh"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def apply_windows_netsh(root: Path) -> Tuple[Path, int]:
    script = generate_windows_netsh(root)
    try:
        code = subprocess.call(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)])
    except Exception:
        code = 1
    return script, code


__all__ = [
    "ensure_fw_storage",
    "list_rules",
    "add_rule_interactive",
    "remove_rule_by_index",
    "generate_windows_netsh",
    "generate_linux_iptables",
    "apply_windows_netsh",
]

