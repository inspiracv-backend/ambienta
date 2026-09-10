# Por qué no se puede archivar ninguno de los 9 cambios

**Medido el 10-sep-2026, requisito por requisito contra el código.**

## El resultado, primero

**Cero de nueve.** Y no por burocracia: cada uno tiene al menos un requisito que
el sistema no cumple.

Esto contradice lo que decía el plan de cierre esa misma mañana —que siete se
podían archivar ya— y esa afirmación era mía. Salió de mirar la tabla de estado
del proyecto en vez de los deltas. **Es exactamente el error que el bloque F
existe para arreglar**, cometido al planificar el bloque F.

| Cambio | Reqs | Veredicto | Qué lo bloquea |
|---|---|---|---|
| `credenciales-de-acceso` | 3 | **Casi** | Los tres están implementados; **un escenario describe otro flujo** del que se construyó |
| `sistema-actores-roles-rbac` | 6 | No — 2 | El acotamiento de un rol a una planta **no se aplica**; no hay guarda que impida al Admin Global escribir datos de una empresa |
| `integracion-clerk-auth` | 8 | No — 1 | **Microsoft SSO**, que está fuera de la 1.0 por decisión |
| `acceso-por-sso` | 3 | No — 1 | El mismo requisito de Microsoft |
| `ingesta-normativa-bcn` | 4 | No — 2 | Las relaciones entre normas y la bitácora de sincronización: **tabla, modelo y schema existen; nadie escribe y nadie expone** |
| `matrices-ambientales-iso-14001` | 7 | No — 1 | La bandera de reversibilidad no existe — probablemente sobra el requisito |
| `escrituras-de-la-interfaz` | 3 | No — 2 | Seis campos se ofrecen editables sin poder guardarse; el motivo del rechazo no tiene formato estable |
| `hallazgos-auditoria-no-conformidades` | 8 | No | Bloqueado en **#57** |
| `modelo-de-tareas-del-plan-de-accion` | 6 | No | Las tareas no existen en el modelo (**#169**) |

---

## Lo grave: acotar un rol a una planta no acota nada

Es el hallazgo que justifica la auditoría entera, y **no se ve mirando la
pantalla** — al contrario, la pantalla afirma que sí funciona.

`user_roles.facility_id` y `department_id` existen desde el principio.
`alcance_del_usuario()` los resuelve. `GET /me` los devuelve en
`instalaciones`, `departamentos` y `acotado`, con un docstring que explica que
un alcance vacío significa «sin acotar» y no «ninguno».

**`alcance_del_usuario()` tiene un solo llamador: `/me`, que lo informa.**
Ninguna consulta de negocio filtra por instalación. Medido por la API con el rol
acotado a una sola planta:

| `GET /compliance/article-compliance` | filas |
|---|---|
| de su planta | 92 |
| **de las otras dos** | **172** |

**No es una fuga entre empresas.** RLS sigue siendo la única barrera entre
tenants y sigue firme. Esto es acotamiento *dentro* de una empresa, y el daño
está en otro lado: en lo que se puede prometer en una venta —«el encargado de
Calama sólo ve Calama»— y en lo que se contesta en una auditoría de accesos.

`apps/api/tests/test_alcance_de_rol.py` fija el estado real y **debe fallar** el
día que alguien lo implemente. Mismo criterio que las pruebas del catálogo RETC
incompleto: el hueco no se ve, así que necesita algo que lo sostenga por
escrito.

---

## El patrón, otra vez: escrito, probado, sin llamador

Tres de los nueve fallan por lo mismo, y es el patrón que este repositorio ya
documenta en `bcn.sincronizar()`, `control_documental.py` y
`equipos_sin_operador_habilitado()`:

| Qué existe | Qué falta |
|---|---|
| `alcance_del_usuario()` + `user_roles.facility_id` | que alguna consulta filtre |
| `NormSyncRun` (tabla + modelo) | que la sincronización la escriba, y una ruta que la lea |
| `LegalRelation` (tabla + modelo + schema) | que la sincronización las escriba, y una ruta que las lea |

En los tres casos la mitad cara está hecha. Y en los tres, **el spec afirma el
comportamiento completo**, así que archivarlo dejaría `openspec/specs/`
describiendo un sistema que no existe — que es literalmente lo contrario de para
qué sirve archivar.

---

## Los tres que necesitan una decisión, no código

### 1. Microsoft SSO bloquea dos cambios

`integracion-clerk-auth` y `acceso-por-sso` comparten el requisito *«iniciar
sesión con correo y contraseña, con Microsoft y con Google»*. Google funciona y
está verificado; Microsoft **no está configurado** y el plan de cierre lo pone
explícitamente fuera de la 1.0.

Las dos cosas no pueden ser ciertas a la vez. Hay que elegir:

- **Configurar Entra ID** (#92) y archivar los dos cambios completos, o
- **Bajar el requisito** a lo que la 1.0 sí ofrece, dejando Microsoft como un
  cambio propio y posterior.

La segunda es más honesta con lo que hay. La primera exige un registro en Entra
ID con tipo de cuenta *cualquier directorio + cuentas personales*: con «sólo
este directorio» ningún cliente puede entrar.

### 2. La bandera de reversibilidad de ISO 14001

El requisito pide *«mantener esta capacidad detrás de una bandera, de modo que
apagarla devuelva el comportamiento anterior»*. Era una precaución de
despliegue, la épica #28 cerró el 6-sep y la bandera nunca se construyó.

**Probablemente sobra el requisito, no falta la bandera.** Mantener para siempre
un interruptor que devuelva el sistema a antes de ISO 14001 es más deuda que
seguro. Pero quitarlo del spec es una decisión, no una corrección: lo escribió
alguien con un motivo.

### 3. El Admin Global y los datos de las empresas

El requisito dice que el rol de plataforma **no** puede modificar contenido de
negocio de un cliente. No hay ninguna guarda que lo impida: `_es_admin_global`
existe y se usa para lo contrario —gatear lo que **sólo** el Admin Global puede
hacer, como cambiar el RUT de una empresa—.

Hace falta decidir qué significa exactamente. Un `platform_admin` con
`tenant_id` en su token escribe como cualquiera; si no lo tiene, RLS ya lo frena
y el requisito se cumple solo. **Cuál de los dos es el diseño no está escrito en
ninguna parte.**

---

## El que casi se puede archivar

`credenciales-de-acceso` tiene sus tres requisitos implementados y bien
cubiertos por pruebas — invitación con `tenant_id` en `public_metadata`, clave
local con RUT y sus formatos, acceso de invitado acotado, temporal, revocable y
sin cruce entre empresas ni entre invitados.

Lo único que no calza es un escenario:

> **THEN** el sistema crea una invitación en el proveedor de identidad con la
> empresa A y el rol ya asociados
> **AND** crea la fila del usuario en la empresa A con estado `invited`

El sistema hace eso en **dos pasos**: `POST /users/` crea la fila y
`POST /users/{id}/invitacion` emite la invitación. Y la separación tiene un
motivo — la base exige departamento a los usuarios internos
(`ck_users_interno_con_departamento`), así que la fila necesita datos que la
invitación no pide.

El *motivo* del requisito se cumple: «que la empresa quede determinada por quien
invita y no por una configuración manual posterior». Lo que no calza es la
mecánica del escenario. Corregir el escenario antes de archivar es exactamente
lo que manda `CLAUDE.md` §1.2 —*«si el modelo real contradice la spec, se corrige
el `design.md` antes de seguir»*— pero conviene que lo confirme quien decidió el
flujo.

---

## Qué hacer con esto

En orden de lo que más destraba:

1. **Decidir sobre Microsoft SSO.** Destraba dos cambios de una.
2. **Confirmar el escenario de la invitación.** Destraba el tercero.
3. **Decidir si el acotamiento por planta entra en la 1.0.** Es el único hueco
   de los nueve que importa por sí mismo, más allá de archivar.
4. Escribir la bitácora de sincronización y las relaciones de la BCN, o bajar
   esos dos requisitos a lo que hay.
5. Los otros tres esperan a #57, a #169 y a que se terminen de conectar las seis
   escrituras que faltan.

**Lo que no hay que hacer es archivar igual.** Un spec que describe lo que no
existe es peor que no tener spec: el próximo cambio se escribe contra él.
