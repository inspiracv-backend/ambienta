# SPEC-02 · Identidad: token, empresa y usuario

**Objetivo.** Que cada consulta al AI Service sepa con certeza quién pregunta y de qué empresa,
sin que ese dato pueda venir de otro lado que un token verificado.

## Alcance
- Validar el JWT de Clerk que llega al AI Service.
- Reenviar ese mismo token al backend.
- Resolver el UUID interno del usuario con `/me`.
- Modo desarrollo con las mismas reglas que el backend.

## Fuera de alcance
- Emitir tokens, gestionar usuarios o permisos: es de Clerk y del backend.
- La cuenta de servicio para escribir mensajes (decisión del handoff §9: se usa la sesión de
  la persona).

## Reglas

| Regla | De dónde sale |
|---|---|
| La empresa sale **solo** del claim `tenant_id` del JWT verificado | D-12, handoff §2 |
| Con `CLERK_JWKS_URL` configurada, `X-Tenant-Id` se ignora por completo. Sin ella, se acepta `X-Tenant-Id` y no hay usuario | Igual que el backend: una sola variable gobierna los dos modos |
| El token de la persona se reenvía al backend en cada llamada. El AI Service no tiene credenciales propias para leer datos de una empresa | Handoff §9, primera opción |
| El `user_id` para abrir conversaciones es el UUID que devuelve `/me`, nunca el `sub` del JWT (`user_xxx`) | Handoff §1 |
| `/me` se consulta una vez por petición al AI Service y su resultado viaja en el contexto de la petición | — |
| Los `permisos` de `/me` deciden qué herramientas recibe el agente: sin `obligation.read` no hay herramienta de obligaciones | Handoff §5: consultar permisos antes de ofrecer una acción |
| Sin `chatbot.use` la consulta se rechaza con 403 antes de llamar al modelo | Un mensaje sin poder guardarse es una conversación que no existe |
| Toda lista vacía inesperada del backend se registra con el `tenant_id` de la sesión | Handoff §3: es el síntoma de un tenant equivocado, no de falta de datos |
| La cuenta `servicio_lectura` se usa **solo** para sincronizar el catálogo público | Lee una empresa y no escribe; el catálogo es igual para todas |

## Interfaz

```python
@dataclass(frozen=True)
class Sesion:
    token: str | None           # None en modo desarrollo
    tenant_id: UUID
    usuario_id: UUID | None     # None en modo desarrollo
    permisos: frozenset[str]
    modo_desarrollo: bool

async def sesion_desde_peticion(request: Request) -> Sesion   # dependencia de FastAPI
```

| Situación | Respuesta del AI Service |
|---|---|
| Sin token (con Clerk activo) | 401 |
| Firma inválida o token vencido | 401 |
| Token válido sin claim `tenant_id` | 403, `"La cuenta no tiene empresa asignada"` |
| Sin `chatbot.use` | 403, nombrando el permiso |
| Modo desarrollo sin `X-Tenant-Id` | 401 |

## Criterios de aceptación

```gherkin
# language: es
Característica: La empresa sale del token y de ningún otro lado

  Escenario: Token válido
    Dado Clerk configurado
    Y un JWT firmado con tenant_id "A" y sub "user_123"
    Y /me devuelve el usuario con UUID "U1" y el permiso "chatbot.use"
    Cuando llega una consulta con ese token
    Entonces la sesión tiene tenant_id "A" y usuario_id "U1"
    Y el backend recibe el mismo token en Authorization

  Escenario: Con Clerk activo, X-Tenant-Id no cambia la empresa
    Dado Clerk configurado
    Y un JWT firmado con tenant_id "A"
    Cuando llega una consulta con ese token y "X-Tenant-Id: B"
    Entonces la sesión tiene tenant_id "A"

  Escenario: Token sin tenant_id
    Dado Clerk configurado
    Y un JWT firmado sin el claim tenant_id
    Cuando llega una consulta
    Entonces la respuesta es 403
    Y no se llamó al modelo

  Escenario: Sin permiso para el chatbot
    Dado un usuario sin "chatbot.use"
    Cuando llega una consulta
    Entonces la respuesta es 403 y menciona "chatbot.use"
    Y no se llamó al modelo

  Escenario: Modo desarrollo
    Dado Clerk sin configurar
    Cuando llega una consulta con "X-Tenant-Id: A"
    Entonces la sesión tiene tenant_id "A", usuario_id nulo y modo_desarrollo verdadero

  Escenario: Las herramientas siguen a los permisos
    Dado un usuario con "catalog.read" y sin "obligation.read"
    Cuando se construye el agente para esa sesión
    Entonces el agente no tiene la herramienta de obligaciones

  Escenario: Lista vacía inesperada queda registrada
    Dado que /obligations/ devuelve una lista vacía
    Cuando la herramienta de obligaciones termina
    Entonces el registro de la consulta incluye el tenant_id y el endpoint que vino vacío
```

## Pruebas
- **Unitarias**: JWKS local con una clave generada en la prueba; tokens firmados con y sin
  claim, vencidos y con firma ajena.
- **Integración** con el compose de Ambienta en modo desarrollo: los escenarios 5 y 6.
- **Staging** con Clerk real: los escenarios 1 y 2. No se da la fase 5 por cerrada sin esta
  corrida (ver riesgos en `plan.md`).

## Implementación (20/09/2026)

Implementado en `servicio/src/ambienta_ia/identidad.py`. Pruebas: `tests/integracion/test_api.py`
(JWT firmados con una clave generada en la prueba; firma ajena, sin `tenant_id`, sin permiso).

Diferencia con lo escrito arriba: en modo desarrollo `/me` devuelve `permisos: []` (se ve en
`ejemplos-de-respuesta.json` del backend). Tratarlo como "sin permisos" dejaría al agente sin
herramientas, así que **en modo desarrollo los permisos se consideran concedidos**, igual que
el backend, que tampoco los exige en ese modo.

## Contra el backend real (21/09/2026)

Ver [`prueba-contra-ambienta/`](../prueba-contra-ambienta/README.md).
- Probado con tokens firmados por un "Clerk local" contra el backend en modo producción: la
  sesión es la de la persona, con sus permisos reales de `/me`.
- `CLERK_ISSUER=""` exigía un claim `iss` y rechazaba todo: vacío ahora significa no validar el
  emisor, como en el backend.
