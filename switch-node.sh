#!/bin/bash
set -e

TARGET="${1,,}"
WG_CONF="/root/vpn-chain/wireguard-de/wg_confs/wg0.conf"
TEST_URL="${TEST_URL:-https://example.com/test.mpd}"
XRAY_PROXY_USER="${XRAY_PROXY_USER:-replace-me-local-only}"
XRAY_PROXY_PASSWORD="${XRAY_PROXY_PASSWORD:-replace-me-local-only}"

# load local overrides from .env if present
if [ -f /root/vpn-chain/.env ]; then
  set -a
  . /root/vpn-chain/.env
  set +a
fi

case "$TARGET" in
  berlin)
    ENDPOINT="${WG_ENDPOINT_BERLIN:-berlin.example.com:51820}"
    PUBKEY="${WG_PUBLICKEY_BERLIN:-REPLACE_WITH_LOCAL_PUBLIC_KEY}"
    ;;
  frankfurt)
    ENDPOINT="${WG_ENDPOINT_FRANKFURT:-frankfurt.example.com:51820}"
    PUBKEY="${WG_PUBLICKEY_FRANKFURT:-REPLACE_WITH_LOCAL_PUBLIC_KEY}"
    ;;
  hamburg)
    ENDPOINT="${WG_ENDPOINT_HAMBURG:-hamburg.example.com:51820}"
    PUBKEY="${WG_PUBLICKEY_HAMBURG:-REPLACE_WITH_LOCAL_PUBLIC_KEY}"
    ;;
  *)
    echo "Nutzung: $0 {berlin|frankfurt|hamburg}"
    exit 1
    ;;
esac

echo "[1/4] Setze Endpoint auf: $ENDPOINT ($TARGET)..."
sed -i "s|^Endpoint = .*|Endpoint = $ENDPOINT|" "$WG_CONF"
sed -i "s|^PublicKey = .*|PublicKey = $PUBKEY|" "$WG_CONF"

echo "[2/4] Starte Container neu..."
docker restart wireguard-de xray > /dev/null

echo "[3/4] Warte auf WireGuard-Handshake..."
sleep 4
docker exec wireguard-de wg show

echo "[4/4] Teste Manifest über Proxy-Port 2081..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -m 6 \
  -x "http://${XRAY_PROXY_USER}:${XRAY_PROXY_PASSWORD}@127.0.0.1:2081" \
  -H "User-Agent: Mozilla/5.0" \
  -H "Origin: https://example.com" \
  -H "Referer: https://example.com/" \
  "$TEST_URL")

echo "--> HTTP Response: $HTTP_STATUS"

if [ "$HTTP_STATUS" = "200" ]; then
  echo "Erfolg: Standort $TARGET ist aktiv und liefert HTTP 200."
else
  echo "Warnung: Unerwarteter Statuscode $HTTP_STATUS. Eventuell anderen Standort waehlen."
fi
