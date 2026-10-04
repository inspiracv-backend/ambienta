# Prompt para Claude Code — Implementación del sistema de actores/roles de Ambienta

> Cómo usar este prompt: adjunta junto a este mensaje el archivo `Ambienta_Analisis_Actores_v1.md`
> (y opcionalmente el Análisis Funcional v1.7 completo de Notion) en el contexto de la sesión de
> Claude Code, y pega el bloque de abajo como tu primer mensaje.

---

## Contexto

Estás trabajando en **Ambienta**, una PWA multi-tenant de gestión de vencimientos, obligaciones y
cumplimiento ambiental para empresas en Chile (arquitectura multi-país). Stack base: **Next.js +
Fastify + Python (`apps/ai-service`, FastAPI)**, base de datos **PostgreSQL + pgvector**, orquestador
de agentes **LangGraph**, auth con **Microsoft Entra ID (prioridad) + Google + JWT**, correo con
**Resend**, evidencias en **Google Drive (primero) + OneDrive** vía capa de abstracción.

Tienes adjunto el documento `Ambienta_Analisis_Actores_v1.md`: un análisis funcional **enfocado
100% en actores y roles**, derivado del Análisis Funcional v1.7 del proyecto. Ese documento es tu
fuente de verdad para esta tarea. Contiene:

- Sección 2: los 5 actores formales (A0–A4) con su descripción, RFs asociados y ambigüedades detectadas.
- Sección 3: actores **implícitos** que el documento base no formalizó pero que el sistema necesita
  (A5 — cliente final del sub-tenant de un Gestor, A6 — usuario vía LTI/Embed, agente de Soporte
  como sub-rol de A0, y los 4 agentes de IA como identidades de sistema en el audit log).
- Sección 4: matriz de permisos cruzada por módulo (actor × capacidad).
- Sección 5: flujos críticos por actor (onboarding bloqueante de Admin Empresa, alta de Cliente
  Invitado, creación de sub-tenant vía Contrato, aprobación/auditoría).
- Sección 6: inconsistencias y riesgos de gobernanza detectados en el modelo actual.
- Sección 7: recomendaciones concretas para resolverlos.
- Sección 8: preguntas abiertas que aún no tienen respuesta de negocio.
- Sección 9: usuarios de prueba (seed data) para cada actor, incluyendo los implícitos y los
  agentes de sistema, listos para usar como fixtures.

## Objetivo de esta sesión

Implementar el sistema de actores/roles (identidad, autenticación, RBAC, multi-tenancy y audit log)
de Ambienta **a fondo**, usando el análisis adjunto como especificación funcional. No estás
implementando los módulos de negocio (Matriz Legal, Obligaciones, etc.) todavía — el foco es la
capa de actores que todo lo demás va a consumir.

## Antes de escribir código

1. **Explora el repo actual.** Revisa si ya existe un esquema de usuarios/roles, migraciones,
   middleware de auth o RLS de Postgres. No asumas que partes de cero — reporta qué encontraste
   antes de proponer cambios.
2. **Resuelve las secciones 6 y 8 del análisis antes de modelar datos**, no durante. Específicamente,
   necesito que me preguntes (o propongas un default razonable y lo marques explícitamente como
   supuesto a validar) sobre:
   - Cardinalidad de Admin Empresa por tenant (¿1 owner o varios co-admins?).
   - Si A4 (Gestor) se implementa como **flag/módulo sobre el tenant**, no como rol de usuario
     separado (la recomendación del análisis es tratarlo así — confírmalo conmigo si vas a
     apartarte de esa recomendación).
   - Alcance exacto de permisos de A5 (cliente final del sub-tenant): al menos define un default
     mínimo viable (lectura de sus propias declaraciones + recepción de notificaciones, sin edición
     de Contrato) y déjalo fácil de ampliar.
   - Si el Gestor tiene acceso de lectura o escritura sobre los datos del sub-tenant, y cómo eso
     convive con el aislamiento RLS por tenant (RNF-07 del documento base).
3. **Preséntame un plan corto antes de implementar** (modelo de datos, migraciones, capas de
   middleware/guardas de permisos, y orden de implementación). Espera mi confirmación o ajusta según
   mi feedback antes de generar el código completo.

## Alcance de la implementación

1. **Modelo de datos** para actores y tenancy:
   - Tabla de usuarios con `tenant_id` obligatorio (según nota de gobernanza del documento base:
     todo usuario pertenece siempre a una Empresa).
   - Soporte para sub-tenancy vía Contrato (Gestor → Contrato → sub-tenant → cliente final).
   - Departamentos como entidad del Perfil Empresa, con la regla dura de que todo Usuario Interno
     (A2) pertenece obligatoriamente a un Departamento.
   - Manejo de Cliente Invitado (A3): identidad temporal con RUT + clave dinámica autogenerada,
     sin Departamento, con ruta de conversión a usuario permanente vía Admin Empresa.
   - `actor_type` explícito en cualquier tabla de auditoría, distinguiendo actor humano de agente
     de sistema (usa los identificadores sugeridos en la sección 9 del análisis:
     `system.ambiagent`, `system.ingest_bcn`, `system.monitor_normativo`, `system.ambiagent_admin`).
2. **RBAC**: sistema de permisos granular para A2 (no un rol plano), con al menos los permisos que
   el análisis dejó explícitos como faltantes: `puede_aprobar_cierre` separado de
   `puede_editar_evidencia`. Diseña el esquema de permisos de forma que sea fácil agregar nuevos sin
   migración estructural (tabla de permisos + tabla de asignación, no columnas booleanas fijas).
3. **Autenticación**: Microsoft Entra ID + Google (OAuth2/OIDC) + JWT, con la variante de que un
   usuario que entra por proveedor externo pueda setear después una clave local (RUT + clave). Deja
   el punto de extensión para LTI 1.3 (A6) aunque no lo implementes completo en esta sesión —
   documenta dónde debería engancharse.
4. **Flujo de onboarding bloqueante de Admin Empresa (A1)**: fuerza el Perfil Empresa (plantas,
   departamentos, trabajadores, permisos) antes de habilitar acceso a Matriz Legal/Obligaciones.
   Implementa esto como guarda de ruta/middleware, no como validación de UI únicamente.
5. **Flujo de Cliente Invitado (A3)**: endpoint de link especial que genera RUT + clave dinámica
   automáticamente, crea tickets sin cuenta previa, y expone el punto donde el Admin Empresa lo
   convierte en usuario permanente.
6. **Audit log inmutable** (RNF-08/RNF-25 del documento base): quién, cuándo, por qué, quién aprobó,
   incluyendo acciones disparadas por agentes de sistema con su propio `actor_type`.
7. **Seed data**: carga los usuarios de prueba de la sección 9 del análisis como fixtures/seed
   script, manteniendo los tenants encadenados (Aguas del Maule para el flujo estándar; ResiFlow →
   Panadería El Sol → Marcelo Peña para el flujo de Gestor/sub-tenant) para que sirvan de inmediato
   en pruebas end-to-end.

## Reglas de trabajo

- Prioriza correctitud del modelo de permisos y aislamiento multi-tenant por sobre velocidad —
  esta capa la va a consumir todo el resto del sistema.
- Cuando un punto del análisis quede señalado como "sin definir" o "pregunta abierta" (secciones 6
  y 8), no lo implementes en silencio con un supuesto arbitrario: dilo explícitamente y decide con
  un default documentado y fácil de cambiar.
- Sigue las convenciones y estructura de carpetas que ya existan en el repo; si no existen, propone
  una antes de generar múltiples archivos.
- Al terminar, resume qué quedó implementado, qué quedó como default a validar, y qué de las
  secciones 6/7/8 del análisis todavía no fue abordado.
