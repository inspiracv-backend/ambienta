# Proposal: Ingesta del catálogo normativo desde la BCN

Fuentes: `datos.bcn.cl/sparql` (probado el 13-ago-2026) · `accesoLeyesChilenas4.pdf`, especificación del web service XML de Ley Chile · `db/01_schema.sql` · RF-17.

## Why

Hoy el catálogo normativo se llena a mano. Eso funciona como registro, pero **no
responde la primera pregunta de un auditor**: cómo determinaron que estas normas
les aplican, y cómo saben que no falta ninguna.

Cuatro tablas del esquema existen y están vacías esperando exactamente esto:

| Tabla | Qué guardaría |
|---|---|
| `legal_articles` | Los artículos de cada norma |
| `legal_norm_versions` | Qué versión de la norma estaba vigente cuándo |
| `legal_relations` | Qué norma deroga, modifica o complementa a cuál |
| `norm_sync_runs` | Bitácora de cada sincronización |

Las cuatro figuran en `docs/estado-crud-base-de-datos.md` como *"depende del
adaptador de ingesta BCN, que todavía no existe"*.

## Lo que se comprobó, no lo que se supone

**El web service XML de Ley Chile responde 401.** Probado contra
`leychile.cl/Consulta/obtxml` y contra el mismo camino bajo `bcn.cl`: los dos
rechazan sin credenciales, y también el propio esquema XSD. La especificación de
2009 documenta `opt=7` con `idNorma` o `idLey`, pero **hoy no se puede llamar sin
que la BCN habilite un acceso.**

**Hay una API key solicitada el 13-ago-2026, y todavía no sirve.** El panel de la
BCN la muestra como **"No activa"**, y se comprobó: devuelve 401 con las cuatro
formas habituales de mandarla —`Authorization: Bearer`, `X-API-Key`, y como
parámetro `apikey` o `api_key`—. Habrá que reintentar cuando la BCN la habilite,
y recién ahí averiguar cuál de las cuatro es la correcta.

> La clave es un secreto: va en `.env`, nunca en el repositorio. `.env.example`
> lleva el nombre de la variable y ningún valor.

**El endpoint SPARQL de datos abiertos sí responde, sin autenticación.**
`datos.bcn.cl/sparql` devuelve 200 y contiene **748.783 normas**, con las
propiedades que hacen falta.

Prueba concreta, la Ley 20.920 (Ley REP), central para el dominio:

| Propiedad BCN | Valor | Columna nuestra |
|---|---|---|
| `dc:title` | ESTABLECE MARCO PARA LA GESTIÓN DE RESIDUOS… | `title` |
| `hasNumber` | 20920 | `norm_number` |
| `leychileCode` | 1090894 | `external_norm_id` |
| `publishDate` | 2016-06-01 | `publication_date` |
| `type` | ley | `norm_type` |
| URI | …/ministerio-del-medio-ambiente/… | `issuing_body` |

Y las relaciones y versiones vienen modeladas: `modifiesTo`, `isModifiedBy`,
`recasts`, `rectifies`, `isRectifiedBy`, `isRecastedBy`, `regulates`,
`isRegulatedBy`, `versionOf`, `hasVersion`, `versionDate`, `isLatestVersion`.

**`leychileCode` es la bisagra**: es el mismo identificador que pide el web
service XML. Guardarlo ahora permite traer el texto completo el día que haya
credenciales, sin volver a mapear nada.

## What Changes

1. **Un adaptador de solo lectura** contra el SPARQL abierto, que trae metadatos,
   relaciones y versiones de las normas que interesan.
2. **Las relaciones entre normas dejan de ser un campo vacío**: qué deroga a qué
   se lee de la fuente oficial, no de la memoria de quien cargó la lista.
3. **Cada sincronización deja bitácora** en `norm_sync_runs`: cuándo corrió, qué
   trajo, qué falló.

## Qué exige del resto del sistema

| Área | Qué necesita | Estado |
|---|---|---|
| `legal_norms` | Ya tiene `external_norm_id`, `norm_number`, `official_url`, `source_payload` | Existe |
| `legal_relations`, `legal_norm_versions`, `norm_sync_runs` | Exponerlas o al menos escribirlas | **Este cambio** |
| `apps/worker` | Es donde corresponde un job periódico. Hoy es **una carpeta vacía** | **No existe** |
| `countries`, `legal_sources` | Toda norma necesita país y fuente. `countries` no tiene ni lectura (#166) | **Bloquea** |
| Catálogo | Decidir **qué normas** se traen: son 748.783 | **Decisión** |

## Lo que este cambio no hace

- **No trae el texto de los artículos.** El SPARQL da metadatos y relaciones; el
  articulado completo está en el XML que hoy responde 401. `legal_articles`
  queda esperando credenciales.
- **No decide qué normas le aplican a cada empresa.** Eso es aplicabilidad por
  actividad económica, y es trabajo de contenido, no de ingesta.
- **No corre solo.** Sin worker, la sincronización se dispara a mano.

## Decisiones que requiere el equipo

- [ ] **¿Qué subconjunto se trae?** 748.783 normas es todo el corpus chileno.
      Lo razonable es acotar por materia ambiental y por los organismos que nos
      importan (SMA, SEC, SISS, SEREMI de Salud, DGA), pero **eso es un criterio
      de negocio**, no técnico.
- [ ] **¿Se piden credenciales del web service XML a la BCN?** Sin ellas no hay
      articulado, y sin articulado la matriz legal no puede evaluarse artículo
      por artículo — que es justo lo que el módulo existe para hacer.
- [ ] **¿Cada cuánto sincroniza?** Diario, semanal, o a demanda. Y quién revisa
      lo que la sincronización cambió: una norma derogada río arriba cambia el
      cumplimiento de una empresa sin que nadie lo haya tocado.
- [ ] **¿Qué pasa cuando la fuente contradice lo cargado a mano?** Gana la BCN,
      gana lo local, o se marca el conflicto para que alguien decida.
