# Tasks: la línea de tiempo por registro (#75, RF-113)

Plan de [`proposal.md`](./proposal.md) / [`design.md`](./design.md).

## Fase 1 — El servicio

- [x] `services/historial.py` que une `audit_log`, `comments` y `entity_documents`
- [x] La traducción de vocabulario **derivada** de `ANCLAJES[..].modelo.__tablename__`
- [x] Tope con aviso, y las fuentes declaradas (incluido el correo pendiente)

## Fase 2 — La API

- [x] `GET /historial`, con el permiso del registro
- [x] Pruebas por el camino HTTP real, y las mutaciones

## Fase 3 — La interfaz

- [x] `lib/vocabulario-de-entidades.ts` con su prueba de cobertura
- [x] `HistorialTimeline` consume la API **sin cambiar sus props**
- [x] Las fuentes pendientes se muestran
