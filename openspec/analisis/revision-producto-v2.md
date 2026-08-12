# Revisión de producto — hallazgos de la sesión de 2026-07-29

Feedback del equipo tras recorrer el sistema levantado. Cada punto está
verificado contra el código, no asumido. Se separa lo que es **error de
modelo de dominio** (requiere spec antes de implementar, CLAUDE.md §1) de lo
que es **interfaz o funcionalidad faltante** (se puede construir sobre el
modelo actual).

---

## 0. El hallazgo más importante: Hallazgo ≠ No conformidad

**Estado: confirmado. Es un error de modelo, no de interfaz.**

Hoy `packages/shared/src/schemas/audit.ts` solo tiene `NonConformity`. Todo lo
que se registra en una auditoría se registra como no conformidad — no existe
forma de anotar un hallazgo conforme.

Esto contradice **ISO 19011** (directrices para auditoría de sistemas de
gestión), que define el hallazgo de auditoría como el resultado de evaluar la
evidencia contra los criterios de auditoría — y ese resultado **puede indicar
conformidad o no conformidad**. Registrar solo lo negativo:

- Impide demostrar qué se auditó y salió bien, que es la mitad del valor de
  una auditoría ante un certificador.
- Falsea las métricas: el dashboard cuenta "No Conformidades abiertas" sobre
  un universo que en realidad son *todos* los hallazgos.
- Deja sin lugar a las **observaciones** y **oportunidades de mejora**, que en
  la práctica de ISO 9001 son categorías distintas de una no conformidad y no
  disparan acción correctiva obligatoria.

### Modelo propuesto

```
Auditoría (programa: qué se audita, contra qué norma, cuándo, interna/externa)
   └── Hallazgo (resultado de evaluar un requisito)
         ├── tipo: conformidad | no_conformidad | observacion | oportunidad_mejora
         ├── severidad: mayor | menor        ← solo si es no_conformidad
         └── requisitoAuditado: referencia al artículo/cláusula
               └── No conformidad → Acción correctiva → Plan de acción → Seguimiento → Cierre
```

Consecuencias en cascada (por eso necesita spec y no parche):

- `NonConformity` pasa a ser un caso de `Hallazgo`, no la entidad raíz.
- Las métricas del dashboard y los reportes cambian de denominador.
- El audit log ya registra `no_conformidad` como tipo de entidad; habría que
  introducir `hallazgo`.
- Los planes de acción cuelgan de la no conformidad, no del hallazgo genérico.

> **Recomendación:** este punto va a `openspec/changes/` como propuesta antes
> de tocar código. Es el cambio con más alcance de toda la lista.

---

## 1. Auditorías — el módulo con más confusión conceptual

| # | Observación | Verificado | Tipo |
|---|---|---|---|
| 1.1 | **No existe "crear auditoría"** | ✅ Confirmado: no hay ningún `createAudit`/`addAudit` en el código | Funcionalidad faltante |
| 1.2 | Una auditoría planificada debería tener **rango de fechas**, no una sola | ✅ `Audit.fecha` es un solo string | Modelo (menor) |
| 1.3 | El botón de No Conformidades dentro de la auditoría no tiene sentido ahí | ✅ | Interfaz |
| 1.4 | **Se audita contra normas**: al elegir qué se audita deberían salir los ítems/cláusulas a revisar | ✅ `Audit.normativaIds` existe pero no despliega sus artículos | Funcionalidad |
| 1.5 | La gestión de No Conformidades debe ser su propio flujo, separado del registro de hallazgos | ✅ Hoy están fusionados | Ver §0 |

**Lectura de conjunto:** el módulo mezcla tres cosas que en ISO 9001 §9.2 son
etapas distintas: *planificar la auditoría* → *ejecutarla y registrar
hallazgos* → *tratar las no conformidades que resulten*. La interfaz actual
salta directo de la lista de auditorías al registro de no conformidades.

---

## 2. Superadmin y gestión de tenants

| # | Observación | Verificado | Tipo |
|---|---|---|---|
| 2.1 | **No existe crear tenant** | ✅ Confirmado, no hay `createTenant` | Funcionalidad faltante |
| 2.2 | Al crear un tenant falta declarar **país** | ✅ `Tenant` no tiene campo país, pese a que el producto se define multi-país | Modelo |
| 2.3 | Falta **información del cliente / CRM** | ✅ | Modelo + funcionalidad |
| 2.4 | Al crear el tenant hay que **crear su usuario administrador** | ✅ Hoy no hay flujo de alta | Funcionalidad |
| 2.5 | **Planes de prueba / demo** (ej. 10 días) con usuarios manuales | ✅ El ítem existe en el menú marcado "Próximamente" | Funcionalidad (RF-82) |
| 2.6 | El Superadmin debería poder **añadir otro Superadmin**, con permisos diferenciados | ✅ No existe | Modelo (sub-roles de A0) |
| 2.7 | El **historial debería filtrarse por tenant** | ✅ Hoy el Superadmin solo ve eventos de plataforma | Funcionalidad |
| 2.8 | **Chat entre administradores** | ✅ No existe | Módulo nuevo |

**Sobre 2.6:** el Análisis de Actores ya detectó esta tensión — RF-84 distingue
"equipo interno / Superadmin", lo que implica al menos dos niveles dentro de
A0 (Superadmin dueño del software vs. Soporte). Está documentado como pregunta
abierta §3.1 y sigue sin resolverse.

**Sobre 2.7:** hay una decisión de gobernanza detrás. Hoy el aislamiento es
estricto por diseño: el Superadmin **no** ve la operación de un tenant, porque
CLAUDE.md dice "Admin Global NO puede editar contenido de tenants". Poder
filtrar el historial por tenant significa darle **lectura** sobre esa
actividad — que la matriz de permisos sí le concede ("L", para soporte y
auditoría). Es compatible, pero hay que hacerlo explícito y auditado: que el
Superadmin mire el historial de un cliente debería, a su vez, quedar
registrado.

---

## 3. Seguridad de las acciones destructivas

> *"Es muy fácil borrar un usuario. No son usuarios transaccionales; son
> contratos de un año, como SAP. No debe haber botón de borrar tan rápido."*

**Estado: la crítica es válida y el argumento es correcto.**

Hoy desactivar un usuario es un botón directo en la fila de la tabla, con un
diálogo de confirmación. El punto de fondo es de diseño de producto: en una
plataforma corporativa las acciones destructivas no deberían estar al mismo
nivel visual que las de consulta.

**Propuesta:** mover desactivar/eliminar **dentro** de la edición del usuario,
no en la fila. La fila ofrece "Editar"; dentro del formulario, en una zona
separada al final ("Zona de riesgo"), vive la desactivación. Es el patrón que
usan GitHub, Stripe y los ERP: separación física, no solo un `confirm()`.

Aplica igual a suspender un tenant.

---

## 4. Matriz Legal y Catálogo Normativo

> *"Son bastante similares en la vista de Admin Empresa, están iguales y
> deberían estar juntos; quizá ser una función dentro de Matriz Legal."*

**Estado: confirmado, y más de lo que parece.** Ambas pantallas leen del
**mismo store** (`useLegalMatrix`) y de la misma entidad `LegalNorm`. No son
dos módulos: son dos vistas del mismo dato.

- **Catálogo Normativo** = la biblioteca (qué normas existen, sus 3 capas:
  BCN, ISO, RCA) y a qué plantas se asignan.
- **Matriz Legal** = la evaluación de cumplimiento de esas normas.

**Propuesta:** unificar en Matriz Legal con dos pestañas (*Evaluación* /
*Biblioteca*), y sacar Catálogo Normativo del menú principal. El análisis
funcional lo define como "módulo de primer nivel", así que este cambio
contradice el documento — **requiere validación del equipo**, no lo decido yo.

---

## 5. Trazabilidad (ISO) — parcialmente resuelto

| # | Observación | Estado |
|---|---|---|
| 5.1 | Al cambiar un estado en Evaluar debe generar log | ✅ **Ya implementado** en esta sesión: evaluar un artículo registra la respuesta anterior y la nueva, con la forma de cumplimiento como motivo |
| 5.2 | En Matriz Legal, log de cuándo empezó a cumplir y cuándo dejó de cumplir | ✅ **Cubierto** por lo anterior: el diff `Cumple → No cumple` queda con fecha y autor |
| 5.3 | Falta mostrar esa línea de tiempo **en la pantalla del artículo** | ⚠️ El `HistorialTimeline` existe y está montado en tickets, pero **falta montarlo** en el detalle de norma/artículo |

**5.3 es trabajo pequeño y de alto valor**: el componente ya está construido,
solo hay que colocarlo donde el usuario lo espera.

---

## 6. Evidencias — integración real con Drive

> *"Como en Trello: no es pegar un enlace, es ver la vista inmediata."*

**Estado: confirmado.** Hoy la evidencia es un campo de texto donde se pega una
URL (`ArticleEvaluationModal`, `TaskDetailModal`).

RF-09 y la Decisión cerrada #17 ya definen la solución: capa de abstracción de
almacenamiento + **Google Drive Picker** primero, OneDrive después. Lo que
falta es la implementación, que requiere credenciales OAuth y scope
`drive.file`.

**Bloqueado por:** credenciales de Google Cloud. No es un problema de diseño.

---

## 7. Perfil Empresa

| # | Observación | Verificado | Tipo |
|---|---|---|---|
| 7.1 | Falta el **logo de la empresa**, para que salga en los PDF | ✅ `Tenant` no tiene campo logo | Modelo + funcionalidad |
| 7.2 | Falta **mapa de departamentos** | ✅ | Funcionalidad |
| 7.3 | Falta **mapa de procesos** generado a partir de los departamentos | ✅ `Departamento` solo tiene `{id, tenantId, nombre}` — sin tipo de proceso | Modelo + funcionalidad |
| 7.4 | Los **tipos de proceso** son importantes | ✅ No existen | Modelo |
| 7.5 | Si la empresa ya está creada, debería dejarte entrar | ⚠️ Verificar: `PerfilEmpresaGate` solo bloquea si `perfilEmpresaCompleto` es false | A reproducir |

**Sobre 7.3 y 7.4:** ISO 9001 §4.4 exige el enfoque a procesos — identificar
los procesos del sistema de gestión, su secuencia e interacción. La
clasificación habitual es **estratégicos / operativos (o de realización) / de
apoyo**, y el mapa de procesos es la representación de esas interacciones. Hoy
un departamento es solo un nombre: no se puede generar ningún mapa a partir de
eso.

Modelo mínimo para habilitarlo:

```
Departamento/Proceso
  ├── tipo: estrategico | operativo | apoyo
  ├── responsableId
  ├── entradas / salidas        ← lo que permite dibujar interacciones
  └── indicadores               ← opcional
```

---

## 8. Usuarios y Roles

| # | Observación | Estado |
|---|---|---|
| 8.1 | El Admin Empresa debería poder **editar roles** | ✅ **Ya funciona**: `UserFormModal` tiene selector de rol. No requiere cambio |
| 8.2 | Falta **descriptor de cargo** (funciones y responsabilidades) | ✅ Confirmado: `User` no lo tiene |
| 8.3 | ¿Tiene sentido ver trabajadores en Perfil Empresa si están en Usuarios y Roles? | ⚠️ Decisión de diseño existente: en Perfil Empresa son **solo lectura**, la edición vive en Usuarios y Roles. Es duplicación de *visualización*, deliberada |

**Sobre 8.2:** ISO 9001 §7.2 (Competencia) exige determinar la competencia
necesaria de las personas que afectan el desempeño del sistema. El descriptor
de cargo es el documento donde eso normalmente vive, así que enlazarlo desde
el usuario es coherente con la norma. Puede ser un campo de texto, un archivo
adjunto o una entidad propia — hay que decidir el alcance.

---

## 9. Reportes en PDF

> *"Los reportes deberían ser más en PDF que en CSV."*

**Estado: confirmado y ya documentado como gap.** Hoy solo hay CSV, y la
interfaz lo dice explícitamente en vez de prometer PDF.

El motivo original sigue vigente: generar PDF requiere una librería
(`@react-pdf/renderer`, `pdfmake` o generación en el backend) y no hay ADR que
apruebe ninguna. Además, un PDF de auditoría **necesita el logo de la empresa**
(§7.1), así que este punto depende de aquel.

**Orden correcto:** logo → plantilla de PDF → reportes.

---

## Resumen: qué es qué

### Requiere spec antes de implementar (cambios de modelo)

1. **Hallazgo ≠ No conformidad** (§0) — el más grande, con efecto en cascada
2. Sub-roles de Superadmin (§2.6)
3. Tipos de proceso y mapa de procesos (§7.3, §7.4)
4. País y datos CRM del tenant (§2.2, §2.3)

### Se puede construir ahora (funcionalidad faltante)

5. **Crear tenant** con su administrador (§2.1, §2.4)
6. **Crear auditoría** con rango de fechas (§1.1, §1.2)
7. Logo de empresa (§7.1)
8. Descriptor de cargo (§8.2)
9. Historial filtrable por tenant para el Superadmin (§2.7)
10. Montar el historial en Matriz Legal / artículo (§5.3)

### Interfaz y seguridad

11. **Mover desactivar dentro de editar** (§3) — pequeño y de alto impacto
12. Unificar Catálogo Normativo dentro de Matriz Legal (§4) — *requiere validar
    contra el análisis funcional, que lo define como módulo de primer nivel*

### Bloqueado por decisiones o credenciales

13. Drive Picker (§6) — necesita credenciales OAuth
14. Reportes PDF (§9) — necesita ADR de librería, y depende del logo
15. Chat entre administradores (§2.8) — módulo nuevo, sin RF que lo respalde

### Ya resuelto — no requiere trabajo

- Log al cambiar estado de evaluación (§5.1, §5.2)
- Admin Empresa editando roles (§8.1)

---

## Sobre "revisar cómo lo hacen los sistemas ISO"

La estructura modular habitual de un software de sistema de gestión (SGC/SGA)
sigue el ciclo PHVA de la propia norma, y difiere de la actual de Ambienta en
un punto: **los procesos son el eje**, no un dato del perfil de la empresa.

| Bloque | Contenido típico | Dónde está hoy en Ambienta |
|---|---|---|
| Contexto y procesos | Mapa de procesos, partes interesadas, alcance | Parcial (departamentos sin tipo) |
| Información documentada | Control de documentos, versiones, vigencia | Catálogo Normativo (parcial) |
| Requisitos legales | Matriz de requisitos y su evaluación | Matriz Legal ✅ |
| Planificación operativa | Objetivos, programas, obligaciones | Obligaciones ✅ |
| Competencia | Perfiles de cargo, formación, evaluación | Falta (§8.2) |
| Auditoría | Programa anual, ejecución, hallazgos | Parcial (§1) |
| Mejora | No conformidades, acciones correctivas, seguimiento | Fusionado con hallazgos (§0) |
| Revisión por la dirección | Entradas/salidas consolidadas | No existe |

**Dos ausencias que el equipo no mencionó y conviene evaluar:**

- **Revisión por la dirección** (ISO 9001 §9.3): es una salida obligatoria del
  sistema y consolida casi todo lo demás. Sería un reporte, no un módulo.
- **Control de información documentada** (§7.5): versionado y vigencia de los
  documentos. Hoy el Catálogo guarda normas, pero sin control de versiones.
