# Proposal: Acceso por SSO con alta controlada

Fuentes: `apps/api/app/auth.py` · `apps/api/app/services/clerk_sync.py` · `apps/web/components/organisms/AuthProvider/ClerkApiBridge.tsx` · `db/01_schema.sql` (tabla `users`) · `openspec/changes/integracion-clerk-auth/design.md` §9.

## Why

Encender SSO de Google y Microsoft en el panel de Clerk son quince minutos y no
requiere código. **El problema es lo que pasa el minuto dieciséis.**

Hoy, una persona que entra con Google y no está dada de alta recorre este
camino, verificado leyéndolo entero:

| Paso | Qué ocurre |
|---|---|
| 1 | Clerk la autentica y crea el usuario con `public_metadata` vacío |
| 2 | El webhook `user.created` exige `tenant_id` en ese metadata y responde **400**. No se crea fila |
| 3 | El middleware ve una sesión válida y la deja entrar al tablero |
| 4 | El token que emite el template **no lleva `tenant_id`**: no se puede inyectar lo que no existe |
| 5 | La API responde **401** a todas las llamadas |
| 6 | El puente de Clerk ve la sesión viva y **deliberadamente no redirige**, para no armar un bucle |

**Resultado: un tablero vacío, permanente, sin ninguna explicación.**

El paso 6 no es un defecto. Evita un bucle real y está bien resuelto. Lo que
falla es el supuesto con el que se escribió: que ese estado significaba *"el JWT
Template está mal configurado"* —un error de desarrollo, visible solo para
nosotros— y no *"esta persona no pertenece a ninguna empresa"*, que con SSO
encendido pasa a ser un caso **normal y frecuente**.

Y hay algo que hoy hace de red de contención por accidente: el registro público
sigue abierto. Cualquiera con un Gmail puede crear una cuenta. Que después no
vea nada es la única razón por la que eso no ha sido un problema.

## What Changes

1. **El registro público se cierra.** SSO queda como forma de **ingresar**, no
   de registrarse. Solo entra quien un Admin Empresa dio de alta.
2. **"Autenticado sin empresa" pasa a ser un estado con nombre**, distinto de
   "no pude verificar tu sesión", y se explica en pantalla.
3. **Se habilitan Microsoft y Google** en el panel de Clerk.

## Qué exige del resto del sistema

| Área | Qué necesita | Quién |
|---|---|---|
| Panel de Clerk | Desactivar el registro público | Equipo |
| Panel de Clerk | Conexión SSO de Microsoft, con App Registration en Azure | Equipo |
| Panel de Clerk | Conexión SSO de Google, con OAuth Client en Google Cloud | Equipo |
| `apps/api` | Separar "token ilegible" de "token válido sin empresa" | Este cambio |
| `apps/web` | Pantalla para el estado sin empresa, con cierre de sesión disponible | Este cambio |
| `apps/web` | Retirar la pantalla de registro propio | Este cambio |
| `credenciales-de-acceso` | Es quien construye el alta por invitación. **Sin ese cambio, dar de alta sigue siendo un INSERT a mano** | Otro cambio |
| Documentación | El modo sin Clerk no cambia: `.env` vacío sigue dando DevRoleSwitcher | Este cambio |

## Lo que este cambio no hace

- **No construye la invitación por correo.** Eso es `credenciales-de-acceso`
  Fase 2, hoy en 0 de 44 tareas. Este cambio deja el hueco **visible y
  explicado**; no lo llena.
- **No decide permisos.** Qué puede hacer alguien dentro de su empresa sigue en
  `sistema-actores-roles-rbac`.
- **No toca el acceso del Cliente Invitado**, que no pasa por Clerk.

## Decisiones que requiere el equipo

- [x] **¿Se cierra el registro público?** **Sí**, decidido el 12-ago-2026. SSO
      es forma de ingresar, no de registrarse.
- [ ] **¿Microsoft y Google, o solo Microsoft?** RF-05 marca Microsoft como
      prioridad MVP y Google como secundario. Habilitar los dos duplica la
      superficie de configuración; el código es el mismo.
- [ ] **¿SSO con cuentas personales o solo del directorio de la empresa?** Un
      Entra ID restringido a su directorio es más seguro pero puede rechazar a
      contratistas, que son parte del negocio de los Gestores.
- [ ] **¿Qué le decimos exactamente a quien queda sin empresa?** El texto debe
      ayudar sin revelar si esa empresa existe en el sistema.
- [ ] **¿Se avisa a alguien cuando esto pasa?** Alguien autenticándose sin alta
      puede ser un empleado nuevo a quien olvidaron dar de alta, o alguien que
      no debería estar. Hoy no queda registro de ninguno de los dos.
