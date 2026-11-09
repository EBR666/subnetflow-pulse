# Política de Seguridad — SubNetFlow Pulse

| | |
|---|---|
| **Documento** | Política de seguridad y divulgación coordinada de vulnerabilidades |
| **Versión del documento** | 1.0 · noviembre de 2026 (SubNetFlow Pulse 1.0.0) |
| **Producto** | SubNetFlow Pulse (agente de nodos Proxmox VE para SubNetFlow) |
| **Responsable** | Andrés Eduardo Brand Ruiz |
| **Canal privado de reporte** | andresebr644@gmail.com |

---

## 1. Propósito

El Agente corre como root en hipervisores y envía su inventario fuera del nodo. Un fallo en él puede exponer la topología de un cliente o servir de punto de entrada al hipervisor. Esta política dice cómo reportar una vulnerabilidad, qué controles implementa el Agente y qué le corresponde a quien lo opera.

## 2. Versiones con soporte

| Versión | Correcciones de seguridad |
|---|---|
| **1.0.x** (actual) | Sí, todas las severidades |

Actualiza con `git pull && sudo ./install.sh --upgrade`.

## 3. Cómo reportar una vulnerabilidad

Escribe **solo** a **andresebr644@gmail.com** con el asunto `[SEGURIDAD] SubNetFlow Pulse — <resumen>`. **No abras una incidencia pública** ni publiques detalles antes de la corrección.

Incluye la versión (`pulse.py version`), la versión de Proxmox VE y de SubNetFlow, los pasos para reproducirlo y una prueba de concepto no destructiva. **No envíes tokens reales**, contenidos de `agent.conf` ni datos de clientes: usa los vectores de prueba de `tests/vectors.json` o datos sintéticos.

Plazos: acuse de recibo en 3 días hábiles; evaluación inicial en 10 días hábiles; corrección según severidad (Crítica: 7 días; Alta: 30; Media: 60; Baja: próxima versión). La divulgación se coordina con quien reporta.

## 4. Pruebas permitidas

Solo en Nodos y en instalaciones de SubNetFlow propios o con autorización escrita de su dueño. No se permiten pruebas de denegación de servicio, ingeniería social ni acceso a datos de terceros.

## 5. Controles del Agente

| Área | Control |
|---|---|
| **Autenticación** | Token por sede de 256 bits. El servidor guarda el secreto cifrado y lo muestra una sola vez. Rotación y revocación inmediatas, con segundo factor del administrador y registro forense. |
| **Confidencialidad** | Cada reporte va en un sobre AES-256-GCM con una llave HKDF-SHA256 derivada del token, además de HTTPS (TLS 1.2 o superior, certificado verificado). Un proxy que termina TLS no puede leer el contenido. |
| **Integridad y autenticidad** | La etiqueta GCM cubre el contenido, el id del agente, la marca de tiempo y la dirección. La respuesta del servidor va cifrada igual: el Agente descarta una que no descifra. |
| **Anti-repetición** | Ventana de ±5 minutos y nonce aleatorio de 96 bits que el servidor no acepta dos veces. |
| **Aislamiento por sede** | El token solo escribe en su sede. En el servidor, los datos quedan cifrados con la llave de la sede. |
| **Mínimo privilegio en los datos** | Solo lectura. No envía contraseñas, claves ni contenido de discos o VM. `pulse.py dry-run` muestra exactamente lo que se enviaría. |
| **En el nodo** | `agent.conf` con permisos `600` de root (el Agente se niega a arrancar con permisos más abiertos). El token se pide sin eco o se lee de un archivo, para que no quede en el historial. El servicio corre con `NoNewPrivileges`, `ProtectHome`, `PrivateTmp`, `ProtectKernelModules`, `RestrictAddressFamilies`, `MemoryMax` y `CPUQuota`. |
| **Dependencias** | Solo la biblioteca estándar de Python y `python3-cryptography` del sistema. Ninguna dependencia de PyPI. |
| **Límites del servidor** | Cuerpo de hasta 4 MB, descompresión acotada, misma respuesta para todo rechazo y bloqueo de 15 minutos tras 30 rechazos desde una IP. |

## 6. Limitaciones conocidas

- **Corre como root**, porque `pvesh`, `dmidecode` y `/etc/pve` lo exigen. Revisa el código antes de instalarlo y actualízalo desde el repositorio oficial.
- **Quien lea `agent.conf` puede suplantar al nodo** ante SubNetFlow: enviar datos falsos de esa sede, nunca leer los de otra. Si sospechas que se filtró, **rota el token**.
- **El nonce visto vive en la memoria del servidor.** Tras reiniciar SubNetFlow, un sobre capturado podría repetirse mientras siga dentro de su ventana de 5 minutos. Su contenido no se puede alterar y solo actualizaría datos de esa misma sede.
- **La hora del nodo importa:** sin NTP, los reportes se rechazan.

## 7. Responsabilidades de quien lo opera

1. Instalarlo solo desde el repositorio oficial y revisar los cambios antes de actualizar.
2. Custodiar el token: un token por sede, rotarlo si cambia el personal con acceso a los nodos y revocarlo al retirar el Agente.
3. Mantener la hora de los nodos con NTP y SubNetFlow detrás de HTTPS.
4. Permitir en el WAF o en el proxy solo `POST /api/pulse/v1/report` hacia SubNetFlow para el tráfico del Agente.

## 8. Contacto

Reportes de seguridad: **andresebr644@gmail.com**.
