# Convenciones de desarrollo

## Metodologia: Spec-Driven Development

Cada feature nueva sigue el ciclo OpenSpec:

1. **Especificar**: crear `proposal.md` + `design.md` + `tasks.md` en `openspec/changes/<nombre>/`
2. **Revisar y aprobar** la spec
3. **Implementar** solo specs aprobadas
4. **Actualizar** la spec si hay cambios durante la implementacion

No se implementa nada sin spec aprobada. Ver `CLAUDE.md` para las reglas completas.

## Estructura de codigo

### Frontend (`apps/web`)

- **Atomic Design**: atomos, moleculas, organismos, templates en `components/`
- **Stores**: un archivo por dominio en `lib/`, conectados a la API real
- **Paginas**: App Router de Next.js 14, una carpeta por seccion en `app/(dashboard)/`
- **Tipos**: importar de `@ambienta/shared` cuando existen, crear locales solo si son exclusivos del frontend

### Backend (`apps/api`)

- **Routers**: un archivo por dominio en `app/routers/`, registrado en `main.py`
- **CRUD**: operaciones genericas en `app/crud/`, heredan de `CRUDBase`
- **Services**: logica de negocio en `app/services/`
- **Models**: SQLAlchemy 2.0 en `app/models/`
- **Schemas**: Pydantic v2 en `app/schemas/`

### Schemas compartidos (`packages/shared`)

- Schemas Zod que definen la fuente de verdad de tipos entre frontend y backend
- Exportar todo desde `src/index.ts`

## Nombrado

| Que | Convencion | Ejemplo |
|---|---|---|
| Archivos frontend | kebab-case | `obligation-card.tsx` |
| Componentes React | PascalCase | `ObligationCard` |
| Stores | kebab-case + `-store` | `obligations-store.tsx` |
| Routers backend | snake_case | `legal_norms.py` |
| Modelos SQLAlchemy | PascalCase singular | `Obligation` |
| Tablas PostgreSQL | snake_case plural | `obligations` |
| Endpoints API | kebab-case plural | `/api/v1/legal-norms/` |
| Branches | `tipo/numero-descripcion` | `fix/84-readme-discrepancias` |
| Commits | Conventional Commits | `feat(web): agregar dashboard` |

## Commits

Formato: `tipo(scope): descripcion corta`

Tipos: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`

Scopes: `web`, `api`, `shared`, `db`, `infra`, `docs`, `openspec`

## Seguridad multi-tenant

- Toda consulta filtra por `tenant_id`
- RLS en PostgreSQL como segunda barrera (siempre activo)
- RBAC verificado en la API, nunca solo en el frontend
- Admin Global NO puede editar contenido de tenants
- Passwords encriptados, nunca en texto plano
- `secret_reference`: referencia al secret manager, nunca el token en claro
- Audit log inmutable

## Pull requests

- Una PR por cambio logico (no mezclar features)
- Titulo con Conventional Commits
- Body con `## Summary` y `## Test plan`
- Referenciar el issue con `Closes #N`
- Base branch: `002-backend-api-stores-integracion` (rama de integracion actual)
