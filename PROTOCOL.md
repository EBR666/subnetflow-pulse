# Protocolo `snf-pulse-v1`

Comunicación entre el agente SubNetFlow Pulse y una instalación de SubNetFlow. El agente lo implementa en `pulse.py`;
el servidor, en `src/utils/pulse-crypto.js` y `src/services/pulse.js` de SubNetFlow. Los dos comparten los vectores de
`tests/vectors.json`.

## 1. Token

```
snfp_<id>_<secreto>
```

- `id`: 16 caracteres de base32 de Crockford (`0-9 A-H J K M N P-T V-Z`), 80 bits aleatorios. Es público: identifica al agente.
- `secreto`: 52 caracteres de base32 de Crockford, 256 bits aleatorios (`crypto.randomBytes(32)`).
- Uno activo por sede. SubNetFlow guarda el secreto cifrado con la llave de la sede (AES-256-GCM) y solo lo muestra al crearlo o rotarlo.

## 2. Llave

```
K = HKDF-SHA256(ikm = secreto (UTF-8), salt = "snf-pulse:" + id, info = "snf-pulse-v1", longitud = 32)
```

## 3. Sobre

Cuerpo JSON de `POST /api/pulse/v1/report` (máximo 4 MB):

```json
{ "v": 1, "id": "<id>", "ts": 1762600000, "z": 1, "n": "<nonce base64>", "c": "<cifrado base64>" }
```

| Campo | Contenido |
|---|---|
| `v` | Versión del protocolo: `1`. |
| `id` | El `id` del token. |
| `ts` | Segundos UNIX al cifrar. El servidor acepta ±300 s. |
| `z` | `1`: el texto se comprimió con zlib (RFC 1950) antes de cifrar. |
| `n` | Nonce aleatorio de 12 bytes. El servidor no acepta dos veces el mismo por agente. |
| `c` | `AES-256-GCM(K, n, zlib(JSON), aad)` seguido de la etiqueta de 16 bytes. |

Datos asociados (AAD), en UTF-8:

```
"snf-pulse-v1|req|<id>|<ts>"   del agente al servidor
"snf-pulse-v1|res|<id>|<ts>"   del servidor al agente
```

La dirección en el AAD impide devolver al agente un sobre suyo como si fuera la respuesta del servidor.

## 4. Reporte (texto del sobre del agente)

El mismo JSON que produce el comando de extracción de SubNetFlow (`"schema": "subnetflow-node-1"`), más:

- `agent`: `{ "name": "subnetflow-pulse", "version": "1.0.0" }`.
- `qemu` y `lxc`: las salidas de `pvesh get /nodes/<nodo>/qemu` y `/lxc`.
- `ext`: `cpu_pct` (muestra de 1 s de `/proc/stat`), `dmi` (fabricante, modelo y tipo de chasis), `memory` (tipo, ECC y módulos de `dmidecode`), `nics` (puertos físicos con velocidad y estado) y `guests` (`ostype` y red de cada VM/LXC según su configuración).

El servidor lo interpreta con `parseProxmoxNode`, que limita tamaños y descarta lo que no reconoce.

## 5. Respuestas

| Código | Cuerpo | El agente |
|---|---|---|
| 200 | Sobre cifrado (`res`) con `{ ok, interval_s, node, registered, synced, server_time }` | Descifra y verifica; espera `interval_s` (60–3600 s). |
| 400 | `{ "error": "…" }` | Reintenta con espera creciente. |
| 401 | `{ "error": "Agente no autorizado." }`: misma respuesta para token desconocido, revocado, firma inválida, marca de tiempo fuera de ventana o nonce repetido | Espera una hora. |
| 429 | `{ "error": "…" }` (reporte del mismo nodo con menos de 20 s, o 30 rechazos desde la IP en 15 min) | Espera `Retry-After` o 120 s. |

## 6. Rotación y revocación

- **Rotar:** SubNetFlow genera `id` y secreto nuevos para el mismo agente. El token anterior responde 401 desde ese momento.
- **Revocar:** el agente queda inactivo y todo reporte responde 401. Para volver a usar el agente en la sede, hay que crear uno nuevo.

Ambas acciones exigen el segundo factor del administrador y quedan en la auditoría forense de SubNetFlow (`agente.token`).
