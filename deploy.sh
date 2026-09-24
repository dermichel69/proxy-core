#!/bin/bash
set -a
[ -f /root/vpn-chain/.env ] && . /root/vpn-chain/.env
set +a

mkdir -p /root/vpn-chain
cd /root/vpn-chain

WIREGUARD_PRIVATE_KEY="${WIREGUARD_PRIVATE_KEY:-replace-me-local-only}"
XRAY_PROXY_USER="${XRAY_PROXY_USER:-replace-me-local-only}"
XRAY_PROXY_PASSWORD="${XRAY_PROXY_PASSWORD:-replace-me-local-only}"

# 1. docker-compose.yml erstellen
cat <<EOL > docker-compose.yml
version: '3.8'

services:
  protonvpn:
    image: qmcgaw/gluetun:v4.0.0
    container_name: protonvpn
    cap_add:
      - NET_ADMIN
    devices:
      - /dev/net/tun:/dev/net/tun
    ports:
      - "0.0.0.0:1080:1080/tcp"
    environment:
      - VPN_SERVICE_PROVIDER=custom
      - OPENVPN_CUSTOM_CONFIG=
      - WIREGUARD_ENABLED=on
      - WIREGUARD_PRIVATE_KEY=${WIREGUARD_PRIVATE_KEY}
      - WIREGUARD_ADDRESSES=10.2.0.2/32
    restart: unless-stopped

  warp:
    image: ghcr.io/wg-easy/wg-easy:latest
    container_name: warp
    network_mode: container:protonvpn
    cap_add:
      - NET_ADMIN
    restart: unless-stopped
EOL

# 2. xray.json erstellen (placeholder values; lokal mit echten Werten aus .env befüllen)
cat <<EOL > xray.json
{
  "log": {
    "loglevel": "warning"
  },
  "dns": {
    "servers": ["1.1.1.1", "8.8.8.8"],
    "queryStrategy": "UseIPv4",
    "disableCache": false,
    "disableFallback": true
  },
  "inbounds": [
    {
      "port": 1080,
      "listen": "0.0.0.0",
      "protocol": "socks",
      "settings": {
        "auth": "password",
        "accounts": [
          {
            "user": "${XRAY_PROXY_USER}",
            "pass": "${XRAY_PROXY_PASSWORD}"
          }
        ],
        "udp": true
      },
      "streamSettings": {
        "tcpSettings": {
          "header": { "type": "none" }
        },
        "sockopt": { "tcpNoDelay": true }
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "wireguard",
      "settings": {
        "secretKey": "${WIREGUARD_PRIVATE_KEY}",
        "address": ["172.16.0.2/32"],
        "peers": [
          {
            "endpoint": "engage.cloudflareclient.com:2408",
            "publicKey": "REPLACE_WITH_LOCAL_PUBLIC_KEY",
            "keepAlive": 5
          }
        ],
        "mtu": 1360
      },
      "tag": "warp-out",
      "streamSettings": {
        "sockopt": {
          "domainStrategy": "UseIPv4",
          "tcpKeepAliveInterval": 5,
          "tcpNoDelay": true
        }
      }
    },
    {
      "protocol": "freedom",
      "tag": "direct"
    }
  ],
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
      {
        "type": "field",
        "domain": ["example.com"],
        "outboundTag": "warp-out"
      }
    ]
  }
}
EOL

# 3. Firewall für Streamer öffnen
apt update && apt install -y netfilter-persistent iptables-persistent
iptables -I DOCKER-USER 1 -p tcp --dport 1080 -s 0.0.0.0/0 -j ACCEPT
netfilter-persistent save

# 4. Docker Stack starten
docker compose down
docker compose up -d

echo "Deployment abgeschlossen!"
