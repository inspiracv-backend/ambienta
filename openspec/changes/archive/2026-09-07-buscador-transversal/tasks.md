# Tasks: el buscador transversal (#76, RF-114)

Plan de [`proposal.md`](./proposal.md) / [`design.md`](./design.md).

## Fase 1 — El servicio

- [x] `services/buscador.py` con las fuentes y sus columnas
- [x] FTS `spanish` para los títulos; `ILIKE` sólo para el número de norma
- [x] El filtro por permiso **antes** de consultar, con `familia_de`
- [x] Tope por grupo con aviso, y mínimo de dos caracteres

## Fase 2 — La API

- [x] `GET /buscar`, con sus declaraciones meta
- [x] Pruebas por el camino HTTP real, incluido el caso del acento
- [x] Mutaciones: quitar el filtro de permiso, y cambiar FTS por `ILIKE`

## Fase 3 — La interfaz

- [x] Pantalla `/buscar` con los cuatro estados
- [x] La advertencia de que no se busca dentro de los archivos
