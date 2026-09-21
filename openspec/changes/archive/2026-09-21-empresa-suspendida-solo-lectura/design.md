# Design: Una empresa suspendida queda en solo lectura

## 1. Dónde vive la guarda

En `exigir_permiso_de_la_ruta`, que ya se aplica como dependencia de cada router
de negocio, y **antes** del `if not clerk_configured: return user`.

**Por qué antes.** Las otras guardas de ese archivo dependen de quién es la
persona, y sin Clerk no hay de dónde sacarlo. Esta no: depende del estado de la
empresa, que se conoce igual con `X-Tenant-Id`. Ponerla después la dejaría
escrita, en verde y sin ejecutarse en toda la suite —la trampa que `CLAUDE.md`
ya documenta para la guarda del Admin Global—.

**Por qué no en `get_tenant_db`.** Esa dependencia también la usan lecturas,
tareas y el webhook; mezclar ahí una regla de escritura haría que cualquier
consulta nueva cargue con ella.

**Qué es escribir.** `POST`, `PUT`, `PATCH` y `DELETE`, por método, igual que
`METODOS_DE_LECTURA` en `permisos_de_rutas.py`. Se pierde la posibilidad de
permitir escrituras "inocuas" —marcar una notificación como leída—; a cambio no
hay una lista de excepciones que mantener, y una lista así es la que se desactualiza.

## 2. Qué empresa se mira

**La efectiva y la de la sesión**, las dos. La efectiva es la que se declara
para RLS —la del cliente, si un gestor actúa por él— y la de la sesión es la de
la persona. Si cualquiera de las dos está en solo lectura, no se escribe:

| quién | empresa efectiva | empresa de la sesión | escribe |
|---|---|---|---|
| usuario de una empresa suspendida | suspendida | suspendida | no |
| gestor activo, cliente suspendido | suspendida | activa | no |
| gestor suspendido, cliente activo | activa | suspendida | no |
| Admin Global reactivando una empresa | plataforma | plataforma | sí |

Mirar solo la efectiva dejaría escribir a un gestor suspendido a través de sus
clientes.

## 3. La respuesta

`403` con `{"codigo": "empresa_en_solo_lectura", "mensaje": ..., "estado": ...}`.
**Código propio y no `permiso_insuficiente`**: no le falta un permiso que alguien
pueda concederle dentro de la empresa, y mandarlo a pedirlo sería una pista
falsa. Mismo criterio que `plataforma_no_edita_contenido`.

## 4. Los avisos

`tareas/avisos.py::_empresas` deja fuera las empresas en solo lectura y el
informe cuenta cuántas quedaron en pausa. **No genera ni despacha**: la decisión
fue pausar los avisos, y generarlos sin mandarlos acumularía una cola que sale
entera el día de la reactivación.

Lo que se pierde: los avisos que ya estaban encolados al suspender salen al
reactivar, quizás tarde (pregunta abierta 1).

## 5. Estados

`ESTADOS_SOLO_LECTURA = {"suspended", "closed"}`, en un solo lugar y usado por
la guarda y por el cron. Dos listas separadas se desincronizan sin que nada falle.
