# SubNetFlow Pulse

Agente para nodos **Proxmox VE** que mantiene al día el inventario de virtualización de **SubNetFlow**.
Cada pocos minutos lee el estado del nodo y lo envía cifrado a tu instalación de SubNetFlow por su dominio público:
CPU y RAM en uso, discos, almacenamiento, interfaces de red con su velocidad y cada VM y contenedor LXC con su consumo.

| | |
|---|---|
| **Versión** | 1.0.0 |
| **Protocolo** | `snf-pulse-v1` (ver [PROTOCOL.md](PROTOCOL.md)) |
| **Requisitos** | Proxmox VE 8 o 9, `python3` y `python3-cryptography` (paquete de Debian) |
| **Compatible con** | SubNetFlow 1.9.97 o posterior |
| **Licencia** | Propietaria, de código visible (ver [LICENSE.md](LICENSE.md)) |

---

## Contenido

1. [Qué hace](#1-qué-hace)
2. [Qué envía y qué no](#2-qué-envía-y-qué-no)
3. [Cómo protege los datos](#3-cómo-protege-los-datos)
4. [Instalación](#4-instalación)
5. [Operación](#5-operación)
6. [Actualizar, cambiar el token y desinstalar](#6-actualizar-cambiar-el-token-y-desinstalar)
7. [Solución de problemas](#7-solución-de-problemas)
8. [Estructura del repositorio](#8-estructura-del-repositorio)

---

## 1. Qué hace

- Corre en el nodo como servicio de systemd (`subnetflow-pulse.service`).
- Cada intervalo lee el estado del nodo, arma un reporte, lo cifra y lo envía a SubNetFlow. El intervalo lo decides en SubNetFlow: 1, 5 (predeterminado), 10, 20, 30 o 60 minutos. El agente lo toma de cada respuesta del servidor, así que no hace falta tocar el nodo para cambiarlo.
- En SubNetFlow, el nodo muestra **CPU y RAM en uso reales** y cada VM o LXC, su consumo, sistema e IP.
- Si el nodo ya está registrado en SubNetFlow, su ficha se actualiza cuando cambia el hardware. En el servidor solo se llenan los campos que estaban vacíos: nunca se pisa lo escrito a mano.
- Si el nodo aún no está registrado, SubNetFlow ofrece **Registrar nodo** con los datos del reporte.
- Es **de solo lectura**: no cambia nada en el nodo ni en sus VM.

## 2. Qué envía y qué no

**Envía** (puedes verlo tal cual con `pulse.py dry-run`):

| Dato | De dónde sale |
|---|---|
| Estado del nodo: CPU, RAM, carga, tiempo encendido, versión de Proxmox | `pvesh get /nodes/<nodo>/status` |
| CPU en uso medida durante 1 segundo | `/proc/stat` |
| Interfaces, bridges y su configuración | `pvesh get /nodes/<nodo>/network` |
| Velocidad y estado de cada puerto físico | `/sys/class/net/*/speed` y `operstate` |
| Almacenamientos y su capacidad | `pvesh get /nodes/<nodo>/storage` |
| Discos físicos (modelo, tamaño, tipo, serie) | `pvesh get /nodes/<nodo>/disks/list` |
| VM y LXC: estado, vCPU, RAM, disco, consumo y etiquetas | `pvesh get /nodes/<nodo>/qemu` y `/lxc` |
| De cada VM/LXC: sistema (`ostype`), bridge, VLAN, MAC e IP configurada | `/etc/pve/nodes/<nodo>/{qemu-server,lxc}/*.conf` |
| Discos y PCIe en passthrough | Los mismos archivos y `lspci -Dnn` |
| Fabricante, modelo y tipo de chasis | `/sys/class/dmi/id/` |
| Tipo de RAM, ECC y módulos | `dmidecode -t 16` y `-t 17` |

**No envía:** contraseñas ni claves, el contenido de los discos o de las VM, notas de las VM, registros del sistema, credenciales de Proxmox ni nada que el agente no lea de la lista anterior.

## 3. Cómo protege los datos

- **Token por sede.** SubNetFlow genera un token único por sede (`snfp_<id>_<secreto>`) que se ve una sola vez. Se puede **rotar** (el anterior deja de valer en el acto) o **revocar**.
- **Cifrado de extremo a extremo además de HTTPS.** Cada reporte va en un sobre **AES-256-GCM** con una llave derivada del token (HKDF-SHA256). La llave nunca viaja. Aunque un proxy o un túnel (Cloudflare, por ejemplo) termine el TLS, solo tu SubNetFlow puede leer el reporte.
- **Respuesta autenticada.** La respuesta del servidor también va cifrada con la misma llave: si no descifra, el agente la descarta. Así sabe que habla con tu SubNetFlow y no con un impostor.
- **Sin repeticiones.** Cada sobre lleva marca de tiempo (ventana de ±5 minutos) y un nonce aleatorio que el servidor no acepta dos veces.
- **Aislamiento por sede.** El token solo puede escribir en su sede. En SubNetFlow los datos quedan cifrados con la llave de la sede, y la IP y la MAC de las cargas se censuran según el rol.
- **En el nodo.** La configuración con el token queda en `/etc/subnetflow-pulse/agent.conf`, con permisos `600` de root. El agente se niega a arrancar si el archivo tiene permisos más abiertos. El servicio corre con el aislamiento de systemd que permite su tarea; ver `subnetflow-pulse.service`.

El detalle está en [PROTOCOL.md](PROTOCOL.md) y [SECURITY.md](SECURITY.md).

## 4. Instalación

1. **En SubNetFlow:** abre la sede, ve a **Virtualización → 📡 SubNetFlow Pulse → Crear agente** (pide tu segundo factor si tienes MFA). Copia el token: solo se muestra esta vez.
2. **En el nodo** (consola de Proxmox o SSH, como root):

   ```bash
   apt-get install -y git python3-cryptography
   git clone https://github.com/EBR666/subnetflow-pulse.git
   cd subnetflow-pulse
   ./install.sh --url https://subnetflow.ejemplo.com
   ```

   El instalador pide el token sin mostrarlo, para que no quede en el historial. Copia el programa a `/opt/subnetflow-pulse`, guarda la configuración, hace un reporte de prueba y activa el servicio. Si la prueba falla, no activa nada.

3. **De vuelta en SubNetFlow:** el nodo aparece en el panel del agente. Si no estaba registrado, usa **Registrar nodo**.

Para varios nodos de la misma sede se usa el mismo token: cada nodo reporta con su nombre.

## 5. Operación

```bash
systemctl status subnetflow-pulse          # estado del servicio
journalctl -u subnetflow-pulse -f          # registro en vivo
/opt/subnetflow-pulse/pulse.py dry-run     # lo que enviaría, en claro, sin enviarlo
/opt/subnetflow-pulse/pulse.py test        # un reporte ahora, con el resultado
/opt/subnetflow-pulse/pulse.py version
```

El servicio usa como máximo 128 MB de RAM y el 20 % de una CPU. Cada reporte tarda unos segundos: 1 s de muestra de CPU y las consultas a `pvesh`.

## 6. Actualizar, cambiar el token y desinstalar

```bash
cd subnetflow-pulse && git pull
./install.sh --upgrade        # actualiza el programa y conserva la configuración
./install.sh --set-token      # tras rotar el token en SubNetFlow
./uninstall.sh                # quita el servicio y el programa (conserva /etc/subnetflow-pulse)
./uninstall.sh --purge        # también borra la configuración y el token
```

Al desinstalar, revoca el token en SubNetFlow si no vas a reinstalar el agente.

## 7. Solución de problemas

| Mensaje | Causa y solución |
|---|---|
| `token rechazado` | El token se rotó o revocó, o se copió incompleto. Cópialo de nuevo y aplica `./install.sh --set-token`. |
| `marca de tiempo fuera de la ventana` o 401 constantes | La hora del nodo no está al día. Revisa NTP: `chronyc tracking`. |
| `respuesta no auténtica del servidor` | La respuesta no la firmó tu SubNetFlow (proxy que altera el cuerpo, o dirección equivocada). Revisa `SNF_URL`. |
| `CERTIFICATE_VERIFY_FAILED` | El certificado no es de una CA pública. Pon tu CA en `SNF_CA_FILE` en `agent.conf`. |
| `el servidor pide esperar` | Dos reportes del mismo nodo con menos de 20 s de diferencia: el agente espera y sigue. |
| `Falta python3-cryptography` | `apt-get install -y python3-cryptography`. |
| 403 / 1020 de Cloudflare | Una regla de WAF o de bots bloquea al agente. Permite `POST /api/pulse/v1/report` en tu dominio. |

## 8. Estructura del repositorio

```
pulse.py                    agente (recolección, cifrado y envío)
install.sh / uninstall.sh   instalador y desinstalador
subnetflow-pulse.service    servicio de systemd
PROTOCOL.md                 protocolo snf-pulse-v1
tests/                      pruebas del protocolo (python3 -m unittest discover -s tests -v)
LICENSE.md / SECURITY.md / CHANGELOG.md
```

Copyright © 2026 Andrés Eduardo Brand Ruiz. Todos los derechos reservados.
