import type { Departamento } from '@ambienta/shared';

/**
 * Departamentos/procesos del Perfil Empresa (RF-11, RF-12, v1.7).
 *
 * Se declaran con los tres tipos de ISO 9001 §4.4 para que el mapa de procesos
 * tenga sus tres franjas pobladas: con solo operativos el mapa no comunica
 * nada — lo que se lee de un mapa es precisamente cómo la dirección y el apoyo
 * envuelven a la cadena de valor.
 *
 * Las entradas y salidas están encadenadas a propósito (la salida de Gestión
 * Ambiental es entrada de Operaciones) para poder mostrar la interacción, que
 * es lo que la norma pide representar.
 */
export const mockDepartamentos: Departamento[] = [
  {
    id: 'depto-direccion',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    nombre: 'Dirección y Planificación',
    tipo: 'estrategico',
    descripcion: 'Define objetivos ambientales y revisa el desempeño del sistema de gestión.',
    responsableId: 'user-admin-empresa',
    entradas: ['Resultados de auditorías', 'Indicadores de cumplimiento'],
    salidas: ['Objetivos ambientales', 'Asignación de recursos'],
  },
  {
    id: 'depto-medioambiente',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    nombre: 'Medio Ambiente',
    tipo: 'estrategico',
    descripcion: 'Identifica requisitos legales aplicables y controla su cumplimiento.',
    responsableId: 'user-especialista',
    entradas: ['Normativa vigente', 'Cambios regulatorios'],
    salidas: ['Matriz legal actualizada', 'Programa de auditorías'],
  },
  {
    id: 'depto-operaciones',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    nombre: 'Operaciones',
    tipo: 'operativo',
    descripcion: 'Recepción, clasificación y valorización de residuos industriales.',
    responsableId: 'user-interno',
    entradas: ['Residuos recepcionados', 'Matriz legal actualizada'],
    salidas: ['Material valorizado', 'Registros de tratamiento'],
  },
  {
    id: 'depto-declaraciones',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    nombre: 'Declaraciones y Reportes',
    tipo: 'operativo',
    descripcion: 'Prepara y presenta las declaraciones ante los sistemas del RETC.',
    responsableId: 'user-interno',
    entradas: ['Registros de tratamiento', 'Guías de despacho'],
    salidas: ['Declaraciones presentadas', 'Comprobantes de recepción'],
  },
  {
    id: 'depto-administracion',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    nombre: 'Administración y Finanzas',
    tipo: 'apoyo',
    descripcion: 'Gestiona recursos, compras y contratos con terceros.',
    responsableId: null,
    entradas: ['Requerimientos de recursos'],
    salidas: ['Presupuesto asignado', 'Contratos vigentes'],
  },
  {
    id: 'depto-personas',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    nombre: 'Gestión de Personas',
    tipo: 'apoyo',
    descripcion: 'Competencia, formación y descriptores de cargo (ISO 9001 §7.2).',
    responsableId: null,
    entradas: ['Necesidades de competencia'],
    salidas: ['Personal capacitado', 'Registros de formación'],
  },
  {
    id: 'depto-servicio-cliente',
    tenantId: 'a0000000-0000-0000-0000-000000000002',
    nombre: 'Servicio al Cliente',
    tipo: 'operativo',
    descripcion: 'Atención y seguimiento de los sub-tenants gestionados.',
    responsableId: 'user-gestor',
    entradas: ['Solicitudes de clientes'],
    salidas: ['Declaraciones por cliente'],
  },
];
