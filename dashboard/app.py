import subprocess
import json
import time
import os
import shutil
import threading
from datetime import timedelta
from functools import wraps
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.secret_key = os.getenv("STREAMNET_SECRET_KEY", "change-me-local-only")
app.permanent_session_lifetime = timedelta(days=30)

ADMIN_USER = os.getenv("STREAMNET_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("STREAMNET_ADMIN_PASSWORD", "change-me-local-only")
USERS = {
    ADMIN_USER: generate_password_hash(ADMIN_PASSWORD)
}

STREAMERS = [
    {"name": "Streamer 1 (Primary DE)", "ip": "67.159.11.66", "target_proxy": "2080 (SOCKS)"},
    {"name": "Streamer 2 (Secondary)", "ip": "50.7.224.34", "target_proxy": "2090 (SOCKS)"},
    {"name": "Streamer 3 (Standby 3)", "ip": "185.181.60.212", "target_proxy": "2092 (SOCKS)"},
    {"name": "Streamer 4 (PL Node 2)", "ip": "193.200.221.48", "target_proxy": "2094 (SOCKS)"},
    {"name": "Streamer 5 (PL Node 3)", "ip": "195.16.73.81", "target_proxy": "2096 (SOCKS)"}
]

WG_CONFIG_PATHS = {
    "de": "/root/vpn-chain/wireguard-de/wg_confs/wg0.conf"
}

EXIT_IP_CACHE = {
    "de": {"ip": "194.35.233.28", "loc": "DE · Hamburg", "city": "Hamburg (Switch-Node)"},
    "de2": {"ip": "185.216.33.86", "loc": "DE · Berlin", "city": "Berlin (Standby Node)"},
    "de3": {"ip": "187.13.9.174", "loc": "DE · Berlin", "city": "Berlin 2 (Redundanz)"},
    "de4": {"ip": "187.40.55.143", "loc": "DE · Frankfurt", "city": "Frankfurt am Main (de1521)"},
    "de5": {"ip": "187.40.43.113", "loc": "DE · Frankfurt", "city": "Frankfurt am Main (de1429)"},
    "de6": {"ip": "187.40.55.140", "loc": "DE · Frankfurt", "city": "Frankfurt am Main (de1520)"}
}

PROXIES_DEF = [
    {"id": "de", "name": "Proxy 1 (DE WireGuard)", "port": 2080, "containers": ["wireguard-de", "xray"]},
    {"id": "de2", "name": "Proxy 2 (DE OpenVPN)", "port": 2090, "containers": ["openvpn-de2", "xray2"]},
    {"id": "de3", "name": "Proxy 3 (DE OpenVPN)", "port": 2092, "containers": ["openvpn-de3", "xray3"]},
    {"id": "de4", "name": "Proxy 4 (DE de1521)", "port": 2094, "containers": ["openvpn-de4", "xray4"]},
    {"id": "de5", "name": "Proxy 5 (DE de1429)", "port": 2096, "containers": ["openvpn-de5", "xray5"]},
    {"id": "de6", "name": "Proxy 6 (DE de1520)", "port": 2098, "containers": ["openvpn-de6", "xray6"]}
]

TRAFFIC_STATE = {
    "wireguard-de": {"last_rx": 0, "last_tx": 0, "last_time": 0, "rx_val": 0.0, "tx_val": 0.0, "rx_rate": "0.00 MB/s", "tx_rate": "0.00 MB/s", "total_rx": "0 B", "total_tx": "0 B"},
    "openvpn-de2": {"last_rx": 0, "last_tx": 0, "last_time": 0, "rx_val": 0.0, "tx_val": 0.0, "rx_rate": "0.00 MB/s", "tx_rate": "0.00 MB/s", "total_rx": "0 B", "total_tx": "0 B"},
    "openvpn-de3": {"last_rx": 0, "last_tx": 0, "last_time": 0, "rx_val": 0.0, "tx_val": 0.0, "rx_rate": "0.00 MB/s", "tx_rate": "0.00 MB/s", "total_rx": "0 B", "total_tx": "0 B"},
    "openvpn-de4": {"last_rx": 0, "last_tx": 0, "last_time": 0, "rx_val": 0.0, "tx_val": 0.0, "rx_rate": "0.00 MB/s", "tx_rate": "0.00 MB/s", "total_rx": "0 B", "total_tx": "0 B"},
    "openvpn-de5": {"last_rx": 0, "last_tx": 0, "last_time": 0, "rx_val": 0.0, "tx_val": 0.0, "rx_rate": "0.00 MB/s", "tx_rate": "0.00 MB/s", "total_rx": "0 B", "total_tx": "0 B"},
    "openvpn-de6": {"last_rx": 0, "last_tx": 0, "last_time": 0, "rx_val": 0.0, "tx_val": 0.0, "rx_rate": "0.00 MB/s", "tx_rate": "0.00 MB/s", "total_rx": "0 B", "total_tx": "0 B"}
}

HEALTH_STATE = {
    p["id"]: {
        "cdn_status": "checking",
        "http_code": "---",
        "latency_ms": 0,
        "conn_fail_count": 0,
        "auto_heal_attempts": 0,
        "last_heal": 0
    }
    for p in PROXIES_DEF
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized", "redirect": "/login"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def format_bytes(b):
    if b >= 1024 * 1024 * 1024:
        return f"{b / (1024 * 1024 * 1024):.2f} GB"
    if b >= 1024 * 1024:
        return f"{b / (1024 * 1024):.1f} MB"
    if b >= 1024:
        return f"{b / 1024:.0f} KB"
    return f"{b} B"

def get_container_pid(name):
    try:
        out = subprocess.check_output(["docker", "inspect", "-f", "{{.State.Pid}}", name], stderr=subprocess.DEVNULL, universal_newlines=True).strip()
        pid = int(out)
        return pid if pid > 0 else None
    except Exception:
        return None

def is_container_running(name):
    try:
        res = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", name], capture_output=True, text=True, timeout=1)
        return res.stdout.strip() == "true"
    except Exception:
        return False

def fast_ping(ip):
    try:
        res = subprocess.run(["ping", "-c", "1", "-W", "1", ip], capture_output=True, text=True, timeout=1)
        for line in res.stdout.splitlines():
            if "time=" in line:
                ms = line.split("time=")[1].split(" ")[0]
                return {"status": "online", "latency": f"{float(ms):.1f} ms"}
        return {"status": "online", "latency": "< 1 ms"}
    except Exception:
        return {"status": "offline", "latency": "Timeout"}

def get_active_sessions(port):
    try:
        cmd = f"ss -nt sport = :{port} or dport = :{port} | grep -v State | wc -l"
        res = subprocess.check_output(cmd, shell=True, universal_newlines=True).strip()
        return int(res)
    except Exception:
        return 0

def get_real_traffic(container_name):
    state = TRAFFIC_STATE.get(container_name, {"last_rx": 0, "last_tx": 0, "last_time": 0, "rx_val": 0.0, "tx_val": 0.0, "rx_rate": "0.00 MB/s", "tx_rate": "0.00 MB/s", "total_rx": "0 B", "total_tx": "0 B"})
    pid = get_container_pid(container_name)
    now = time.time()

    if not pid:
        return state

    net_dev_path = f"/proc/{pid}/net/dev"
    if not os.path.exists(net_dev_path):
        return state

    try:
        rx_total = 0
        tx_total = 0
        with open(net_dev_path, "r") as f:
            for line in f:
                line = line.strip()
                if ":" in line and not line.startswith("lo:"):
                    parts = line.split(":", 1)[1].split()
                    if len(parts) >= 9:
                        rx_total += int(parts[0])
                        tx_total += int(parts[8])

        dt = now - state["last_time"]
        if state["last_time"] > 0 and dt > 0.4:
            delta_rx = max(0, rx_total - state["last_rx"])
            delta_tx = max(0, tx_total - state["last_tx"])
            rx_sec = delta_rx / dt
            tx_sec = delta_tx / dt

            state["rx_val"] = round(rx_sec / (1024 * 1024), 2)
            state["tx_val"] = round(tx_sec / (1024 * 1024), 2)
            state["rx_rate"] = f"{state['rx_val']:.2f} MB/s"
            state["tx_rate"] = f"{state['tx_val']:.2f} MB/s"

        state["last_rx"] = rx_total
        state["last_tx"] = tx_total
        state["total_rx"] = format_bytes(rx_total)
        state["total_tx"] = format_bytes(tx_total)
        state["last_time"] = now
    except Exception:
        pass

    TRAFFIC_STATE[container_name] = state
    return state

def cdn_health_check_worker():
    manifest_url = "https://svc45.main.sl.t-online.de/bpk-tv/KID00754_TelekomEishockey1_hd/DASH/index.mpd"
    while True:
        for p in PROXIES_DEF:
            pid = p["id"]
            port = p["port"]
            proxy_url = f"socks5h://streamnet:secret123@127.0.0.1:{port}"
            cmd = [
                "curl", "-s", "-o", "/dev/null",
                "-w", "%{http_code}:%{time_total}",
                "--max-time", "6",
                "--proxy", proxy_url,
                manifest_url
            ]

            code = "000"
            ms = 0
            try:
                out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, universal_newlines=True).strip()
                if ":" in out:
                    code, t = out.split(":", 1)
                    ms = int(float(t) * 1000)
            except Exception:
                code = "000"
                ms = 0

            HEALTH_STATE[pid]["http_code"] = code
            HEALTH_STATE[pid]["latency_ms"] = ms

            if code == "200":
                HEALTH_STATE[pid]["cdn_status"] = "OK"
                HEALTH_STATE[pid]["conn_fail_count"] = 0
                HEALTH_STATE[pid]["auto_heal_attempts"] = 0

            elif code == "403":
                # Echtes Blacklisting / Geoblock: KEIN Neustart-Loop!
                HEALTH_STATE[pid]["cdn_status"] = "BLOCKED"
                HEALTH_STATE[pid]["conn_fail_count"] = 0  # Kein Verbindungsfehler

            else:
                # Timeout (000), 5xx oder DNS-Probleme: Zähler erhöhen
                HEALTH_STATE[pid]["cdn_status"] = "TIMEOUT" if code == "000" else f"ERR {code}"
                HEALTH_STATE[pid]["conn_fail_count"] += 1

                # Auto-Heal: Bei echten Verbindungsproblemen max. 2 Restarts versuchen
                now = time.time()
                if HEALTH_STATE[pid]["conn_fail_count"] >= 3 and HEALTH_STATE[pid]["auto_heal_attempts"] < 2:
                    if now - HEALTH_STATE[pid]["last_heal"] > 180:
                        HEALTH_STATE[pid]["last_heal"] = now
                        HEALTH_STATE[pid]["auto_heal_attempts"] += 1
                        HEALTH_STATE[pid]["conn_fail_count"] = 0
                        for c in p["containers"]:
                            subprocess.run(["docker", "restart", c], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        time.sleep(25)

threading.Thread(target=cdn_health_check_worker, daemon=True).start()

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username in USERS and check_password_hash(USERS.get(username), password):
            session.permanent = True
            session["user"] = username
            return redirect(url_for("index"))
        else:
            error = "Ungültiger Benutzername oder Passwort"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    return render_template("index.html")

@app.route("/api/status")
@login_required
def api_status():
    streamer_status = []
    for s in STREAMERS:
        p = fast_ping(s["ip"])
        streamer_status.append({
            "name": s["name"],
            "ip": s["ip"],
            "target_proxy": s["target_proxy"],
            "status": p["status"],
            "latency": p["latency"]
        })

    proxies = []
    for p in PROXIES_DEF:
        pid = p["id"]
        c_vpn = p["containers"][0]
        c_xray = p["containers"][1]
        st = "running" if (is_container_running(c_vpn) or is_container_running(c_xray)) else "stopped"
        bw = get_real_traffic(c_vpn)
        h = HEALTH_STATE.get(pid, {"cdn_status": "checking", "http_code": "---", "latency_ms": 0})
        sessions = get_active_sessions(p["port"])

        proxies.append({
            "id": pid,
            "name": p["name"],
            "port": p["port"],
            "exit_ip": EXIT_IP_CACHE[pid]["ip"],
            "exit_loc": EXIT_IP_CACHE[pid]["loc"],
            "chain": EXIT_IP_CACHE[pid]["city"],
            "status": st,
            "cdn_status": h["cdn_status"],
            "cdn_code": h["http_code"],
            "tunnel_latency": f"{h['latency_ms']} ms" if h["latency_ms"] > 0 else "--",
            "sessions": sessions,
            "rx_rate": bw["rx_rate"],
            "tx_rate": bw["tx_rate"],
            "rx_val": bw["rx_val"],
            "tx_val": bw["tx_val"],
            "total_rx": bw["total_rx"],
            "total_tx": bw["total_tx"]
        })

    return jsonify({"streamers": streamer_status, "proxies": proxies})

@app.route("/api/upload_config/<target>", methods=["POST"])
@login_required
def upload_config(target):
    if target not in WG_CONFIG_PATHS:
        return jsonify({"error": "Ungültiges Ziel"}), 400

    if 'config_file' not in request.files:
        return jsonify({"error": "Keine Datei ausgewählt"}), 400

    file = request.files['config_file']
    if file.filename == '':
        return jsonify({"error": "Leerer Datei-Name"}), 400

    target_path = WG_CONFIG_PATHS[target]

    try:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        if os.path.exists(target_path):
            shutil.copy2(target_path, f"{target_path}.bak")

        file.save(target_path)
        subprocess.run(["docker", "restart", "wireguard-de", "xray"], check=True)
        return jsonify({"success": True, "message": "WireGuard-Config aktualisiert."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/action/<action_type>/<target>", methods=["POST"])
@login_required
def container_action(action_type, target):
    if action_type not in ["restart", "stop", "start"]:
        return jsonify({"error": "Invalid action"}), 400

    target_map = {p["id"]: p["containers"] for p in PROXIES_DEF}

    if target in target_map:
        for c in target_map[target]:
            subprocess.run(["docker", action_type, c])
        return jsonify({"success": True})

    return jsonify({"error": "Unknown target"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
