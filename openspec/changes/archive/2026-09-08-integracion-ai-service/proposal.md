# Proposal: Lo que el backend le debe al AI Service

Fuente: *Informe de requerimientos Backend para integración del AI Service*,
del encargado de la épica #24. Este cambio cubre **sólo el lado del backend**:
el endpoint de consulta del chatbot es del AI Service y no entra acá, como el
propio informe dice.

## Lo que se midió antes de empezar

El informe parte de tres premisas que hoy **no son ciertas**, y conviene
corregirlas antes de construir sobre ellas:

| lo que dice el informe | lo medido el 8-sep-2026 |
|---|---|
| *«Las tablas legales se encuentran sin datos porque la ingesta desde la BCN está bloqueada por la autenticación de Ley Chile»* | **Falso desde el 26-ago.** Hay **24 normas y 689 artículos**; la Ley 19.300 con su versión vigente de 2024-04-10. El 401 era la cabecera de navegador, no una credencial |
| *«existe búsqueda full-text en español sobre los artículos»* | A medias. La búsqueda FTS se construyó el 7-sep (#76) y cubre **título y código**, no el **texto del articulado** |
| *«el AI Service no dispone de una forma segura de obtener el archivo»* | El enlace firmado **ya existe**: `GET /documents/{id}/versions/{version_id}/download-url`, con expiración y aislamiento por RLS |

Lo demás del informe sí describe huecos reales, verificados uno por uno:
`updated_since` no aparece en ningún archivo del backend, no hay endpoint de
versiones de una norma, el articulado sólo se sirve en su versión vigente, y las
cabeceras de paginación se emiten sin estar declaradas en el contrato.

## Lo que se implementa

1. **`updated_since`** en `/catalog/norms` y `/documents/`. Sin él, cada ciclo
   de indexación descarga el catálogo entero para comparar en local.
2. **`GET /catalog/norms/{norm_id}/versions`** — el historial que el modelo ya
   guarda y ninguna ruta exponía.
3. **Articulado por fecha**: `vigente_el` en el endpoint de artículos, que hoy
   sólo sirve el texto marcado `is_current`.
4. **El checksum en el enlace de descarga.** Es lo único que le falta al
   endpoint que ya existe para cumplir los criterios del informe: hoy hay que
   pedirlo aparte, y entre las dos llamadas la revisión puede cambiar.
5. **`X-Has-More` y `X-Page-Limit` declaradas** en el contrato.
6. **`X-Tenant-Id` descrita como lo que es**: el respaldo de desarrollo, no el
   mecanismo de producción.

## La corrección de ruta que NO se hace

El informe propone `GET /documents/{id}/versions/{version}/download`. El
endpoint real es `.../{version_id}/download-url` y **se queda como está**:
renombrarlo rompería la pantalla de documentos, que ya lo llama, y la diferencia
es de nombre, no de capacidad. Lo que se corrige es la documentación, para que
el AI Service apunte a la ruta que existe.

## Lo que NO entra, y por qué

- **Búsqueda semántica ni indexación.** `pgvector` está instalado y no lo usa
  nadie; construir el índice RAG es del AI Service, y el informe lo dice.
- **FTS sobre el texto del articulado.** No lo pide el informe y es una decisión
  de costo aparte: 689 artículos con su texto completo es otro orden de
  magnitud que buscar títulos.
- **Las tres definiciones del punto 5** —cómo se autentica el AI Service, dónde
  vive, qué datos son reales—. No son técnicas y no las decide este cambio.
  Sobre la primera, el sistema ya tiene un rol `servicio_lectura` pensado
  exactamente para integraciones, y conviene evaluarlo antes de inventar otro
  mecanismo.
