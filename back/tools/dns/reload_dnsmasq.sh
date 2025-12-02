#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  exec sudo -E "$0" "$@"
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl restart dnsmasq
  systemctl --no-pager --full status dnsmasq | sed -n '1,10p'
elif command -v service >/dev/null 2>&1; then
  service dnsmasq restart
elif command -v rc-service >/dev/null 2>&1; then
  rc-service dnsmasq restart
else
  echo "Impossible de redémarrer automatiquement dnsmasq (manager inconnu)."
fi

echo "dnsmasq rechargé."

