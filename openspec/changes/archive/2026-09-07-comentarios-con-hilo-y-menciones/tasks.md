# Tasks: comentarios con hilo y menciones (#74, RF-111 y RF-112)

Plan de [`proposal.md`](./proposal.md) / [`design.md`](./design.md).

## Fase 1 — La base

- [x] `db/28_comentarios.sql`: `comments` y `comment_mentions`, **con su propia RLS y sus GRANT**
- [x] Registrar el archivo en los **cinco** lugares
- [x] Modelos y esquemas

## Fase 2 — El servicio

- [x] `services/comentarios.py` reusando `ANCLAJES` de RF-108
- [x] Hilo de un nivel: la respuesta a una respuesta se rechaza diciendo la raíz
- [x] Menciones comprobadas una por una, con la negativa idéntica
- [x] La notificación por la cola existente, sin notificarse a uno mismo

## Fase 3 — La API

- [x] `GET`, `POST`, `PATCH`, `DELETE` de `/comentarios`
- [x] Sin sesión identificada, 409

## Fase 4 — La interfaz

- [x] El hilo en la ficha de la obligación, con los tres estados
- [x] Marca de edición visible
