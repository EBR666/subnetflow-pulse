#!/usr/bin/env python3
# SubNetFlow Pulse — agente de nodos Proxmox VE para SubNetFlow.
# Copyright (c) 2026 Andrés Eduardo Brand Ruiz. Todos los derechos reservados. Ver LICENSE.md.
#
# Lee el estado del nodo (solo lectura: pvesh get, /proc, /sys, dmidecode y la configuración de las VM/LXC) y lo envía
# a SubNetFlow cada N minutos dentro de un sobre AES-256-GCM, por HTTPS. La llave sale del token de la sede (HKDF-SHA256)
# y nunca viaja. El protocolo está en PROTOCOL.md. No cambia nada en el nodo.
"""SubNetFlow Pulse: agente de nodos Proxmox VE para SubNetFlow."""

import argparse
import base64
import glob
import json
import logging
import os
import random
import re
import secrets
import signal
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

VERSION = "1.0.4"
NAME = "subnetflow-pulse"
PROTO = "snf-pulse-v1"
SCHEMA = "subnetflow-node-1"
DEFAULT_CONF = "/etc/subnetflow-pulse/agent.conf"
REPORT_PATH = "/api/pulse/v1/report"
TOKEN_RE = re.compile(r"^snfp_([0-9A-HJKMNP-TV-Z]{16})_([0-9A-HJKMNP-TV-Z]{52})$")
MAX_SKEW_S = 300
MIN_INTERVAL_S = 60
MAX_INTERVAL_S = 3600

log = logging.getLogger(NAME)


class Unauthorized(Exception):
    """El servidor rechazó el token (revocado, rotado o inválido) o el sobre."""


class Foreign(Exception):
    """Respondió algo que no es SubNetFlow (un proxy, Cloudflare Access, una página de error)."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """1.0.2: no se siguen redirecciones. Un 302 delante de SubNetFlow suele ser Cloudflare Access pidiendo inicio de
    sesión; seguirlo convertía el POST en GET y devolvía la página de login (\"Expecting value\")."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Foreign("el servidor redirige a %s (HTTP %s)" % (urllib.parse.urlsplit(newurl).netloc or newurl, code))


class TooSoon(Exception):
    def __init__(self, retry):
        super().__init__("demasiado seguido")
        self.retry = retry


# --------------------------------------------------------------------------------------------------------------------
# Criptografía (python3-cryptography, el paquete de Debian / Proxmox). No hay criptografía escrita a mano.
# --------------------------------------------------------------------------------------------------------------------
def _crypto():
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    except ImportError:
        sys.exit("Falta python3-cryptography. Instálalo con: apt-get install -y python3-cryptography")
    return hashes, AESGCM, HKDF


def parse_token(token):
    m = TOKEN_RE.match((token or "").strip())
    if not m:
        raise ValueError("El token no tiene la forma snfp_<id>_<secreto>.")
    return m.group(1), m.group(2)


def derive_key(agent_id, secret):
    hashes, _, HKDF = _crypto()
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=("snf-pulse:%s" % agent_id).encode(), info=PROTO.encode()).derive(secret.encode())


def _aad(direction, agent_id, ts):
    return ("%s|%s|%s|%d" % (PROTO, direction, agent_id, ts)).encode()


def seal(key, direction, agent_id, obj, ts=None, nonce=None):
    _, AESGCM, _ = _crypto()
    ts = int(time.time()) if ts is None else ts
    nonce = secrets.token_bytes(12) if nonce is None else nonce
    plain = zlib.compress(json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    ct = AESGCM(key).encrypt(nonce, plain, _aad(direction, agent_id, ts))
    return {"v": 1, "id": agent_id, "ts": ts, "z": 1, "n": base64.b64encode(nonce).decode(), "c": base64.b64encode(ct).decode()}


def open_envelope(key, direction, agent_id, env, check_time=True):
    _, AESGCM, _ = _crypto()
    if not isinstance(env, dict) or env.get("v") != 1 or env.get("id") != agent_id or not isinstance(env.get("ts"), int):
        raise ValueError("sobre con forma inválida")
    if check_time and abs(int(time.time()) - env["ts"]) > MAX_SKEW_S:
        raise ValueError("marca de tiempo fuera de la ventana de 5 minutos (revisa la hora del nodo)")
    nonce = base64.b64decode(env["n"])
    plain = AESGCM(key).decrypt(nonce, base64.b64decode(env["c"]), _aad(direction, agent_id, env["ts"]))
    if env.get("z") == 1:
        plain = zlib.decompress(plain)
    return json.loads(plain.decode("utf-8"))


# --------------------------------------------------------------------------------------------------------------------
# Recolección (solo lectura)
# --------------------------------------------------------------------------------------------------------------------
def _run(cmd, timeout=30):
    return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=timeout)


def pv(path):
    """pvesh get <path> en JSON; None si falla."""
    try:
        return json.loads(_run(["pvesh", "get", path, "--output-format", "json"]))
    except Exception:
        return None


def read_file(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except Exception:
        return ""


def cpu_sample(seconds=1.0):
    """CPU ocupada (%) medida en /proc/stat durante `seconds`. El valor instantáneo de Proxmox suele dar 0."""
    def read():
        with open("/proc/stat") as f:
            vals = [int(x) for x in f.readline().split()[1:]]
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        return idle, sum(vals)
    try:
        i1, t1 = read()
        time.sleep(seconds)
        i2, t2 = read()
        dt = t2 - t1
        return round(100.0 * (1 - (i2 - i1) / dt), 1) if dt > 0 else None
    except Exception:
        return None


GENERIC_DMI = re.compile(r"^(to be filled.*|default string|system (product name|version)|not (specified|applicable)|none|o\.e\.m\.?|\d+(\.\d+)*)$", re.I)


def product_label(vendor, product, version):
    """Nombre del equipo para mostrar. 1.0.4: Lenovo guarda el tipo de máquina en product_name (10T8S5W400) y el nombre
    comercial en product_version (ThinkCentre M720q): se muestran los dos. Otros fabricantes usan product_version para
    una revisión ("1.0"), que no se agrega."""
    product, version = (product or "").strip(), (version or "").strip()
    if vendor.strip().upper() == "LENOVO" and version and not GENERIC_DMI.match(version) and version.lower() != product.lower() and " " in version:
        return "%s (%s)" % (version, product) if product else version
    return product


def dmi():
    base = "/sys/class/dmi/id/"
    vendor = read_file(base + "sys_vendor")
    product = product_label(vendor, read_file(base + "product_name"), read_file(base + "product_version"))
    return {"vendor": vendor, "product": product, "chassis_type": read_file(base + "chassis_type")}


def memory_info():
    """Tipo de RAM, ECC y módulos según dmidecode (si está). Nada si no se puede leer."""
    try:
        out = _run(["dmidecode", "-t", "17"], timeout=15).decode("utf-8", "replace")
    except Exception:
        return {}
    types, modules = set(), []
    for block in out.split("\n\n"):
        if "Memory Device" not in block:
            continue
        size = re.search(r"^\s*Size:\s*(\d+)\s*(MB|GB|TB)", block, re.M)
        if not size:
            continue
        gb = int(size.group(1)) / 1024 if size.group(2) == "MB" else int(size.group(1)) * (1024 if size.group(2) == "TB" else 1)
        typ = re.search(r"^\s*Type:\s*(\S+)", block, re.M)
        if typ and typ.group(1) not in ("Unknown", "Other"):
            types.add(typ.group(1))
        speed = re.search(r"^\s*Speed:\s*(\d+\s*MT/s|\d+\s*MHz)", block, re.M)
        modules.append({"size_gb": round(gb, 2), "speed": speed.group(1) if speed else ""})
    ecc = None
    try:
        out16 = _run(["dmidecode", "-t", "16"], timeout=15).decode("utf-8", "replace")
        m = re.search(r"Error Correction Type:\s*(.+)", out16)
        if m and m.group(1).strip() not in ("Unknown", "Other"):
            ecc = m.group(1).strip() != "None"
    except Exception:
        pass
    return {"type": ",".join(sorted(types)), "ecc": ecc, "modules": modules}


def nics():
    """Interfaces físicas (las que tienen /device) con su velocidad y estado."""
    out = []
    for path in sorted(glob.glob("/sys/class/net/*")):
        if not os.path.exists(os.path.join(path, "device")):
            continue
        try:
            speed = int(read_file(path + "/speed") or -1)
        except ValueError:
            speed = -1
        out.append({"name": os.path.basename(path), "speed_mbps": speed, "state": read_file(path + "/operstate")})
    return out


def _kv(text):
    out = {}
    for part in text.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def guests_and_passthrough(node):
    """Sistema, red y passthrough de cada VM/LXC según su archivo de configuración (solo la sección principal)."""
    guests, pt, pci = {}, {}, set()
    for sub in ("qemu-server", "lxc"):
        for f in sorted(glob.glob("/etc/pve/nodes/%s/%s/*.conf" % (node, sub))):
            vmid = os.path.basename(f).split(".")[0]
            txt = read_file(f)
            g = {"ostype": "", "net": []}
            ipcfg = {}
            disks, pcis = [], []
            for line in txt.splitlines():
                if line.startswith("["):
                    break
                m = re.match(r"^ostype:\s*(\S+)", line)
                if m:
                    g["ostype"] = m.group(1)
                m = re.match(r"^net(\d+):\s*(.+)$", line)
                if m:
                    kv = _kv(m.group(2))
                    mac = kv.get("hwaddr") or next((v for k, v in kv.items() if re.match(r"^(virtio|e1000e?|rtl8139|vmxnet3)$", k)), "")
                    g["net"].append({"idx": int(m.group(1)), "bridge": kv.get("bridge", ""), "hwaddr": mac, "ip": kv.get("ip", ""), "tag": kv.get("tag", "")})
                m = re.match(r"^ipconfig(\d+):\s*(.+)$", line)
                if m:
                    ipcfg[int(m.group(1))] = _kv(m.group(2)).get("ip", "")
                m = re.match(r"^hostpci\d+:\s*(\S+)", line)
                if m:
                    a = m.group(1).split(",")[0]
                    a = a if a.count(":") > 1 else "0000:" + a
                    pcis.append(a)
                    pci.add(a)
                m = re.match(r"^(?:scsi|sata|ide|virtio|mp)\d+:\s*(/dev/\S+?)(?:,|$)", line)
                if m:
                    disks.append(m.group(1))
            for n in g["net"]:
                if not n["ip"] and n["idx"] in ipcfg:
                    n["ip"] = ipcfg[n["idx"]]
            g["net"].sort(key=lambda x: x["idx"])
            guests[vmid] = g
            if disks or pcis:
                pt[vmid] = {"disks": disks, "pci": pcis}
    devices = {}
    if pci:
        try:
            for line in _run(["lspci", "-Dnn"]).decode("utf-8", "replace").splitlines():
                addr = line.split()[0] if line.split() else ""
                if addr in pci:
                    devices[addr] = line
        except Exception:
            pass
    return guests, pt, devices


def collect():
    node = socket.gethostname().split(".")[0]
    cpu = cpu_sample()
    guests, pt, devices = guests_and_passthrough(node)
    out = {"schema": SCHEMA, "node": node, "agent": {"name": NAME, "version": VERSION}}
    for key, path in (("status", "status"), ("network", "network"), ("storage", "storage"), ("disks", "disks/list"), ("qemu", "qemu"), ("lxc", "lxc")):
        out[key] = pv("/nodes/%s/%s" % (node, path))
    out["passthrough"] = pt
    out["pci_devices"] = devices
    out["ext"] = {"cpu_pct": cpu, "dmi": dmi(), "memory": memory_info(), "nics": nics(), "guests": guests}
    return out


# --------------------------------------------------------------------------------------------------------------------
# Envío
# --------------------------------------------------------------------------------------------------------------------
def load_conf(path):
    try:
        st = os.stat(path)
    except FileNotFoundError:
        sys.exit("No existe %s. Instala el agente con install.sh." % path)
    if st.st_mode & 0o077:
        sys.exit("%s tiene permisos abiertos: deja solo al dueño (chmod 600). Guarda el token de la sede." % path)
    conf = {}
    for line in read_file(path).splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            conf[k.strip()] = v.strip().strip('"')
    url = conf.get("SNF_URL", "").rstrip("/")
    if not url.startswith("https://") and not (url.startswith("http://") and conf.get("SNF_ALLOW_HTTP") == "yes"):
        sys.exit("SNF_URL debe empezar por https:// (por HTTP, solo con SNF_ALLOW_HTTP=yes y en una red de pruebas).")
    try:
        agent_id, secret = parse_token(conf.get("SNF_TOKEN", ""))
    except ValueError:
        sys.exit("El token de %s está vacío o incompleto. Cámbialo con: sudo ./install.sh --set-token" % path)
    cf = (conf.get("SNF_CF_ACCESS_CLIENT_ID", ""), conf.get("SNF_CF_ACCESS_CLIENT_SECRET", ""))
    return {"url": url, "agent_id": agent_id, "key": derive_key(agent_id, secret), "ca": conf.get("SNF_CA_FILE") or None,
            "cf_access": cf if all(cf) else None}


def _foreign_hint(detail):
    """Mensaje para una respuesta que no viene de SubNetFlow."""
    if "cloudflareaccess.com" in detail or "Cloudflare-Access" in detail:
        return ("Cloudflare Access bloquea al agente (%s). Crea un token de servicio en Zero Trust → Access → Service Auth, "
                "dale acceso a /api/pulse/v1/report y guárdalo con: sudo ./install.sh --cf-access. Ver README, sección 7." % detail)
    return "la respuesta no viene de SubNetFlow (%s). Revisa SNF_URL y el proxy o WAF delante de SubNetFlow." % detail


def post(conf, body, timeout=30):
    """POST del sobre. Devuelve (código, JSON, cabeceras); si la respuesta no es JSON de SubNetFlow, lanza Foreign."""
    data = json.dumps(body, separators=(",", ":")).encode()
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "%s/%s" % (NAME, VERSION)}
    if conf.get("cf_access"):
        headers["CF-Access-Client-Id"], headers["CF-Access-Client-Secret"] = conf["cf_access"]
    req = urllib.request.Request(conf["url"] + REPORT_PATH, data=data, method="POST", headers=headers)
    handlers = [_NoRedirect()]
    if conf["url"].startswith("https://"):
        ctx = ssl.create_default_context(cafile=conf["ca"]) if conf["ca"] else ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    opener = urllib.request.build_opener(*handlers)
    try:
        r = opener.open(req, timeout=timeout)
        status, hdrs, raw = r.status, r.headers, r.read(1 << 20)
        r.close()
    except urllib.error.HTTPError as e:
        status, hdrs, raw = e.code, e.headers, e.read(65536)
    try:
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError
    except Exception:
        auth = hdrs.get("Www-Authenticate", "") if hdrs else ""
        raise Foreign("HTTP %s, %s%s" % (status, (hdrs.get("Content-Type", "?") if hdrs else "?").split(";")[0], ", " + auth[:60] if auth else ""))
    return status, payload, hdrs


def send_once(conf):
    report = collect()
    env = seal(conf["key"], "req", conf["agent_id"], report)
    try:
        status, resp, headers = post(conf, env)
    except Foreign as e:
        raise RuntimeError(_foreign_hint(str(e)))
    if status == 401:
        raise Unauthorized(resp.get("error", "no autorizado"))
    if status == 429:
        try:
            retry = int(headers.get("Retry-After") or 0)
        except (TypeError, ValueError):
            retry = 0
        raise TooSoon(retry or 120)
    if status != 200:
        raise RuntimeError("el servidor respondió %s: %s" % (status, resp.get("error", "")))
    # La respuesta también va cifrada: si no descifra, no viene de tu SubNetFlow.
    try:
        return report, open_envelope(conf["key"], "res", conf["agent_id"], resp)
    except Exception as e:
        raise RuntimeError("respuesta no auténtica del servidor (%s)" % e)


def run_loop(conf):
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    # 1.0.4: espera de 20 a 30 s al arrancar. Así el primer reporte no llega pegado al de prueba de install.sh (el servidor
    # rechaza dos del mismo nodo con menos de 20 s), y varios nodos reiniciados a la vez no reportan en el mismo segundo.
    time.sleep(random.uniform(20, 30))
    backoff = 60
    while True:
        try:
            report, resp = send_once(conf)
            interval = max(MIN_INTERVAL_S, min(MAX_INTERVAL_S, int(resp.get("interval_s") or 300)))
            backoff = 60
            log.info("reporte enviado: nodo %s, %d carga(s); %s; próximo en %d s", report["node"],
                     len(report.get("qemu") or []) + len(report.get("lxc") or []),
                     "registrado en SubNetFlow" if resp.get("registered") else "aún no registrado en SubNetFlow", interval)
            time.sleep(interval + random.uniform(0, 5))
        except Unauthorized as e:
            log.error("token rechazado (%s): revocado, rotado o inválido. Actualízalo con: sudo ./install.sh --set-token", str(e).rstrip("."))
            time.sleep(MAX_INTERVAL_S)
        except TooSoon as e:
            log.warning("el servidor pide esperar %d s", e.retry)
            time.sleep(e.retry)
        except Exception as e:
            log.warning("no se pudo reportar: %s (reintento en %d s)", e, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 900)


def main(argv=None):
    ap = argparse.ArgumentParser(prog=NAME, description="Agente de nodos Proxmox VE para SubNetFlow.")
    ap.add_argument("command", choices=["run", "once", "test", "dry-run", "version"],
                    help="run: servicio; once: un reporte; test: un reporte con detalle; dry-run: muestra lo que se enviaría, sin enviar; version")
    ap.add_argument("--config", default=DEFAULT_CONF, help="archivo de configuración (por defecto %s)" % DEFAULT_CONF)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)

    if args.command == "version":
        print("%s %s (protocolo %s)" % (NAME, VERSION, PROTO))
        return 0
    if args.command == "dry-run":
        print(json.dumps(collect(), indent=2, ensure_ascii=False))
        return 0
    conf = load_conf(args.config)
    if args.command == "run":
        run_loop(conf)
        return 0
    try:
        report, resp = send_once(conf)
    except Unauthorized as e:
        print("Token rechazado (%s). Revisa que sea el vigente de la sede." % str(e).rstrip("."), file=sys.stderr)
        return 3
    except Exception as e:
        print("Falló el reporte: %s" % e, file=sys.stderr)
        return 1
    if args.command == "test":
        print("OK: SubNetFlow recibió el reporte del nodo %s (%d carga(s))." % (report["node"], len(report.get("qemu") or []) + len(report.get("lxc") or [])))
        print("Registrado en SubNetFlow: %s. Próximo reporte en %d min." % ("sí" if resp.get("registered") else "no (regístralo desde Virtualización)", int(resp.get("interval_s") or 300) // 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
