# SPEC-01 · Cliente del backend

**Objetivo.** Un único módulo que habla con la API de Ambienta tal como existe, y que ningún otro
módulo del servicio tenga que saber cómo pagina, reintenta o se autentica.

## Alcance
Lectura de: `/me`, catálogo (normas, versiones, artículos), normativa propia, obligaciones,
documentos (listado, vinculados, versiones, enlace de descarga), `/buscar/`, `/historial/`,
`/comentarios/`. Escritura de: conversaciones y mensajes del chatbot.

## Fuera de alcance
- Cualquier otra escritura en el backend (decisión abierta F del plan).
- Descargar y parsear archivos: el cliente devuelve el enlace y el checksum; bajarlo es de
  quien lo necesite.

## Reglas

| Regla | De dónde sale |
|---|---|
| El token se fija al construir el cliente. Ningún método recibe `tenant_id` | D-12 |
| Los modelos de respuesta se **generan** desde el `openapi.json` del backend; no se escriben a mano | Un cambio de contrato tiene que romper el build |
| Se pagina mientras `X-Has-More: true`, avanzando `skip` en `limit`. Nunca se deduce el final por el tamaño de la página | Handoff §3 |
| `limit` máximo 500. Pedir más es un error de programación, no algo a recortar | Handoff §3 (422) |
| `updated_since` recibe el `updated_at` **máximo visto**, nunca la hora local | Handoff §3 |
| 5xx y errores de red: reintentar 3 veces con espera 1, 2, 4 s. 4xx: nunca. 503 de descarga: nunca (es configuración) | Handoff §3 y §00 |
| Un 404 o 422 no se interpreta como "es de otra empresa": se trata como "no existe" | Handoff §3 |
| Modo desarrollo: si el servicio corre sin Clerk, manda `X-Tenant-Id` en vez de `Authorization` | Handoff §2 |
| Timeout por llamada configurable, 20 s por defecto | — |

## Interfaz

```python
class ClienteBackend:
    @classmethod
    def con_token(cls, base_url: str, token: str) -> "ClienteBackend": ...
    @classmethod
    def modo_desarrollo(cls, base_url: str, tenant_id: UUID) -> "ClienteBackend": ...

    # identidad
    async def yo(self) -> Me

    # catálogo público
    def normas(self, *, updated_since: datetime | None = None, tipo: str | None = None) -> AsyncIterator[Norma]
    async def versiones(self, norm_id: UUID) -> list[VersionNorma]
    async def articulos(self, norm_id: UUID, *, vigente_el: date | None = None) -> list[Articulo]

    # de la empresa
    def normativa_propia(self) -> AsyncIterator[Norma]
    async def articulos_propios(self, norma_id: UUID) -> list[Articulo]
    def obligaciones(self, **filtros) -> AsyncIterator[Obligacion]
    def documentos(self, *, updated_since: datetime | None = None) -> AsyncIterator[Documento]
    async def documentos_vinculados(self, entity_type: str, entity_id: UUID) -> list[Documento]
    async def enlace_descarga(self, document_id: UUID, version_id: UUID) -> EnlaceDescarga
    async def buscar(self, q: str) -> ResultadoBusqueda
    async def historial(self, entity_type: str, entity_id: UUID) -> Historial
    async def comentarios(self, entity_type: str, entity_id: UUID) -> list[Comentario]

    # chatbot
    async def abrir_conversacion(self, user_id: UUID, titulo: str) -> Conversacion
    async def mensajes(self, conversation_id: UUID) -> list[Mensaje]
    async def guardar_mensaje(self, conversation_id: UUID, mensaje: MensajeNuevo) -> Mensaje
```

Errores propios, para que quien llama no tenga que mirar códigos HTTP:

| Excepción | Cuándo |
|---|---|
| `SinAutenticar` | 401 |
| `SinPermiso(permiso)` | 403; lleva el permiso que nombra el mensaje |
| `NoEncontrado` | 404 |
| `PeticionInvalida(detalle)` | 422 |
| `EstadoNoAdmite(detalle)` | 409 |
| `AlmacenamientoNoConfigurado` | 503 en descarga |
| `BackendCaido` | 5xx o red, tras agotar reintentos |

## Criterios de aceptación

```gherkin
# language: es
Característica: El cliente habla con la API real

  Escenario: Paginar hasta que el backend diga que no hay más
    Dado un backend con 24 normas
    Cuando se recorren las normas con limit 10
    Entonces se hacen 3 peticiones con skip 0, 10 y 20
    Y se obtienen 24 normas
    Y la tercera respuesta trae "X-Has-More: false"

  Escenario: Una página llena no significa que haya más
    Dado un backend con exactamente 10 normas
    Cuando se recorren las normas con limit 10
    Entonces se hace una sola petición

  Escenario: Sincronización incremental con el máximo visto
    Dado que la última sincronización vio updated_at máximo "2026-09-08T12:00:00Z"
    Cuando se piden las normas modificadas
    Entonces la petición lleva updated_since=2026-09-08T12:00:00Z
    Y no lleva la hora local de la máquina

  Escenario: Un 4xx no se reintenta
    Dado un backend que responde 403 "Falta el permiso obligation.read."
    Cuando se piden las obligaciones
    Entonces se hace una sola petición
    Y se lanza SinPermiso con permiso "obligation.read"

  Escenario: Un 5xx se reintenta con espera creciente
    Dado un backend que responde 502 dos veces y después 200
    Cuando se pide /me
    Entonces se hacen 3 peticiones
    Y las esperas fueron de 1 y 2 segundos

  Escenario: El 503 de descarga no se reintenta
    Dado un backend sin almacenamiento configurado
    Cuando se pide el enlace de descarga de un documento
    Entonces se hace una sola petición
    Y se lanza AlmacenamientoNoConfigurado

  Escenario: El enlace y su checksum vienen juntos
    Cuando se pide el enlace de descarga de una versión
    Entonces el resultado trae url, expires_in y checksum_sha256 de la misma respuesta

  Escenario: Modo desarrollo
    Dado un cliente construido en modo desarrollo con el tenant "A"
    Cuando se pide /me
    Entonces la petición lleva "X-Tenant-Id: A"
    Y no lleva cabecera Authorization

  Escenario: Ningún método acepta la empresa
    Entonces ningún método público de ClienteBackend tiene un parámetro tenant_id ni empresa_id
```

## Pruebas
- **Unitarias** con `respx` simulando la API: todos los escenarios salvo el último.
- **Estructural**: el último escenario inspecciona las firmas con `inspect`.
- **Contrato**: las respuestas simuladas se validan contra los modelos generados; si el
  backend cambia un campo, fallan.
- **Integración** (marcada, corre contra el compose de Ambienta): la secuencia mínima del
  handoff §1 completa.

## Implementación (20/09/2026)

Implementado en `servicio/src/ambienta_ia/backend/`. Pruebas: `tests/unit/test_cliente_backend.py`.

Diferencias con lo escrito arriba:
- `obligaciones()` no recibe filtros: no están confirmados los nombres de los parámetros del
  backend, así que el filtro por estado y vencimiento lo hace la herramienta del agente.
- Se agregaron `norma()`, `conversacion()` y `versiones_documento()`.
- Los modelos están escritos a mano desde el spec del 02/09 y el handoff, con `extra="allow"`.
  Se regeneran con `datamodel-codegen` cuando llegue el `openapi.json` del 08/09.
- Si un listado no trae `X-Has-More`, se toma como no paginado (la respuesta está completa).

## Contra el backend real (21/09/2026)

Ver [`prueba-contra-ambienta/`](../prueba-contra-ambienta/README.md).
- Se verificó contra el `openapi.json` real con pruebas de contrato (`servicio/tests/contrato/`,
  55 chequeos): detectan los dos supuestos que estaban mal (`NormaPropiaRead` sin `updated_at`;
  el estado de una revisión es `lifecycle_status`).
- Nueva: `articulos_propios()` usa `/compliance/normativa-propia/{id}/articulos`.
- Algunos 403 traen `detail` como objeto (`{"codigo", "mensaje"}`); se leen los dos.
