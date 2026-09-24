# StreamNet Edge Core

Ein privates Multi-Proxy- und VPN-Management-Setup für den Betrieb mehrerer Exit-Nodes, Streaming-Proxy-Ketten und Live-Monitoring über ein Web-Dashboard.

Dieses Repository bündelt Docker-Container, WireGuard/OpenVPN-Referenzkonfigurationen, Xray-Konfigurationen und ein Flask-Dashboard, das den Status der Proxys, CDN-Checks und Traffic-Metriken überwacht.

## Überblick

Das Projekt dient als interne Infrastruktur für:

- mehrere VPN-/Proxy-Pipelines
- SOCKS5-Proxy-Endpunkte auf verschiedenen Ports
- Live-Healthchecks gegen CDN-/Manifest-URLs
- automatisches Wiederherstellen fehlerhafter Container
- Verwaltung über ein Web-Frontend

Die Hauptkomponenten liegen in:

- [proxy-core/docker-compose.yml](docker-compose.yml)
- [proxy-core/dashboard/app.py](dashboard/app.py)
- [proxy-core/switch-node.sh](switch-node.sh)
- [proxy-core/deploy.sh](deploy.sh)
- [proxy-core/xray.json](xray.json)

## Architektur

```text
Streaming Clients
      |
      v
SOCKS5 / HTTP Proxy Ports (2080, 2090, 2092, ...)
      |
      +--> WireGuard / OpenVPN / WARP / Xray routes
                |
                +--> CDN / DASH manifest checks
                +--> Traffic monitoring
                +--> Auto-heal restart logic
                +--> Dashboard UI on :8080
```

Die Infrastruktur ist bewusst als Ketten-/Stack-Setup aufgebaut: Ein Proxy kann über unterschiedliche Transportwege laufen und über das Dashboard beobachtet werden.

## Verfügbare Komponenten

### 1) Docker-Stack

Im Basis-Setup wird ein WARP-Container über Docker gestartet, siehe [proxy-core/docker-compose.yml](docker-compose.yml).

Der Stack ist dafür gedacht, proxyfähige Verbindungen in einer stabilen Umgebung zu halten und als gemeinsame Basis für weitere Knoten zu laufen.

### 2) Dashboard

Das Flask-Dashboard in [proxy-core/dashboard/app.py](dashboard/app.py) stellt auf Port `8080` eine Oberfläche bereit. Es zeigt unter anderem:

- Proxy-Status
- Exit-IP und Standort
- CDN-Status / HTTP-Code
- Latenzwerte
- Traffic-Volumen (RX/TX)
- aktiver Verbindungs-/Session-Status

Das Frontend sitzt in [proxy-core/dashboard/templates/index.html](dashboard/templates/index.html) und nutzt Tailwind für eine Dark-Mode-UI.

### 3) WireGuard / OpenVPN / Xray

Im Projekt liegen mehrere Konfigurations- und Resourcenordner vor, darunter:

- [proxy-core/wireguard/](wireguard/)
- [proxy-core/wireguard-de/](wireguard-de/)
- [proxy-core/wireguard-pl/](wireguard-pl/)
- [proxy-core/openvpn-de4/](openvpn-de4/)
- [proxy-core/openvpn-de5/](openvpn-de5/)
- [proxy-core/openvpn-de6/](openvpn-de6/)
- [proxy-core/xray.json](xray.json)
- [proxy-core/xray-de.json](xray-de.json)

Diese Ordner enthalten die zugehörigen Node-Konfigurationen oder Betriebspakete für die einzelnen Proxy-Instanzen.

### 4) Switch-Node-Funktionalität

[proxy-core/switch-node.sh](switch-node.sh) erlaubt das Wechseln zwischen Standorten wie:

- `berlin`
- `frankfurt`
- `hamburg`

Es setzt den WireGuard-Endpoint und prüft anschließend via Proxy-Port, ob der Standort korrekt antwortet.

### 5) Deploy-Workflow

[proxy-core/deploy.sh](deploy.sh) richtet ein Deployment-Script für die Infrastruktur ein und konfiguriert dabei:

- Docker-Compose-Setup
- Firewall-Regeln
- Xray-/Proxy-Base-Konfigurationen
- Start des kompletten Stacks

## Projektstruktur

```text
proxy-core/
├── README.md
├── deploy.sh
├── docker-compose.yml
├── switch-node.sh
├── xray.json
├── xray-de.json
├── xray-de.json.working
├── dashboard/
│   ├── app.py
│   ├── Dockerfile
│   └── templates/
├── wireguard/
├── wireguard-de/
├── wireguard-pl/
├── openvpn-de4/
├── openvpn-de5/
├── openvpn-de6/
├── test-nord/
├── test-nord-1429/
├── test-nord-1520/
├── warp-data/
├── warp-data-2/
├── xray2/
├── xray3/
├── xray4/
└── ...
```

## Verwendete Technologien

- Docker / Docker Compose
- WireGuard
- OpenVPN
- Xray
- Cloudflare WARP
- Flask
- Tailwind CSS
- Linux-Netzwerk-Tools (iptables, ss, curl, ping)

## Schnellstart

### Voraussetzungen

- Linux- oder Debian-/Ubuntu-basierte Umgebung
- Docker und Docker Compose installiert
- Root-/sudo-Rechte
- vorhandene VPN-/WireGuard-/OpenVPN-Konfigurationen

### Starten

```bash
cd /path/to/proxy-core
sudo docker compose up -d
```

### Dashboard starten

```bash
cd /path/to/proxy-core/dashboard
python3 app.py
```

Danach ist das Dashboard auf `http://<host>:8080` erreichbar.

## Monitoring und Betrieb

Das System prüft regelmäßig die CDN-Resourcen und bewertet jede Pipeline mit Zuständen wie:

- `OK`
- `BLOCKED`
- `TIMEOUT`
- `ERR <code>`

Falls ein Proxy wiederholt nicht erreichbar ist, versucht das System automatische Restarts der betroffenen Container.

## Standortwechsel

```bash
cd /path/to/proxy-core
./switch-node.sh berlin
./switch-node.sh frankfurt
./switch-node.sh hamburg
```

Damit werden passende Konfigurationswerte gesetzt und der Status des Standorts anschließend geprüft.

## Sicherheits-Hinweis

Dieses Projekt enthält Interna, feste Credentials und host-spezifische Konfigurationen. Es ist für kontrollierte, interne Nutzung gedacht und sollte nicht unverändert in öffentliche oder fremde Umgebungen übernommen werden.

Wichtige Punkte:

- geheime Schlüssel nicht in öffentlichen Repos veröffentlichen
- lokale Konfigurationsdateien separat halten
- Container-Ports nur nach Bedarf freigeben
- Zugang zum Dashboard mit Login-Mechanismus absichern

## Fazit

Dieses Repository ist kein generisches Startprojekt, sondern ein operatives Infrastruktur-Setup für einen privaten Proxy-/VPN-Stack mit Monitoring, Live-Checks und automatischer Wiederherstellung.

Es eignet sich für eigene Netzwerkketten, Streaming-Access-Workflows und Multi-Node-Proxy-Operationen mit zentraler Sichtbarkeit.

## Hinweis

Der Code zeigt stark betriebsspezifische Strukturen, Konfigurationen und Zonenangaben. Daher ist das Projekt am sinnvollsten als internes System zu betreiben und nicht als allgemeines Open-Source-Produkt für breite Nutzung.
