# Changelog — SubNetFlow Pulse

## 1.0.1 — 2026-11-09

### Corregido
- **`install.sh` no esperaba el token:** al pegar los cuatro comandos de la guía de una vez, la pregunta del token tomaba la línea siguiente (vacía). Ahora lee el token de la terminal (`/dev/tty`) y da tres intentos.
- **Un token inválido no detenía el instalador:** la validación corría dentro de una subshell y su error no frenaba nada; se guardaba un token vacío y la prueba fallaba con un traceback. Ahora se valida antes de instalar nada, y sin un token válido no se toca el sistema.
- **`pulse.py` con un token vacío o incompleto** mostraba un traceback de Python. Ahora dice que se corrija con `./install.sh --set-token`.

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
