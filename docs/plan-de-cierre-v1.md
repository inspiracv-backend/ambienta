# Plan de cierre de la versión 1.0

**Actualizado el 10-sep-2026.** La tanda 1 se ejecutó, y al hacerlo **este
mismo plan resultó tener tres errores**, dos de ellos míos. Están corregidos
abajo y dichos, no borrados: un plan que se corrige en silencio es la misma
clase de documento que este archivo existe para evitar.

## Qué es esto, y qué no

Es el plan para dejar Ambienta en **versión 1.0 y listo para desplegar**.
Desplegar **no entra**: el MVP corre en local, no hay dominio, y pasar a
producción es una decisión posterior.

**Este archivo existe porque el plan vivía sólo en una conversación.** La
pregunta "¿en qué semana vamos?" no se podía contestar mirando el repositorio, y
eso es exactamente lo que este proyecto persigue en todo lo demás: estado que
sólo existe en la cabeza de alguien.

---

## 0. Qué pasó con la tanda 1 (10-sep)

| Ítem | Estado | Lo que apareció |
|---|---|---|
| A · `legal-matrix.addNorm` | **Hecho** | Conectar sólo la escritura era medio viaje: `/catalog/norms` no trae la normativa propia, así que la RCA desaparecía al recargar. Y faltaba un endpoint: los considerandos se escribían y **ninguna respuesta devolvía el texto** |
| B · `gestores.addContrato` | **Hecho** | El RUT del cliente no venía en la cartera y la tabla lo mostraba en blanco; los contactos salían como `0` |
| C · Pantalla de RBAC | **Ya estaba hecha** | `/usuarios` la abre desde hace tiempo. Tres documentos —éste incluido— decían que faltaba |
| — · `departamentos.updateTipo` | **Hecho** (no estaba en el plan) | `process_type` se podía **leer y no escribir**: la API respondía 200 y descartaba el campo |
| F · RF-109 | **Estaba mal clasificado.** Va a bloqueado | El proposal archivado de #73 ya lo decía: *«es una segunda barrera sobre un modelo que hoy no la tiene en ninguna tabla, y merecería su propia decisión»* |
| D · #72 captura de correos | **Estaba mal clasificado.** Va a bloqueado | No hay análisis funcional para RF-107, y capturar correo entrante necesita un dominio con MX — o sea infraestructura, y desplegar está fuera de la 1.0 |

**Y un defecto de aislamiento que apareció de paso:** `olvidar()` —la función que
deja una conexión sin empresa declarada— **no hacía nada**. Su `set_config` corría
en una transacción sin confirmar y el `ROLLBACK` del pool lo revertía. Medido: con
`olvidar()` y sin `olvidar()` la conexión siguiente veía exactamente lo mismo. La
prueba que lo cubría usaba un engine propio, así que nunca pasaba por el pool.

## 1. Lo que cambió desde el 7-sep

| Lo que decía | Lo que es hoy |
|---|---|
| "Queda D y F" | El **bloque E está cerrado** (#73–76) y **D está a medias**: el modelo y la API de normativa propia se cerraron el 8-sep |
| Suite de API: 1214 (medida el 4-sep) | **1352 en verde**, 12 saltadas — medido el 10-sep |
| Frontend: 653 (7-sep) | **700 en verde**, `tsc --noEmit` limpio — 10-sep |
| 10 escrituras del frontend bloqueadas | **Cuatro ya no lo están**, y una nunca lo estuvo. Ver §2 |
| — | El AI Service tiene documento de integración y contrato regenerado (9-sep) |

### Tres escrituras que el documento cree bloqueadas y ya no lo están

`docs/escrituras-del-frontend.md` las lista con causas que **se resolvieron
después de que se escribió esa tabla**. Es el mismo patrón que este repositorio
repite: el trabajo está hecho y nadie volvió a mirar.

| Escritura | La causa que figura | Por qué ya no aplica |
|---|---|---|
| `legal-matrix.addNorm` | "hay que decidir dónde vive la normativa propia" | **Decidido y construido** el 8-sep: `db/29` y `/compliance/normativa-propia` |
| `gestores.addContrato` | "la sub-tenancy no existe" | **El bloque C la cerró.** `POST /contracts/` y `/gestor/clientes` existen |
| `users.updatePermisos` | "falta el endpoint que administre las excepciones por usuario" | **El endpoint existe:** `GET`, `PUT` y `DELETE /users/{id}/permissions[/{codigo}]`, con `role.manage` |

**Y `users.updatePermisos` nunca estuvo bloqueada**: la pantalla existe y la
llama. O sea que el conteo era **30 de 39, no 29** — un número afirmado que
nadie volvió a medir, citado después como un hecho.

Con las tres conectadas el 10-sep más `departamentos.updateTipo`: **33 de 39**,
6 bloqueadas. Ese número no salió de correr el script otra vez, salió de revisar
las diez una por una contra el código.

---

## 2. Lo que falta, completo

### 2.1 Listo para hacer — no depende de nadie

**Queda uno.** La tanda 1 se ejecutó el 10-sep y lo demás salió de esta lista,
en las dos direcciones: tres se hicieron, uno ya estaba hecho, y **dos estaban
mal clasificados y se fueron a §2.2**.

| # | Qué | Tamaño | Estado |
|---|---|---|---|
| A | Conectar `legal-matrix.addNorm` | chico | ✅ 10-sep |
| B | Conectar `gestores.addContrato` | chico | ✅ 10-sep |
| C | Pantalla de administración de RBAC | mediano | ✅ **ya estaba hecha** |
| — | `departamentos.updateTipo` | chico | ✅ 10-sep, no estaba en el plan |
| **E** | **Bloque F** — archivar los 9 cambios OpenSpec y recorrer el sistema | mediano | **lo único que queda** |
| G | **#52** — portar `01_schema.sql` a migración versionada | mediano, riesgoso | va después de B3, o no va |

**Y eso cambia el orden de todo el plan.** El bloque F estaba puesto último con
el argumento de que archivar antes de terminar D y B3 significa archivar dos
veces. Sigue siendo cierto **para los cambios que D y B3 van a tocar** — y no
para los otros siete, que están estables desde hace semanas. Ver §3.

### 2.2 Bloqueado en una decisión de negocio

| # | Qué | Espera |
|---|---|---|
| H | **Bloque B3** (#38, #43, #40): las 5 etapas con responsable | **#57** — escala de severidad, estados del hallazgo, y si las etapas son JSONB o tabla tipada |
| I | **Bloque D** — parseo de un PDF de RCA a artículos | 2–3 RCA reales y qué secciones son exigibles |
| J | Parte de la épica #27 | **#34** — las 9 decisiones abiertas de la v1.8 |
| K | Confirmar el catálogo RETC | Los 21 sistemas y su periodicidad. Hoy: 12 sembrados, todos `active = false` |
| L | Clasificar normativa por sector | **17 de los 21 sectores CIIU están en cero**. No es decisión, es trabajo humano |
| M | Con qué identidad escribe el AI Service | Token de la persona, o cuenta de servicio con `chatbot.use` |
| **N** | **RF-109** — permisos de lectura por documento | **Una decisión de modelo.** El proposal archivado de #73 ya lo advertía: *«es una segunda barrera sobre un modelo que hoy no la tiene en ninguna tabla»*. Estaba mal clasificado como «chico» en la versión anterior de este plan |
| **O** | **#72 / RF-107** — captura de correos entrantes | **Infraestructura y diseño.** No hay análisis funcional para RF-107, y recibir correo exige un dominio con MX — o sea desplegar, que está fuera de la 1.0. Además hay que decidir *cómo* un correo se ata a un registro: dirección con sufijo, token en el asunto, hilo |

### 2.3 Fuera de la 1.0, a propósito

- **Desplegar.** El MVP corre en local.
- **La épica #24 (AmbiAgent)** y sus nueve issues — la hace Bastián, en paralelo.
- **#64**, extracción con IA de un PDF de contrato: depende de `ai-service`.
- **#116**, el repositorio de plantillas Excel, y la `periodicidad` de
  `retc_systems`: son contenido oficial de los portales del Estado, no código.
  Inventarlos produce **vencimientos falsos**, que en este dominio es el peor
  error posible — la empresa cree que declaró a tiempo.
- **#92**, Microsoft SSO: exige registro en Entra ID. Google SSO ya funciona.

---

## 3. El plan de trabajo

### La observación que ordena todo

**El código no es el cuello de botella. Las dos decisiones lo son.**

El bloque B3 y el parseo de RCA son lo más grande que queda, y ninguno de los
dos se puede empezar bien hoy. Si #57 se contesta esta semana y llegan 2–3 RCA,
la 1.0 se cierra en el orden de abajo. Si no, el trabajo de §2.1 se termina y
**después hay que esperar igual** — sólo que con la semana ya gastada.

Por eso el plan empieza pidiendo, no construyendo.

### Día 0 — hoy, y no lo hago yo

1. **Contestar #57.** Tres preguntas concretas. Destraba el bloque más grande.
2. **Conseguir 2–3 RCA reales** y marcar qué secciones son exigibles.
3. **Definir la identidad del AI Service** (§2.2 M) — Bastián está esperando eso.

Las tres son cortas. Ninguna necesita que yo esté presente.

### Tanda 1 — ✅ ejecutada el 10-sep

Ver §0. Tres conectadas, una que ya estaba, una de regalo, y dos que resultaron
estar bloqueadas.

### Tanda 2 — el bloque F: **auditado el 10-sep, y no se puede archivar nada**

**Esto también estaba mal en la versión anterior de este plan, y era mío.** Decía
que siete de los nueve cambios se podían archivar ya. Salió de mirar la tabla de
estado del proyecto en vez de los deltas.

Auditados requisito por requisito contra el código: **cero de nueve**. Cada uno
tiene al menos un requisito que el sistema no cumple. El detalle completo está en
[`auditoria-de-los-9-cambios.md`](auditoria-de-los-9-cambios.md); lo esencial:

| Cambio | Qué lo bloquea |
|---|---|
| `credenciales-de-acceso` | **Casi**: los tres requisitos están; un escenario describe otro flujo del que se construyó |
| `sistema-actores-roles-rbac` | El acotamiento de un rol a una planta **no se aplica** |
| `integracion-clerk-auth` · `acceso-por-sso` | **Microsoft SSO**, que este mismo plan pone fuera de la 1.0 |
| `ingesta-normativa-bcn` | Relaciones entre normas y bitácora: tabla y modelo existen, **nadie escribe** |
| `matrices-ambientales-iso-14001` | Una bandera de reversibilidad que probablemente sobra |
| `escrituras-de-la-interfaz` | Seis campos editables que no se pueden guardar |
| `hallazgos-…` · `modelo-de-tareas-…` | #57 y #169 |

**Y de paso apareció el hueco que importa por sí mismo**, más allá de archivar:
`user_roles.facility_id` existe, `alcance_del_usuario()` lo resuelve y `/me` lo
informa — y **ninguna consulta de negocio filtra por él**. Medido: con el rol
acotado a una planta, la API devuelve **172 filas de las otras dos**. No es una
fuga entre empresas —RLS sigue firme— pero se puede prometer en una venta y
contestar mal en una auditoría de accesos.

Lo que destraba, en orden: decidir sobre **Microsoft SSO** (destraba dos de una),
confirmar el **escenario de la invitación** (destraba el tercero), y decidir si
el **acotamiento por planta** entra en la 1.0.

### Tanda 3 — apenas llegue #57

**Bloque B3** (#38, #43, #40): las 5 etapas con responsable, la migración de
`improvement_stages` al modelo definitivo, y el aviso por correo al responsable
de cada etapa con fecha límite.

La migración de JSONB a tabla tipada tiene filas escritas, y el frontend traduce
los tres valores actuales en `CRITICIDAD_POR_SEVERITY`: **hay que mover los dos
lados a la vez.**

### Tanda 4 — apenas lleguen las RCA

**Bloque D**, el parseo. Con documentos reales delante y no antes: una RCA tiene
una estructura que hay que ver para poder parsearla, y escribirlo contra una
estructura supuesta es cómo se produce un parser que anda con el ejemplo y con
nada más.

### En paralelo, sin cruzarse

**Bastián con la épica #24.** No comparte código con nada de arriba: el
documento de integración y el contrato ya están entregados
(`docs/integracion-agente/`). Lo único que necesita de este lado es la decisión
§2.2 M.

**La clasificación por sector** (§2.2 L) la puede hacer cualquiera con criterio
ambiental, en paralelo, sin tocar código. La pantalla
`/clasificacion-normativa` ya existe y muestra sector por sector qué falta.

---

## 4. Cómo se mide que un bloque está cerrado

No por el checkbox del issue. Este proyecto ya cerró épicas enteras sobre código
que respondía 500 —el CRM— o que nadie llamaba —`bcn.sincronizar()`,
`control_documental.py`, `equipos_sin_operador_habilitado()`—. Un bloque se
cierra cuando:

1. Las escrituras se ejecutan **por el camino HTTP real**, no llamando al
   handler: `TestClient` pasa por `app/errores.py`, y llamar al handler directo
   confunde un 422 con un fallo del servidor.
2. Hay una prueba que **falla al romper a propósito** lo que dice proteger.
3. Lo que se agrega tiene **un llamador**. Una tabla que nadie lee es el patrón
   que este repositorio repite.

---

## 5. Verificación

```bash
python herramientas/auditar.py          # los detectores de las clases ya sufridas
npm run spec:check                      # los 4 artefactos de cada cambio
cd apps/api && DATABASE_URL=postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta python -m pytest
cd apps/web && npx vitest run
bash db/run.sh --with-tests
```

**Medido el 10-sep:** **1352** pruebas de API en verde, 12 saltadas (las que
salen a internet); **700** del frontend sobre 65 archivos; `tsc --noEmit`
limpio. El auditor: 27 endpoints sin llamador, 9 funciones de servicio sin
llamador, 22 importaciones de datos de ejemplo en el frontend.
