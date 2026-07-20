# Segmentos Objetivo — Ambienta
**Fecha:** 2026-05-30  
**Estado:** v1.0 — hipótesis a validar con entrevistas JTBD

---

## Marco de segmentación

Tres variables definen quién tiene el dolor más agudo:

| Variable | Pregunta clave |
|---|---|
| **Sector industrial** | ¿Cuántas normativas distintas le aplican? ¿Cuál es la multa máxima? |
| **Tamaño de empresa** | ¿Cuántas plantas? ¿Hay especialista ambiental dedicado o lo hace alguien "de paso"? |
| **Carga regulatoria** | ¿Qué combinación de obligaciones tiene? ¿Con qué frecuencia declara? |

---

## Dimensión 1 — Por sector industrial

| Segmento | Normativas que aplican | Frecuencia de declaración | Riesgo multa | Accesibilidad |
|---|---|---|---|---|
| **Manufactura (químicos, papel, plásticos)** | RETC, SINADER, DAE, SIDREP, SIGRH | Mensual + anual | 🔴 Alta (SMA) | Media |
| **Agroindustria (vinos, salmones, alimentos)** | RETC, SINADER, DAE, DJA, normativa sanitaria | Mensual + anual | 🔴 Alta (SMA + SAG + SEREMI) | Alta |
| **Energía (generadoras, distribuidoras)** | RETC, SINADER, Ley Marco CC (GEI), HuellaChile, RCI | Mensual + anual + trimestral | 🔴 Muy alta (SMA + SEC) | Baja |
| **Retail con logística (importadores de productos prioritarios)** | Ley REP (envases, RAEE, pilas), DAE | Mensual SISREP | 🟡 Media | Alta |
| **Minería (mediana y grande)** | RETC, SINADER, SIDREP, DAE, normativa SERNAGEOMIN | Mensual + anual | 🔴 Alta | Baja |
| **Construcción e infraestructura** | RETC, RCA (compromisos ICA), DAE | Anual + por proyecto | 🟡 Media | Media |
| **Consultoras ambientales (canal)** | Gestionan cumplimiento de múltiples clientes | Variable | N/A | 🟢 Alta |

**Sectores prioritarios para el MVP:**
1. Agroindustria
2. Manufactura (alimentos, químicos, papel)
3. Retail con logística / importadores bajo Ley REP
4. Consultoras ambientales (como canal)

---

## Dimensión 2 — Por tamaño de empresa

| Segmento | N° plantas | Perfil de dolor | WTP | Ciclo de venta | ¿ICP? |
|---|---|---|---|---|---|
| **PYME industrial** | 1–2 plantas | Un especialista que hace todo. Sin sistema. | Bajo–medio (USD 100–150/planta) | Corto | Secundario |
| **Mediana empresa** ⭐ | 3–10 plantas | Especialistas por planta sin coordinación central. Gerencia sin visibilidad. Pain máximo. | Medio (USD 150–250/planta) | 4–8 semanas | **ICP primario** |
| **Gran empresa** | 10+ plantas | Área de cumplimiento dedicada. Buscan trazabilidad para directorio. | Alto (USD 100–180/planta) | 3–6 meses | ICP secundario |
| **Consultora ambiental** (BPO) | Gestiona 10–50 clientes | Necesita eficiencia para escalar sin contratar | Medio-alto (modelo reseller) | 2–4 semanas | Canal estratégico |

**Por qué la mediana empresa (3–10 plantas) es el ICP primario:**
- Suficiente complejidad como para sentir el dolor (coordinación multi-planta)
- No tan grande como para tener inercia institucional o consultoras instaladas
- Decisión de compra tomada por gerente de operaciones o jefe de planta — no por directorio
- CAC bajo, LTV razonable, churn bajo si el producto resuelve el problema

---

## Dimensión 3 — Por carga regulatoria

Variable más operacionalmente útil para calificar un lead.

| Perfil regulatorio | Obligaciones activas | N° declaraciones/planta/año | Riesgo acumulado | Prioridad Ambienta |
|---|---|---|---|---|
| **Multi-norma pesado** ⭐ | RETC + SINADER + DAE + SIDREP + Ley REP | 20–30+ | 🔴 Máximo | **Prioritario** |
| **REP-intensivo** | Ley REP (SISREP mensual) + RETC anual | 12–15 | 🔴 Alta multa REP | Prioritario |
| **RETC + residuos** | RETC + SINADER + DAE | 10–15 | 🟡 Media-alta | Prioridad media |
| **Solo ICA/RCA** | Compromisos de calificación ambiental | Variable | 🟡 Media | Baja prioridad MVP |
| **Solo Ley REP** | SISREP mensual | 12 | 🟡 Media | Canal de entrada pero no diferenciador vs. EcoREP/ReBits |

**Regla de calificación para leads:** Un cliente es ICP si tiene ≥3 normativas activas simultáneas y ≥2 plantas. Si solo tiene Ley REP, es posible pero no prioritario.

---

## ICP Definitivo

### ICP Primario — "El coordinador sin sistema"

> Empresa industrial chilena mediana, 3–10 plantas fiscalizables, en sectores de agroindustria o manufactura, con obligaciones activas en RETC + SINADER + DAE (mínimo), sin sistema de gestión centralizado. El especialista ambiental hace todo en Excel. La gerencia no tiene visibilidad consolidada. Ya han tenido al menos un incidente de plazo vencido o multa.

| Atributo | Descripción |
|---|---|
| Sector | Agroindustria, manufactura, retail con logística |
| Tamaño | 3–10 plantas · 100–500 empleados totales |
| Geografía | Chile (RM, V, VI, VII, VIII Región) |
| Obligaciones | RETC + SINADER + DAE (base mínima). Bonus: Ley REP activa |
| Señal de dolor | Historial en SNIFA, presión ESG de clientes o directorio, especialista recargado |
| Decisor | Gerente de Operaciones / Jefe de Planta / Subgerente de Sustentabilidad |
| Influenciador | Especialista ambiental — usuario operacional, su aprobación es necesaria |

### ICP Secundario — "La consultora que necesita escalar"

> Consultora ambiental que gestiona cumplimiento de 10–50 clientes con 1–3 especialistas. Hace BPO manual. Su cuello de botella es la capacidad humana, no el conocimiento. Ambienta les multiplica la capacidad sin contratar.

| Atributo | Descripción |
|---|---|
| Tipo | Consultora ambiental mediana o pequeña |
| N° clientes gestionados | 10–50 empresas |
| Equipo | 1–3 especialistas ambientales |
| Modelo de negocio | BPO de cumplimiento (cobra por servicio, no por software) |
| Propuesta Ambienta | Herramienta para su equipo (no para sus clientes directamente) |
| Potencial | Canal de adquisición: cada consultora trae N clientes finales |

---

## Matriz de priorización de segmentos

| Segmento | Dolor | Accesibilidad | Tamaño mercado | WTP | Prioridad |
|---|---|---|---|---|---|
| Manufactura mediana (3–10 plantas) | 🔴 Alto | 🟡 Media | 🟡 Medio | 🟡 Medio | **1** |
| Agroindustria mediana (3–10 plantas) | 🔴 Alto | 🟢 Alta | 🟡 Medio | 🟡 Medio | **1** |
| Consultoras ambientales (canal) | 🟡 Medio | 🟢 Alta | 🟢 Alto | 🟢 Alto | **2** |
| Retail / importadores REP | 🟡 Medio | 🟢 Alta | 🟡 Medio | 🟡 Medio | **3** |
| Energía / minería grande | 🔴 Alto | 🔴 Baja | 🟡 Medio | 🔴 Alto | **4 (post-MVP)** |
| PYME (1–2 plantas) | 🟡 Medio | 🟡 Media | 🟢 Alto | 🔴 Bajo | **5 (futura)** |

---

## Hipótesis a validar en entrevistas

Estas son las hipótesis que guían los segmentos. Las entrevistas JTBD deben confirmarlas o refutarlas.

1. **H1:** El especialista ambiental es el usuario que siente el dolor operacional más agudo — y su validación es necesaria para la adopción.
2. **H2:** Las medianas empresas (3–10 plantas) tienen el dolor más alto y la menor resistencia al cambio tecnológico.
3. **H3:** Las empresas con historial de multas en SNIFA tienen mayor urgencia de compra.
4. **H4:** Las consultoras ambientales son el canal más eficiente para adquisición de clientes en la etapa inicial.
5. **H5:** El sector agroindustrial tiene mayor disposición a pagar que el sector manufactura por el riesgo reputacional ESG asociado.
6. **H6:** El pain principal no es el tiempo de preparación (2 hrs/declaración) sino el riesgo de plazo vencido — la multa es el detonante de compra.

---

*Documento generado 2026-05-30. Hipótesis a actualizar tras entrevistas de descubrimiento (deadline: 2026-07-04).*
