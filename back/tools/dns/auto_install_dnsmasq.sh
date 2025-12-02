#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "[auto-install] Ce script nécessite les droits root. Relance avec sudo..."
  exec sudo -E "$0" "$@"
fi

PM=""
if command -v apt-get >/dev/null 2>&1; then
  PM=apt
elif command -v dnf >/dev/null 2>&1; then
  PM=dnf
elif command -v yum >/dev/null 2>&1; then
  PM=yum
elif command -v pacman >/dev/null 2>&1; then
  PM=pacman
elif command -v zypper >/dev/null 2>&1; then
  PM=zypper
elif command -v apk >/dev/null 2>&1; then
  PM=apk
fi

case "$PM" in
  apt)
    apt-get update -y
    DEBIAN_FRONTEND=noninteractive apt-get install -y dnsmasq
    ;;
  dnf)
    dnf install -y dnsmasq
    ;;
  yum)
    yum install -y dnsmasq
    ;;
  pacman)
    pacman -Sy --noconfirm dnsmasq
    ;;
  zypper)
    zypper -n install dnsmasq
    ;;
  apk)
    apk add --no-cache dnsmasq
    ;;
  *)
    echo "[auto-install] Gestionnaire de paquets non détecté. Installez dnsmasq manuellement."
    exit 1
    ;;
esac

# Lancer la configuration Elhomeshield
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/install_native_linux.sh"

echo "[auto-install] Terminé. Si dnsmasq ne démarre pas, vérifiez qu'aucun autre service n'occupe le port 53 (ex: systemd-resolved)."

