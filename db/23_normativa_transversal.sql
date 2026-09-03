-- 23_normativa_transversal.sql — clasifica en TODOS los sectores la normativa
-- que aplica a cualquier actividad, no solo a un rubro.
--
-- ## El problema que arregla
--
-- Medido el 1-sep-2026: de los 8 sectores CIIU sembrados, **4 estaban en cero**
-- y las normas con mas articulado estaban clasificadas **solo en el sector 5**
-- (suministro de agua y gestion de residuos):
--
--     DS 40  (reglamento del SEIA) .......... 210 articulos ... solo sector 5
--     Ley 19.300 (bases generales) .......... 151 articulos ... solo sector 5
--     DS 148 (residuos peligrosos) .......... 109 articulos ... solo sector 5
--     DS 1   (registro de emisiones) ........  42 articulos ... sin clasificar
--
-- La consecuencia es concreta: una empresa **minera** declara su sector y el
-- CORE le propone dos normas y cuatro articulos, cuando la Ley 19.300 es la ley
-- marco del medio ambiente chileno y le aplica igual que a todos. No es que el
-- calculo este mal; es que la clasificacion estaba incompleta.
--
-- ## El criterio: solo lo transversal por su propio texto
--
-- Se clasifican **cuatro normas y ninguna mas**, y cada una por una razon que
-- esta en la norma misma, no en un juicio nuestro sobre el rubro:
--
--   * **Ley 19.300** es la ley marco. Su articulo 1 regula el derecho a vivir
--     en un medio ambiente libre de contaminacion para toda actividad.
--   * **DS 40** reglamenta el Sistema de Evaluacion de Impacto Ambiental, que
--     se aplica a los proyectos del articulo 10 de la 19.300 — una lista que
--     abarca todos los rubros productivos.
--   * **DS 148** aplica a **quien genera** residuos peligrosos. La condicion es
--     generar, no pertenecer a un rubro.
--   * **DS 1** crea el Registro de Emisiones y Transferencias de Contaminantes,
--     al que reportan establecimientos de cualquier sector.
--
-- **Lo que NO se toca, a proposito:** DS 13 (centrales termoelectricas), DS 90
-- (residuos liquidos), DS 38 (ruido de fuentes fijas) y la Ley 20.920 (REP).
-- Las cuatro tienen un alcance mas acotado y decidir a que sectores alcanzan
-- **es una decision de negocio con criterio legal**, no una migracion. Ampliar
-- la clasificacion a ojo produciria matrices con normativa que no aplica, y una
-- matriz con normas de mas es peor que una con normas de menos: obliga a la
-- empresa a evaluar articulos que no la rigen y ensucia su porcentaje de
-- cumplimiento.
--
-- ## Hay que volver a aplicarla despues de sincronizar la BCN
--
-- Esta migracion corre **al inicializar la base**, y en ese momento el catalogo
-- son las normas sembradas. La sincronizacion con la BCN **crea normas que
-- antes no existian** —el DS 1 del registro de emisiones es una— y esas quedan
-- sin clasificar hasta que esto se vuelva a correr:
--
--     docker compose exec -T postgres psql -U ambienta -d ambienta --       -v ON_ERROR_STOP=1 -f /dev/stdin < db/23_normativa_transversal.sql
--
-- `sembrar_demo` lo comprueba y avisa, para que no pase inadvertido.
--
-- Idempotente: se puede correr las veces que sea.

BEGIN;

-- `rationale` no es decoracion: es lo que le permite a quien revise la matriz
-- entender por que le aparecio esta norma. Sin eso, una norma inesperada se lee
-- como un error del sistema.
-- **Se busca por numero y titulo, NO por `norm_type`.** La primera version
-- exigia `norm_type = 'decreto_supremo'` y clasifico solo una de las cuatro: las
-- filas sembradas no tienen ese tipo, lo adquieren recien cuando la
-- sincronizacion con la BCN las adopta. Medido: DS 40 y DS 148 quedaron con un
-- sector en vez de ocho, sin que nada fallara.
--
-- El titulo acota lo que el numero solo no distingue: "1" es un numero que
-- muchas normas comparten, y clasificar la equivocada en los ocho sectores
-- pondria en todas las matrices una norma que no aplica.
WITH transversales(numero, patron_titulo, motivo) AS (
    VALUES
    ('19300', '%BASES GENERALES DEL MEDIO AMBIENTE%',
     'Ley marco del medio ambiente. Su articulo 1 regula el derecho a vivir en un medio ambiente libre de contaminacion para toda actividad, sin distinguir rubro.'),
    ('40', '%SISTEMA DE EVALUACI%N DE IMPACTO AMBIENTAL%',
     'Reglamenta el Sistema de Evaluacion de Impacto Ambiental, aplicable a los proyectos del articulo 10 de la Ley 19.300, que abarca todos los rubros productivos.'),
    ('148', '%RESIDUOS PELIGROSOS%',
     'Aplica a quien genera residuos peligrosos. La condicion que la activa es generar, no pertenecer a un sector economico determinado.'),
    ('1', '%REGISTRO DE EMISIONES Y TRANSFERENCIA%',
     'Crea el Registro de Emisiones y Transferencias de Contaminantes, al que reportan establecimientos de cualquier sector.')
)
INSERT INTO norm_sectors (norm_id, sector_id, applicability_level, rationale, source)
SELECT n.id, s.id, 'directa', t.motivo, 'analyst'
FROM transversales t
JOIN legal_norms n
  ON n.norm_number = t.numero
 AND upper(n.title) LIKE upper(t.patron_titulo)
 AND n.deleted_at IS NULL
CROSS JOIN sectors s
ON CONFLICT (norm_id, sector_id) DO UPDATE
   -- Si ya estaba clasificada, se conserva el nivel que puso quien la reviso y
   -- solo se completa el motivo si estaba vacio: esta migracion agrega
   -- cobertura, no pisa trabajo humano.
   SET rationale = COALESCE(norm_sectors.rationale, EXCLUDED.rationale);

COMMIT;
