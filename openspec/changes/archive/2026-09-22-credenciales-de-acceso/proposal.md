# Credenciales de acceso

## Why

Hoy hay exactamente **una** forma de entrar a Ambienta: correo y clave (o SSO)
contra Clerk. El análisis funcional describe dos más, y ninguna existe.

**RF-06 (Sección N).** Un usuario que entró con Google o Microsoft puede
después fijarse una clave local y entrar con **RUT**. En Chile el RUT es el
identificador que la gente sabe de memoria; el correo corporativo no siempre.
En faena, además, no todo el mundo tiene cuenta de Google o Microsoft a mano.

**RF-01 / RF-02 / RF-07 (Sección A).** El Cliente Invitado accede con RUT y
clave dinámica, o por link público, **sin cuenta previa**. La pantalla existe
en `/acceso-invitado` y está entera simulada: `generateMockRut()` y
`generateDynamicPassword()` corren en el navegador, no se guardan en ninguna
parte y no autentican nada. Cualquiera que escriba cualquier cosa entra. Es la
puerta por la que se supone que entran los clientes y contratistas del tenant.

**Por qué ahora.** La integración con Clerk acaba de quedar funcionando de
punta a punta, así que este es el momento de cerrar el modelo de identidad
completo en vez de dejarlo a medias. Y hay un prerrequisito que ninguno de los
dos requisitos puede saltarse: **nada en el repositorio le habla a Clerk**. La
sincronización es de una sola vía (webhook Clerk → base). Sin la mitad
saliente, un Admin Empresa que invita a alguien crea una fila en la base de una
persona que no puede entrar nunca.

## What Changes

Tres piezas, en orden de dependencia.

**1. Cliente saliente hacia Clerk.** Un módulo en la API que llama a la
Backend API de Clerk. Habilita crear invitaciones con `public_metadata`
(`tenant_id` y `role`) ya puestos, de modo que el alta deje de depender de que
alguien copie el `tenant_id` a mano en el dashboard. Es el prerrequisito de la
pieza 2 y lo que convierte el `tenant_id` en consecuencia de un botón.

**2. RF-06 — clave local con RUT.** El RUT viaja como `username` de Clerk.
Requiere normalizar: **verificado contra la instancia real, Clerk rechaza un
RUT crudo** con `Username must contain one non-number character`. Un RUT es
todo dígitos salvo cuando el verificador es K (1 de cada 11). Se guarda con
prefijo, `rut12345678-9`, y la pantalla de ingreso lo antepone sin que el
usuario lo vea. Como el componente `<SignIn />` prearmado no puede transformar
lo que se escribe, la pestaña de RUT necesita formulario propio con
`useSignIn()`.

**3. RF-02/RF-07 — acceso de invitado real.** Las credenciales del invitado
dejan de generarse en el navegador y pasan a existir en la base, con vigencia
y alcance. **No se crea una cuenta de Clerk por invitado** (ver decisión
abierta #1).

Fuera de alcance: recuperación de contraseña (el análisis ya lo dejó fuera,
Sección A, punto 24) y MFA.

## Capabilities

### New Capabilities
- `credenciales-de-acceso`: cómo obtiene credenciales cada actor y qué puede
  hacer con ellas — invitación de usuarios internos, clave local con RUT, y
  acceso temporal del Cliente Invitado.

### Modified Capabilities
<!-- Ninguna. `dashboard` es el único spec vivo y no cambia su comportamiento. -->

## Impact

### Qué exige este cambio del resto del sistema

| Área | Qué se le exige | Bloqueante |
|---|---|---|
| Clerk (dashboard) | Habilitar **Username** como identificador de ingreso. Sin eso el RUT no es credencial válida | Sí, para RF-06 |
| Clerk (dashboard) | Decidir y aplicar el cierre del registro público (decisión abierta #4 del cambio de Clerk, aún sin resolver) | No, pero deja un hueco |
| `apps/api` | Módulo saliente nuevo + `CLERK_SECRET_KEY` en runtime. Hoy la clave está en el entorno pero no se usa desde la API | Sí |
| `db/` | Migración idempotente `db/NN_*.sql` con **su propia política RLS y sus GRANT** — el bucle de `01_schema` corre una sola vez | Sí |
| `packages/shared` | Esquemas Zod nuevos, con su gemelo Pydantic. El modelo se escribe dos veces y ya se desincronizó antes | Sí |
| `apps/web` | Formulario de ingreso propio: `<SignIn />` no admite transformar el identificador | Sí, para RF-06 |
| RBAC | Invitar usuarios debe exigir Admin Empresa. Hoy `get_tenant_db` valida empresa, no rol | Sí, y depende de `sistema-actores-roles-rbac`, que tiene 0 de 33 tareas y **no está aprobado** |
| CI | Corre sin Clerk. Nada de lo saliente queda cubierto por los tests actuales | No, pero ver abajo |

### Riesgo de método, no de código

Los 190 tests del frontend y los 57 de la API estuvieron en verde mientras la
aplicación estaba completamente rota con Clerk real. No fue casualidad: **CI
corre sin Clerk y todo lo del proveedor estaba simulado**. Un test con mock
verifica lo que uno cree que hace el proveedor, nunca lo que hace.

Este cambio agrega superficie contra Clerk, así que agranda exactamente ese
punto ciego. Incluye por eso un smoke test contra la instancia real como parte
del entregable, no como mejora futura.

## Decisiones abiertas

1. **¿El Cliente Invitado es una cuenta de Clerk o un token nuestro?**
   Recomendación: **token nuestro**. RF-02 dice literalmente que no necesita
   cuenta; crear una cuenta por cada cliente que manda un ticket contradice el
   requisito, ensucia el directorio de identidades y Clerk cobra por usuario
   activo. El costo de la alternativa es tener dos emisores de token, que es
   justo lo que ADR-006 quiso evitar — se acota dejando el token del invitado
   sin acceso a ningún endpoint de negocio. **Necesita firma del equipo.**

2. **¿Qué vigencia tiene el acceso del invitado?** El análisis dice "clave
   dinámica" sin plazo. Propuesta: 30 días, renovable con el mismo link.

3. **¿El RUT es único por tenant o global?** Un contratista puede trabajar para
   dos empresas del sistema. Como el `username` de Clerk es global, dos tenants
   no podrían tener el mismo RUT. Propuesta: aceptar la restricción y que la
   persona sea un solo usuario con acceso a dos tenants — pero eso **hoy no
   existe**: `users.tenant_id` es una sola columna, no una relación.

4. **¿Se migran los usuarios existentes?** Las 5 filas de demo no tienen
   `rut_tax_id`. Sin RUT no pueden usar RF-06 hasta que alguien lo cargue.
