#!/usr/bin/env bash
# SubNetFlow Pulse — instalador para nodos Proxmox VE (Debian). Ver README.md.
#
#   sudo ./install.sh --url https://subnetflow.ejemplo.com   instala o actualiza y pide el token de la sede
#   sudo ./install.sh --set-token                             cambia el token (tras rotarlo en SubNetFlow)
#   sudo ./install.sh --cf-access                             guarda el token de servicio de Cloudflare Access
#   sudo ./install.sh --upgrade                               actualiza el programa y conserva la configuración
#
# Los secretos se piden por teclado (sin eco) o se leen de --token-file: así no quedan en el historial de la consola.
set -euo pipefail

PREFIX=/opt/subnetflow-pulse
CONF_DIR=/etc/subnetflow-pulse
CONF="$CONF_DIR/agent.conf"
UNIT=/etc/systemd/system/subnetflow-pulse.service
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOKEN_RE='^snfp_[0-9A-HJKMNP-TV-Z]{16}_[0-9A-HJKMNP-TV-Z]{52}$'

URL=""
TOKEN_FILE=""
MODE="install"
ASSUME_YES="no"
CF_ACCESS="no"

die() { echo "✗ $*" >&2; exit 1; }
say() { echo "• $*"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --url) URL="${2:-}"; shift 2 ;;
    --token-file) TOKEN_FILE="${2:-}"; shift 2 ;;
    --set-token) MODE="set-token"; shift ;;
    --cf-access) CF_ACCESS="yes"; shift ;;
    --upgrade) MODE="upgrade"; shift ;;
    --yes|-y) ASSUME_YES="yes"; shift ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) die "Opción desconocida: $1 (usa --help)" ;;
  esac
done
# --cf-access solo (sin --url ni --set-token): actualiza la configuración que ya existe.
if [ "$CF_ACCESS" = "yes" ] && [ "$MODE" = "install" ] && [ -z "$URL" ] && [ -f "$CONF" ]; then MODE="cf-access"; fi

[ "$(id -u)" -eq 0 ] || die "Ejecútalo como root (sudo)."
command -v python3 >/dev/null || die "Falta python3."
command -v pvesh >/dev/null || echo "⚠ No se encontró pvesh: este equipo no parece un nodo Proxmox VE. El agente reportará poco." >&2

# python3-cryptography: AES-256-GCM y HKDF del paquete de Debian (el agente no trae criptografía propia).
if ! python3 -c 'import cryptography' 2>/dev/null; then
  if [ "$ASSUME_YES" != "yes" ]; then
    read -r -p "Falta python3-cryptography. ¿Instalarlo con apt? [s/N] " ans < /dev/tty
    case "$ans" in s|S|si|SI|sí|y|Y) ;; *) die "Instálalo con: apt-get install -y python3-cryptography" ;; esac
  fi
  apt-get install -y python3-cryptography
fi

# Valor guardado de una clave de agent.conf (vacío si no existe).
existing() { [ -f "$CONF" ] && sed -n "s/^$1=//p" "$CONF" | head -n1 || true; }

# Deja el token en $TOKEN. Se lee de la terminal (/dev/tty), no de la entrada estándar: así, si se pegan varios comandos
# de una vez, la pregunta espera al token en lugar de tragarse la línea siguiente. Tres intentos antes de rendirse.
# 1.0.1: antes se llamaba dentro de $(…) y su validación no detenía el instalador (guardaba un token vacío).
TOKEN=""
read_token() {
  local t="" i
  if [ -n "$TOKEN_FILE" ]; then
    t="$(tr -d ' \t\r\n' < "$TOKEN_FILE")"
    [[ "$t" =~ $TOKEN_RE ]] || die "El archivo $TOKEN_FILE no contiene un token válido (snfp_<id>_<secreto>)."
    TOKEN="$t"
    return 0
  fi
  [ -r /dev/tty ] || die "No hay una terminal para pedir el token. Usa --token-file /ruta/al/archivo."
  for i in 1 2 3; do
    read -r -s -p "Pega el token de la sede (snfp_…) y pulsa Enter: " t < /dev/tty || true
    echo >&2
    t="$(printf '%s' "$t" | tr -d ' \t\r\n')"
    if [[ "$t" =~ $TOKEN_RE ]]; then
      TOKEN="$t"
      return 0
    fi
    echo "✗ Eso no es un token completo: empieza por snfp_ y tiene 74 caracteres (intento $i de 3)." >&2
  done
  die "No se recibió un token válido. Cópialo de nuevo en SubNetFlow con el botón ⧉ Copiar y vuelve a ejecutar el instalador."
}

# 1.0.2: token de servicio de Cloudflare Access (Zero Trust → Access → Service Auth). Deja $CF_ID y $CF_SECRET.
CF_ID=""
CF_SECRET=""
read_cf_access() {
  local id="" secret="" i
  [ -r /dev/tty ] || die "No hay una terminal para pedir el token de Cloudflare Access."
  echo "Token de servicio de Cloudflare Access (Zero Trust → Access → Service Auth → Service Tokens)." >&2
  for i in 1 2 3; do
    read -r -p "Client ID (termina en .access): " id < /dev/tty || true
    id="$(printf '%s' "$id" | tr -d ' \t\r\n')"
    [[ "$id" =~ ^[A-Za-z0-9._-]{8,200}\.access$ ]] && break
    echo "✗ El Client ID termina en .access (cópialo completo desde Cloudflare; intento $i de 3)." >&2
    id=""
  done
  [ -n "$id" ] || die "No se recibió un Client ID válido."
  for i in 1 2 3; do
    read -r -s -p "Client Secret (no se muestra): " secret < /dev/tty || true
    echo >&2
    secret="$(printf '%s' "$secret" | tr -d ' \t\r\n')"
    # 1.0.3: no se exige un formato (1.0.2 pedía 64 hexadecimales y rechazaba secretos reales). Si es incorrecto, lo
    # dirá Cloudflare en la prueba de conexión.
    [ "${#secret}" -ge 16 ] && [ "${#secret}" -le 512 ] && break
    echo "✗ No llegó el Client Secret completo (${#secret} caracteres). Pégalo de nuevo (intento $i de 3)." >&2
    secret=""
  done
  [ -n "$secret" ] || die "No se recibió un Client Secret válido."
  CF_ID="$id"
  CF_SECRET="$secret"
}

# Escribe agent.conf (0600 root) y conserva lo que no se cambia en esta ejecución (Cloudflare Access, CA propia).
write_conf() {
  local url="$1" token="$2"
  local cf_id="${CF_ID:-$(existing SNF_CF_ACCESS_CLIENT_ID)}"
  local cf_secret="${CF_SECRET:-$(existing SNF_CF_ACCESS_CLIENT_SECRET)}"
  local ca="$(existing SNF_CA_FILE)"
  install -d -m 0700 -o root -g root "$CONF_DIR"
  umask 077
  {
    echo "# SubNetFlow Pulse — configuración del agente. Solo root puede leerla: contiene el token de la sede."
    echo "SNF_URL=$url"
    echo "SNF_TOKEN=$token"
    if [ -n "$cf_id" ] && [ -n "$cf_secret" ]; then
      echo "# Cloudflare Access: token de servicio para pasar la protección del dominio."
      echo "SNF_CF_ACCESS_CLIENT_ID=$cf_id"
      echo "SNF_CF_ACCESS_CLIENT_SECRET=$cf_secret"
    fi
    if [ -n "$ca" ]; then echo "SNF_CA_FILE=$ca"; else echo "# SNF_CA_FILE=/ruta/a/ca.pem   (opcional: CA propia si el certificado de SubNetFlow no es público)"; fi
  } > "$CONF.tmp"
  chmod 0600 "$CONF.tmp"
  mv "$CONF.tmp" "$CONF"
}

install_program() {
  install -d -m 0755 "$PREFIX"
  install -m 0755 "$HERE/pulse.py" "$PREFIX/pulse.py"
  install -m 0644 "$HERE/subnetflow-pulse.service" "$UNIT"
  systemctl daemon-reload
}

need_conf() { [ -f "$CONF" ] || die "No hay configuración en $CONF: instala primero con --url."; }

case "$MODE" in
  set-token)
    need_conf
    read_token
    [ "$CF_ACCESS" = "yes" ] && read_cf_access
    write_conf "$(existing SNF_URL)" "$TOKEN"
    say "Token actualizado."
    ;;
  cf-access)
    need_conf
    read_cf_access
    install_program   # el envío del token de Access llegó en 1.0.2: se actualiza el programa de paso
    write_conf "$(existing SNF_URL)" "$(existing SNF_TOKEN)"
    say "Token de Cloudflare Access guardado."
    ;;
  upgrade)
    need_conf
    install_program
    say "Programa actualizado a $(python3 "$PREFIX/pulse.py" version)."
    ;;
  install)
    if [ -z "$URL" ] && [ -f "$CONF" ]; then URL="$(existing SNF_URL)"; fi
    [ -n "$URL" ] || die "Indica la dirección de SubNetFlow: --url https://subnetflow.ejemplo.com"
    URL="${URL%/}"
    [[ "$URL" =~ ^https://[^/[:space:]]+$ ]] || die "La dirección debe ser https://dominio, sin ruta."
    read_token   # antes de tocar nada: sin token válido no se instala
    [ "$CF_ACCESS" = "yes" ] && read_cf_access
    install_program
    write_conf "$URL" "$TOKEN"
    ;;
esac

say "Probando la conexión con SubNetFlow…"
if python3 "$PREFIX/pulse.py" test; then
  systemctl enable --now subnetflow-pulse.service >/dev/null
  systemctl restart subnetflow-pulse.service
  say "Servicio activo. Registro: journalctl -u subnetflow-pulse -f"
else
  echo "⚠ La prueba falló: el servicio no se activó. La configuración quedó guardada." >&2
  echo "  Token: ./install.sh --set-token · Cloudflare Access: ./install.sh --cf-access · Hora del nodo: chronyc tracking" >&2
  exit 1
fi
