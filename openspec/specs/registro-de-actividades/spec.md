# Registro de actividades

## Purpose

Qué pasó en la empresa, quién lo hizo y cuándo (RNF-08, RNF-25), y qué salió del
sistema hacia afuera (RNF-26). El registro se escribe solo —un observador del
`flush` anota lo que cambia por la ORM— y es de solo agregar: la aplicación
inserta y lee, nunca edita ni borra.

Esta capacidad cubre las dos cosas que le faltaban para servir en una auditoría
de accesos: **poder leerlo** desde la pantalla, con los eventos del servidor y no
los de la sesión del navegador, y **anotar las emisiones** de documentos, que no
pasan por la ORM y por eso no dejaban rastro.

## Requirements

### Requirement: El registro de actividades se puede consultar
El sistema SHALL mostrar a quien tenga permiso de historial los eventos registrados de su empresa, del más reciente al más antiguo, con quién actuó, cuándo, qué cambió y sobre qué registro.

El registro se escribe solo desde el 24-ago; sin una pantalla que lo lea, la trazabilidad que exigen RNF-08 y RNF-25 existía y nadie la podía ver.

#### Scenario: Consulta del registro
- **GIVEN** una empresa con actividad registrada
- **WHEN** alguien con permiso de historial abre el registro
- **THEN** ve los eventos del servidor, no solo los de su sesión, y siguen ahí después de recargar

#### Scenario: Un evento de un tipo que la pantalla no conoce
- **WHEN** el registro contiene un cambio sobre una tabla sin tipo reconocido en la pantalla
- **THEN** el evento se muestra igual, con la tabla como referencia, en vez de esconderse

#### Scenario: Página cortada
- **GIVEN** más eventos que los que caben en una página
- **WHEN** se muestra el registro
- **THEN** la pantalla dice que hay eventos anteriores sin mostrar

#### Scenario: Consulta por período
- **WHEN** se pide el registro entre dos fechas
- **THEN** el sistema responde con los eventos de esos días de calendario de la empresa, incluido el último día completo

### Requirement: La emisión de un documento queda registrada
El sistema SHALL anotar en el registro de actividades cada vez que alguien emite un documento del sistema —un informe de auditoría, una matriz o un reporte—, con qué documento, qué filtros y cuántas filas.

Lo que sale del sistema hacia una auditoría externa es lo que RNF-26 pide poder rastrear. Se anota que se abrió la impresión, porque el navegador no informa si se canceló.

#### Scenario: Emisión de un informe de auditoría
- **WHEN** alguien imprime o guarda en PDF el informe de una auditoría
- **THEN** el registro lo anota contra esa auditoría, y aparece en su historial

#### Scenario: Emisión sobre un registro ajeno
- **WHEN** la emisión nombra un registro que no es visible para la empresa
- **THEN** el sistema la rechaza con la misma respuesta que si no existiera

#### Scenario: Empresa en solo lectura
- **GIVEN** una empresa suspendida
- **WHEN** alguien de esa empresa exporta un documento
- **THEN** la emisión queda anotada igual: exportar está permitido y su rastro también
