# Plan de cierre de la versión 1.0

**Actualizado el 9-sep-2026.** La versión anterior era del 7-sep y quedó
desactualizada en cuatro puntos, marcados abajo.

## Qué es esto, y qué no

Es el plan para dejar Ambienta en **versión 1.0 y listo para desplegar**.
Desplegar **no entra**: el MVP corre en local, no hay dominio, y pasar a
producción es una decisión posterior.

**Este archivo existe porque el plan vivía sólo en una conversación.** La
pregunta "¿en qué semana vamos?" no se podía contestar mirando el repositorio, y
eso es exactamente lo que este proyecto persigue en todo lo demás: estado que
sólo existe en la cabeza de alguien.

---

## 1. Lo que cambió desde el 7-sep

| Lo que decía | Lo que es hoy |
|---|---|
| "Queda D y F" | El **bloque E está cerrado** (#73–76) y **D está a medias**: el modelo y la API de normativa propia se cerraron el 8-sep |
| Suite de API: 1214 (medida el 4-sep) | **1338 en verde**, 12 saltadas — medido el 8-sep |
| 10 escrituras del frontend bloqueadas | **Tres ya no lo están.** Ver §2 |
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

O sea que las escrituras conectadas no son 29 de 39 con 10 bloqueadas: son **29
de 39 con 3 listas para conectar y 7 realmente bloqueadas**.

Y la tercera arrastra otra cosa: **la "pantalla de administración de RBAC" que
figura como faltante es sólo pantalla.** La API está completa y probada. Mismo
patrón que `bcn.sincronizar()` y `control_documental.py`.

---

## 2. Lo que falta, completo

### 2.1 Listo para hacer — no depende de nadie

| # | Qué | Tamaño |
|---|---|---|
| A | Conectar `legal-matrix.addNorm` a `/compliance/normativa-propia` | chico |
| B | Conectar `gestores.addContrato` a `POST /contracts/` | chico |
| C | Pantalla de administración de RBAC + `users.updatePermisos` | mediano |
| D | **#72 / RF-107** — captura de correos entrantes al registro | mediano |
| E | **Bloque F** — archivar los 9 cambios OpenSpec y recorrer el sistema | mediano |
| F | **RF-109** — permisos de lectura por documento | chico |
| G | **#52** — portar `01_schema.sql` a migración versionada | mediano, riesgoso |

### 2.2 Bloqueado en una decisión de negocio

| # | Qué | Espera |
|---|---|---|
| H | **Bloque B3** (#38, #43, #40): las 5 etapas con responsable | **#57** — escala de severidad, estados del hallazgo, y si las etapas son JSONB o tabla tipada |
| I | **Bloque D** — parseo de un PDF de RCA a artículos | 2–3 RCA reales y qué secciones son exigibles |
| J | Parte de la épica #27 | **#34** — las 9 decisiones abiertas de la v1.8 |
| K | Confirmar el catálogo RETC | Los 21 sistemas y su periodicidad. Hoy: 12 sembrados, todos `active = false` |
| L | Clasificar normativa por sector | **17 de los 21 sectores CIIU están en cero**. No es decisión, es trabajo humano |
| M | Con qué identidad escribe el AI Service | Token de la persona, o cuenta de servicio con `chatbot.use` |

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

### Tanda 1 — mientras tanto, lo que no espera a nadie

En este orden, porque va de lo que más desbloquea a lo que menos:

| Orden | Qué | Por qué acá |
|---|---|---|
| 1 | **A + B** — las dos escrituras desbloqueadas | Son chicas y cierran una brecha que el documento reporta mal. Empezar por acá deja el conteo verdadero |
| 2 | **C** — RBAC: pantalla + `users.updatePermisos` | La API está completa. Es la última pieza de un módulo que hoy figura como "falta la pantalla" desde hace semanas |
| 3 | **F** — RF-109, permisos por documento | Chico, y cierra la épica #31 salvo por #72 |
| 4 | **D** — #72, captura de correos | El más grande de la tanda. `/historial` ya lo declara como `fuentes_pendientes`, así que hoy el sistema **dice** que le falta |

**No entra en esta tanda: #52** (portar el esquema a migración). Es mecánico
pero toca la base entera, y hacerlo mientras B3 va a agregar tablas es pedir un
conflicto. Va después de B3 o no va en la 1.0 — funcionalmente no cambia nada.

### Tanda 2 — apenas llegue #57

**Bloque B3** (#38, #43, #40): las 5 etapas con responsable, la migración de
`improvement_stages` al modelo definitivo, y el aviso por correo al responsable
de cada etapa con fecha límite.

Es el más grande de los que quedan. La migración de JSONB a tabla tipada tiene
filas escritas, y el frontend traduce los tres valores actuales en
`CRITICIDAD_POR_SEVERITY`: hay que mover los dos lados a la vez.

### Tanda 3 — apenas lleguen las RCA

**Bloque D**, el parseo. Con 2–3 documentos reales delante, no antes: una RCA
tiene una estructura que hay que ver para poder parsearla, y escribir el parser
contra una estructura imaginada es cómo se produce un parser que anda con el
ejemplo y con nada más.

### Tanda 4 — al final, y sólo al final

**Bloque F.** Dos partes:

1. **Archivar los 9 cambios OpenSpec.** Son 9 deltas de capacidad para fundir en
   `openspec/specs/`, que hoy tiene 5 specs vivos y 9 cambios archivados.
2. **Recorrer el sistema entero** con el criterio de §4.

Va último por una razón concreta: **archivar specs antes de terminar D y B3
significa archivarlos dos veces.** Y no es sólo mecánico — los contadores de
tareas mienten en las dos direcciones y hay que verificar cada delta contra el
código antes de fundirlo:

| Cambio | Dice | Realidad |
|---|---|---|
| `ingesta-normativa-bcn` | 0/36 | El catálogo se alimenta de la BCN desde el 26-ago |
| `matrices-ambientales-iso-14001` | 18/32 | La épica #28 se cerró el 6-sep |
| `integracion-clerk-auth` | 100/116 | Auth funciona de punta a punta desde el 10-ago |

Fundir un delta confiando en su checkbox dejaría `specs/` describiendo un sistema
que no existe — que es exactamente lo que el bloque F viene a arreglar.

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

**Medido el 8-sep:** 1338 pruebas de API en verde, 12 saltadas (las que salen a
internet). El auditor: 26 endpoints sin llamador, 9 funciones de servicio sin
llamador, 22 importaciones de datos de ejemplo en el frontend.

**Del 7-sep, sin volver a medir:** 653 pruebas del frontend en verde sobre 58
archivos, `tsc --noEmit` limpio.
