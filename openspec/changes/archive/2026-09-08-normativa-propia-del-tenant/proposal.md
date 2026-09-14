# Proposal: La normativa propia de cada empresa (su RCA y sus ISO)

Fuente: Análisis Funcional, sección D — **RF-10** (*soporte diferenciado normas
públicas BCN / ISO internas / RCA del tenant*) y **RF-11** (*carga de PDF/HTML
para RCA; RCAs públicas y privadas, pre y post 2015*). Pantalla S-12.

Es el bloque D del plan de cierre, y **no tenía issue**: vivía sólo en
`docs/plan-de-cierre-v1.md`, que es exactamente el problema que ese archivo
existe para evitar.

## Lo que hay hoy, medido el 7-sep-2026

**El catálogo normativo es enteramente público, y no puede dejar de serlo sin
un cambio de modelo.** Las cuatro tablas:

| tabla | `tenant_id` | RLS |
|---|---|---|
| `legal_norms` | **no** | **no** |
| `legal_norm_versions` | **no** | **no** |
| `legal_articles` | **no** | **no** |
| `norm_sectors` | no | no |

Y es correcto que sea así: la ley es la misma para todos, y por eso 24 normas y
689 artículos se comparten entre empresas.

**La consecuencia es que hoy una empresa no puede registrar su RCA.** Su
Resolución de Calificación Ambiental es un permiso de **ese** proyecto, con
condiciones que sólo la obligan a ella; escribirla en `legal_norms` la dejaría
visible para todas las demás empresas del sistema — y el daño no es abstracto:
las condiciones de una RCA describen la operación de la planta.

Los tipos que hay en la base lo confirman: `resolucion` (9), `decreto_supremo`
(9), `ley` (6). Todas públicas.

## Lo que se propone

`tenant_id` **nulable** en las tres tablas del catálogo, con RLS y una política
de dos lados:

```
USING       (tenant_id IS NULL OR tenant_id = current_tenant_id())
WITH CHECK  (tenant_id = current_tenant_id())
```

Leído: *«veo lo público y lo mío; escribo sólo lo mío»*. Una norma propia entra
por el mismo camino que cualquier otra —matriz, evaluación por artículo,
obligaciones, reportes— porque **sigue siendo una norma**. No hay una segunda
tabla ni un segundo flujo.

## Por qué una columna nulable y no una tabla aparte

Una `tenant_norms` separada obligaría a que `matrix_norms.norm_id` apuntara a
dos tablas —polimórfico, sin clave foránea— y a duplicar el camino en la
matriz, la evaluación por artículo, el cálculo de cumplimiento, el dashboard y
los reportes. Serían **dos implementaciones del mismo concepto** que hay que
mantener coherentes, y la primera vez que se separen la empresa verá dos
porcentajes de cumplimiento distintos sobre la misma planta.

Con una columna, una RCA **es** una norma. Todo lo construido funciona sin
tocarse.

## Lo que NO entra, y por qué

- **La extracción con IA del PDF (RF-11, opcional).** El propio análisis la deja
  fuera: *«el botón Subir RCA/ISO sólo agrega el registro con artículos
  vacíos/a completar manualmente»*. Depende de `ai-service`, que es una carpeta
  vacía, y la épica #24 la lleva otra persona.
- **Sembrar el contenido de ninguna RCA.** Qué considerandos de una RCA son
  exigibles es una decisión que necesita 2–3 RCA reales sobre la mesa. Es el
  mismo criterio que la `periodicidad` vacía de `retc_systems` y que el
  repositorio de plantillas Excel: **se construye el mecanismo, no se inventa
  el contenido.** Una condición inventada en una matriz legal produce un
  incumplimiento que no existe.
- **Clasificar una norma propia por sector.** `norm_sectors` sirve para
  *proponer* normativa a empresas de un rubro; una RCA aplica a **una** empresa
  por definición, así que no se propone: se carga.
