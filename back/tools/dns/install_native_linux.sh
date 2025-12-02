#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "[install] Ce script nécessite les droits root. Relance avec sudo..."
  exec sudo -E "$0" "$@"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"

GEN_FILE="$REPO_ROOT/back/generated/dns/dnsmasq_blocklist.conf"
TARGET_DIR="/opt/elhomeshield"
TARGET_FILE="$TARGET_DIR/dnsmasq_blocklist.conf"
DROPIN="/etc/dnsmasq.d/10-elhomeshield.conf"

mkdir -p "$REPO_ROOT/back/generated/dns"
[[ -f "$GEN_FILE" ]] || printf '# empty blocklist\n' > "$GEN_FILE"

echo "[install] Création du dossier $TARGET_DIR"
mkdir -p "$TARGET_DIR"

echo "[install] Lien symbolique du blocklist vers $TARGET_FILE"
ln -sf "$GEN_FILE" "$TARGET_FILE"

echo "[install] Drop-in dnsmasq: $DROPIN"
mkdir -p /etc/dnsmasq.d
cat > "$DROPIN" <<EOF
# Elhomeshield base config (native)
# Écoute uniquement sur loopback pour éviter conflits (systemd-resolved sur 127.0.0.53)
listen-address=127.0.0.1
bind-interfaces

# Ne pas utiliser les resolvers du système; définir nos upstreams ici
no-resolv
server=1.1.1.1
server=1.0.0.1

# Charger la blocklist générée par Elhomeshield
conf-file=$TARGET_FILE

# Cache raisonnable
cache-size=10000
EOF

echo "[install] (Re)démarrage du service dnsmasq"
if command -v systemctl >/dev/null 2>&1; then
  systemctl enable dnsmasq >/dev/null 2>&1 || true
  systemctl restart dnsmasq
  systemctl --no-pager --full status dnsmasq | sed -n '1,10p'
elif command -v service >/dev/null 2>&1; then
  service dnsmasq restart
elif command -v rc-service >/dev/null 2>&1; then
  rc-service dnsmasq restart
else
  echo "[install] Impossible de redémarrer automatiquement dnsmasq (manager inconnu). Redémarrez-le manuellement."
fi

echo "[install] OK. Prochaines étapes:"
echo "- Configurez le DNS de votre machine sur 127.0.0.1 (via NetworkManager/resolveconf/etc)."
echo "- Générez/maj le fichier via le CLI (DNS -> Générer config dnsmasq) : $GEN_FILE"
echo "- Pour recharger: sudo $(realpath "$SCRIPT_DIR/reload_dnsmasq.sh")"
