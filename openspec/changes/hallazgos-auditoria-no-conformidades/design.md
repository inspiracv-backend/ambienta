# Design: Hallazgos de auditoría y gestión de no conformidades

Documento técnico de la propuesta [`proposal.md`](./proposal.md).

---

## 1. Las tres etapas y por qué deben ser tres entidades

ISO 9001 trata como distintas tres cosas que hoy el sistema fusiona:

| Etapa | Norma | Pregunta que responde | Entidad |
|---|---|---|---|
| Planificar | §9.2.2 | ¿Qué se va a auditar, contra qué criterios y cuándo? | `Auditoria` |
| Ejecutar | ISO 19011 | ¿Qué se encontró al evaluar cada requisito? | `Hallazgo` |
| Tratar | §10.2 | ¿Qué se hace con lo que no cumple? | `NoConformidad` |

Fusionarlas tiene un costo concreto: **no se puede cerrar una auditoría sin
cerrar sus no conformidades**, porque son el mismo objeto. En la realidad la
auditoría se cierra con su informe, y las no conformidades siguen su propio
ciclo durante semanas o meses después.

---

## 2. Modelo propuesto

### 2.1 `Auditoria`

```ts
Auditoria {
  id
  tenantId
  plantId
  tipo: 'interna' | 'externa'

  // Rango, no fecha única: una auditoría se planifica con ventana.
  fechaInicioPlanificada: string
  fechaTerminoPlanificada: string
  fechaInicioReal?: string
  fechaTerminoReal?: string

  estado: 'planificada' | 'en_ejecucion' | 'ejecutada' | 'cerrada' | 'cancelada'

  // Criterios de auditoría (ISO 19011): contra qué se audita.
  normativaIds: string[]
  // Alcance: qué procesos/departamentos entran.
  procesoIds: string[]

  auditorLiderId: string
  equipoAuditorIds: string[]

  // Solo para externas: quién audita desde fuera.
  organismoAuditor?: string

  conclusiones?: string   // Se completa al cerrar (informe de auditoría)
}
```

**Por qué `fechaInicioReal` separada de la planificada:** ISO 9001 §9.2.2 pide
mantener el programa de auditorías. Si al reprogramar se sobrescribe la fecha
original, se pierde la evidencia de que el programa se desvió — que es
justamente lo que un certificador mira.

**Por qué `cancelada` es un estado y no un borrado:** una auditoría planificada
que no se ejecutó es información auditable. Borrarla oculta un incumplimiento
del programa.

### 2.2 `Hallazgo` — la entidad nueva

```ts
Hallazgo {
  id
  tenantId
  auditoriaId              // Ver decisión abierta #4 en proposal.md
  plantId

  // El corazón del cambio.
  tipo: 'conformidad' | 'no_conformidad' | 'observacion' | 'oportunidad_mejora'

  // Solo aplica si tipo === 'no_conformidad'. En el resto debe ser null.
  severidad: 'mayor' | 'menor' | null

  // Contra qué requisito se evaluó: permite medir cobertura de la auditoría.
  requisitoAuditado: {
    normaId: string
    articuloId?: string     // Opcional: hay hallazgos a nivel de norma completa
    referencia: string      // Foto legible: "ISO 9001 §7.5.3"
  }

  descripcion: string       // Qué se observó
  evidencia: string         // En qué se sustenta (ISO 19011: evidencia de auditoría)
  evidenciaUrls: string[]

  detectadoPorId: string
  fechaDeteccion: string

  // Se completa solo si el hallazgo derivó en tratamiento.
  noConformidadId?: string
}
```

**Regla de integridad:** `severidad` solo puede ser no nula cuando
`tipo === 'no_conformidad'`. Una conformidad "menor" no significa nada, y
permitirlo genera datos que después nadie sabe interpretar.

**Por qué `evidencia` es obligatoria y separada de `descripcion`:** ISO 19011
distingue el hallazgo (la conclusión) de la evidencia de auditoría (el hecho
verificable que lo sustenta). Un hallazgo sin evidencia no es defendible ante
una apelación del auditado.

### 2.3 `NoConformidad` — pasa a ser el tratamiento

```ts
NoConformidad {
  id
  tenantId
  hallazgoId               // Origen: siempre nace de un hallazgo

  estado: 'abierta' | 'en_analisis' | 'en_tratamiento' | 'en_verificacion' | 'cerrada'

  // §10.2.1 a): reaccionar — qué se hizo de inmediato para contener.
  correccionInmediata?: string

  // §10.2.1 b): analizar la causa.
  cincoPorques: string[]
  causaRaiz?: string

  // §10.2.1 c/d): la acción correctiva vive como Plan de Acción.
  planAccionId?: string

  // §10.2.1 e): revisar la eficacia. ESTA ES LA ETAPA QUE FALTA HOY.
  verificacionEficacia?: {
    fecha: string
    verificadaPorId: string
    esEficaz: boolean
    observaciones: string
  }

  cierre?: {
    fecha: string
    responsableId: string
    firmada: boolean
  }

  responsableId: string
  fechaCompromiso: string
}
```

**La verificación de eficacia es el hueco más serio del modelo actual.** Hoy
una no conformidad se cierra con firma (RF-49) directamente desde el
tratamiento. §10.2.1 e) exige revisar la eficacia de la acción correctiva
**antes** de cerrar: si la acción no resolvió la causa, la NC no debería
cerrarse. Sin este paso, el sistema permite cerrar formalmente problemas que
siguen abiertos en la práctica — que es exactamente el hallazgo que un
certificador levanta contra el propio sistema de gestión.

---

## 3. Máquina de estados de la No Conformidad

```
abierta ──► en_analisis ──► en_tratamiento ──► en_verificacion ──► cerrada
                                                      │
                                                      └──► (no eficaz) ──► en_tratamiento
```

| Transición | Precondición |
|---|---|
| `abierta → en_analisis` | — |
| `en_analisis → en_tratamiento` | `causaRaiz` no vacía |
| `en_tratamiento → en_verificacion` | Existe `planAccionId` **y** su plan está cerrado |
| `en_verificacion → cerrada` | `verificacionEficacia.esEficaz === true` **y** firma del responsable |
| `en_verificacion → en_tratamiento` | `verificacionEficacia.esEficaz === false` |

**El bucle de reapertura no es un detalle:** es lo que distingue un sistema de
gestión real de un registro de tareas. Una acción correctiva que no funcionó
devuelve la NC a tratamiento, y ese ida y vuelta queda en el audit log.

---

## 4. Cobertura de auditoría

Al elegir las normas de una auditoría (`normativaIds`), el sistema despliega
sus artículos como **requisitos a auditar**. Cada uno puede terminar en un
hallazgo o quedar sin evaluar.

```
Cobertura = requisitos con hallazgo / requisitos en alcance
```

Esto responde una pregunta que hoy el sistema no puede contestar: *"¿qué parte
de la norma alcanzamos a auditar?"*. Una auditoría con 20% de cobertura y cero
no conformidades no es una buena noticia — es una auditoría incompleta, y hoy
se ve idéntica a una completa sin hallazgos.

---

## 5. Migración desde el modelo actual

Los datos actuales son mocks, así que la migración es de **código**, no de
datos productivos. Aun así hay que definirla porque el audit log ya tiene
eventos con `entidadTipo: 'no_conformidad'`.

| Dato actual | Destino |
|---|---|
| `NonConformity` con `hallazgo`, `criticidad` | Se divide: `Hallazgo` (tipo `no_conformidad`, severidad derivada de criticidad) + `NoConformidad` (tratamiento) |
| `criticidad: alta` | `severidad: mayor` |
| `criticidad: media` \| `baja` | `severidad: menor` |
| `cincoPorques` | Se mueve a `NoConformidad` |
| `cierre` | Se mantiene, pero ahora exige `verificacionEficacia` previa |
| Audit log con `entidadTipo: 'no_conformidad'` | **Se conserva tal cual.** Los eventos históricos no se reescriben |

**Sobre el audit log:** reescribir eventos pasados para que apunten a la nueva
entidad violaría su inmutabilidad (RNF-08). Se agrega `'hallazgo'` como tipo
nuevo y los eventos antiguos siguen diciendo `no_conformidad`, que es lo que
efectivamente ocurrió cuando se registraron.

---

## 6. Impacto en pantallas

| Pantalla | Cambio |
|---|---|
| S-20 Listado de auditorías | Agregar **crear auditoría**; mostrar rango de fechas y cobertura |
| S-21 Detalle de auditoría | Mostrar requisitos a auditar y sus hallazgos; quitar el acceso directo a NC |
| S-24 Registrar hallazgo | **Cambia de fondo:** primero se elige el tipo; los campos de tratamiento solo aparecen si es no conformidad |
| Nueva: Gestión de No Conformidades | Su propio módulo, con la máquina de estados y la verificación de eficacia |
| S-06/S-07 Dashboard | El contador pasa a ser "No conformidades abiertas" sobre no conformidades reales |
| S-39/S-40 Reportes | Permite filtrar por tipo de hallazgo; la carpeta de auditoría incluye los conformes |

---

## 7. Lo que este diseño deliberadamente no resuelve

- **Auditorías de proveedores (segunda parte).** El funcional solo distingue
  interna/externa. Auditar a un tercero necesita modelar al auditado como
  entidad, y eso toca el módulo de Gestores.
- **Programa anual de auditorías.** §9.2.2 pide un programa, no auditorías
  sueltas. Aquí cada auditoría es independiente. Es una carencia real pero de
  alcance mayor.
- **Firma electrónica con validez legal.** `firmada: boolean` es un registro de
  acto, no una firma criptográfica. Si el cliente necesita valor probatorio
  ante terceros, requiere otra propuesta.
