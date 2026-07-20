# ADR-004: ReportabilidadInstalacion como núcleo del módulo RETC/Declaraciones

**Estado:** `Aceptado` — 2026-06-01  
**Decisores:** Gabriel Tovar  
**Categoría:** Funcionalidad · Modelo de datos  
**Validado por:** Análisis de diagrama de flujo RETC y matrices de reportabilidad (empresa sector ambiental, confidencial). 21 sistemas sectoriales mapeados.  
**Spec técnica:** Sección 8c de `ADD-ambienta-monolito-modular.md`

---

## Contexto

El ecosistema RETC tiene 21 portales distintos (12 sistemas sectoriales + 9 sistemas SMA) con periodicidades completamente distintas: tiempo real, mensual, trimestral, anual y variable según RCA. Cada instalación tiene un subconjunto diferente de obligaciones, determinado por su RCA específica.

El estado de cada sistema para cada instalación puede ser `SÍ`, `CONDICIONAL`, `N/A`, `NO` u `OBLIGATORIO`. Hoy el especialista determina esto manualmente para cada instalación nueva. Es un trabajo de días cruzar artículos de RCA con los sistemas que aplican.

---

## Decisión

El núcleo del módulo es la entidad **`ReportabilidadInstalacion`**: el resultado de configurar, **una sola vez en el onboarding**, qué sistemas sectoriales aplican a cada instalación y con qué estado.

El modelo de datos es:

```
SistemaSectorial   ←   ReportabilidadInstalacion   →   Instalacion
 (SINADER, DJA...)       (estado + condición + vars)
        ↓
 DeclaracionPeriodo   (una por instalación × sistema × periodo)
```

La lógica de estados CONDICIONAL se resuelve en el **wizard de onboarding de instalación**, capturando preguntas como:
- ¿Genera o gestiona residuos peligrosos (RESPEL)? → activa SIDREP
- ¿Tiene bodega de sustancias peligrosas con autorización? → activa DASUPEL
- ¿Está en zona con PPDA? → activa compromisos reforzados en SISAT

Una vez configurada la instalación, el sistema genera automáticamente todas las `DeclaracionPeriodo` del año con sus fechas límite.

La única declaración universal hardcodeada (sin configuración) es la **DJA: Octubre 1–31**. Aplica a todas las instalaciones, todos los años, sin excepción.

---

## Consecuencias

### ✅ Positivas
- El wizard de onboarding elimina semanas de trabajo manual por instalación nueva
- Las `DeclaracionPeriodo` se generan automáticamente — el sistema sabe el calendario completo del año desde enero
- El semáforo de urgencia (días hábiles restantes) es calculable en tiempo real sin intervención del usuario
- El botón "Ir al sistema" con URL oficial de cada portal está disponible inmediatamente
- El registro de folio de confirmación cierra el ciclo de trazabilidad de cada declaración

### ⚠️ Trade-offs
- El wizard de onboarding debe ser exhaustivo pero no abrumador — requiere buen diseño UX de flujo de preguntas
- Las fechas del calendario RETC cambian anualmente por resolución → requiere proceso de actualización anual del seed (no es automático sin integración con BCN/SMA)
- Los sistemas con `periodicidad: VariableRCA` (SSA, SRCA, SIVEM) requieren configuración manual de fechas — no se pueden auto-generar
- La DJA de octubre hardcodeada asume que el periodo siempre es 1–31 octubre; si el MMA lo modifica un año, requiere parche

### 🔄 Neutral
- Este módulo es independiente del módulo de Cumplimiento Legal (ADR-003): gestiona *cuándo y dónde declarar*, no *si cada artículo normativo está siendo cumplido*
- El seed de los 21 sistemas sectoriales con URLs oficiales es un activo estático que solo cambia si el MMA/SMA crea o elimina portales

---

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Configuración manual completa por instalación (sin wizard) | El especialista debe tomar las mismas decisiones de siempre — no agrega valor vs el Excel actual |
| Auto-detectar obligaciones desde la RCA vía IA | Atractivo pero riesgoso: los artículos de RCA son ambiguos y el error tiene consecuencias legales. El wizard con preguntas binarias es más seguro y auditadle. |
| Un solo calendario fijo para todos los tenants | Ignora que los estados CONDICIONAL varían por instalación — imposible sin configuración |
| Integración automática con portales (auto-declarar) | Fuera de scope para MVP. Los portales no tienen APIs públicas de escritura. El usuario declara manualmente; Ambienta gestiona el seguimiento. |

---

## Criterios de revisión

Revisar si:
- El MMA publica una API de escritura en la Ventanilla Única → evaluar integración directa para auto-declaración
- Los usuarios reportan que el wizard de onboarding es demasiado largo → simplificar a perfiles predefinidos por tipo de instalación (Tipo A–E)
- Se añaden más sistemas sectoriales al RETC → actualizar seed y lógica de generación de períodos

---

## Referencias
- Calendarios y sistemas oficiales: `resources/normativa-legal-chile/retc-sistemas-calendarios-2026.md`
- Spec técnica (entidades, Prisma schema, servicio de alertas): sección 8c de `ADD-ambienta-monolito-modular.md`
- Módulo relacionado: `ADR-003-modulo-cumplimiento-legal.md`
- URL oficial de verificación: https://portalvu.mma.gob.cl/caja-de-herramientas/calendario-declaraciones/
