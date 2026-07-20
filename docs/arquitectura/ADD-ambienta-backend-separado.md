# ADD — Ambienta: Arquitectura Backend Separado
**Documento:** Architecture Design Document v1.0  
**Fecha:** 2026-06-01  
**Autor:** Arquitectura de Software — Ambienta  
**Estado:** Draft para revisión técnica  
**Clasificación:** Confidencial

---

## Control de documento

| Versión | Fecha | Autor | Cambios |
|---|---|---|---|
| 0.1 | 2026-06-01 | Arq. Ambienta | Borrador inicial |
| 1.0 | 2026-06-01 | Arq. Ambienta | Primera versión completa |

---

## 1. Introducción

### 1.1 Propósito
Este documento define la arquitectura de **Ambienta** bajo el patrón **Backend Separado** — frontend desacoplado del API, con servicios independientes para IA, notificaciones y procesamiento asíncrono. Aplica Clean Architecture, diseño orientado a dominio (DDD táctico) y principios de API-first.

### 1.2 Por qué backend separado
Esta arquitectura es elegida cuando:
- El equipo necesita escalar frontend y backend de forma independiente
- Se planea construir una app móvil nativa que consuma la misma API
- El backend debe ser consumible por sistemas externos (ERP, integraciones de cliente)
- El procesamiento IA y las notificaciones requieren recursos distintos al servidor web

### 1.3 Diferencias clave respecto al Monolito Modular

| Aspecto | Monolito Modular | Backend Separado |
|---|---|---|
| Deployables | 1 | 4 (web, api, ai-service, worker) |
| Comunicación inter-módulo | Llamada de función | HTTP / tRPC |
| Complejidad inicial | Baja | Media-alta |
| Escalabilidad independiente | Parcial | Total |
| API pública disponible | No (Server Actions) | Sí (desde día 1) |
| Ideal desde | MVP | ≥ 3 devs o app móvil planeada |

---

## 2. Visión general del sistema

### 2.1 Diagrama de servicios

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLIENTES                                       │
│         Browser Web  ·  App Móvil (futuro)  ·  Webhooks                 │
└──────────────┬─────────────────────────────────────────────────────────┘
               │ HTTPS
┌──────────────▼──────────────┐
│   apps/web                  │  Next.js 15 — solo UI y BFF
│   (Frontend)                │  Server Components + tRPC Client
│   Vercel / CDN              │
└──────────────┬──────────────┘
               │ tRPC over HTTP  (JWT en Authorization header)
┌──────────────▼──────────────┐      ┌──────────────────────────────────┐
│   apps/api                  │─────▶│   apps/ai-service                │
│   (Backend API)             │      │   (Python FastAPI + LangGraph)   │
│   Fastify + tRPC            │      │   Qwen3 via Ollama               │
│   Railway / AWS ECS         │      │   RAG + pgvector                 │
└──────┬──────────────────────┘      └──────────────────────────────────┘
       │
       ├──────────────────────────────▶ PostgreSQL 16 + pgvector
       ├──────────────────────────────▶ Redis 7
       ├──────────────────────────────▶ S3 / Cloudflare R2
       │
       └─────────▶ apps/notification-worker (BullMQ)
                        └──▶ Resend (email)
                        └──▶ WebSocket / SSE (in-app)
```

### 2.2 Principios de diseño

1. **API-first:** el backend es agnóstico del cliente — el mismo API sirve a web, móvil y terceros.
2. **Type-safe end-to-end:** tRPC garantiza tipos desde el server hasta el cliente sin code generation.
3. **Servicios por responsabilidad:** IA en Python (mejor ecosistema ML), API en Node.js (mejor ecosistema JS/TypeScript), worker separado para jobs sin afectar latencia del API.
4. **Shared packages:** el dominio, tipos y esquema DB se comparten entre servicios vía workspaces.
5. **Observabilidad desde el inicio:** trazas distribuidas, logs estructurados y métricas en todos los servicios.

---

## 3. Estructura del repositorio (Turborepo monorepo)

```
ambienta/
├── apps/
│   ├── web/                     # Next.js 15 — frontend puro
│   │   ├── app/
│   │   │   ├── (auth)/
│   │   │   └── (dashboard)/
│   │   │       ├── declaraciones/
│   │   │       ├── calendario/
│   │   │       ├── obligaciones/
│   │   │       ├── plantas/
│   │   │       ├── usuarios/
│   │   │       ├── reportes/
│   │   │       └── ambi/        # Chat con AmbiAgent
│   │   └── src/
│   │       ├── lib/
│   │       │   └── trpc.ts      # tRPC client + React Query provider
│   │       └── components/
│   │
│   ├── api/                     # Fastify + tRPC server
│   │   └── src/
│   │       ├── domain/          # ← Copia/symlink de packages/domain
│   │       ├── application/
│   │       │   ├── use-cases/
│   │       │   └── services/
│   │       ├── infrastructure/
│   │       │   ├── db/          # Drizzle repositories
│   │       │   ├── adapters/    # External services
│   │       │   └── queue/       # BullMQ producers
│   │       ├── routers/         # tRPC routers por dominio
│   │       │   ├── declarations.router.ts
│   │       │   ├── obligations.router.ts
│   │       │   ├── plants.router.ts
│   │       │   ├── users.router.ts
│   │       │   └── reports.router.ts
│   │       ├── middleware/
│   │       │   ├── auth.ts      # JWT validation
│   │       │   ├── tenant.ts    # Tenant context injection
│   │       │   └── rbac.ts      # CASL permission check
│   │       └── server.ts        # Fastify app entry point
│   │
│   ├── ai-service/              # Python FastAPI — servicio IA
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── agent/
│   │   │   │   ├── ambi_agent.py        # LangGraph agent
│   │   │   │   ├── tools.py             # Agent tools
│   │   │   │   └── prompts.py
│   │   │   ├── rag/
│   │   │   │   ├── ingestor.py          # Document ingestion
│   │   │   │   ├── retriever.py         # Hybrid search
│   │   │   │   └── embedder.py          # Ollama embeddings
│   │   │   ├── adapters/
│   │   │   │   ├── ollama_adapter.py
│   │   │   │   ├── bcn_adapter.py
│   │   │   │   └── sma_adapter.py
│   │   │   └── routers/
│   │   │       ├── chat.py              # POST /chat (streaming)
│   │   │       ├── ingest.py            # POST /ingest
│   │   │       └── health.py
│   │   └── requirements.txt
│   │
│   └── notification-worker/     # Node.js BullMQ worker
│       └── src/
│           ├── workers/
│           │   ├── deadline.worker.ts
│           │   ├── approval.worker.ts
│           │   └── weekly-digest.worker.ts
│           ├── templates/        # React Email
│           └── index.ts
│
├── packages/
│   ├── domain/                  # Entidades y puertos (TypeScript puro)
│   │   ├── entities/
│   │   ├── value-objects/
│   │   ├── events/
│   │   └── ports/
│   ├── db/                      # Drizzle schema + migrations
│   │   ├── schema/
│   │   │   ├── declarations.ts
│   │   │   ├── obligations.ts
│   │   │   ├── plants.ts
│   │   │   └── users.ts
│   │   └── migrations/
│   ├── trpc/                    # Router types compartidos (type-safe)
│   │   └── index.ts             # AppRouter type exported
│   ├── permissions/             # CASL ability builder compartido
│   │   └── index.ts
│   ├── email/                   # React Email templates
│   │   └── templates/
│   └── types/                   # DTOs y tipos compartidos
│
├── turbo.json
└── package.json                 # Workspaces
```

---

## 4. Backend API — Fastify + tRPC

### 4.1 Setup del servidor

```typescript
// apps/api/src/server.ts
import Fastify from 'fastify';
import { fastifyTRPCPlugin } from '@trpc/server/adapters/fastify';
import { createContext } from './context';
import { appRouter } from './routers';

const app = Fastify({ logger: true });

// Plugins
await app.register(fastifyCors, { origin: process.env.WEB_URL });
await app.register(fastifyHelmet);
await app.register(fastifyRateLimit, { max: 100, timeWindow: '1 minute' });

// tRPC
await app.register(fastifyTRPCPlugin, {
  prefix: '/trpc',
  trpcOptions: {
    router: appRouter,
    createContext,
    onError: ({ path, error }) => {
      logger.error({ path, error }, 'tRPC error');
    },
  },
});

// REST endpoints para webhooks externos
app.register(webhookRoutes, { prefix: '/webhooks' });
app.register(healthRoutes, { prefix: '/health' });

await app.listen({ port: 4000, host: '0.0.0.0' });
```

### 4.2 Contexto de request (tenant + RBAC)

```typescript
// apps/api/src/context.ts
export async function createContext({ req }: CreateFastifyContextOptions): Promise<Context> {
  const token = req.headers.authorization?.replace('Bearer ', '');

  if (!token) return { session: null };

  const session = await verifyJWT(token);
  const ability = buildAbility(session); // CASL

  return {
    session,
    ability,
    tenantId: session.tenantId,
    userId: session.userId,
    role: session.role,
    plantIds: session.plantIds,
    db,       // Drizzle client
    redis,    // Redis client
  };
}
```

### 4.3 Routers tRPC

```typescript
// apps/api/src/routers/declarations.router.ts
import { z } from 'zod';
import { router, protectedProcedure, plantScopedProcedure } from '../trpc';
import { TRPCError } from '@trpc/server';
import { subject } from '@casl/ability';

export const declarationsRouter = router({

  list: protectedProcedure
    .input(z.object({
      plantId: z.string().optional(),
      estado: DeclarationStatusSchema.optional(),
      periodo: z.string().optional(),
      cursor: z.string().optional(),
      limit: z.number().min(1).max(100).default(20),
    }))
    .query(async ({ input, ctx }) => {
      // RBAC: filtrar por plantas autorizadas
      const allowedPlantIds = ctx.role === 'superadmin' || ctx.role === 'admin_corporativo'
        ? undefined  // Sin filtro = todas las plantas
        : ctx.plantIds;

      return declarationRepo.findPaginated({
        tenantId: ctx.tenantId,
        plantIds: allowedPlantIds,
        ...input,
      });
    }),

  submit: protectedProcedure
    .input(z.object({ declarationId: z.string() }))
    .mutation(async ({ input, ctx }) => {
      const declaration = await declarationRepo.findById(input.declarationId, ctx.tenantId);

      if (!declaration) throw new TRPCError({ code: 'NOT_FOUND' });

      // Verificar que el usuario puede operar esta planta
      if (!ctx.ability.can('submit', subject('Declaration', declaration))) {
        throw new TRPCError({ code: 'FORBIDDEN' });
      }

      const useCase = new SubmitDeclarationUseCase(declarationRepo, eventBus);
      await useCase.execute({ declarationId: input.declarationId, ...ctx });

      return { success: true };
    }),

  approve: protectedProcedure
    .input(z.object({ declarationId: z.string(), comentario: z.string().optional() }))
    .mutation(async ({ input, ctx }) => {
      const declaration = await declarationRepo.findById(input.declarationId, ctx.tenantId);

      if (!ctx.ability.can('approve', subject('Declaration', declaration))) {
        throw new TRPCError({ code: 'FORBIDDEN', message: 'Solo jefes de operaciones y superiores pueden aprobar' });
      }

      const useCase = new ApproveDeclarationUseCase(declarationRepo, notificationQueue, eventBus);
      return useCase.execute({ ...input, approverId: ctx.userId, tenantId: ctx.tenantId });
    }),

  getComplianceReport: protectedProcedure
    .input(z.object({ periodo: z.string(), plantId: z.string().optional() }))
    .query(async ({ input, ctx }) => {
      const useCase = new GenerateComplianceReportUseCase(obligationRepo, declarationRepo);
      return useCase.execute({ ...input, tenantId: ctx.tenantId, userPlantIds: ctx.plantIds, role: ctx.role });
    }),
});
```

### 4.4 Frontend — tRPC client (Next.js)

```typescript
// apps/web/src/lib/trpc.ts
import { createTRPCReact } from '@trpc/react-query';
import type { AppRouter } from '@ambienta/trpc';
import { httpBatchLink } from '@trpc/client';

export const trpc = createTRPCReact<AppRouter>();

export function TRPCProvider({ children }: PropsWithChildren) {
  const [queryClient] = useState(() => new QueryClient());
  const [trpcClient] = useState(() =>
    trpc.createClient({
      links: [
        httpBatchLink({
          url: `${process.env.NEXT_PUBLIC_API_URL}/trpc`,
          async headers() {
            const session = await getSession();
            return { Authorization: `Bearer ${session?.token}` };
          },
        }),
      ],
    })
  );
  return (
    <trpc.Provider client={trpcClient} queryClient={queryClient}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </trpc.Provider>
  );
}

// Uso en componente:
export function DeclaracionesList({ plantId }: { plantId: string }) {
  const { data, isLoading } = trpc.declarations.list.useQuery({ plantId });
  const submitMutation = trpc.declarations.submit.useMutation();

  return (/* ... */);
}
```

---

## 5. Servicio IA — Python FastAPI + LangGraph

### 5.1 ¿Por qué Python para el servicio IA?
El ecosistema de IA en Python es significativamente más maduro: LangChain, LangGraph, Ollama Python SDK, sentence-transformers, PyMuPDF para PDFs, y todas las herramientas de procesamiento de documentos. El servicio IA se comunica con el API Node.js vía HTTP interno.

```python
# apps/ai-service/app/main.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from .routers import chat, ingest, health

app = FastAPI(title="Ambienta AI Service", version="1.0.0")
app.include_router(chat.router, prefix="/chat")
app.include_router(ingest.router, prefix="/ingest")
app.include_router(health.router, prefix="/health")
```

### 5.2 AmbiAgent — LangGraph

```python
# apps/ai-service/app/agent/ambi_agent.py
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_ollama import ChatOllama
from .tools import get_ambi_tools

SYSTEM_PROMPT = """Eres AmbiAgent, el asistente experto en cumplimiento ambiental de Ambienta.
Ayudas a ingenieros ambientales chilenos a gestionar obligaciones regulatorias:
RETC, Ley REP (20.920), SINADER, SIDREP, DAE, Ley Marco Cambio Climático (21.455).

Principios de respuesta:
- Preciso y técnico. Usa terminología ambiental chilena correcta.
- Cita siempre la fuente normativa (número de ley, artículo, DS).
- Si no tienes certeza, lo dices. No inventes datos regulatorios.
- Sugiere acciones concretas cuando detectes riesgo de incumplimiento.
- Si el usuario está próximo a un vencimiento, alértalo proactivamente."""

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    tenant_id: str
    user_id: str
    plant_ids: list[str]
    role: str

def build_ambi_graph(tools: list):
    llm = ChatOllama(
        model="qwen3:14b-q4_K_M",
        base_url=settings.OLLAMA_HOST,
        temperature=0.2,
        num_ctx=8192,
    )
    llm_with_tools = llm.bind_tools(tools)

    def call_llm(state: AgentState):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        return "tools" if last.tool_calls else END

    graph = StateGraph(AgentState)
    graph.add_node("agent", call_llm)
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")
    return graph.compile()

# apps/ai-service/app/routers/chat.py
@router.post("/stream")
async def chat_stream(request: ChatRequest, ctx: AgentContext = Depends(get_agent_context)):
    tools = get_ambi_tools(ctx)
    graph = build_ambi_graph(tools)

    async def generate():
        async for event in graph.astream_events(
            {"messages": request.messages, **ctx.dict()},
            version="v2"
        ):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"].content
                if chunk:
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
            elif event["event"] == "on_tool_end":
                yield f"data: {json.dumps({'tool_result': event['data']['output']})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 5.3 RAG Pipeline

```python
# apps/ai-service/app/rag/ingestor.py
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
import psycopg2
from pgvector.psycopg2 import register_vector

class RegulatoryIngestor:
    def __init__(self):
        self.embedder = OllamaEmbeddings(
            model="nomic-embed-text",
            base_url=settings.OLLAMA_HOST
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=51,
            separators=["Artículo", "\n\n", "\n", " "],
        )

    async def ingest_bcn_document(self, normativa_id: str, texto: str, metadata: dict):
        chunks = self.splitter.create_documents([texto])

        for chunk in chunks:
            embedding = await self.embedder.aembed_query(chunk.page_content)

            await db.execute("""
                INSERT INTO regulatory_chunks
                    (content, embedding, normativa_id, normativa_codigo, fuente, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (normativa_id, chunk_hash) DO UPDATE
                SET content = EXCLUDED.content, embedding = EXCLUDED.embedding
            """, chunk.page_content, embedding, normativa_id,
                metadata['codigo'], 'BCN', json.dumps(metadata))

# apps/ai-service/app/rag/retriever.py
class HybridRetriever:
    async def search(self, query: str, limit: int = 5, filters: dict = None) -> list[RegulatoryChunk]:
        query_embedding = await self.embedder.aembed_query(query)

        # Búsqueda híbrida: cosine similarity + tsvector full-text
        results = await db.fetch("""
            WITH vector_search AS (
                SELECT id, content, metadata,
                    1 - (embedding <=> $1::vector) AS vector_score
                FROM regulatory_chunks
                WHERE ($3::text IS NULL OR normativa_codigo = $3)
                ORDER BY embedding <=> $1::vector
                LIMIT 20
            ),
            text_search AS (
                SELECT id,
                    ts_rank(to_tsvector('spanish', content),
                            plainto_tsquery('spanish', $2)) AS text_score
                FROM regulatory_chunks
                WHERE to_tsvector('spanish', content) @@ plainto_tsquery('spanish', $2)
                LIMIT 20
            )
            SELECT vs.id, vs.content, vs.metadata,
                (vs.vector_score * 0.7 + COALESCE(ts.text_score, 0) * 0.3) AS hybrid_score
            FROM vector_search vs
            LEFT JOIN text_search ts ON vs.id = ts.id
            ORDER BY hybrid_score DESC
            LIMIT $4
        """, query_embedding, query, filters.get('normativa_codigo'), limit)

        return [RegulatoryChunk(**r) for r in results]
```

---

## 6. Worker de notificaciones

```typescript
// apps/notification-worker/src/workers/deadline.worker.ts
import { Worker, QueueScheduler } from 'bullmq';
import { render } from '@react-email/render';
import { Resend } from 'resend';
import { DeadlineReminderEmail } from '@ambienta/email';

const resend = new Resend(process.env.RESEND_API_KEY);

// Worker: procesa jobs de email transaccional
export const emailWorker = new Worker('email-transactional',
  async (job) => {
    const { template, to, data } = job.data;

    const html = render(getTemplate(template, data));

    const { error } = await resend.emails.send({
      from: 'Ambienta <alertas@ambienta.cl>',
      to,
      subject: getSubject(template, data),
      html,
    });

    if (error) throw new Error(`Email send failed: ${error.message}`);
  },
  {
    connection: redis,
    concurrency: 10,
    limiter: { max: 50, duration: 60_000 }, // 50 emails/minuto
  }
);

// Scheduler: genera jobs de recordatorio cada día a las 8 AM
const deadlineScheduler = new Worker('cron',
  async (job) => {
    if (job.name !== 'daily-deadline-check') return;

    const ALERT_WINDOWS = [15, 7, 3, 1]; // días antes del vencimiento
    const obligations = await fetchObligationsWithUpcomingDeadlines(ALERT_WINDOWS);

    for (const ob of obligations) {
      const daysUntil = differenceInDays(ob.proximaFecha, new Date());

      await emailTransactionalQueue.add('deadline-reminder', {
        template: 'deadline-reminder',
        to: ob.responsable.email,
        data: {
          nombre: ob.responsable.nombre,
          normativa: ob.normativa.nombre,
          planta: ob.planta.nombre,
          diasRestantes: daysUntil,
          fechaLimite: format(ob.proximaFecha, 'dd/MM/yyyy'),
          urlDeclaracion: `${process.env.WEB_URL}/declaraciones/${ob.id}`,
        }
      }, {
        deduplication: {
          id: `deadline-${ob.id}-${daysUntil}d-${format(new Date(), 'yyyy-MM-dd')}`
        }
      });

      // También notificar al jefe de operaciones asignado
      if (ob.revisor && daysUntil <= 7) {
        await emailTransactionalQueue.add('deadline-reminder-supervisor', {
          template: 'deadline-supervisor',
          to: ob.revisor.email,
          data: { ...ob, diasRestantes: daysUntil }
        });
      }
    }
  },
  { connection: redis }
);

// Cron: ejecutar cada día a las 8:00 AM (hora Chile, UTC-3 = 11:00 UTC)
await new QueueScheduler('cron', { connection: redis });
await cronQueue.add('daily-deadline-check', {}, {
  repeat: { cron: '0 11 * * *' },  // 8 AM Santiago
  removeOnComplete: true,
});
```

---

## 7. Integración con APIs públicas

### 7.1 Sync programado con BCN

```python
# apps/ai-service/app/adapters/bcn_adapter.py
import httpx
from datetime import datetime

NORMATIVAS_RELEVANTES = {
    'LEY_REP':    '1141102',  # Ley 20.920 REP
    'LEY_BASES':  '19300',    # Ley de Bases MA
    'LEY_CC':     '1171542',  # Ley Marco CC 21.455
    'DS_SINADER': '148',      # DS 148 SINADER
    'DS_DAE':     '6',        # DS 6 DAE
}

class BCNAdapter:
    BASE_URL = "https://www.bcn.cl/leychile/consulta/legislacion_abierta_web_service"

    async def fetch_law(self, id_norma: str) -> BCNDocument:
        async with httpx.AsyncClient() as client:
            r = await client.get(self.BASE_URL, params={
                'idNorma': id_norma,
                'tipo_doc': 'json',
            }, timeout=30.0)
            r.raise_for_status()
            return BCNDocument(**r.json())

    async def sync_all_relevant_normativas(self):
        """Sync diario: ingesta las normativas relevantes al RAG"""
        for codigo, id_norma in NORMATIVAS_RELEVANTES.items():
            doc = await self.fetch_law(id_norma)
            await ingestor.ingest_bcn_document(
                normativa_id=id_norma,
                texto=doc.texto_norma,
                metadata={'codigo': codigo, 'titulo': doc.titulo, 'fuente': 'BCN'}
            )
```

### 7.2 SNIFA — Historial de sanciones

```python
# apps/ai-service/app/adapters/sma_adapter.py
class SMAAdapter:
    BASE_URL = "https://snifa.sma.gob.cl/DatosAbiertos"

    async def get_sanction_history(self, rut: str) -> list[SMAExpediente]:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.BASE_URL}/expedientes",
                params={'rut': rut, 'formato': 'json'}, timeout=30.0)
            r.raise_for_status()
            return [SMAExpediente(**e) for e in r.json()]

    async def get_monitoring_data(self, ufe_id: str, fecha_desde: str) -> list[dict]:
        """UFE = Unidad Fiscalizable de Emisiones"""
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.BASE_URL}/monitoreo",
                params={'id_ufe': ufe_id, 'fecha_desde': fecha_desde, 'formato': 'json'})
            return r.json()
```

---

## 8. Infraestructura — Docker Compose completo

```yaml
# docker-compose.yml
version: '3.9'

services:
  # ── FRONTEND ──────────────────────────────────────────────
  web:
    build: ./apps/web
    ports: ["3000:3000"]
    environment:
      NEXT_PUBLIC_API_URL: http://api:4000
    depends_on: [api]

  # ── BACKEND API ────────────────────────────────────────────
  api:
    build: ./apps/api
    ports: ["4000:4000"]
    environment:
      DATABASE_URL: postgresql://ambienta:${DB_PASSWORD}@db:5432/ambienta
      REDIS_URL: redis://redis:6379
      JWT_SECRET: ${JWT_SECRET}
      AI_SERVICE_URL: http://ai-service:8000
      STORAGE_BUCKET: ambienta-documents
    depends_on: [db, redis]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4000/health"]
      interval: 30s
      retries: 3

  # ── AI SERVICE ─────────────────────────────────────────────
  ai-service:
    build: ./apps/ai-service
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://ambienta:${DB_PASSWORD}@db:5432/ambienta
      OLLAMA_HOST: http://ollama:11434
      OLLAMA_MODEL: qwen3:14b-q4_K_M
      EMBED_MODEL: nomic-embed-text
    depends_on: [db, ollama]

  # ── NOTIFICATION WORKER ─────────────────────────────────────
  notification-worker:
    build: ./apps/notification-worker
    environment:
      DATABASE_URL: postgresql://ambienta:${DB_PASSWORD}@db:5432/ambienta
      REDIS_URL: redis://redis:6379
      RESEND_API_KEY: ${RESEND_API_KEY}
      WEB_URL: https://app.ambienta.cl
    depends_on: [db, redis]
    deploy:
      replicas: 2  # Dos workers en paralelo

  # ── OLLAMA (LLM) ────────────────────────────────────────────
  ollama:
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    volumes:
      - ollama_models:/root/.ollama
    environment:
      OLLAMA_KEEP_ALIVE: "24h"
      OLLAMA_NUM_PARALLEL: "2"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  # ── DATABASE ────────────────────────────────────────────────
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: ambienta
      POSTGRES_USER: ambienta
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./packages/db/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ambienta"]
      interval: 10s

  # ── REDIS ───────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data

  # ── BULL BOARD (monitoreo de colas) ─────────────────────────
  bull-board:
    image: deadly0/bull-board:latest
    ports: ["3001:3000"]
    environment:
      REDIS_HOST: redis
      REDIS_PORT: "6379"

volumes:
  pgdata:
  redis_data:
  ollama_models:
```

---

## 9. Base de datos — extensiones y vectores

```sql
-- packages/db/init.sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";        -- pgvector para embeddings
CREATE EXTENSION IF NOT EXISTS "pg_trgm";       -- búsqueda de texto difuso
CREATE EXTENSION IF NOT EXISTS "unaccent";      -- búsqueda sin tildes

-- Tabla de chunks para RAG
CREATE TABLE regulatory_chunks (
    id           uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    normativa_id text NOT NULL,
    normativa_codigo text NOT NULL,
    content      text NOT NULL,
    embedding    vector(768),          -- nomic-embed-text = 768 dims
    chunk_hash   text GENERATED ALWAYS AS (md5(content)) STORED,
    fuente       text,                 -- 'BCN' | 'MMA' | 'SMA' | 'manual'
    metadata     jsonb DEFAULT '{}',
    created_at   timestamptz DEFAULT now(),
    UNIQUE (normativa_id, chunk_hash)
);

-- Índice HNSW para búsqueda vectorial eficiente
CREATE INDEX idx_chunks_embedding ON regulatory_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Índice full-text para búsqueda híbrida
CREATE INDEX idx_chunks_fts ON regulatory_chunks
    USING gin (to_tsvector('spanish', content));

-- Row Level Security para declaraciones
ALTER TABLE declaraciones ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON declaraciones
    USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

---

## 9b. Módulo de Cumplimiento Legal — Modelo de datos validado

> **Fuente de validación (2026-06-01):** Análisis de matriz de cumplimiento real de empresa del sector ambiental nacional (confidencial), v8 (2024-10-16). ~5.000 artículos evaluados × ~30 instalaciones. El modelo está alineado con la estructura operacional real del mercado.

### 9b.1 Tablas SQL del módulo de cumplimiento

```sql
-- packages/db/schema/cumplimiento.sql

CREATE TYPE tipo_documento AS ENUM (
  'NCh', 'Ley', 'Decreto', 'DFL', 'Constitución',
  'Circular', 'Resolución', 'Ordenanza', 'Autorización', 'Guía'
);

CREATE TYPE ambito_aplicacion AS ENUM ('SSO', 'MA', 'SSOMA', 'SIG', 'DTP');

CREATE TYPE respuesta_cumplimiento AS ENUM ('SI', 'NO', 'N/A', 'N/E');

CREATE TYPE frecuencia_evaluacion AS ENUM (
  'Anual', 'Semestral', 'Mensual', 'PorEvento', 'Continua'
);

-- Catálogo maestro de requisitos legales (compartido entre tenants)
CREATE TABLE requisitos_legales (
  id                        uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tipo_documento            tipo_documento NOT NULL,
  codigo_numero             text NOT NULL,
  nombre                    text NOT NULL,
  ambito                    ambito_aplicacion NOT NULL,
  entidad_emisora           text,
  anio_publicacion          int,
  fecha_ultima_actualizacion date,
  alcance                   text NOT NULL DEFAULT 'Transversal', -- Transversal | PorInstalacion
  criticidad                int NOT NULL DEFAULT 1,              -- 1=Alta 2=Media 3=Baja
  vigente                   boolean NOT NULL DEFAULT true,
  created_at                timestamptz DEFAULT now(),
  updated_at                timestamptz DEFAULT now(),
  UNIQUE (tipo_documento, codigo_numero)
);

-- Artículos / cláusulas de cada requisito (unidad mínima de evaluación)
CREATE TABLE articulos_requisito (
  id                    uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  requisito_id          uuid NOT NULL REFERENCES requisitos_legales(id),
  numero                text NOT NULL,          -- "Art. 22", "Cláusula 4.1"
  descripcion           text NOT NULL,
  medidas_verificacion  text,                   -- Qué documento/registro lo acredita
  frecuencia            frecuencia_evaluacion NOT NULL DEFAULT 'Anual',
  created_at            timestamptz DEFAULT now()
);

CREATE INDEX idx_articulos_requisito ON articulos_requisito(requisito_id);

-- Evaluaciones por instalación × artículo (núcleo del módulo)
CREATE TABLE evaluaciones_cumplimiento (
  id                      uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id               uuid NOT NULL,
  instalacion_id          uuid NOT NULL,
  articulo_id             uuid NOT NULL REFERENCES articulos_requisito(id),
  requisito_id            uuid NOT NULL REFERENCES requisitos_legales(id),
  respuesta               respuesta_cumplimiento NOT NULL DEFAULT 'N/E',
  resultado               numeric(4,3),          -- 1.0 | 0.0 | NULL (N/A, N/E)
  periodo_evaluacion      text NOT NULL,          -- '2024-ANUAL', '2025-Q1'
  fecha_revision          timestamptz DEFAULT now(),
  revisor_id              uuid NOT NULL,
  observaciones           text,
  documento_evidencia_id  uuid,                  -- FK a tabla de documentos
  created_at              timestamptz DEFAULT now(),
  updated_at              timestamptz DEFAULT now(),
  UNIQUE (tenant_id, instalacion_id, articulo_id, periodo_evaluacion)
);

CREATE INDEX idx_eval_tenant_instalacion ON evaluaciones_cumplimiento(tenant_id, instalacion_id);
CREATE INDEX idx_eval_articulo ON evaluaciones_cumplimiento(articulo_id);
CREATE INDEX idx_eval_respuesta ON evaluaciones_cumplimiento(respuesta);

-- RLS: un tenant no puede ver evaluaciones de otro
ALTER TABLE evaluaciones_cumplimiento ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_eval ON evaluaciones_cumplimiento
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Log de revisión normativa anual (proceso hoy 100% manual en Excel)
CREATE TABLE revisiones_normativas (
  id                      uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id               uuid NOT NULL,
  fecha                   date NOT NULL,
  responsable_id          uuid NOT NULL,
  cuerpos_legales_ids     uuid[],                -- requisitos_legales.id[] nuevos identificados
  instalaciones_afectadas uuid[],                -- instalacion_id[] que deben actualizar evaluación
  observaciones           text,
  created_at              timestamptz DEFAULT now()
);

CREATE INDEX idx_revision_tenant ON revisiones_normativas(tenant_id);
CREATE INDEX idx_revision_fecha ON revisiones_normativas(fecha);
```

### 9b.2 Vistas para el dashboard de cumplimiento

```sql
-- Vista: % evaluación y % cumplimiento por instalación (replica el "Resumen" del Excel)
CREATE VIEW resumen_cumplimiento_instalacion AS
SELECT
  tenant_id,
  instalacion_id,
  periodo_evaluacion,
  COUNT(*)                                                          AS total_articulos,
  COUNT(*) FILTER (WHERE respuesta != 'N/E')                       AS articulos_evaluados,
  COUNT(*) FILTER (WHERE respuesta = 'SI')                         AS articulos_cumplidos,
  COUNT(*) FILTER (WHERE respuesta = 'NO')                         AS articulos_incumplidos,
  COUNT(*) FILTER (WHERE respuesta = 'N/A')                        AS articulos_no_aplica,
  ROUND(
    COUNT(*) FILTER (WHERE respuesta != 'N/E')::numeric / NULLIF(COUNT(*), 0),
    4
  )                                                                 AS pct_evaluacion,
  ROUND(
    COUNT(*) FILTER (WHERE respuesta = 'SI')::numeric /
    NULLIF(COUNT(*) FILTER (WHERE respuesta IN ('SI','NO')), 0),
    4
  )                                                                 AS pct_cumplimiento
FROM evaluaciones_cumplimiento
GROUP BY tenant_id, instalacion_id, periodo_evaluacion;

-- Vista: resumen por requisito (para ver qué norma tiene peor desempeño)
CREATE VIEW resumen_cumplimiento_requisito AS
SELECT
  e.tenant_id,
  e.instalacion_id,
  e.requisito_id,
  r.nombre,
  r.ambito,
  r.tipo_documento,
  e.periodo_evaluacion,
  ROUND(
    COUNT(*) FILTER (WHERE e.respuesta = 'SI')::numeric /
    NULLIF(COUNT(*) FILTER (WHERE e.respuesta IN ('SI','NO')), 0),
    4
  ) AS pct_cumplimiento
FROM evaluaciones_cumplimiento e
JOIN requisitos_legales r ON r.id = e.requisito_id
GROUP BY e.tenant_id, e.instalacion_id, e.requisito_id, r.nombre, r.ambito, r.tipo_documento, e.periodo_evaluacion;
```

### 9b.3 Ámbitos y sectores de operación (para configuración por instalación)

| Código | Ámbito | Descripción |
|---|---|---|
| `SSO` | Seguridad y Salud Ocupacional | Normas laborales, prevención de riesgos |
| `MA` | Medio Ambiente | Emisiones, residuos, autorizaciones, RCAs |
| `SSOMA` | SSO + MA | Artículos que aplican a ambos simultáneamente |
| `SIG` | Sistema de Gestión Integrado | ISO 9001, 14001, 45001, 37001 |
| `DTP` | Dirección Técnica y Proyectos | Requisitos técnicos de obras y proyectos |

| Sector instalación | Ámbitos dominantes | Carga normativa |
|---|---|---|
| Rellenos Sanitarios | MA + SSOMA | Alta |
| Residuos Peligrosos / Clínico | MA + SSOMA + SIG | Muy alta |
| Aguas | MA + SSOMA | Alta |
| Industrial | MA + SSOMA + SIG | Alta |
| Minería | MA + SSOMA | Alta |
| Recolección / Barrido | SSOMA | Media |

> **Para el seed de demo:** perfil Industrial con 3 instalaciones y ~200 artículos cubre la mayoría de normativas SSO + MA sin configuración específica.

---

## 10. Observabilidad y monitoreo

```typescript
// apps/api/src/infrastructure/telemetry.ts
import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';

const sdk = new NodeSDK({
  serviceName: 'ambienta-api',
  traceExporter: new OTLPTraceExporter({
    url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT,
  }),
});

// Métricas de negocio clave:
// - declaraciones.created (counter)
// - declaraciones.approved (counter, by_plant)
// - declarations.overdue (gauge, crítico)
// - ai_agent.requests (counter)
// - ai_agent.latency (histogram)
// - email.sent / email.failed (counter)
```

**Stack de observabilidad recomendado:**
- **Logs:** Pino (JSON estructurado) → Axiom o Grafana Loki
- **Trazas:** OpenTelemetry → Jaeger o Grafana Tempo
- **Métricas:** Prometheus + Grafana
- **Errores:** Sentry (API + Frontend + Worker)
- **Uptime:** Better Uptime o Checkly

---

## 11. Seguridad multi-servicio

| Vector | Medida |
|---|---|
| Comunicación inter-servicio | JWT de servicio (service-to-service) con claims `iss: api` → ai-service verifica origen |
| API pública | Rate limiting por IP + por tenant (Fastify + Upstash) |
| Ollama | No expuesto al exterior; solo red Docker interna |
| PostgreSQL | Solo accesible desde red privada; sin Puerto 5432 público |
| Redis | Solo accesible desde red privada; AUTH habilitado |
| Storage | Presigned URLs con expiración de 1 hora; nunca URLs públicas |
| Secrets | Variables de entorno cifradas; rotación mensual de JWT_SECRET |

---

## 12. Despliegue en producción

```
┌──────────────────────────────────────────────────────────┐
│                   PRODUCCIÓN                              │
│                                                          │
│  Vercel (apps/web)          CDN global, edge functions   │
│                                                          │
│  Railway Pro (apps/api)     2 instancias, auto-scaling   │
│  Railway Pro (worker)       2 instancias paralelas       │
│  Railway Pro (PostgreSQL)   pgvector habilitado          │
│  Railway Pro (Redis)        512MB, persistence           │
│                                                          │
│  VPS GPU (ai-service)       Hetzner/Lambda Labs          │
│  → RTX 4000 Ada (20GB)      qwen3:14b sin problemas      │
│  → Costo: ~USD 120/mes      latencia: 3-6s/respuesta     │
│                                                          │
│  Resend                     email transaccional          │
│  Cloudflare R2              storage documentos           │
└──────────────────────────────────────────────────────────┘
Costo estimado total: USD 300–500/mes (hasta 50 tenants)
```

---

## 13. Roadmap técnico

| Sprint | Semanas | Entregables |
|---|---|---|
| Setup arquitectura | 1–2 | Turborepo, DB schema, auth JWT, pipeline CI/CD |
| Ciclo 1 — API core | 3–8 | tRPC routers: plants, obligations, users, RBAC completo |
| Ciclo 2 — Declaraciones | 9–14 | Workflow completo, evidencias, notificaciones email |
| Ciclo 3 — AI Service | 15–20 | Ollama + RAG + AmbiAgent v1 con 4 herramientas |
| Ciclo 4 — Dashboard | 21–26 | Dashboard ejecutivo, reportes PDF, API pública v1 |

---

*SDD Backend Separado v1.0 — Ambienta · 2026-06-01*
