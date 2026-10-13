-- =============================================================================
-- 36 · A que sectores llega el D.S. 609 (RILes al alcantarillado)
-- =============================================================================
-- **Decision B del plan de cierre, aprobada el 13-oct-2026.**
--
-- El D.S. 609/1998 del MOP entro al catalogo el 21-sep con la sincronizacion de
-- la BCN y quedo **sin un solo sector**, asi que el CORE no se lo proponia a
-- nadie: la norma estaba en el catalogo y no llegaba a ninguna empresa.
--
-- ## El criterio: la descarga, no el rubro
--
-- Lo que activa esta norma es **descargar residuos industriales liquidos a una
-- red de alcantarillado** por encima de las cargas que fija, no pertenecer a un
-- sector. Es el mismo razonamiento del D.S. 148 con los residuos peligrosos:
-- la condicion es generar, no el rubro.
--
-- Por eso la clasificacion no es plana. En el CORE, `directa` se propone como
-- **obligatoria** y las otras dos como **recomendadas**, asi que el nivel dice
-- cuanto se le insiste a la empresa, no si la norma existe para ella.
--
-- ## Lo que NO se hace, y es deliberado
--
-- **Los dos decretos que la modifican no se clasifican.** La sincronizacion
-- trajo tambien el 3592/2000 y el 601/2004 —sus titulos empiezan con "MODIFICA
-- DECRETO Nº 609"— porque el termino de busqueda los alcanza. No se clasifican
-- porque **no son normas aparte para la empresa**: su contenido ya esta en el
-- texto vigente del 609, y proponerlos por separado haria evaluar tres veces lo
-- mismo. De ahi el filtro por `norm_number = '609'` mas el titulo que empieza
-- con "ESTABLECE": distingue la norma de sus modificaciones sin ambiguedad.
--
-- ## Hay que volver a aplicarla despues de sincronizar la BCN
--
-- Igual que `db/23`, y por el mismo motivo: en una base limpia de produccion no
-- hay ninguna norma —el catalogo de ejemplo vive en `02_seed.sql`, que
-- produccion no carga— asi que esta migracion no encuentra el 609 y **no
-- inserta nada, sin fallar**. Cuando `sincronizar-bcn` lo traiga, hay que
-- reaplicarla. Esta en el runbook, en el mismo paso que `db/23`.
--
-- Idempotente: se puede correr tantas veces como haga falta.
-- =============================================================================

BEGIN;

WITH niveles(codigo_sector, nivel, motivo) AS (VALUES
    ('C', 'directa',
     'El caso tipico de la norma: establecimiento industrial en zona urbana '
     'conectado a la red de alcantarillado.'),
    ('A', 'indirecta',
     'La agroindustria —packing, lecherias, faenadoras— descarga al '
     'alcantarillado cuando esta en zona urbana.'),
    ('B', 'indirecta',
     'Las faenas mineras rara vez estan conectadas a una red, pero si las '
     'plantas de proceso y los talleres emplazados en ciudad.'),
    ('D', 'indirecta',
     'Centrales y plantas de gas urbanas con agua de proceso.'),
    ('E', 'indirecta',
     'Las sanitarias reciben y controlan la descarga; un relleno o una planta '
     'de tratamiento de residuos puede ser emisor.'),
    ('F', 'referencial',
     'Descargas de obra puntuales, que rara vez superan las cargas de la norma.'),
    ('G', 'referencial',
     'Lavanderias, cocinas industriales o lavado de vehiculos pueden calificar '
     'como emisores.'),
    ('H', 'referencial',
     'Talleres y lavado de flota, el mismo caso que el comercio.')
)
INSERT INTO norm_sectors (norm_id, sector_id, applicability_level, rationale, source)
SELECT n.id, s.id, v.nivel, v.motivo, 'analyst'
FROM niveles v
JOIN sectors s ON s.code = v.codigo_sector
JOIN legal_norms n
  ON n.norm_number = '609'
 -- "ESTABLECE ..." es la norma; "MODIFICA DECRETO Nº 609 ..." son los otros dos.
 AND upper(n.title) LIKE 'ESTABLECE NORMA DE EMISION%'
 AND upper(n.title) LIKE '%ALCANTARILLADO%'
 AND n.deleted_at IS NULL
ON CONFLICT (norm_id, sector_id) DO UPDATE
   -- Si alguien ya la reviso a mano, se conserva **su** nivel y solo se
   -- completa el motivo si estaba vacio: esto agrega cobertura, no pisa
   -- trabajo humano. Misma regla que `db/23`.
   SET rationale = COALESCE(norm_sectors.rationale, EXCLUDED.rationale);

DO $$
DECLARE clasificados int;
BEGIN
    SELECT count(*) INTO clasificados
    FROM norm_sectors ns
    JOIN legal_norms n ON n.id = ns.norm_id
    WHERE n.norm_number = '609'
      AND upper(n.title) LIKE 'ESTABLECE NORMA DE EMISION%';

    IF clasificados = 0 THEN
        RAISE NOTICE
            'El D.S. 609 no esta en el catalogo todavia: no se clasifico nada. '
            'Correr `python -m app.tareas sincronizar-bcn` y volver a aplicar '
            'este archivo.';
    ELSE
        RAISE NOTICE 'OK · el D.S. 609 quedo clasificado en % sector(es)', clasificados;
    END IF;
END $$;

COMMIT;
