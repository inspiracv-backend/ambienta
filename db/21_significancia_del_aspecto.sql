-- 21 · `environmental_aspects.significance` guarda significancia, no cumplimiento
--
-- La columna se llama `significance` y su CHECK admitia
-- `compliant | partial | non_compliant | pending`: los estados de
-- `article_compliance.compliance_status`, de donde se copio. **Son dos
-- preguntas distintas y ninguna responde a la otra.**
--
-- En ISO 14001 §6.1.2 la significancia contesta "¿este aspecto ambiental
-- importa lo suficiente como para gestionarlo?", y de ahi sale la obligacion de
-- tratarlo. El cumplimiento contesta "¿cumplimos este requisito legal?". Un
-- aspecto puede ser significativo y estar perfectamente controlado; con el
-- vocabulario viejo eso no se podia ni escribir.
--
-- El dano no era teorico: la pantalla de Aspectos Ambientales tiene una columna
-- "Significativo" y un filtro "significativo sin tratar" —el hallazgo mas comun
-- en una auditoria de 14001—, y ninguno de los dos podia funcionar, porque
-- `significant` no era un valor que la base admitiera.
--
-- ## Que pasa con las filas que ya existen
--
-- Pasan a `pending`, y **no se traducen**. Traducir exigiria decidir que
-- `non_compliant` significaba "significativo", y eso es inventar una evaluacion
-- de significancia que nadie hizo: los valores que hay son restos de la copia,
-- no el juicio de una persona sobre si el aspecto importa.
--
-- `pending` dice la verdad —nadie evaluo la significancia todavia— y deja el
-- trabajo a la vista en la pantalla en vez de esconderlo tras una etiqueta
-- inventada. Son 3 filas de demostracion; no hay produccion.
--
-- Idempotente: se puede correr dos veces.

BEGIN;

ALTER TABLE environmental_aspects
    DROP CONSTRAINT IF EXISTS environmental_aspects_significance_check;

-- Primero los datos, despues la restriccion: al reves, el UPDATE chocaria con
-- el CHECK viejo.
UPDATE environmental_aspects
   SET significance = 'pending'
 WHERE significance IN ('compliant', 'partial', 'non_compliant');

ALTER TABLE environmental_aspects
    ADD CONSTRAINT environmental_aspects_significance_check
    CHECK (significance IN ('significant', 'not_significant', 'pending'));

COMMENT ON COLUMN environmental_aspects.significance IS
    'Significancia del aspecto (ISO 14001 §6.1.2): si importa lo suficiente '
    'como para gestionarlo. NO es un estado de cumplimiento — un aspecto puede '
    'ser significativo y estar controlado.';

COMMIT;
