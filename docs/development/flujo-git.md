# Flujo Git

## Branches

```
main
  └── 002-backend-api-stores-integracion   ← rama de integracion actual
        ├── fix/84-readme-discrepancias     ← una branch por sub-issue
        ├── fix/85-turborepo-pipeline
        └── feat/xxx-descripcion
```

### Reglas

- **Una branch por issue/sub-issue**, con el formato `tipo/numero-descripcion`
- Crear desde la rama de integracion, no desde `main`
- Cada branch produce un PR independiente

## Workflow por issue

1. Checkout desde la rama de integracion:
   ```bash
   git checkout 002-backend-api-stores-integracion
   git checkout -b fix/N-descripcion
   ```

2. Hacer los cambios y commitear con Conventional Commits:
   ```bash
   git add archivo.ts
   git commit -m "feat(web): agregar componente de dashboard"
   ```

3. Push y crear PR:
   ```bash
   git push -u origin fix/N-descripcion
   gh pr create --base 002-backend-api-stores-integracion \
     --title "feat(web): agregar componente de dashboard" \
     --body "Closes #N"
   ```

4. Cerrar el issue con referencia al PR:
   ```bash
   gh issue close N --comment "Resuelto en PR #M"
   ```

5. Actualizar el status en el GitHub Project a Done.

## Conventional Commits

```
tipo(scope): descripcion imperativa corta

Cuerpo opcional con contexto.

Closes #N

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Tipos validos: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`

## GitHub Project

- Proyecto: https://github.com/users/inspiracv-backend/projects/3/views/1
- Cada EPIC es un issue con sub-issues
- Status: Todo → In Progress → Done
- Al crear un PR, agregarlo al proyecto
- Al cerrar un issue, marcarlo como Done en el proyecto
