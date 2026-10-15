# Specs del AI Service

Especificaciones escritas **antes** del código. Cada una define qué tiene que pasar y cómo se
comprueba; el código se escribe para que esas pruebas pasen, no al revés.

Base: el handoff **"Ambienta para el AI Service"** (API 0.1.0, 08/09/2026) y
[`../decisiones.md`](../decisiones.md). Donde una spec aplica una decisión, la cita como `D-xx`.

---

## Decisión: el servicio se escribe de cero, el material se corrige

| Qué | Cómo | Por qué |
|---|---|---|
| **El servicio** (`servicio/`) | De cero, como paquete Python | El código actual son scripts: rutas con `sys.path`, conexión nueva por consulta, variables leídas al importar, y un cliente escrito contra un contrato que no existe. Adaptarlo cuesta más que rehacerlo con tests desde el principio |
| **Las carpetas `00` a `05`** | Se corrigen, no se reescriben | Son el material de las sesiones y las guías las citan línea por línea. Se arreglan los defectos que enseñan un comportamiento equivocado (SPEC-00) y cada README apunta a su equivalente en el servicio |
| **La lógica que ya está bien** | Se porta con tests | La fusión RRF, la detección de citas, el partido de artículos largos y los guardrails pasan al paquete con sus pruebas |

El servicio vive en este repositorio mientras se construye. El destino final es
`apps/ai-service/` del monorepo de Ambienta, reemplazando el stub de TypeScript; la estructura
del paquete está pensada para moverse entera.

---

## Índice

| Spec | Qué define | Depende de | Sesión |
|---|---|---|---|
| [SPEC-00](SPEC-00-correcciones-material.md) | Los cinco defectos del material actual | — | 3 |
| [SPEC-01](SPEC-01-cliente-backend.md) | El cliente contra la API real | — | 3 |
| [SPEC-02](SPEC-02-identidad.md) | Token, empresa, usuario y modo desarrollo | 01 | 3 |
| [SPEC-03](SPEC-03-base-conocimiento.md) | La base del AI Service y su aislamiento | — | 3 |
| [SPEC-04](SPEC-04-sincronizacion-catalogo.md) | Traer el catálogo y mantenerlo al día | 01, 03 | 3 |
| [SPEC-05](SPEC-05-recuperacion.md) | Buscar: exacta, por palabras, semántica, con vigencia | 03, 04 | 4 |
| [SPEC-06](SPEC-06-agente.md) | El grafo, las herramientas y la abstención | 01, 02, 05 | 6 |
| [SPEC-07](SPEC-07-consulta-y-persistencia.md) | `POST /consulta` de punta a punta | 02, 06 | 6 |
| [SPEC-08](SPEC-08-evaluacion.md) | Medir recuperación, respuesta y abstención | 05, 06 | 5 |
| [SPEC-09](SPEC-09-operacion.md) | Configuración, contenedor, trazas y CI | todas | 5 |
| [`contrato/ai-service.openapi.yaml`](contrato/ai-service.openapi.yaml) | Lo que el AI Service expone | — | 2 |

El orden de trabajo, las fases y lo que falta decidir están en [`plan.md`](plan.md).

---

## Cómo se lee una spec

Todas tienen la misma forma:

1. **Objetivo**: una frase.
2. **Alcance** y **fuera de alcance**: lo que no está escrito acá no se construye.
3. **Reglas**: lo que no se negocia, con la decisión de la que sale.
4. **Interfaz**: firmas, tablas o endpoints.
5. **Criterios de aceptación** en Gherkin. Cada escenario se vuelve una prueba con el mismo
   nombre.
6. **Pruebas**: dónde vive cada escenario y qué necesita para correr.

Una spec está **terminada** cuando todos sus escenarios tienen prueba, las pruebas pasan en CI
y la spec no se tuvo que cambiar para que pasaran. Si hubo que cambiarla, el cambio se discute
antes, no después.
