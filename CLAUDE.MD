# CLAUDE.md - Contexto del Proyecto Ambienta

## Visión General
Ambienta es un sistema multi-tenant para la gestión de cumplimiento ambiental de empresas industriales en Chile.
Objetivo: Centralizar declaraciones ambientales (RETC, residuos peligrosos, Ley REP, etc.), alertar vencimientos y generar reportes de auditoría.

## Reglas Obligatorias de Desarrollo (NO NEGOCIABLES)

### 1. Spec-Driven Development con OpenSpec

Usamos **OpenSpec** de verdad: el framework, no una imitación.

La versión está fijada en `package.json`, así que `npx openspec ...` funciona
tras `npm install` sin instalar nada más. Para que las skills de `.claude/`
lo invoquen directo hace falta además el global:

```bash
npm install -g @fission-ai/openspec@1.8.0
```

El contexto del proyecto y las reglas por artefacto viven en
`openspec/config.yaml`; el CLI se las muestra a la IA al generar artefactos.

#### 1.1 Los dos directorios

| Directorio | Qué contiene |
|---|---|
| `openspec/specs/<capacidad>/spec.md` | **Cómo se comporta el sistema hoy.** La fuente de verdad |
| `openspec/changes/<nombre>/` | Un cambio propuesto: `proposal.md`, `design.md`, `tasks.md` y `specs/` con los **deltas** |
| `openspec/changes/archive/` | Cambios terminados, con fecha. Sus deltas ya se fundieron en `specs/` |

`openspec/analisis/` es nuestro (secciones del Análisis Funcional) y no forma
parte del framework. Sirve como fuente, no como spec.

#### 1.2 El ciclo: proponer → aplicar → archivar

1. **Proponer** — `/opsx:propose`. Genera los 4 artefactos. **Solo planificación:
   no se escribe código en este paso**, aunque el pedido diga "arregla" o "haz".
2. **Aplicar** — `/opsx:apply`. Se implementa siguiendo `tasks.md`, marcando cada
   checkbox. Si el modelo real contradice la spec, se corrige el `design.md`
   antes de seguir.
3. **Archivar** — `/opsx:archive`. Los deltas se funden en `openspec/specs/` y el
   cambio se mueve a `archive/` con fecha.

**El paso 3 no es opcional.** Sin archivar, `specs/` nunca refleja el sistema
real y cada spec nueva se escribe contra un estado imaginado. Así llegamos a
tener código que leía columnas inexistentes (`compliance_answer`, `is_active`)
sin que nada lo detectara.

#### 1.3 Formato

Un spec es **un contrato de comportamiento, no un plan de implementación**. Qué
hace el sistema, no cómo. El cómo va en `design.md`.

```markdown
### Requirement: Nombre del requisito
El sistema SHALL <comportamiento observable>.

#### Scenario: Caso concreto
- **GIVEN** un estado previo
- **WHEN** ocurre algo
- **THEN** el sistema responde así
```

Los deltas van bajo `## ADDED Requirements`, `## MODIFIED Requirements` o
`## REMOVED Requirements`. Los encabezados y las palabras `SHALL`, `GIVEN`,
`WHEN`, `THEN` son estructura que el CLI parsea: van en inglés. La prosa va en
español.

#### 1.4 Antes de implementar

Leer el cambio completo (`proposal`, `design`, `tasks`, `specs/`), el spec vivo
de la capacidad en `openspec/specs/` si existe, y las fuentes en `fuentes/`.

#### 1.5 Verificación

```bash
npm run spec        # cambios activos y su avance
npm run spec:check  # los 4 artefactos y el formato de los deltas
npx openspec status --change <nombre>
npx openspec list --specs   # capacidades con spec vivo
```

Un cambio sin `specs/` no valida. Si de verdad no toca comportamiento
(herramientas, documentación), va `skip_specs: true` en su `.openspec.yaml`.

**Referencia de calidad:** `openspec/specs/dashboard/spec.md` es el ejemplo de
spec vivo; `openspec/changes/archive/2026-08-08-dashboard-metricas-api/` muestra
el ciclo completo.

### 2. Arquitectura Backend Separado
- Frontend (Next.js) y Backend (FastAPI, Python) completamente separados.
- 4 deployables: web, api, worker, ai-service.
- Nunca mezclar lógica de negocio en el frontend.

### 3. API First + OpenAPI
- Todo endpoint nuevo debe definirse primero en el contrato OpenAPI.
- Usar `packages/shared` para tipos y validadores compartidos.
- Validación automática desde el contrato (Pydantic en la API; Zod en el frontend).

### 4. Seguridad Multi-Tenant (Crítica)
- Toda consulta debe filtrar por `tenant_id`.
- Row Level Security (RLS) en PostgreSQL como segunda barrera.
- RBAC verificado siempre en la API (nunca solo en frontend).
- Admin Global NO puede editar contenido de tenants.

### 5. Roles
- **Admin Global**: Dueño del software (gestión de tenants, catálogo maestro).
- **Admin Empresa**: Gestiona su empresa y empleados.
- **Encargado**: Operativo - crea/envía declaraciones.

### 6. Desarrollo con IA (Claude Code)
- Solo implementar Features que tengan spec aprobada en `openspec/`.
- Revisión humana obligatoria de todo PR generado por IA.
- Seguir convenciones del monorepo y este archivo.

## Estructura del Monorepo