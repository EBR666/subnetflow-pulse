# Changelog — SubNetFlow Pulse

## 1.0.2 — 2026-11-09

### Nuevo
- **Cloudflare Access:** el agente puede enviar un token de servicio (`CF-Access-Client-Id` y `CF-Access-Client-Secret`). Se guarda con `./install.sh --cf-access`, o junto con la instalación (`--url … --cf-access`). Ver README, sección 7.1.

### Corregido
- **"Expecting value: line 1 column 1":** con el dominio detrás de Cloudflare Access, el agente seguía el `302` hacia la página de inicio de sesión y recibía HTML. Ahora no sigue redirecciones, y explica qué pasó y cómo resolverlo.
- **Respuestas que no vienen de SubNetFlow** (un proxy, una página de error): se informan con su código y su tipo, sin un error de Python.
- **`--set-token` y `--upgrade`** conservan el token de Cloudflare Access y la CA propia que ya estaban en `agent.conf`.

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
