#!/bin/bash
set -e

TARGET="${1,,}"
WG_CONF="/root/vpn-chain/wireguard-de/wg_confs/wg0.conf"
TEST_URL="https://svc45.main.sl.t-online.de/bpk-tv/KID00754_TelekomEishockey1_hd/DASH/index.mpd"

case "$TARGET" in
  berlin)
    ENDPOINT="berlin.de.wg.nordhold.net:51820"
    PUBKEY="3ZNjosvvIqfvu3/BqaLzNNXs9zWO4jXpcXNOmDMDpX0="
    ;;
  frankfurt)
    ENDPOINT="frankfurt.de.wg.nordhold.net:51820"
    PUBKEY="b1Qp9oZfB7bUvP7kQh9F2y8T1eXqKxL9wVnM8uRt7mY="
    ;;
  hamburg)
    ENDPOINT="de-ham-wg-001.nordvpn.com:51820"
    PUBKEY="R6qY3B7Vz4X6yKk0D5d8z7w9T1x3L4m5N6p7Q8r9S0t="
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

echo "[4/4] Teste Telekom-Manifest über Proxy-Port 2081..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -m 6 \
  -x http://streamnet:secret123@127.0.0.1:2081 \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
  -H "Origin: https://web.magentatv.de" \
  -H "Referer: https://web.magentatv.de/" \
  "$TEST_URL")

echo "--> HTTP Response: $HTTP_STATUS"

if [ "$HTTP_STATUS" = "200" ]; then
  echo "Erfolg: Standort $TARGET ist aktiv und liefert HTTP 200."
else
  echo "Warnung: Unerwarteter Statuscode $HTTP_STATUS. Eventuell anderen Standort waehlen."
fi
