#!/usr/bin/env bash
set -euo pipefail

# One-shot setup for Linux (no Docker):
# - Imports Hagezi profile into blocklist
# - Generates dnsmasq config
# - Installs dnsmasq (auto)
# - Disables systemd-resolved stub listener if needed (port 53 conflict)
# - Points system DNS to 127.0.0.1 (NetworkManager if available, else resolv.conf)

PROFILE="light"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      PROFILE="${2:-light}"; shift 2 ;;
    --profile=*)
      PROFILE="${1#*=}"; shift ;;
    *)
      echo "Option inconnue: $1" >&2; exit 2 ;;
  esac
done

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "[setup] Ce script nécessite les droits root. Relance avec sudo..."
  exec sudo -E "$0" "$@"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
BACK_SRC="$REPO_ROOT/back/src"
GEN_FILE="$REPO_ROOT/back/generated/dns/dnsmasq_blocklist.conf"

echo "[setup] Profil Hagezi: $PROFILE"

# Detect package manager
PM=""
if command -v apt-get >/dev/null 2>&1; then PM=apt; fi
if command -v dnf >/dev/null 2>&1; then PM=${PM:-dnf}; fi
if command -v yum >/dev/null 2>&1; then PM=${PM:-yum}; fi
if command -v pacman >/dev/null 2>&1; then PM=${PM:-pacman}; fi
if command -v zypper >/dev/null 2>&1; then PM=${PM:-zypper}; fi
if command -v apk >/dev/null 2>&1; then PM=${PM:-apk}; fi

# Ensure python is available
PY="python3"
if ! command -v "$PY" >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then PY=python; else
    echo "[setup] Python non trouvé, installation via $PM..."
    case "$PM" in
      apt) apt-get update -y; DEBIAN_FRONTEND=noninteractive apt-get install -y python3 ;; 
      dnf) dnf install -y python3 ;;
      yum) yum install -y python3 ;;
      pacman) pacman -Sy --noconfirm python ;; 
      zypper) zypper -n install python3 ;;
      apk) apk add --no-cache python3 ;; 
      *) echo "[setup] Installez Python3 manuellement."; exit 1 ;;
    esac
  fi
fi

echo "[setup] Import Hagezi + génération dnsmasq..."
mkdir -p "$(dirname "$GEN_FILE")"
"${PY}" - "$PROFILE" "$REPO_ROOT" <<'PYCODE'
import sys, os
from pathlib import Path
profile = sys.argv[1]
repo = Path(sys.argv[2])
root = repo / 'back'
sys.path.insert(0, str(repo.joinpath('back','src').resolve()))
from elhomeshield.modules.dns.services import hagezi_profiles, import_from_url, generate_dnsmasq_blocklist
profs = hagezi_profiles()
if profile not in profs:
    print(f"[setup] Profil inconnu: {profile}. Profils valides: {', '.join(profs)}")
    sys.exit(2)
ok, msg, _ = import_from_url(root, profs[profile])
print(msg)
out = generate_dnsmasq_blocklist(root)
print(f"[setup] Généré: {out}")
PYCODE

echo "[setup] Installation/configuration dnsmasq..."
bash "$SCRIPT_DIR/auto_install_dnsmasq.sh"

# Handle systemd-resolved stub listener (port 53 conflict)
if systemctl is-active --quiet systemd-resolved 2>/dev/null; then
  RESOLVED_CONF="/etc/systemd/resolved.conf"
  if [[ -f "$RESOLVED_CONF" ]]; then
    if grep -Eq '^[# ]*DNSStubListener=' "$RESOLVED_CONF"; then
      sed -i -E 's/^[# ]*DNSStubListener=.*/DNSStubListener=no/' "$RESOLVED_CONF"
    else
      awk 'BEGIN{added=0} {print} /^\[Resolve\]/{print "DNSStubListener=no"; added=1} END{if(!added) print "[Resolve]\nDNSStubListener=no"}' "$RESOLVED_CONF" > "$RESOLVED_CONF.tmp" && mv "$RESOLVED_CONF.tmp" "$RESOLVED_CONF"
    fi
    systemctl restart systemd-resolved || true
  fi
fi

echo "[setup] Configuration DNS système -> 127.0.0.1"
if command -v nmcli >/dev/null 2>&1; then
  # Apply to active connections
  IFS=$'\n' read -r -d '' -a ACTIVE < <(nmcli -t -f UUID connection show --active && printf '\0') || true
  if [[ "${#ACTIVE[@]}" -eq 0 ]]; then
    echo "[setup] Aucune connexion active NetworkManager détectée. Passage à resolv.conf."
  else
    for UUID in "${ACTIVE[@]}"; do
      nmcli connection modify "$UUID" ipv4.dns "127.0.0.1" ipv4.ignore-auto-dns yes || true
      nmcli connection up "$UUID" || true
    done
  fi
fi

if ! command -v nmcli >/dev/null 2>&1 || [[ "${#ACTIVE[@]:-0}" -eq 0 ]]; then
  # Fallback: write resolv.conf (if not managed by resolvconf/NetworkManager overwriting)
  if [[ -L /etc/resolv.conf ]]; then
    # Often a symlink to systemd-resolved. Try write target if possible.
    TARGET="$(readlink -f /etc/resolv.conf || true)"
    if [[ -n "$TARGET" && -w "$TARGET" ]]; then
      printf 'nameserver 127.0.0.1\n' > "$TARGET" || true
    fi
  elif [[ -w /etc/resolv.conf ]]; then
    printf 'nameserver 127.0.0.1\n' > /etc/resolv.conf || true
  fi
fi

echo "[setup] Redémarrage dnsmasq"
bash "$SCRIPT_DIR/reload_dnsmasq.sh" || true

echo "[setup] Terminé. Test: dig @127.0.0.1 example.com +short"

