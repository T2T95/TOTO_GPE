from __future__ import annotations

import re
import csv
import platform
import subprocess
from pathlib import Path
from typing import List, Dict
import socket
import shutil
import ipaddress
import xml.etree.ElementTree as ET
from ...license import normalize_mac


def _gen_dir(root: Path) -> Path:
    return root / "generated" / "inventory"


def ensure_inventory_storage(root: Path) -> None:
    _gen_dir(root).mkdir(parents=True, exist_ok=True)


def _run(cmd: list[str]) -> str:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="ignore")
        return out
    except Exception:
        return ""


def _parse_arp_a(text: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if not text:
        return rows
    sysname = platform.system().lower()
    lines = text.splitlines()
    cur_iface = ""
    if sysname.startswith("win"):
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            if ln.lower().startswith("interface:"):
                # Interface: 192.168.1.42 --- 0x9
                cur_iface = ln.split("---", 1)[0].replace("Interface:", "").strip()
                continue
            # 192.168.1.1          d8:bb:c1:12:34:56     dynamic
            parts = re.split(r"\s+", ln)
            if len(parts) >= 3 and re.match(r"^\d+\.\d+\.\d+\.\d+$", parts[0]):
                ip = parts[0]
                mac = normalize_mac(parts[1])
                state = parts[2].lower()
                rows.append({"ip": ip, "mac": mac, "state": state, "iface": cur_iface, "src": "arp-a"})
    else:
        # Linux/mac: typical 'arp -a' format
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            m = re.search(r"\((\d+\.\d+\.\d+\.\d+)\) at ([0-9A-Fa-f:]{17}|<incomplete>) on (\S+)", ln)
            if m:
                ip = m.group(1)
                mac_raw = m.group(2)
                iface = m.group(3)
                mac = normalize_mac(mac_raw) if mac_raw != "<incomplete>" else ""
                state = "incomplete" if not mac else "reachable"
                rows.append({"ip": ip, "mac": mac, "state": state, "iface": iface, "src": "arp-a"})
    return rows


def _parse_ip_neigh(text: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if not text:
        return rows
    for ln in text.splitlines():
        # 192.168.1.1 dev eth0 lladdr d8:bb:c1:12:34:56 REACHABLE
        m = re.search(r"^(\d+\.\d+\.\d+\.\d+)\s+dev\s+(\S+)(?:\s+lladdr\s+([0-9A-Fa-f:]{17}))?\s+(\S+)", ln)
        if m:
            ip = m.group(1)
            iface = m.group(2)
            mac = normalize_mac(m.group(3) or "")
            state = m.group(4)
            rows.append({"ip": ip, "mac": mac, "state": state, "iface": iface, "src": "ip-neigh"})
    return rows


def scan_neighbors() -> List[Dict[str, str]]:
    sysname = platform.system().lower()
    res: List[Dict[str, str]] = []
    if sysname.startswith("win"):
        res += scan_with_win_netneighbor()
        res += _parse_arp_a(_run(["arp", "-a"]))
    else:
        res += _parse_ip_neigh(_run(["ip", "neigh"]))
        if not res:
            res += _parse_arp_a(_run(["arp", "-a"]))
    # Deduplicate by (ip, mac or iface)
    seen = set()
    uniq: List[Dict[str, str]] = []
    for r in res:
        key = (r.get("ip",""), r.get("mac",""), r.get("iface",""))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    # Sort by IP
    def ip_key(v: str) -> int:
        try:
            return sum(int(p) << (8*(3-i)) for i,p in enumerate(v.split(".")))
        except Exception:
            return 0
    uniq.sort(key=lambda x: ip_key(x.get("ip","0.0.0.0")))
    return _filter_relevant_hosts(uniq)


def export_csv(root: Path) -> Path:
    ensure_inventory_storage(root)
    rows = smart_scan(None)
    try:
        rows = enrich_with_names(rows, max_lookups=100)
    except Exception:
        pass
    out = _gen_dir(root) / "devices.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ip","name","mac","state","iface","src"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return out


def _reverse_dns(ip: str, timeout: float = 0.5) -> str:
    old_to = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        name, _, _ = socket.gethostbyaddr(ip)
        return name
    except Exception:
        return ""
    finally:
        try:
            socket.setdefaulttimeout(old_to)
        except Exception:
            pass


def _win_ping_name(ip: str, timeout_ms: int = 300) -> str:
    # Parse: Pinging NAME [ip] with 32 bytes of data:
    out = _run(["ping", "-a", "-n", "1", "-w", str(timeout_ms), ip])
    for line in out.splitlines():
        line = line.strip()
        m = re.search(r"^Pinging\s+(.+)\s+\[" + re.escape(ip) + r"\]", line)
        if m:
            name = m.group(1).strip()
            # Avoid echoing back the IP
            if name and name != ip:
                return name
    return ""


def enrich_with_names(rows: List[Dict[str, str]], max_lookups: int = 15) -> List[Dict[str, str]]:
    sysname = platform.system().lower()
    out: List[Dict[str, str]] = []
    count = 0
    for r in rows:
        ip = r.get("ip", "")
        if count < max_lookups and _is_private_unicast(ip):
            name = _reverse_dns(ip)
            if not name and sysname.startswith("win"):
                name = _win_ping_name(ip)
            if name:
                r = dict(r)
                r["name"] = name
            count += 1
        out.append(r)
    return out

def _filter_relevant_hosts(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    # Masquer le bruit: retirer multicast/broadcast et IP non privées
    def is_multicast_or_broadcast(ip: str, mac: str) -> bool:
        if not ip:
            return True
        try:
            parts = [int(p) for p in ip.split('.')]
            if len(parts) != 4:
                return True
            # Multicast 224.0.0.0/4
            if 224 <= parts[0] <= 239:
                return True
            # Limited broadcast .255
            if parts[3] == 255:
                return True
            # 0.0.0.0 or 255.255.255.255
            if ip == '0.0.0.0' or ip == '255.255.255.255':
                return True
        except Exception:
            return True
        mac_u = (mac or '').upper()
        if mac_u.startswith('FF:FF:FF:FF:FF:FF'):
            return True
        if mac_u.startswith('01:00:5E:'):
            return True
        return False

    filtered: List[Dict[str, str]] = []
    for r in rows:
        ip = r.get('ip', '')
        mac = r.get('mac', '')
        if is_multicast_or_broadcast(ip, mac):
            continue
        if not _is_private_unicast(ip):
            continue
        filtered.append(r)
    return filtered


def _is_private_unicast(ip: str) -> bool:
    try:
        a,b,c,d = [int(p) for p in ip.split('.')]
        if a == 10:
            return True
        if a == 172 and 16 <= b <= 31:
            return True
        if a == 192 and b == 168:
            return True
        return False
    except Exception:
        return False


def _detect_subnets() -> List[str]:
    sysname = platform.system().lower()
    subnets: List[str] = []
    if sysname.startswith("win"):
        out = _run(["ipconfig"])
        ip = None
        mask = None
        for ln in out.splitlines():
            ln = ln.strip()
            if "IPv4 Address" in ln or "Adresse IPv4" in ln:
                parts = ln.split(":", 1)
                if len(parts) == 2:
                    ip = parts[1].strip()
            elif "Subnet Mask" in ln or "Masque de sous-réseau" in ln or "Masque de sous-reseau" in ln:
                parts = ln.split(":", 1)
                if len(parts) == 2:
                    mask = parts[1].strip()
            if ip and mask:
                try:
                    net = ipaddress.ip_network((ip, mask), strict=False)
                    if net.is_private and not net.is_loopback:
                        subnets.append(str(net))
                except Exception:
                    pass
                ip = None
                mask = None
    else:
        out = _run(["ip", "-o", "-f", "inet", "addr", "show"])
        for ln in out.splitlines():
            parts = ln.split()
            if "inet" in parts:
                try:
                    idx = parts.index("inet")
                    cidr = parts[idx + 1]
                    net = ipaddress.ip_interface(cidr).network
                    if net.is_private and not net.is_loopback:
                        subnets.append(str(net))
                except Exception:
                    continue
    # de-dup
    seen = set()
    res: List[str] = []
    for s in subnets:
        if s not in seen:
            seen.add(s)
            res.append(s)
    return res


def _has_cmd(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def scan_with_arpscan(subnet: str | None = None) -> List[Dict[str, str]]:
    if platform.system().lower().startswith("win"):
        return []
    if not _has_cmd("arp-scan"):
        return []
    args = ["arp-scan", "--numeric"]
    if subnet:
        args.append(subnet)
    else:
        args.append("-l")
    out = _run(args)
    rows: List[Dict[str, str]] = []
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("Interface:") or ln.startswith("Starting") or ln.startswith("Ending"):
            continue
        # 192.168.1.1	00:11:22:33:44:55	Vendor
        parts = re.split(r"\s+", ln)
        if len(parts) >= 2 and re.match(r"^\d+\.\d+\.\d+\.\d+$", parts[0]):
            ip = parts[0]
            mac = normalize_mac(parts[1])
            vendor = " ".join(parts[2:]) if len(parts) > 2 else ""
            rows.append({"ip": ip, "mac": mac, "vendor": vendor, "state": "up", "iface": "", "src": "arp-scan"})
    return _filter_relevant_hosts(rows)


def scan_with_nmap(subnet: str) -> List[Dict[str, str]]:
    if not _has_cmd("nmap"):
        return []
    out = _run(["nmap", "-sn", subnet, "-oX", "-"])
    rows: List[Dict[str, str]] = []
    if not out:
        return rows
    try:
        root = ET.fromstring(out)
        for host in root.findall("host"):
            status = host.find("status")
            if status is not None and status.get("state") != "up":
                continue
            ip = None
            mac = ""
            vendor = ""
            for addr in host.findall("address"):
                addrtype = addr.get("addrtype")
                if addrtype == "ipv4":
                    ip = addr.get("addr")
                elif addrtype == "mac":
                    mac = normalize_mac(addr.get("addr") or "")
                    vendor = addr.get("vendor") or ""
            name = ""
            hnames = host.find("hostnames")
            if hnames is not None:
                h = hnames.find("hostname")
                if h is not None:
                    name = h.get("name") or ""
            if ip:
                rows.append({
                    "ip": ip,
                    "mac": mac,
                    "vendor": vendor,
                    "name": name,
                    "state": "up",
                    "iface": "",
                    "src": "nmap",
                })
    except Exception:
        return []
    return _filter_relevant_hosts(rows)


def smart_scan(subnet: str | None) -> List[Dict[str, str]]:
    subnets = [subnet] if subnet else _detect_subnets()
    rows: List[Dict[str, str]] = []
    targets = subnets or [None]
    for target in targets:
        part: List[Dict[str, str]] = []
        part = scan_with_arpscan(target)
        if not part and target:
            part = scan_with_nmap(target)
        if not part:
            part = scan_neighbors()
        rows = _merge_rows(rows, part)
    return rows


def _merge_rows(a: List[Dict[str, str]], b: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = {(r.get('ip',''), r.get('mac',''), r.get('iface','')) for r in a}
    for r in b:
        key = (r.get('ip',''), r.get('mac',''), r.get('iface',''))
        if key in seen:
            continue
        a.append(r)
        seen.add(key)
    return a


def detect_subnets() -> List[str]:
    return _detect_subnets()


def force_nmap_scan() -> List[Dict[str, str]]:
    subs = _detect_subnets()
    all_rows: List[Dict[str, str]] = []
    for s in subs:
        part = scan_with_nmap(s)
        if part:
            all_rows = _merge_rows(all_rows, part)
    return all_rows


def scan_with_win_netneighbor() -> List[Dict[str, str]]:
    if not platform.system().lower().startswith("win"):
        return []
    if not _has_cmd("powershell") and not _has_cmd("powershell.exe"):
        return []
    ps = shutil.which("powershell.exe") or shutil.which("powershell") or "powershell"
    out = _run([ps, "-NoProfile", "-Command", "Get-NetNeighbor -AddressFamily IPv4 | ConvertTo-Json -Compress"])
    rows: List[Dict[str, str]] = []
    if not out:
        return rows
    try:
        import json
        data = json.loads(out)
        if isinstance(data, dict):
            data = [data]
        for d in data or []:
            ip = d.get('IPAddress') or ''
            mac = normalize_mac(d.get('LinkLayerAddress') or '')
            state = (d.get('State') or '').lower()
            iface = d.get('InterfaceAlias') or ''
            if ip:
                rows.append({"ip": ip, "mac": mac, "state": state, "iface": iface, "src": "Get-NetNeighbor"})
    except Exception:
        return []
    return rows


__all__ = [
    "ensure_inventory_storage",
    "scan_neighbors",
    "export_csv",
    "smart_scan",
    "detect_subnets",
    "force_nmap_scan",
]
