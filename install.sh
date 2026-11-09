#!/usr/bin/env bash
# SubNetFlow Pulse — instalador para nodos Proxmox VE (Debian). Ver README.md.
#
#   sudo ./install.sh --url https://subnetflow.ejemplo.com   instala o actualiza y pide el token de la sede
#   sudo ./install.sh --set-token                             cambia el token (tras rotarlo en SubNetFlow)
#   sudo ./install.sh --upgrade                               actualiza el programa y conserva la configuración
#
# El token se pide por teclado (sin eco) o se lee de --token-file: así no queda en el historial de la consola.
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

die() { echo "✗ $*" >&2; exit 1; }
say() { echo "• $*"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --url) URL="${2:-}"; shift 2 ;;
    --token-file) TOKEN_FILE="${2:-}"; shift 2 ;;
    --set-token) MODE="set-token"; shift ;;
    --upgrade) MODE="upgrade"; shift ;;
    --yes|-y) ASSUME_YES="yes"; shift ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) die "Opción desconocida: $1 (usa --help)" ;;
  esac
done

[ "$(id -u)" -eq 0 ] || die "Ejecútalo como root (sudo)."
command -v python3 >/dev/null || die "Falta python3."
command -v pvesh >/dev/null || echo "⚠ No se encontró pvesh: este equipo no parece un nodo Proxmox VE. El agente reportará poco." >&2

# python3-cryptography: AES-256-GCM y HKDF del paquete de Debian (el agente no trae criptografía propia).
if ! python3 -c 'import cryptography' 2>/dev/null; then
  if [ "$ASSUME_YES" != "yes" ]; then
    read -r -p "Falta python3-cryptography. ¿Instalarlo con apt? [s/N] " ans
    case "$ans" in s|S|si|SI|sí|y|Y) ;; *) die "Instálalo con: apt-get install -y python3-cryptography" ;; esac
  fi
  apt-get install -y python3-cryptography
fi

read_token() {
  local t=""
  if [ -n "$TOKEN_FILE" ]; then
    t="$(tr -d ' \r\n' < "$TOKEN_FILE")"
  else
    read -r -s -p "Pega el token de la sede (snfp_…): " t; echo
  fi
  [[ "$t" =~ $TOKEN_RE ]] || die "El token no tiene la forma snfp_<id>_<secreto>. Cópialo completo desde SubNetFlow."
  printf '%s' "$t"
}

write_conf() {
  local url="$1" token="$2"
  install -d -m 0700 -o root -g root "$CONF_DIR"
  umask 077
  cat > "$CONF.tmp" <<EOF
# SubNetFlow Pulse — configuración del agente. Solo root puede leerla: contiene el token de la sede.
SNF_URL=$url
SNF_TOKEN=$token
# SNF_CA_FILE=/ruta/a/ca.pem   (opcional: CA propia si el certificado de SubNetFlow no es público)
EOF
  chmod 0600 "$CONF.tmp"
  mv "$CONF.tmp" "$CONF"
}

install_program() {
  install -d -m 0755 "$PREFIX"
  install -m 0755 "$HERE/pulse.py" "$PREFIX/pulse.py"
  install -m 0644 "$HERE/subnetflow-pulse.service" "$UNIT"
  systemctl daemon-reload
}

case "$MODE" in
  set-token)
    [ -f "$CONF" ] || die "No hay configuración en $CONF: instala primero con --url."
    URL="$(sed -n 's/^SNF_URL=//p' "$CONF" | head -n1)"
    write_conf "$URL" "$(read_token)"
    say "Token actualizado."
    ;;
  upgrade)
    [ -f "$CONF" ] || die "No hay configuración en $CONF: instala primero con --url."
    install_program
    say "Programa actualizado a $(python3 "$PREFIX/pulse.py" version)."
    ;;
  install)
    if [ -z "$URL" ] && [ -f "$CONF" ]; then URL="$(sed -n 's/^SNF_URL=//p' "$CONF" | head -n1)"; fi
    [ -n "$URL" ] || die "Indica la dirección de SubNetFlow: --url https://subnetflow.ejemplo.com"
    URL="${URL%/}"
    [[ "$URL" =~ ^https://[^/[:space:]]+$ ]] || die "La dirección debe ser https://dominio, sin ruta."
    install_program
    write_conf "$URL" "$(read_token)"
    ;;
esac

say "Probando la conexión con SubNetFlow…"
if python3 "$PREFIX/pulse.py" test; then
  systemctl enable --now subnetflow-pulse.service >/dev/null
  systemctl restart subnetflow-pulse.service
  say "Servicio activo. Registro: journalctl -u subnetflow-pulse -f"
else
  echo "⚠ La prueba falló: el servicio no se activó. Revisa la dirección, el token y que el nodo tenga la hora al día (NTP)." >&2
  exit 1
fi
