#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"

GEN_FILE="$REPO_ROOT/back/generated/dns/dnsmasq_blocklist.conf"
mkdir -p "$(dirname "$GEN_FILE")"
[[ -f "$GEN_FILE" ]] || printf '# empty blocklist\n' > "$GEN_FILE"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker non trouvé. Installez Docker Desktop / Docker Engine." >&2
  exit 1
fi

pushd "$SCRIPT_DIR" >/dev/null
docker compose up -d
popd >/dev/null

echo "dnsmasq (Docker) écoute sur 127.0.0.1:53. Configurez votre DNS système sur 127.0.0.1."

