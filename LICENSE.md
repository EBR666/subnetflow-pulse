# SubNetFlow Pulse — Licencia de Software Propietario

| | |
|---|---|
| **Versión del documento** | 1.0 · noviembre de 2026 (SubNetFlow Pulse 1.0.0) |
| **Titular de los derechos** | Andrés Eduardo Brand Ruiz |
| **Domicilio** | Envigado, Antioquia, Colombia |
| **Contacto de licenciamiento** | andresebr644@gmail.com |

**Copyright © 2026 Andrés Eduardo Brand Ruiz. Todos los derechos reservados.**

SubNetFlow Pulse es software propietario. **No es software libre ni de código abierto.** Su código fuente se publica para que quien lo instale pueda revisar qué hace en sus servidores; publicarlo no concede una licencia pública ni ningún derecho distinto de los que este documento otorga de forma expresa.

---

## 1. Definiciones

- **«Agente»:** SubNetFlow Pulse en todas sus versiones: el programa `pulse.py`, sus instaladores, el servicio de systemd, el protocolo `snf-pulse-v1`, sus pruebas y su documentación.
- **«SubNetFlow»:** la plataforma de documentación de redes del Titular, regida por su propia licencia.
- **«Titular»:** Andrés Eduardo Brand Ruiz, autor y titular de los derechos patrimoniales sobre el Agente.
- **«Licenciatario»:** la persona natural o jurídica que tiene una licencia vigente de SubNetFlow otorgada por el Titular, y el personal y los contratistas que actúan por su cuenta.
- **«Nodo»:** cada servidor del Licenciatario donde se instala el Agente.

## 2. Naturaleza y protección

El Agente es una obra protegida por el régimen de derecho de autor colombiano y andino, en particular la Ley 23 de 1982, la Decisión Andina 351 de 1993 y el Decreto 1360 de 1989, que reconoce el soporte lógico como obra literaria, y por los tratados internacionales aplicables.

## 3. Licencia de uso

Mientras tenga una licencia vigente de SubNetFlow, el Titular concede al Licenciatario un derecho **no exclusivo, intransferible, gratuito y revocable** para:

1. descargar el Agente de su repositorio oficial e instalarlo y ejecutarlo en sus Nodos, **solo para enviar información a una instalación de SubNetFlow licenciada**;
2. leer y revisar el código fuente para evaluar su seguridad y su funcionamiento;
3. modificar su copia **solo** cuando sea indispensable para operarlo en sus propios Nodos (por ejemplo, la ruta de una CA propia), sin distribuir la versión modificada.

El derecho termina en forma automática cuando termine la licencia de SubNetFlow. En ese momento el Licenciatario debe desinstalar el Agente de sus Nodos.

## 4. Reserva de derechos y prohibiciones

Todo derecho que no se conceda de forma expresa y por escrito queda reservado al Titular. Salvo autorización escrita del Titular, **queda prohibido:**

1. usar el Agente con un sistema distinto de una instalación licenciada de SubNetFlow, o reimplementar el protocolo `snf-pulse-v1` para un producto que compita con SubNetFlow;
2. copiar, publicar, distribuir, vender, sublicenciar u ofrecer el Agente, modificado o no, a terceros, incluso como parte de otro producto o servicio;
3. crear obras derivadas para distribuirlas;
4. eliminar u ocultar los avisos de autoría y de derechos reservados;
5. usar el Agente para obtener información de Nodos o de sedes sobre los que el Licenciatario no tenga autorización;
6. eludir sus mecanismos de autenticación, cifrado o aislamiento por sede;
7. divulgar vulnerabilidades del Agente sin seguir la política de divulgación coordinada de `SECURITY.md`.

## 5. Datos

1. **La información de los Nodos es del Licenciatario.** El Agente solo la envía a la instalación de SubNetFlow que el Licenciatario configura (`SNF_URL`) y a ningún otro destino. No envía telemetría al Titular.
2. El Licenciatario es responsable de contar con autorización para documentar los Nodos donde lo instala y de la custodia del token de cada sede.

## 6. Componentes de terceros

El Agente usa Python 3 y la biblioteca `cryptography` (licencias Apache 2.0 / BSD) que el Licenciatario instala desde los repositorios de su sistema. No se distribuyen con el Agente y se rigen por sus propias licencias.

## 7. Ausencia de garantías y límite de responsabilidad

El Agente se entrega **«tal como está»**, sin garantías de ningún tipo, expresas o implícitas, en la máxima medida que permita la ley aplicable. El Titular no responde por daños indirectos, lucro cesante, pérdida de datos o interrupción del servicio derivados del uso del Agente. Las garantías y la responsabilidad que se pacten en el Contrato de Licencia de SubNetFlow prevalecen sobre esta sección en lo que la contradigan.

## 8. Ley aplicable

Este documento se rige por las leyes de la República de Colombia. Las controversias se someterán a los jueces competentes de Envigado, Antioquia, salvo pacto distinto en el Contrato de Licencia.

## 9. Contacto

Licenciamiento y autorizaciones: **andresebr644@gmail.com**.
