# Design: La cadena de matrices de ISO 14001

Documento técnico de [`proposal.md`](./proposal.md).

---

## 1. La cadena y sus enlaces

```
Departamento (§4.4)
      │  procesoId
      ▼
AspectoAmbiental (§6.1.2) ──────┐
      │  significativo          │ aspectoAmbientalIds
      ▼                         ▼
RiesgoOportunidad (§6.1.4)   LegalNorm (§6.1.3)
      │                         │
      └────────┬────────────────┘
               ▼
        PlanAccion (§6.1.5)
```

Cada flecha es una respuesta a "¿por qué?". Un requisito legal sin aspecto
asociado es un requisito que nadie justificó; un aspecto significativo sin
riesgo ni requisito es un aspecto que nadie trató.

**Ninguno de los enlaces es obligatorio en el schema.** Se modelan como listas
que pueden estar vacías, porque forzarlos impediría cargar una matriz legal
antes de tener los aspectos — que es exactamente la situación de hoy. La
completitud se mide y se muestra; no se impone.

---

## 2. `AspectoAmbiental`

```ts
AspectoAmbiental {
  id
  tenantId
  plantId
  procesoId                  // Departamento del mapa de procesos

  actividad: string          // "Lavado de equipos de envasado"
  aspecto: string            // "Vertido de agua con detergente"
  tipoAspecto: TipoAspecto
  impacto: string            // "Alteración de la calidad del cuerpo receptor"

  // §6.1.2 exige considerar las tres condiciones, no solo la normal.
  condicionOperacion: 'normal' | 'anormal' | 'emergencia'

  // §6.1.2 perspectiva de ciclo de vida.
  etapaCicloVida: 'materias_primas' | 'produccion' | 'distribucion' | 'uso' | 'fin_de_vida'

  evaluacion: EvaluacionSignificancia
  significativo: boolean     // Derivado del puntaje y el umbral del tenant

  requisitoLegalIds: string[]
  riesgoOportunidadIds: string[]

  fechaIdentificacion: string
  fechaUltimaRevision?: string
  responsableId?: string
}
```

`TipoAspecto`: `emision_atmosferica` · `vertido_agua` · `residuo_solido` ·
`residuo_peligroso` · `consumo_agua` · `consumo_energia` · `ruido` ·
`contaminacion_suelo` · `biodiversidad` · `gases_efecto_invernadero` · `otro`.

**Por qué `biodiversidad` y `gases_efecto_invernadero` están en la lista:** ISO
14001:2026 amplía el contexto para incluirlos explícitamente. En la edición 2015
se habrían modelado como `otro`, y eso vuelve imposible reportarlos.

**Por qué `condicionOperacion` es un campo y no una nota:** la norma pide
considerar situaciones anormales y de emergencia. Un derrame no ocurre en
condición normal, y si el modelo solo admite la normal, la matriz omite
precisamente los aspectos de mayor impacto.

### 2.1 `EvaluacionSignificancia`

```ts
EvaluacionSignificancia {
  criterios: { criterioId: string; valor: number }[]
  puntaje: number            // Calculado según el método del tenant
  metodoId: string           // Del catálogo de configuración
  evaluadoPorId: string
  fecha: string
  justificacion?: string
}
```

Los criterios y el método viven en la configuración del tenant, no en el
schema. Un default razonable: severidad, frecuencia, alcance y existencia de
requisito legal, cada uno de 1 a 3, con umbral de significancia en el producto
o la suma según el método elegido.

**Por qué configurable.** Los criterios de significancia varían por sector y por
la madurez del sistema de gestión. Cablearlos obliga a migrar el día que entre
un cliente con su propia metodología ya auditada, que es el caso normal en una
empresa certificada.

---

## 3. `RiesgoOportunidad`

```ts
RiesgoOportunidad {
  id
  tenantId
  plantId
  codigo: string

  tipo: 'riesgo' | 'oportunidad'

  // De dónde salió. §6.1.4 los deriva del contexto y de las partes interesadas.
  origen: 'aspecto_ambiental' | 'requisito_legal' | 'contexto' | 'parte_interesada'
        | 'auditoria' | 'cambio_climatico' | 'registro_mejora'
  origenId?: string

  descripcion: string
  procesoIds: string[]

  evaluacion: {
    probabilidad: number
    consecuencia: number
    nivel: 'bajo' | 'medio' | 'alto' | 'critico'
    metodoId: string
    fecha: string
  }

  // Para riesgo: evitar/mitigar/transferir/aceptar. Para oportunidad: aprovechar/descartar.
  tratamiento: 'evitar' | 'mitigar' | 'transferir' | 'aceptar' | 'aprovechar' | 'descartar'
  justificacionTratamiento?: string   // Obligatoria si se acepta o se descarta

  planAccionId?: string
  responsableId: string
  estado: 'identificado' | 'en_tratamiento' | 'controlado' | 'cerrado'

  fechaIdentificacion: string
  proximaRevision?: string
}
```

**Por qué `justificacionTratamiento` es obligatoria al aceptar o descartar:**
son las dos decisiones que no dejan rastro de acción. Un riesgo aceptado sin
justificación es indistinguible de un riesgo olvidado, y es lo primero que un
auditor pide explicar.

**Relación con el registro de mejora.** Un registro de tipo `riesgo` u
`oportunidad` puede originar una entrada acá (`origen: 'registro_mejora'`), pero
la matriz existe con independencia de que alguien reporte algo. Esa es la
diferencia entre planificar y reaccionar.

---

## 4. Ampliación de `LegalNorm`

Todos los campos nuevos son **opcionales**, para que la matriz existente siga
validando sin migración.

```ts
LegalNorm {
  // ...campos actuales sin cambios...

  // §6.1.3 "obligaciones de compliance": la ley y lo que la empresa decide cumplir.
  categoriaRequisito?: 'legal' | 'otro_requisito'
  subtipo?: 'ley' | 'decreto' | 'resolucion' | 'rca' | 'permiso_sectorial'
          | 'iso' | 'apl' | 'requisito_cliente' | 'compromiso_voluntario'

  organismoFiscalizador?: string    // SMA · SEC · SISS · Seremi de Salud · DGA

  vigencia?: {
    estado: 'vigente' | 'derogada' | 'modificada' | 'proyecto'
    desde?: string
    hasta?: string
    reemplazaANormaId?: string
    reemplazadaPorNormaId?: string
  }

  aplicabilidad?: {
    determinadaPor: 'automatica' | 'manual'
    actividadesEconomicas: string[]   // Códigos CIIU
    criterio?: string                 // Por qué aplica, en palabras
    aspectoAmbientalIds: string[]     // El "por qué" trazable
  }

  // §9.1.2 exige la evaluación de compliance periódicamente.
  evaluacionPeriodica?: {
    frecuenciaMeses: number
    ultimaEvaluacion?: string
    proximaEvaluacion?: string
  }
}
```

Y el artículo:

```ts
Articulo {
  // ...campos actuales sin cambios...

  // El D.S. 609 no se cumple o incumple: fija un programa de monitoreo.
  obligacionMonitoreo?: {
    parametros: { nombre: string; unidad: string; limiteMaximo?: number; metodo?: string }[]
    frecuencia: 'diaria' | 'semanal' | 'mensual' | 'trimestral' | 'semestral' | 'anual'
    requiereLaboratorioAcreditado: boolean
    cuerpoReceptor?: string
  }

  // La reunión: las empresas no digitalizan; el papel bajo custodia es evidencia.
  evidenciaFisica?: {
    ubicacion: string
    custodioId?: string
    referencia?: string
  }

  equipoIds?: string[]        // Requisitos anclados a un activo concreto
}
```

**Por qué `obligacionMonitoreo` es una estructura y no texto libre.** Un límite
de parámetro con su frecuencia es lo que permite generar el calendario y
detectar que una medición venció. En texto libre, el sistema no puede avisar
nada — que es justamente el problema que Ambienta existe para resolver.

---

## 5. `EquipoRegulado`

```ts
EquipoRegulado {
  id
  tenantId
  plantId
  tipo: 'caldera' | 'generador' | 'grupo_electrogeno' | 'estanque' | 'compresor' | 'otro'
  marca?: string
  modelo?: string
  numeroSerie?: string

  inscripcion?: {
    organismo: string          // SEC, Seremi de Salud
    numero: string
    fecha: string
    vencimiento?: string
  }

  // Operadores con competencia habilitante vigente.
  operadores: {
    usuarioId: string
    certificacion: string      // "Operador de caldera clase B"
    emitidaPor?: string
    vence?: string
  }[]

  requisitoLegalIds: string[]
  estado: 'operativo' | 'fuera_de_servicio' | 'baja'
}
```

**Por qué existe.** La reunión fue concreta: hay que inscribir calderas,
generadores y grupos electrógenos, y *"cuando hay calderas hay que ver cuándo
hay habilitados operadores de caldera con ciertos cursos que se deben cumplir;
hay distintos modelos de caldera, eso es importante, que esté mapeado"*.

Un requisito legal que exige un operador certificado no se cumple a nivel de
planta: se cumple si **esa persona** tiene **ese curso** vigente. Sin el equipo
y sin la certificación con fecha de vencimiento, el sistema no puede alertar que
mañana la caldera queda sin operador habilitado.

---

## 6. Los dos indicadores

```
Cumplimiento legal = artículos con respuesta SI / artículos aplicables
                     (NO, N_E y sin evaluar cuentan en el denominador)

Cobertura         = artículos evaluados / artículos aplicables
                     (NA sale de ambos: no aplicable no es incumplido)
```

`incluidoEnCalculo` se mantiene y sigue afectando **solo** al cumplimiento, no
a la cobertura. Excluir un artículo del cálculo de cumplimiento es una decisión
legítima; excluirlo de la cobertura sería esconder que no se revisó.

---

## 7. La feature flag

```ts
// packages/shared/src/feature-flags.ts
FEATURE_FLAGS = { matricesIso: boolean }
```

Lee `NEXT_PUBLIC_FF_MATRICES_ISO`. **Por defecto encendida**, porque el objetivo
es evaluar la cadena; se apaga con `NEXT_PUBLIC_FF_MATRICES_ISO=false`.

Con la flag apagada:

- Las entidades nuevas no se muestran ni se cargan.
- Los campos nuevos de `LegalNorm` se ignoran; como son opcionales, la matriz
  actual valida igual.
- El cálculo de cumplimiento vuelve a un solo indicador.

**Por qué una flag y no una rama.** Una rama obliga a elegir entre tener el
trabajo o tener el sistema estable. La flag permite mostrar la cadena completa
a un cliente el martes y apagarla el miércoles sin tocar código.

---

## 8. Lo que este diseño no resuelve

- **Poblar el catálogo de aplicabilidad por CIIU.** Es trabajo de contenido
  permanente. El modelo lo admite; nadie lo llena todavía.
- **Carga de resultados de laboratorio.** Se modela qué hay que medir, no cómo
  entra el resultado.
- **SEA y APL como flujos.** Entran como tipos de requisito, sin su ciclo propio.
- **La interfaz.** Esta entrega es modelo, mocks y flag.
