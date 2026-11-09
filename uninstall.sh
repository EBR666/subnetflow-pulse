#!/usr/bin/env bash
# SubNetFlow Pulse — desinstalador. Detiene el servicio y borra el programa.
#   sudo ./uninstall.sh            conserva /etc/subnetflow-pulse (el token)
#   sudo ./uninstall.sh --purge    borra también la configuración y el token
# Después, revoca el token de la sede en SubNetFlow (Virtualización → SubNetFlow Pulse → Revocar).
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Ejecútalo como root (sudo)." >&2; exit 1; }

systemctl disable --now subnetflow-pulse.service 2>/dev/null || true
rm -f /etc/systemd/system/subnetflow-pulse.service
systemctl daemon-reload
rm -rf /opt/subnetflow-pulse
if [ "${1:-}" = "--purge" ]; then
  rm -rf /etc/subnetflow-pulse
  echo "• Agente y configuración borrados."
else
  echo "• Agente borrado. La configuración sigue en /etc/subnetflow-pulse (bórrala con --purge)."
fi
echo "• Revoca el token en SubNetFlow si no vas a reinstalar el agente en este nodo."
