# Tareas

**Supuestos vigentes** (medidos el 4-sep, no hace falta confirmarlos):

- `legal_norms` y `legal_articles` no tienen `tenant_id` ni RLS. 24 normas y 689
  artículos, todos del catálogo compartido.
- El permiso `catalog.write` («Cargar RCAs e ISO del tenant») y la fila `RCA` de
  `norm_sources` ya están sembrados y no los usa nadie.
- El control documental sube a B2 con el `tenant_id` en la ruta y comprueba
  tamaño y tipo reales contra el bucket.
- La cadena artículo → evaluación → obligación → aviso → reporte funciona.

**Supuestos que hay que confirmar antes de la fase que los usa** (ver
`proposal.md — Decisiones que necesita el equipo`):

- Bloquea la **fase 5**: si se guarda el texto íntegro de las normas ISO o solo
  su estructura.
- Bloquea la **fase 5**: qué secciones de una RCA son obligación exigible.
- Bloquea la **fase 6**: qué se hace con una RCA modificatoria.

## 0. Prerrequisitos fuera de este módulo

- [ ] 0.1 Conseguir 2 o 3 RCAs reales y, si entra ISO, una norma comprada de
      ejemplo. Sin documentos reales no se escribe el parser de la fase 5
- [ ] 0.2 Confirmar que el bucket de B2 acepta subidas (`python -m
      app.tareas.comprobar_almacenamiento` dentro del contenedor). La carga
      depende del control documental, que depende del bucket
- [ ] 0.3 Registrar la decisión sobre el texto de las ISO en el issue de las 9
      decisiones abiertas (#34), o abrir uno propio si se resuelve aparte

## 1. Aislamiento en la base

- [ ] 1.1 Escribir `db/NN_normativa_propia.sql` idempotente: `tenant_id uuid
      NULL` en `legal_norms` y `legal_articles`, con su índice
- [ ] 1.2 Habilitar `ROW LEVEL SECURITY` y `FORCE` en las dos tablas, con la
      política `tenant_id IS NULL OR tenant_id = current_tenant_id()` para
      lectura y `tenant_id = current_tenant_id()` en el `WITH CHECK`
- [ ] 1.3 Declarar los `GRANT` a `ambienta_app` en la misma migración: el bucle
      de `01_schema` corrió una vez y no alcanza a lo que nace después
- [ ] 1.4 Crear la tabla de candidatos con `tenant_id`, su RLS, sus GRANT, el
      vínculo a la norma y a la versión de documento, el fragmento de origen, su
      ubicación y el estado de revisión
- [ ] 1.5 Registrar la migración en **las cinco listas**: `docker-compose.yml`,
      `docker-compose.prod.yml`, `db/run.sh`, `db/README.md` y el bucle de
      `.github/workflows/ci.yml`
- [ ] 1.6 Contar `legal_norms` y `legal_articles` antes y después de aplicar. Si
      el número baja, la política está mal y se revierte
- [ ] 1.7 Prueba de aislamiento contra la base real: la empresa B no ve la norma
      ni los artículos propios de la empresa A, y las dos siguen viendo el
      catálogo compartido

## 2. Que lo existente no se lleve por delante lo propio

- [ ] 2.1 `services/bcn.py`: acotar la búsqueda de normas a adoptar a
      `tenant_id IS NULL`, con prueba de que una norma propia no se adopta ni se
      modifica al sincronizar
- [ ] 2.2 `services/normativa_aplicable.py`: excluir la normativa propia del
      cálculo por sector, con prueba
- [ ] 2.3 `services/sincronizar_matriz.py`: no retirar ni marcar «ya no
      aplicable» lo que tenga origen propio, con prueba de que sobrevive a un
      cambio de sector
- [ ] 2.4 Agregar el origen «propia de la empresa» a `matrix_norms` y a su
      lectura, sin reutilizar «agregada a mano»

## 3. API de normativa propia

- [ ] 3.1 Registrar una norma propia colgada de una `document_version`, con el
      permiso `catalog.write` que ya existe. Rechazar la que no traiga documento
- [ ] 3.2 Rechazar convertir en propia una norma del catálogo compartido
- [ ] 3.3 Escribir los artículos de una norma propia a mano, sin pasar por
      extracción
- [ ] 3.4 Incorporar una norma propia confirmada a la matriz de su empresa
- [ ] 3.5 Ejecutar los endpoints nuevos en pruebas que **llamen al handler**, no
      solo al servicio. Es la lección de `crm.py`: 26 llamadas con la firma
      equivocada y ninguna prueba fallando

## 4. Pantallas de carga y revisión

- [ ] 4.1 Pantalla de carga: subir el PDF por el control documental y registrar
      la norma propia con su tipo (RCA o ISO), número y fecha
- [ ] 4.2 Pantalla de revisión de candidatos, con el fragmento original y su
      ubicación **al lado** de cada propuesta
- [ ] 4.3 Aceptar, editar y descartar un candidato; el descartado conserva su
      motivo
- [ ] 4.4 Estado visible de la norma: cargada, en revisión, confirmada — y
      cuántos candidatos salieron de qué secciones
- [ ] 4.5 Distinguir en la matriz legal lo propio de lo que propuso el CORE
- [ ] 4.6 Pruebas de las dos pantallas afirmando sobre **texto visible**

## 5. Extracción (después de 0.1 y de las dos decisiones)

- [ ] 5.1 Elegir y agregar la dependencia de extracción de texto de PDF a la API
- [ ] 5.2 Extraer texto con su ubicación (página o sección) y un tope explícito
      de tamaño y páginas, que responde con un error legible al pasarse
- [ ] 5.3 Distinguir «no se pudo leer el documento» de «no se encontraron
      compromisos», con prueba sobre un PDF sin texto extraíble
- [ ] 5.4 Reglas de corte para RCA, contra los documentos reales de 0.1
- [ ] 5.5 Reglas de corte para ISO por cláusula numerada
- [ ] 5.6 Prueba de que la extracción **no crea** artículos ni obligaciones:
      romperla a propósito y confirmar que la prueba cae

## 6. Cierre

- [ ] 6.1 Decidir e implementar qué pasa con una RCA modificatoria
- [ ] 6.2 Comprobar la cadena completa contra el sistema levantado: cargar una
      RCA real, confirmar sus compromisos, evaluarlos, crear una obligación con
      vencimiento y ver que llega el aviso y sale en el reporte
- [ ] 6.3 Actualizar `CLAUDE.md`: la entrada del catálogo dice «catálogo global»
      y deja de ser toda la verdad
- [ ] 6.4 Archivar el cambio con `/opsx:archive` para que `openspec/specs/`
      refleje el sistema real
