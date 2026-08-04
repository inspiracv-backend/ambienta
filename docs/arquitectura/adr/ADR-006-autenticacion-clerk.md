# ADR-006: Clerk como proveedor de autenticación

**Estado:** `Aceptado`
**Fecha:** 2026-08-03
**Decisores:** Fabrizzio Gomez, con recomendación del mentor técnico
**Categoría:** Arquitectura de software / Seguridad
**Reemplaza parcialmente:** la decisión de JWT propio del Análisis Funcional v1.7 (RF-05)

> **Nota de trazabilidad.** Un borrador previo de este mismo ADR, escrito el mismo día,
> favorecía Supabase Auth. Se revisó y cambió antes de escribir código. El motivo del
> cambio está documentado más abajo, en *"Por qué no Supabase"*, porque la razón importa:
> el argumento principal a favor de Supabase resultó no aplicar a nuestra arquitectura.

---

## Contexto

El Análisis Funcional v1.7 fijó autenticación con **JWT propio + SSO de Microsoft (prioritario) y Google**. Construir eso a mano implica implementar OAuth con dos proveedores, rotación de tokens, recuperación de clave y gestión de sesiones.

Se evaluaron tres proveedores gestionados: **Clerk**, **Firebase Auth** y **Supabase Auth**.

Un dato que reordena la comparación: **Ambienta es B2B con pocos usuarios por empresa**. No son cientos de miles de usuarios activos — son decenas por cliente. Con ese volumen los tres caben holgadamente en el tier gratuito, así que **el precio no es el criterio decisivo**. Lo que pesa es el encaje técnico.

---

## Decisión

Adoptar **Clerk** como proveedor de autenticación.

### Por qué

**Encaje con el frontend.** El frontend de Ambienta es Next.js con 13 secciones ya construidas. Clerk tiene la mejor integración del mercado con Next.js: componentes listos, hooks y middleware. Es el proveedor que menos fricción agrega a lo que ya existe.

**Su modelo de organizations mapea a nuestros tenants.** Ambienta es multi-tenant y Clerk trae esa primitiva de fábrica, incluyendo invitaciones y roles por organización. No reemplaza nuestro modelo — los 39 permisos y la sub-tenancy por contrato siguen siendo nuestros — pero cubre la capa de pertenencia.

**Trae MFA y passkeys incluidos**, sin trabajo adicional. Para un producto de cumplimiento vendido a industriales, poder ofrecer segundo factor sin construirlo es relevante.

### Por qué no Supabase

El argumento principal a su favor era la **integración nativa con Postgres y RLS**. Al revisarlo contra nuestra arquitectura concreta, esa ventaja **no aplica**:

- La integración de Supabase con RLS sirve cuando el cliente consulta Postgres directamente (vía PostgREST) y la base lee `auth.uid()` del token.
- Ambienta tiene **FastAPI en el medio**. La API decodifica el token, extrae el tenant y ejecuta `SET LOCAL ambienta.tenant_id`. Ese mecanismo es **agnóstico del proveedor** y ya está implementado en `apps/api/app/db.py`.

Dicho de otra forma: íbamos a pagar el costo de adoptar Supabase por una característica que nuestra arquitectura nunca iba a ejercer.

### Por qué no Firebase

El peor encaje de los tres. Sin historia con Postgres ni RLS, su multi-tenancy real exige Identity Platform, y arrastra el proyecto a GCP sin aportar nada que necesitemos.

---

## Consecuencias

### Positivas
- Se evita construir OAuth de Microsoft y Google desde cero
- La gestión de contraseñas, recuperación, sesiones, MFA y passkeys deja de ser código nuestro
- El frontend Next.js integra con muy poca fricción
- El modelo de RLS que ya funciona **no cambia**: sigue siendo `SET LOCAL ambienta.tenant_id` desde los claims del token

### Trade-offs
- **Lock-in.** Es el costo real de esta decisión. Clerk no es open source y no hay versión self-hosteable, así que migrar usuarios más adelante es caro. Ver mitigación abajo.
- **Residencia de datos.** La identidad (correo, nombre) queda en infraestructura de Clerk. Es una superficie chica — los datos sensibles de cumplimiento siguen en nuestra base — pero hay que firmar un DPA y documentarlo para RNF-01 (Ley 21.719).
- El equipo tiene que aprender el modelo de organizations de Clerk.

### Mitigación del lock-in

Vale la pena hacerlo desde el día uno, porque es barato ahora y caro después:

1. **Que el proveedor no se filtre al resto del código.** La validación del token y la extracción del tenant viven detrás de una sola dependencia de FastAPI. El resto de la API no sabe quién emite los tokens.
2. **La tabla `users` es nuestra fuente de verdad de negocio.** El `sub` del token de Clerk se usa como `users.id`, pero el tenant, el departamento y los permisos viven en nuestra base. Si mañana se cambia de proveedor, se migran credenciales, no el modelo de datos.

---

## Lo que NO resuelve el proveedor

Tres cosas siguen siendo trabajo propio, con Clerk o sin él:

1. **Acceso de cliente invitado con RUT y clave dinámica** (RF-01, RF-02, RF-07). Es un flujo a medida que ningún proveedor trae.
2. **La sub-tenancy por contrato** (RF-65, RF-66). Las organizations de Clerk cubren la pertenencia básica, no el modelo gestor → cliente.
3. **Los 39 permisos granulares del RBAC** (RF-08). Ya están modelados en la base.

Un proveedor ahorra la plomería de OAuth y contraseñas. Real, pero acotado — conviene no sobreestimarlo al planificar.

---

## Pendiente de verificar

1. **Calidad del SSO con Microsoft / Entra ID en Clerk.** RF-05 lo pone como prioritario, y es donde más varían los proveedores. Verificar antes de comprometerse.
2. **Precios actuales**, en la página oficial de Clerk. La comparación de origen tenía cifras de terceros que no se pudieron verificar.
3. **Cómo mapear organizations de Clerk a nuestros tenants**, y si conviene usarlas o mantener el tenant solo en nuestra base.
