# Changelog — SubNetFlow Pulse

## 1.0.0 — 2026-11-09

Primera versión. Requiere SubNetFlow 1.9.97 o posterior.

### Nuevo
- Agente para nodos Proxmox VE: lee el estado del nodo y lo envía a SubNetFlow cada 1, 5, 10, 20, 30 o 60 minutos (lo decide SubNetFlow).
- Datos: CPU en uso (muestra de 1 s de `/proc/stat`), RAM, carga, discos, almacenamiento, red y velocidad de cada puerto, fabricante y chasis (DMI), tipo de RAM y ECC (`dmidecode`), VM y LXC con su consumo, sistema, bridge, VLAN, MAC e IP, y passthrough.
- Protocolo `snf-pulse-v1`: sobre AES-256-GCM con llave HKDF-SHA256 del token de la sede, anti-repetición (marca de tiempo y nonce) y respuesta del servidor autenticada.
- `install.sh` (instalar, `--upgrade`, `--set-token`), `uninstall.sh` (`--purge`) y servicio de systemd con aislamiento.
- `pulse.py dry-run` para ver lo que se enviaría, `test` para un reporte con resultado.
- Pruebas del protocolo con vectores compartidos con SubNetFlow (`tests/`).

### No probado
- En un nodo Proxmox VE real: el servicio de systemd y su aislamiento, `dmidecode` y la lectura de `/etc/pve`. Las pruebas corrieron en Linux sin Proxmox.
