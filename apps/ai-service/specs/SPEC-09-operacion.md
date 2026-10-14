# SPEC-09 · Operación

**Objetivo.** Que el AI Service se pueda levantar dentro del compose de Ambienta, configurar sin
tocar código, y que cualquier respuesta se pueda reconstruir después: qué se preguntó, qué se
buscó, qué se citó y cuánto costó.

## Alcance
- Estructura del paquete y dependencias.
- Configuración, contenedor, salud.
- Logs, trazas y métricas.
- CI.

## Fuera de alcance
- Despliegue productivo de Ambienta (lo define el equipo).
- Alertas y paneles: se definen cuando haya tráfico.

## Estructura

```
servicio/
  pyproject.toml
  Dockerfile
  migraciones/                 # SPEC-03, numeradas
  src/ambienta_ia/
    config.py                  # pydantic-settings
    api/                       # FastAPI: app, consulta, salud, dependencias
    identidad.py               # SPEC-02
    backend/                   # SPEC-01: cliente, errores, modelos generados
    conocimiento/              # SPEC-03: conexión, repositorio
    sincronizar/               # SPEC-04
    recuperacion/              # SPEC-05
    agente/                    # SPEC-06: grafo, herramientas, guardrails, verificación de citas
    consulta.py                # SPEC-07
    proveedores/               # embeddings y modelo de lenguaje, detrás de una interfaz
    evaluar/                   # SPEC-08
    observabilidad.py
  tests/
    unit/  contrato/  integracion/  evaluacion/
  evaluacion/dorado.jsonl
```

## Reglas

| Regla | Motivo |
|---|---|
| Toda configuración por variables de entorno, validadas al arrancar. Si falta una obligatoria, el servicio no arranca | Mejor no arrancar que arrancar a medias |
| Ningún secreto en el repositorio, en logs ni en trazas. `.env.ejemplo` con nombres y sin valores | Handoff §2: el repositorio del backend es público |
| `GET /salud` responde si el proceso vive; `GET /listo` además comprueba la base y el backend | Distinguir "reiniciar" de "esperar" |
| Logs en JSON, uno por evento, con `request_id`, `tenant_id` y `conversation_id`. Nunca el texto de documentos privados ni el token | — |
| Una traza por consulta: pregunta, modo de búsqueda, fragmentos con similitud, herramientas con duración, modelo, tokens, costo, latencia, `se_abstuvo` y motivo | Es lo que permite explicar una respuesta |
| Pool de conexiones a la base y cliente HTTP reutilizado; nada abre una conexión por consulta | El código actual abre una por búsqueda |
| Imagen sin root, con `HEALTHCHECK` sobre `/salud` | — |
| En el compose de Ambienta, el AI Service está en la misma red que la API y no se publica al exterior: el frontend lo alcanza por la API o por el proxy que definan | Evita el tema de `CORS_ORIGINS` del handoff §9 |

## Variables

| Variable | Obligatoria | Uso |
|---|---|---|
| `BACKEND_URL` | sí | Base de la API de Ambienta |
| `CLERK_JWKS_URL` | no | Presente = producción; ausente = modo desarrollo |
| `CLERK_ISSUER` | con Clerk | Validación del `iss` |
| `DATABASE_URL_CONSULTA` / `DATABASE_URL_SINCRONIZADOR` | sí | Los dos roles de SPEC-03 |
| `SERVICIO_TOKEN` | para sincronizar | Token de la cuenta `servicio_lectura` |
| `PROVEEDOR_LLM`, `MODELO_LLM`, `PROVEEDOR_EMBEDDINGS`, `MODELO_EMBEDDINGS`, `DIMENSION_EMBEDDINGS` | sí | Decisiones A y B del plan |
| `UMBRAL_EVIDENCIA`, `K_RECUPERACION`, `MAX_HERRAMIENTAS`, `MAX_TOKENS_CONSULTA` | no | Calibrados con SPEC-08 |
| `TRAZAS_*` | no | Destino de trazas (LangSmith u OpenTelemetry) |

## CI

| Job | Cuándo | Qué |
|---|---|---|
| `calidad` | cada PR | ruff, mypy, pytest `unit` y `contrato` |
| `integracion` | cada PR | pytest `integracion` con PostgreSQL + pgvector en servicio y backend simulado |
| `evaluacion-recuperacion` | cada PR | SPEC-08 sin modelo de lenguaje, con umbrales |
| `evaluacion-completa` | rama principal | SPEC-08 con modelo y juez |
| `contrato-backend` | diario | Baja el `openapi.json` del backend y falla si los modelos generados cambian |

## Criterios de aceptación

```gherkin
# language: es
Característica: Se levanta, se configura y se explica

  Escenario: Falta configuración
    Dado que BACKEND_URL no está definida
    Cuando arranca el servicio
    Entonces termina con un error que nombra BACKEND_URL

  Escenario: Listo solo cuando puede trabajar
    Dado que la base responde y el backend no
    Cuando se pide /listo
    Entonces la respuesta es 503 y dice que el backend no responde
    Y /salud responde 200

  Escenario: Una consulta se reconstruye desde su traza
    Cuando se responde una consulta
    Entonces existe una traza con la pregunta, los fragmentos con su similitud, las herramientas, los tokens y se_abstuvo

  Escenario: Nada sensible en los logs
    Cuando se responde una consulta que usó un documento privado
    Entonces ningún log contiene el token ni el texto del documento

  Escenario: Levantarlo junto a Ambienta
    Dado el compose de Ambienta con el servicio ai-service agregado
    Cuando se corre docker compose up
    Entonces /listo del AI Service responde 200
    Y la sincronización inicial deja el catálogo indexado
```

## Pruebas
- Escenarios 1, 2 y 4 en `unit` e `integracion`.
- Escenario 3 con un exportador de trazas en memoria.
- Escenario 5 es la prueba de humo de la fase 6, manual la primera vez y después en CI.

## Implementación (20/09/2026)

Implementado: `servicio/Dockerfile`, `servicio/compose.yml` (todo el circuito en local, sin
claves), `servicio/compose.ambienta.yml` (fragmento para el monorepo),
`.github/workflows/servicio.yml` y `servicio/.env.ejemplo`. El compose de demo se levantó y
respondió de punta a punta el 20/09/2026. Los puertos del host se cambian con `PUERTO_IA` y
`PUERTO_BACKEND`.

Diferencias con la tabla de CI de arriba: todavía no corren `mypy` ni el job diario
`contrato-backend` (necesita la URL del `openapi.json` del backend), y la evaluación con modelo
y juez en la rama principal queda para cuando esté elegido el proveedor. Lo que sí corre en cada
PR: ruff, pruebas unitarias, validación del contrato OpenAPI, integración con pgvector,
evaluación de recuperación con umbrales, y el build de la imagen.
