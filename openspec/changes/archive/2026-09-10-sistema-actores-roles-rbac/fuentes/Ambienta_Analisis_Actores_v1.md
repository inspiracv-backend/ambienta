# Ambienta — Análisis Funcional de Actores y Roles

**Documento base:** Ambienta — Análisis Funcional v1.7 (27-jul-2026)
**Enfoque de este análisis:** 100% actores/roles — modelo de acceso, gobernanza, RBAC, flujos y brechas
**Tipo:** Análisis extra / auditoría de diseño de roles

---

## 1. Resumen ejecutivo

El documento base define **5 actores formales** (A0–A4) en la sección 2, bajo un modelo multi-tenant con aislamiento por `tenant_id`. Sin embargo, al revisar los Requerimientos Funcionales (RF-01 a RF-89) y los Casos de Uso (UC-01 a UC-18), aparecen **al menos 3 actores adicionales que operan en el sistema pero no están formalizados como fila en la tabla de actores**, más **2 actores no-humanos (agentes IA)** que toman decisiones y generan artefactos visibles a otros actores, y **1 actor externo de plataforma** (LMS vía LTI) que consume el sistema como Tool Consumer.

Esto no es necesariamente un error — es normal que un análisis funcional v1 deje roles secundarios implícitos — pero para un modelo RBAC sólido, **cada actor que puede leer, escribir, aprobar o ser notificado necesita entrada propia**, aunque herede permisos de otro. Este documento:

1. Audita los 5 actores formales en profundidad (objetivos, límites, RFs asociados, RNFs de gobernanza, preguntas abiertas).
2. Identifica y perfila los actores implícitos.
3. Construye la matriz de permisos cruzada por módulo.
4. Mapea los flujos críticos centrados en actor (onboarding, cliente invitado, gestor/sub-tenant, aprobación/auditoría).
5. Señala inconsistencias, ambigüedades y riesgos de gobernanza en el modelo de actores actual.
6. Cierra con recomendaciones concretas para la v1.8 / OpenSpec.

---

## 2. Actores formales (según sección 2 del documento base)

| ID | Actor | Tipo de acceso | Alcance |
|----|-------|-----------------|---------|
| A0 | Superadmin / Admin de Plataforma | Plataforma completa | Cross-tenant |
| A1 | Admin Empresa (Tenant Owner) | Completo dentro del tenant | Un tenant |
| A2 | Usuario Interno | Según RBAC del tenant | Un tenant, por departamento |
| A3 | Cliente / Invitado | Limitado (tickets) | Semi-público, pre-tenant |
| A4 | Gestor | Módulo de gestores + sub-tenants | Un tenant + sus sub-tenants |

### 2.1 A0 — Superadmin / Admin de Plataforma

**Naturaleza:** único actor cross-tenant. No pertenece a ningún tenant de negocio; es dueño de la plataforma.

**Responsabilidades (RF-81 a RF-84, UC-01 a UC-03):**
- Habilitar/deshabilitar tenants, definir límites de usuarios y módulos activos (RF-81).
- Gestionar planes de prueba y onboarding de nuevos clientes (RF-82).
- Operar el módulo de Soporte: tickets, nuevos requerimientos, corrección de logs erróneos —con auditoría obligatoria (RF-83).
- Usar un **Chatbot IA privilegiado** exclusivo, con métricas globales y estado de tenants, sin acceso a datos de un tenant salvo permiso explícito (RF-60, RF-84).
- Recibir alertas de los agentes de monitoreo normativo (RF-61, UC-03).

**Punto de fricción detectado:** RF-84 dice *"el soporte debe diferenciar claramente lo que ve el cliente versus lo que ve el equipo interno / Superadmin"*, lo que implica un **equipo de Soporte** que no es necesariamente el mismo individuo que el Superadmin. Ver actor implícito §3.1.

**Pregunta abierta:** ¿Existe un nivel intermedio (ej. "Admin de Sistemas" vs "Superadmin dueño del software") o son el mismo rol con dos nombres? El título de la sección 3.14 dice *"Admin de Sistemas / Superadmin + Soporte"*, tratándolos como un bloque, pero A0 en la tabla de actores solo nombra "Superadmin / Admin de Plataforma".

### 2.2 A1 — Admin Empresa (Tenant Owner)

**Naturaleza:** dueño operativo del tenant. Es el actor con más superficie de responsabilidad del sistema — toca prácticamente todos los módulos.

**Responsabilidades clave:**
- **Flujo obligatorio de entrada:** completar Perfil Empresa (plantas, departamentos, trabajadores, permisos) antes de poder usar Matriz Legal u Obligaciones (RF-10 a RF-12, UC-04). Este es el único actor que puede "bloquear" el sistema para sí mismo si no completa este paso.
- Sube los PDFs de ISO y RCAs al Catálogo Normativo (RF-15).
- Configura Matriz Legal a partir del Catálogo (RF-19 a RF-24, UC-05).
- Gestiona Obligaciones/Declaraciones como megaproyectos (UC-06), evalúa cumplimiento (UC-07), genera planes de acción (UC-08), gestiona auditorías y no conformidades (UC-09).
- Es quien **registra permanentemente** a un Cliente Invitado que lo solicite (RF-03, decisión cerrada #11).
- Si opera como Gestor, crea Contratos y sub-tenants (UC-12, RF-65).

**Ambigüedad detectada:** el documento no distingue si puede existir **más de un Admin Empresa por tenant**. El nombre "Tenant Owner" (singular) sugiere que sí es único, pero en la práctica organizacional (una pyme con gerente + jefe de HSE) suele necesitarse más de una persona con permisos de administrador. Esto no está resuelto en RF-08 (que solo lista los "tipos" de usuario, no la cardinalidad).

**Superposición con Gestor:** A1 y A4 no son mutuamente excluyentes. Un Gestor **es** una Empresa cuyo Admin Empresa tiene además el módulo de Gestores habilitado (RF-64). Es decir, A4 no es un rol independiente de A1 — es una **extensión de capacidades** de A1 cuando el tenant es de tipo "gestor". El diagrama anterior refleja esto: la caja "Admin empresa — rol de gestor" es funcionalmente A1, no un actor nuevo.

### 2.3 A2 — Usuario Interno

**Naturaleza:** el actor "operativo" del día a día, siempre atado a un Departamento.

**Reglas duras:**
- **RF-11 (obligatoria):** todo Usuario Interno pertenece a un Departamento del Perfil Empresa. No puede existir un A2 huérfano.
- Opera "según permisos RBAC" (A2 no es un rol único, sino una familia de perfiles configurados por el Admin Empresa vía la matriz de permisos del Perfil Empresa).

**Responsabilidades (UC-13 a UC-15):**
- Evaluar tareas/artículos asignados, adjuntar evidencias, ver historial.
- Gestionar su calendario, Gantt y Kanban de tareas, filtrado por Departamento (RF-40).
- Recibir notificaciones y usar el Chatbot tenant-aware.

**Nota de diseño clave:** A2 es el único rol que el documento describe explícitamente como **"configurable"** (RBAC granular), mientras A0, A1, A3 y A4 son roles fijos de plataforma. Esto significa que, en la práctica, "A2" en la matriz de permisos (§4 de este documento) no es una fila única sino un **espacio de configuración** — el análisis funcional no debería tratarlo como un permiso plano, sino documentar qué combinaciones de permisos son válidas dentro de RBAC (ver §7.2, riesgo de sub-especificación).

### 2.4 A3 — Cliente / Invitado

**Naturaleza:** el único actor "semi-público" — puede interactuar sin cuenta previa. Es el rol con el flujo más detallado del documento (clarificado explícitamente en v1.7).

**Flujo exacto (decisión cerrada #11, RF-01 a RF-03):**
1. El actor llega vía un **link especial** (no requiere cuenta).
2. El sistema le asigna automáticamente **RUT + clave dinámica**.
3. Genera tickets de gestión con esa identidad temporal.
4. Si quiere volverse permanente, **solo el Admin Empresa puede registrarlo** — A3 no puede autopromoverse a A2.
5. *(Camino inverso)* un usuario que entra con Google/Microsoft puede setear una clave local (RUT + clave) para no depender del proveedor externo — esto es una variante de autenticación, no un cambio de rol.

**Puntos críticos de gobernanza:**
- A3 es el único actor cuya identidad la genera el **sistema**, no el usuario ni un admin. Esto tiene implicancias de seguridad (RNF-01, Ley 21.719) que deberían mapearse explícitamente: ¿cómo se comunica esa clave dinámica al invitado? ¿expira? El documento no lo especifica — es una brecha real para el diseño de seguridad, no solo de actores.
- A3 no tiene Departamento (RF-11 solo aplica a Usuario Interno), por lo que **queda fuera del modelo de filtrado por Departamento** que sí aplica a A2 (RF-40). Vale la pena confirmar que los tickets de A3 son visibles para *todos* los Usuarios Internos del tenant o si necesitan enrutamiento.

### 2.5 A4 — Gestor

**Naturaleza:** no es un rol de usuario individual sino una **capacidad de tenant** (ver superposición con A1 en §2.2). El ejemplo dado (Veolia, Resistance) son empresas que administran residuos de sus propios clientes.

**Modelo de sub-tenancy (RF-64 a RF-70, decisión cerrada #16):**
- El **Contrato** es la entidad formal que dispara la creación de un sub-tenant.
- Los sub-tenants **los crea el Admin Empresa del Gestor** — no el Superadmin, no automáticamente.
- El cliente final del Gestor es un **usuario sub-tenant con permisos limitados** (RF-67) — este es el actor implícito más importante, ver §3.2.
- Campos customizables por tenant para datos de cliente/contrato (RF-69), con extracción asistida por IA desde el PDF del contrato (RF-70).

**Ambigüedad de acceso:** la tabla de actores dice que A4 tiene *"módulo de gestores + visibilidad de sub-tenants"*, pero no aclara si esa visibilidad es de **solo lectura** sobre los datos operativos del sub-tenant o si el Gestor puede operar directamente dentro del tenant del cliente final (ej. cargar declaraciones en su nombre). RF-64 dice que el Gestor "administra residuos/servicios de sus propios clientes", lo que sugiere permisos de escritura — pero esto choca con el aislamiento RLS declarado en RNF-07 ("datos de cada Empresa lógicamente aislados") si el sub-tenant es tratado como tenant propio. Esto debería resolverse explícitamente: ¿el sub-tenant es un tenant real con RLS propio al que el Gestor accede por relación de Contrato, o es una partición lógica dentro del tenant del Gestor?

---

## 3. Actores implícitos (no formalizados en la tabla de la sección 2)

### 3.1 Equipo de Soporte (interno, distinto del Superadmin)

**Evidencia textual:** RF-83 ("Módulo de Soporte: listado de tickets... y capacidad de corregir logs erróneos") y RF-84 ("el soporte debe diferenciar claramente lo que ve el cliente versus lo que ve el **equipo interno / Superadmin**").

**Por qué importa como actor separado:** si "equipo interno" y "Superadmin" fueran la misma persona, RF-84 no necesitaría distinguirlos. Esto sugiere una jerarquía de al menos dos niveles dentro de "plataforma":
- **A0a — Superadmin:** control total, gestión de tenants y límites.
- **A0b — Agente de Soporte:** puede ver/gestionar tickets y corregir logs, pero probablemente no gestionar tenants ni límites de módulos.

**Recomendación:** formalizar esto como sub-roles de A0 en el RBAC, no como actor nuevo en la tabla — pero **sí** documentarlo explícitamente para que el diseño de permisos no colapse "Soporte = Superadmin".

### 3.2 Cliente final del Gestor (sub-tenant end user)

**Evidencia textual:** RF-67 — *"el cliente final es un usuario sub-tenant con permisos limitados"* — y UC-16 (Gestor gestiona "sus declaraciones de residuos" en representación del cliente final).

**Por qué es el hallazgo más importante de este análisis:** es un actor que:
- Tiene su propio dashboard (generado a partir del Contrato, RF-66).
- Tiene permisos limitados (¿lee sus propias obligaciones? ¿puede subir evidencias? ¿solo visualiza?).
- No es Cliente Invitado (A3) — no llega por link especial, sino que existe porque el Gestor lo dio de alta vía Contrato.
- No es Usuario Interno (A2) — no pertenece a un Departamento del tenant del Gestor, pertenece a su propio sub-tenant.

Este actor merece una fila propia en la tabla de actores (sugerido **A5 — Cliente final / Usuario sub-tenant**), con su propio conjunto de RFs de permisos, porque hoy sus límites de acceso quedan totalmente indefinidos: ¿puede invitar a otros usuarios de su empresa? ¿puede ver el Contrato completo o solo un resumen? ¿puede escalar a Soporte directamente o solo a través del Gestor?

### 3.3 Aprobador (rol funcional, no un tipo de usuario nuevo)

**Evidencia textual:** RF-27 ("responsable"), RF-29 ("responsable" de cumplimiento), RF-32 y RNF-08 (*"quién aprobó"* en el audit log), RF-49 (*"cierre de no conformidades con firma del responsable"*).

**Naturaleza:** "Aprobador" no es un actor con login distinto — es una **capacidad** que probablemente recae sobre A1 o un A2 con permiso elevado. Pero el documento lo trata como si fuera un dato de auditoría automático ("quién aprobó") sin definir **quién tiene la capacidad de aprobar** dentro del RBAC de A2. Esto es una laguna de permisos, no de actores: se recomienda que RBAC incluya explícitamente un permiso `puede_aprobar_cierre` separado de `puede_editar_evidencia`, porque hoy no hay ningún RF que lo declare.

### 3.4 Agentes de IA como actores del sistema (no humanos)

El documento describe 4 "agentes" en la sección 3.11 que **actúan**, no solo responden — esto los convierte en actores del sistema en sentido funcional, aunque no tengan login:

| Agente | Rol funcional | A quién notifica / afecta |
|---|---|---|
| **AmbiAgent** (chat tenant-aware) | Responde consultas del tenant, solo ve datos de ese tenant + normativa pública | A1, A2 |
| **Agente de ingesta/Catálogo** | Consume BCN, parsea PDFs de ISO/RCA, genera embeddings | Alimenta Matriz Legal y Obligaciones (afecta a A1) |
| **Agentes de monitoreo normativo** | Detectan cambios normativos y **crean notificaciones/tickets internos** (no solo mensajes de chat) | A0 y tenants afectados (A1) — RF-61 |
| **Chatbot privilegiado** | Igual stack, pero con métricas globales, sin acceso a datos de tenant salvo permiso explícito | A0 exclusivamente |

**Por qué importa en un análisis de actores:** el "agente de monitoreo normativo" **genera tickets internos automáticamente** (RF-61) — es decir, actúa como un actor con capacidad de escritura en el sistema (crea una obligación o alerta) sin que un humano lo dispare. Cualquier análisis de permisos/auditoría (RNF-08, "quién... cuándo... por qué") debería tratar a este agente como una identidad de sistema con su propio registro en el audit log ("actor = agente_monitoreo_normativo", no "actor = null" o "actor = Superadmin").

### 3.5 Organismo / Autoridad regulatoria (actor externo, fuera del sistema pero referenciado)

El documento aclara en §1.4 que "la presentación de declaraciones ante la autoridad se hace en la Ventanilla Única oficial" — es decir, **la SMA y los sistemas sectoriales (SINADER, SIDREP, RUEA, DJA, SISAT, DAE) no son actores del sistema**, son consumidores externos del resultado (el template Excel que Ambienta genera). No requiere modelado de acceso, pero **sí** vale la pena declararlo explícitamente como "actor fuera de alcance" en la tabla de actores para que quede documentado que Ambienta no tiene integración directa (API) con la autoridad — solo generación de evidencia/templates.

### 3.6 Plataforma LMS (Tool Consumer vía LTI 1.3)

La decisión cerrada #10 introduce integración como Tool Provider bajo LTI 1.3 Advantage para Blackboard/Moodle/Canvas, con la exigencia de que *"todas las pantallas del core deben contemplar variante Modo Embed/LTI"*. Esto introduce un actor externo de tipo sistema: **la plataforma LMS actúa como intermediario de autenticación/contexto** para un usuario que llega embebido. No queda claro en el documento **qué actor humano (A1/A2/A3) es el que llega vía LTI**, ni si el modo Embed afecta el RBAC (ej. ¿un usuario que entra vía LTI tiene los mismos permisos que si entrara directo?). Esto es una brecha de diseño más que de actores, pero debe resolverse antes de OpenSpec porque afecta el modelo de autenticación (RF-05 a RF-07 no mencionan LTI).

---

## 4. Matriz de permisos por módulo (actor × capacidad)

Leyenda: **C** completo · **G** gestiona/escribe · **L** lectura · **P** parcial/limitado · **A** aprueba · — sin acceso

| Módulo | A0 Superadmin | A1 Admin Empresa | A2 Usuario Interno | A3 Cliente Invitado | A4 Gestor (= A1 + módulo) | A5 Cliente final (implícito) |
|---|---|---|---|---|---|---|
| Gestión de tenants / límites / módulos | C | — | — | — | — | — |
| Perfil Empresa (plantas, deptos, trabajadores) | L (soporte) | C | L propio perfil | — | C (su tenant) | — |
| Catálogo Normativo (subir ISO/RCA) | L (auditoría) | G | L | — | G | — |
| Matriz Legal | L | C | L / P (según RBAC) | — | C | — |
| Obligaciones / Declaraciones (megaproyectos) | L | C | G (asignadas) | Genera ticket propio | C | P (propias, sin definir) |
| Calendario / Gantt / Kanban | L | C | G (filtrado por depto) | — | C | P (sin definir) |
| Notificaciones y correo (ciclo completo) | Recibe alertas de agentes | C | Recibe + responde | Recibe confirmación de ticket | C | P (sin definir) |
| Auditorías y No Conformidades | L | C | G / A (si tiene permiso) | — | C | — |
| Dashboard consolidado | C (global) | C (su tenant) | P (según RBAC) | — | C (tenant + sub-tenants) | P (su sub-tenant) |
| Templates Excel | L | C (descarga/usa) | L / usa | Recibe adjunto | C | Recibe adjunto |
| Módulo Gestores / Contratos / Sub-tenants | L | C (si es Gestor) | — | — | C | L (su propio contrato) |
| Chatbot IA tenant-aware | — | C | C | — | C | Sin definir |
| Chatbot IA privilegiado | C | — | — | — | — | — |
| Soporte (tickets, planes de prueba) | C | Genera tickets como cliente del soporte | — | Genera ticket vía link | Genera tickets | Sin definir |
| Auth / Perfil propio | C | C | C | P (auto-generado) | C | Sin definir |

**Celdas marcadas "sin definir" o "P (sin definir)"** son exactamente los puntos donde el análisis funcional necesita RFs nuevos antes de pasar a OpenSpec — concentradas casi todas en A5 (cliente final del Gestor), confirmando que es el actor con mayor deuda de especificación.

---

## 5. Flujos críticos vistos desde el actor

### 5.1 Onboarding de Admin Empresa (A1) — flujo bloqueante
```
A1 se registra (Microsoft/Google/JWT)
        │
        ▼
RF-10: sistema fuerza Perfil Empresa
(RUT, razón social, plantas, departamentos,
 trabajadores, matriz de permisos)
        │
        ▼
Sin este perfil completo → A1 NO puede
avanzar a Matriz Legal ni Obligaciones
```
Este es el único punto del sistema donde un actor completo (A1, con acceso "completo dentro del tenant") queda **funcionalmente bloqueado** por el propio sistema. Vale la pena definir en OpenSpec qué tan estricto es el bloqueo (¿puede ver el dashboard vacío? ¿puede invitar a otro A1/A2 antes de terminar el perfil para delegar la carga de datos?).

### 5.2 Cliente Invitado (A3) — de anónimo a ticket
```
A3 llega por link especial (sin cuenta)
        │
        ▼
Sistema asigna RUT + clave dinámica automática
        │
        ▼
A3 genera ticket de gestión
        │
        ├──► (permanece invitado) → tickets futuros repiten el flujo
        │
        └──► (Admin Empresa decide registrarlo) → A1 lo convierte en
             usuario permanente → pasa a operar como A2 (o similar)
```
Nota de diseño: el flujo NO permite que A3 se auto-registre — el control de alta permanece siempre en A1, coherente con el "nota de gobernanza" del documento base ("todo usuario debe estar siempre asignado a una Empresa").

### 5.3 Gestor (A4) y creación de sub-tenant vía Contrato
```
A1 (con módulo Gestor activo = A4) crea un Contrato formal
        │
        ▼
El Contrato dispara la creación del sub-tenant
        │
        ▼
Se genera el dashboard del sub-tenant a partir del Contrato
        │
        ▼
El cliente final (A5, implícito) opera dentro de ese
sub-tenant con permisos limitados — alcance no definido
```
Este es el flujo con más brechas de especificación del documento base: existe el disparador (Contrato) y el resultado (dashboard), pero falta el **contrato de permisos** de quien vive dentro de ese resultado.

### 5.4 Aprobación y auditoría (rol funcional, no un actor con login)
```
A2 (o A1) cambia estado de cumplimiento / cierra no conformidad
        │
        ▼
RNF-08: se genera registro inmutable
(quién, cuándo, por qué, quién aprobó)
        │
        ▼
"Quién aprobó" implica un segundo actor —
sin RF que defina qué nivel de RBAC habilita aprobar
```

---

## 6. Inconsistencias y riesgos detectados en el modelo de actores

1. **A4 (Gestor) no es un actor independiente de A1** — es una capacidad de tenant. La tabla de la sección 2 los presenta como pares (A0–A4), lo cual puede inducir a error en el diseño de RBAC si se implementa como un rol de usuario separado en vez de un flag/módulo sobre el tenant.
2. **Cliente final del sub-tenant (A5) no tiene fila propia** pese a tener dashboard, permisos y flujo de alta explícitos en el texto (RF-65 a RF-67). Es el hallazgo de mayor prioridad de este análisis.
3. **"Soporte" como equipo distinto de Superadmin se menciona pero no se modela** (RF-84) — riesgo de que en implementación se trate como el mismo usuario que A0, contradiciendo el propio RF.
4. **No se define cardinalidad de A1** (¿un solo Admin Empresa por tenant o varios?). Afecta directamente el diseño de la tabla `users` y de RLS.
5. **A3 no tiene Departamento** y por tanto queda fuera del filtro de RF-40 (vista por departamento) — hay que decidir explícitamente cómo se enruta un ticket de A3 a un A2 responsable.
6. **Los agentes de IA actúan (crean notificaciones/tickets) pero el RNF-08 de auditoría no aclara si su "identidad" queda registrada como actor de sistema** en el audit log, algo crítico para RNF-25 (auditorías externas) y para distinguir acción humana de acción automatizada ante un ente regulador.
7. **El actor que entra vía LTI (LMS externo) no está mapeado a ninguno de los 5 roles** — falta declarar si un usuario vía LTI equivale a A2, a un modo de solo lectura, o a un rol nuevo "A6 — Usuario LTI/Embed".
8. **Visibilidad del Gestor sobre datos del sub-tenant**: no se aclara si es lectura, escritura o representación total ("actuar en nombre de"), lo cual tiene implicancia directa sobre RNF-07 (aislamiento RLS) — si el Gestor puede escribir directamente en el tenant del cliente final, el aislamiento "lógico por tenant" necesita una excepción documentada, no implícita.

---

## 7. Recomendaciones para v1.8 / OpenSpec

1. **Agregar A5 — Cliente final / Usuario sub-tenant** a la tabla de actores de la sección 2, con RFs propios de permisos (lectura de sus obligaciones, carga de evidencias, límites de visibilidad del Contrato).
2. **Reclasificar A4 (Gestor)** en el documento no como actor par de A0–A3, sino como *"extensión de capacidades de A1 cuando el tenant tiene el módulo Gestores activo"* — evita ambigüedad de implementación en RBAC.
3. **Formalizar el rol de Soporte** como sub-permiso de A0 (ej. `platform.support.tickets` vs `platform.tenants.manage`), documentando explícitamente que Soporte ≠ Superadmin en capacidades.
4. **Definir cardinalidad de A1** por tenant (¿1 owner + N co-admins? ¿solo 1?) antes de diseñar la tabla `users`/`roles`.
5. **Añadir un RF explícito de enrutamiento de tickets de A3** hacia el A2/Departamento responsable, dado que A3 no tiene Departamento.
6. **Tratar a los agentes de IA como identidades de sistema en el audit log** (RNF-08/RNF-25), con un `actor_type` distinto de "usuario humano", trazable ante auditoría externa.
7. **Definir el mapeo de usuarios LTI a roles existentes** (o crear A6) antes de diseñar el modo Embed mencionado en la decisión cerrada #10.
8. **Aclarar el modo de acceso del Gestor sobre el sub-tenant** (lectura vs escritura vs actuación en nombre de) y su relación con el aislamiento RLS de RNF-07 — esto es tanto una decisión de actores como de arquitectura de datos.
9. **Separar explícitamente el permiso de "aprobar"** dentro del RBAC de A2, en vez de dejarlo implícito en el campo "quién aprobó" del audit log.

---

## 8. Preguntas para la próxima reunión de gobernanza

- ¿El cliente final del Gestor puede tener más de un usuario, o es 1:1 con el Contrato?
- ¿Un Admin Empresa puede delegar su rol completo a un segundo usuario, o solo delegar permisos parciales vía RBAC de Usuario Interno?
- ¿Qué pasa si un Cliente Invitado genera múltiples tickets con distintas claves dinámicas — se consolidan bajo el mismo RUT?
- ¿El agente de monitoreo normativo notifica directamente al Admin Empresa o siempre pasa primero por el Superadmin?
- ¿Un usuario que entra vía LTI puede además tener una cuenta directa (Microsoft/Google) en el mismo tenant, o son excluyentes?

---

## 9. Usuarios de prueba (seed data) por actor

Set de usuarios ficticios listos para usar en desarrollo/QA. Cubren los 5 actores formales **más** los implícitos identificados en la sección 3, para que ningún flujo quede sin cobertura de prueba. RUTs con formato válido pero ficticio; contraseñas de ejemplo para ambiente de desarrollo, nunca para producción.

### A0 — Superadmin / Admin de plataforma

| Campo | Valor |
|---|---|
| Nombre | Bárbara Contreras |
| Email | barbara.contreras@ambienta-platform.dev |
| Auth | Microsoft SSO |
| Tenant | — (cross-tenant, sin Empresa) |
| Permisos | Gestión total de tenants, límites, módulos, planes de prueba |
| Uso sugerido | Probar habilitar/deshabilitar tenants, revisar Chatbot privilegiado, ver alertas de agentes de monitoreo normativo |

### A0b — Agente de Soporte (implícito, sub-rol de plataforma)

| Campo | Valor |
|---|---|
| Nombre | Diego Salinas |
| Email | diego.salinas@ambienta-platform.dev |
| Auth | Microsoft SSO |
| Tenant | — (cross-tenant, acceso restringido a módulo Soporte) |
| Permisos | Ver/gestionar tickets de soporte, corregir logs erróneos (con auditoría). Sin permiso para gestionar tenants ni límites |
| Uso sugerido | Verificar que RF-84 se cumple: este usuario NO debería poder deshabilitar un tenant ni ver el Chatbot privilegiado con métricas globales |

### A1 — Admin Empresa (Tenant Owner)

| Campo | Valor |
|---|---|
| Nombre | Rodrigo Faúndez |
| Email | rodrigo.faundez@mineraaltoandes.cl |
| RUT | 12.345.678-9 |
| Auth | Microsoft SSO (con clave local de respaldo RUT + clave) |
| Empresa / tenant | Minera Alto Andes SpA |
| Permisos | Completo dentro del tenant. Aún no completó Perfil Empresa |
| Uso sugerido | Probar el flujo bloqueante de onboarding (RF-10): este usuario debería quedar impedido de entrar a Matriz Legal/Obligaciones hasta terminar plantas, departamentos y trabajadores |

### A1 (variante) — Admin Empresa con Perfil Empresa ya completo

| Campo | Valor |
|---|---|
| Nombre | Camila Yévenes |
| Email | camila.yevenes@aguasdelmaule.cl |
| RUT | 15.987.654-3 |
| Auth | Google |
| Empresa / tenant | Aguas del Maule Ltda. |
| Permisos | Completo dentro del tenant. Perfil Empresa completo (2 plantas, 3 departamentos, 8 trabajadores) |
| Uso sugerido | Probar Matriz Legal, Obligaciones, subida de PDFs ISO/RCA al Catálogo Normativo, generación de Contratos si se activa el módulo Gestor |

### A2 — Usuario Interno

| Campo | Valor |
|---|---|
| Nombre | Ignacio Riquelme |
| Email | ignacio.riquelme@aguasdelmaule.cl |
| RUT | 18.222.333-5 |
| Auth | Google |
| Empresa / tenant | Aguas del Maule Ltda. |
| Departamento | Medio Ambiente y Cumplimiento |
| Permisos (RBAC) | Evaluar tareas asignadas, adjuntar evidencias, ver Gantt/Kanban filtrado por su departamento. Sin permiso de aprobar cierre de no conformidades |

### A2 (variante) — Usuario Interno con permiso de aprobación

| Campo | Valor |
|---|---|
| Nombre | Valentina Ossandón |
| Email | valentina.ossandon@aguasdelmaule.cl |
| RUT | 16.555.888-1 |
| Auth | Google |
| Empresa / tenant | Aguas del Maule Ltda. |
| Departamento | Jefatura HSE |
| Permisos (RBAC) | Todo lo de Usuario Interno + `puede_aprobar_cierre` (ver hallazgo §3.3 y recomendación §7.9) |
| Uso sugerido | Probar el flujo de aprobación/firma de cierre de no conformidades (RF-49) y verificar que quede en el audit log como "aprobador" distinto de quien reportó el hallazgo |

### A3 — Cliente / Invitado

| Campo | Valor |
|---|---|
| Nombre | (sin nombre registrado — llega por link especial) |
| RUT asignado por el sistema | 9.111.222-K |
| Clave dinámica asignada | AMB-7f3k9d (ejemplo de formato) |
| Empresa / tenant | Minera Alto Andes SpA (empresa que emitió el link) |
| Permisos | Solo generar/consultar sus propios tickets. Sin Departamento asignado |
| Uso sugerido | Probar el link especial de principio a fin: generación automática de RUT + clave, creación de ticket, y luego que el A1 (Rodrigo Faúndez) lo registre como permanente para verificar la transición A3 → A2 |

### A4 — Admin Empresa con módulo Gestor activo

| Campo | Valor |
|---|---|
| Nombre | Francisca Lagos |
| Email | francisca.lagos@resiflow-gestion.cl |
| RUT | 14.777.111-8 |
| Auth | Microsoft SSO |
| Empresa / tenant | ResiFlow Gestión de Residuos SpA (tenant tipo Gestor) |
| Permisos | Todo lo de A1 + módulo de Gestores: crear Contratos formales y sub-tenants, ver datos de clientes/contactos |
| Uso sugerido | Probar creación de un Contrato con un cliente ficticio y verificar que se genere automáticamente el dashboard del sub-tenant (RF-66) |

### A5 — Cliente final / usuario sub-tenant (implícito, ver hallazgo §3.2)

| Campo | Valor |
|---|---|
| Nombre | Marcelo Peña |
| Email | marcelo.pena@panaderiaelsol.cl |
| RUT | 17.444.222-6 |
| Auth | RUT + clave (asignada al crear el sub-tenant vía Contrato) |
| Sub-tenant | Panadería El Sol Ltda. (cliente de ResiFlow Gestión de Residuos) |
| Contrato asociado | Contrato #RF-2026-0143 (ResiFlow ↔ Panadería El Sol) |
| Permisos | Limitados — pendientes de definición exacta (ver §6, punto 2). Se recomienda partir con: lectura de sus propias declaraciones de residuos y recepción de notificaciones, sin edición de Contrato |
| Uso sugerido | Usuario clave para levantar todas las preguntas abiertas de la sección 8 sobre alcance de permisos del cliente final |

### A6 — Usuario vía LTI / Embed (implícito, ver hallazgo §3.6)

| Campo | Valor |
|---|---|
| Nombre | Usuario de prueba LTI |
| Contexto de origen | Curso "Gestión Ambiental Industrial" en Moodle (LMS ficticio de prueba) |
| Rol heredado propuesto | Usuario Interno (A2), Departamento "Capacitación" — a confirmar con negocio |
| Auth | Lanzamiento LTI 1.3 Advantage (no login directo) |
| Uso sugerido | Probar el "Modo Embed/LTI" mencionado en la decisión cerrada #10 y confirmar si este usuario debería o no poder acceder también de forma directa (fuera del LMS) con el mismo RUT |

### Agentes de sistema (no humanos, con identidad propia en el audit log)

| Actor de sistema | Identificador sugerido | Rol funcional |
|---|---|---|
| AmbiAgent (chat tenant-aware) | `system.ambiagent` | Responde consultas, tenant-aware |
| Agente de ingesta / Catálogo | `system.ingest_bcn` | Alimenta Matriz Legal / Obligaciones |
| Agente de monitoreo normativo | `system.monitor_normativo` | Crea notificaciones/tickets automáticos |
| Chatbot privilegiado | `system.ambiagent_admin` | Exclusivo de A0 |

**Nota de uso general:** todos los `tenant` de ejemplo (Minera Alto Andes, Aguas del Maule, ResiFlow Gestión de Residuos, Panadería El Sol) son ficticios y pueden reutilizarse consistentemente en QA para simular el flujo completo: Gestor (ResiFlow) → Contrato → sub-tenant (Panadería El Sol) → cliente final (Marcelo Peña), en paralelo con un tenant estándar (Aguas del Maule) para el flujo de cumplimiento normal.
