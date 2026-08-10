## Context

Lo que ya existe y condiciona todo lo que sigue:

- **La sincronización con Clerk es de una sola vía.** `clerk_sync.py` traduce
  eventos entrantes a filas de `users`. No hay una sola llamada saliente en el
  repositorio. `CLERK_SECRET_KEY` está en el entorno del servicio `web`
  (la usa `clerkMiddleware`), no en el de la API.
- **`users` ya tiene las columnas que hacen falta**: `rut_tax_id varchar(32)`,
  `password_hash varchar(255)` y `clerk_id text`, todas vacías hoy.
  `email` es `citext` con UNIQUE global; `clerk_id` tiene UNIQUE.
- **`user_type`** admite `platform_admin`, `tenant_admin`, `internal`, `guest`,
  `manager` por CHECK. El invitado ya tiene su tipo: `guest`.
- **`lib/rut.ts`** tiene el cálculo del dígito verificador módulo 11, pero solo
  para *generar* RUTs simulados. No hay función que *valide* uno escrito.
- **El invitado ya está contenido en el frontend**: `ClienteInvitadoGate` lo
  saca de cualquier pantalla de negocio. Es solo UX; la API no lo bloquea.

Restricción dura, verificada contra la instancia real el 10-ago-2026:

| Formato probado | Resultado de Clerk |
|---|---|
| `12.345.678-9` | `Username can only contain letters, numbers and - or _` |
| `12345678-9` | `Username must contain one non-number character` |
| `123456789` | `Username must contain one non-number character` |
| `12345678-K` | Aceptado |
| `rut12345678-9` | Aceptado |

Un RUT es todo dígitos salvo cuando el verificador es K, así que el RUT crudo
funciona en 1 de cada 11 casos. No sirve.

## Goals / Non-Goals

**Goals:**
- Que el `tenant_id` de un usuario sea consecuencia de quién lo invitó, no de
  que alguien lo copie a mano en el dashboard de Clerk.
- Que un usuario interno pueda entrar con RUT sin perder el ingreso por SSO.
- Que las credenciales del Cliente Invitado existan de verdad, con vigencia y
  alcance verificables del lado del servidor.
- Que quede una comprobación automatizable contra la instancia real de Clerk.

**Non-Goals:**
- Recuperación de contraseña (el análisis lo dejó fuera, Sección A punto 24).
- MFA.
- Que una persona pertenezca a más de un tenant. `users.tenant_id` es una sola
  columna; cambiarlo es otro cambio (ver decisión abierta #3 del proposal).
- Reemplazar el ingreso por correo. Se agrega una vía, no se saca ninguna.

## Decisions

### D1. El RUT viaja como `username` de Clerk, con prefijo

`rut` + dígitos sin puntos + `-` + verificador en minúscula: `rut12345678-9`.
La pantalla lo antepone y lo quita; el usuario nunca lo escribe ni lo ve.

**Por qué el prefijo y no el RUT crudo.** Porque Clerk lo rechaza (tabla
arriba). Un prefijo fijo garantiza el carácter no numérico en los 11 casos, y
además evita colisiones con cualquier otro esquema de username que se adopte
después.

**Por qué `username` y no una clave propia en nuestra base.** `users` ya tiene
`password_hash`, así que técnicamente podríamos autenticar nosotros. Se
descarta: significaría dos almacenes de contraseñas, dos políticas de robustez,
dos lugares donde revocar una sesión, y emitir tokens propios — exactamente lo
que ADR-006 sacó de la API. **Lo que se pierde:** quedamos atados al formato de
username de Clerk, que ya nos obligó al prefijo y podría cambiar. Se acota
porque la normalización vive en una sola función.

**Por qué formulario propio y no `<SignIn />`.** El componente prearmado no
permite transformar el identificador antes de enviarlo, y necesitamos
anteponer el prefijo. La pestaña de RUT usa el flujo programático; la de correo
puede seguir con el componente prearmado.

### D2. El Cliente Invitado NO es una cuenta de Clerk

Sus credenciales viven en nuestra base, en su propia tabla, con vigencia.

**Por qué.** RF-02 dice que el invitado no necesita cuenta. Crear una identidad
en Clerk por cada cliente que manda un ticket contradice el requisito, mezcla
en el mismo directorio a los empleados y a terceros ocasionales, y Clerk cobra
por usuario activo — el volumen de invitados es, por diseño, el más alto y el
menos valioso de mantener.

**Lo que se pierde:** dos emisores de credenciales en el sistema, que es justo
lo que ADR-006 quiso evitar. Se acota con D3: el token del invitado no abre
ningún endpoint de negocio, así que la superficie donde importa que la
identidad sea fuerte sigue teniendo un solo emisor.

**Alternativa descartada:** un solo usuario de Clerk compartido por todos los
invitados de un tenant. Más barato, pero hace imposible que un invitado vea
solo sus propias solicitudes, que es un requisito explícito.

### D3. El acceso del invitado es un alcance, no un rol

El token del invitado no se valida en `get_current_user` junto al de Clerk.
Los endpoints que el invitado puede tocar dependen de una función distinta.

**Por qué.** Si ambos caminos desembocaran en el mismo `CurrentUser`, cada uno
de los 95 endpoints tendría que preguntarse si quien llama es un invitado, y
basta olvidarlo en uno para filtrar datos del tenant a un tercero. Con
dependencias separadas, el default es negar: un endpoint de negocio no acepta
credencial de invitado porque ni siquiera sabe leerla.

**Lo que se pierde:** dos caminos de autenticación en `deps.py` en vez de uno.
Es el precio de que el error por omisión sea seguro.

### D4. La invitación crea primero en Clerk y después en la base

**Por qué en ese orden.** Si primero se crea la fila y Clerk falla, queda una
persona en la base que no puede entrar nunca — el estado exacto que este cambio
viene a eliminar. Al revés, si Clerk crea la invitación y falla nuestra fila,
la persona entra y el webhook `user.created` la crea con el `tenant_id` que
Clerk ya tiene en `public_metadata`. El sistema se repara solo.

**Lo que se pierde:** una invitación de Clerk huérfana si el fallo es total.
Es basura visible en el dashboard, no un usuario roto.

### D5. El RUT se guarda también en `users.rut_tax_id`

Duplicado respecto al `username` de Clerk, a propósito.

**Por qué.** El RUT es dato de negocio, no solo credencial: aparece en informes
y en el perfil, y tiene que poder consultarse sin llamar a Clerk en cada
pantalla. **Lo que se pierde:** dos copias que pueden divergir. Clerk manda; el
webhook `user.updated` reescribe la nuestra.

### D6. Comprobación contra la instancia real como parte del entregable

Un script que, con la clave secreta, emite un token, lo manda a la API y
verifica que responde 200 y que el claim viaje. Corre a mano antes de publicar
y como job programado con secretos.

**Por qué es parte de esto y no una mejora futura.** Los 190 tests del frontend
y los 57 de la API estuvieron en verde mientras la aplicación estaba
completamente rota con Clerk real. CI corre sin Clerk y todo lo del proveedor
está simulado, así que ningún test nuestro podía desmentir lo que creíamos del
proveedor. Este cambio agranda esa superficie.

**Lo que se pierde:** una comprobación que depende de un servicio externo y de
secretos, y que por eso no puede bloquear cada PR. Va aparte del CI normal.

## Risks / Trade-offs

**El RUT es global en Clerk, no por empresa.** Un contratista que trabaje para
dos empresas del sistema no puede tener el mismo RUT en ambas. Es la decisión
abierta #3 del proposal y **no se resuelve acá**: `users.tenant_id` es una sola
columna. Si el equipo decide que ese caso importa, este diseño hay que
revisarlo antes de implementarlo.

**Habilitar `username` cambia también el registro.** Si el registro público
sigue abierto, cualquiera puede reclamar un RUT que no es suyo — nada valida
contra el Registro Civil. Refuerza cerrar el registro público (decisión abierta
#4 del cambio de Clerk, todavía sin resolver).

**RBAC.** Invitar debe exigir Admin Empresa, y hoy `get_tenant_db` valida
empresa, no rol. Este cambio necesita al menos esa verificación puntual, que
pertenece a `sistema-actores-roles-rbac` — 0 de 33 tareas y sin aprobar. Se
implementa acá lo mínimo para no dejar el endpoint abierto, sabiendo que se
reemplazará.

**La migración necesita su propia política RLS y sus GRANT.** El bucle de
políticas y el `GRANT ON ALL TABLES` de `01_schema.sql` corren una sola vez.
Una tabla nacida en una migración no los hereda y queda visible entre empresas.
Ya pasó.

**Sin webhook en local.** Clerk no alcanza `localhost:8000`, así que el ciclo
invitación → alta → webhook no se puede probar entero en desarrollo. Hace falta
un túnel o esperar al VPS. La parte saliente sí es probable en local.
