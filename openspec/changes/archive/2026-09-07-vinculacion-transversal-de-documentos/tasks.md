# Tasks: la vinculación transversal de documentos (#73, RF-108)

Plan de [`proposal.md`](./proposal.md) / [`design.md`](./design.md).

## Fase 1 — La base

- [x] `db/27_vinculos_de_documentos.sql`: agregar `legal_norm` y `process` al CHECK de `entity_type`
- [x] Registrar el archivo en los **cinco** lugares: los dos compose, `db/run.sh`, `db/README.md` y el bucle de `ci.yml`

## Fase 2 — La comprobación

- [x] `services/vinculos_de_documentos.py` con el mapa `ANCLAJES`
- [x] `POST` y `PATCH` de `/documents/{id}/entities` lo llaman
- [x] Prueba que **lee el SQL** y exige que el mapa y el CHECK digan lo mismo
- [x] Prueba de las dos negativas idénticas, por el camino HTTP real

## Fase 3 — El sentido inverso

- [x] `GET /documents/vinculados`, declarado **antes** de `/{document_id}`
- [x] Prueba de que no queda ensombrecido

## Fase 4 — La interfaz

- [x] La ficha de la obligación lista lo que la respalda
- [x] Los tres estados: no se sabe, falló, y vacío de verdad
