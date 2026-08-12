import { z } from 'zod';
import type { Role } from './user';

/**
 * Permisos granulares dentro de un tenant (RF-12: "el Perfil Empresa gestiona
 * ... la matriz de permisos").
 *
 * Hasta ahora el sistema solo tenía **roles**: cinco cajas fijas. Eso no
 * alcanza porque, como señala el Análisis de Actores (§2.3), el Usuario
 * Interno "no es una fila única sino un espacio de configuración" — dos
 * personas con el mismo rol pueden tener responsabilidades muy distintas
 * según su departamento.
 *
 * El modelo sigue el que ya define la propuesta OpenSpec
 * `sistema-actores-roles-rbac`: catálogo de claves, un set por defecto según
 * el rol, y concesiones individuales que lo amplían o recortan. La lista es
 * abierta — agregar un permiso nuevo no cambia la estructura.
 *
 * ⚠️ Esto es UX, no seguridad. Ocultar un botón no impide llamar a la API;
 * la barrera real es el `PermissionsGuard` del backend, que todavía no
 * existe.
 */
export const PermisoSchema = z.enum([
  // Matriz Legal
  'matriz_legal.evaluar',
  'matriz_legal.gestionar_normas',
  // Obligaciones
  'obligaciones.crear',
  'obligaciones.completar_tarea',
  // Evidencias — el análisis pedía separarlo explícitamente de aprobar.
  'evidencias.editar',
  // Auditorías y no conformidades
  'no_conformidades.registrar',
  'no_conformidades.aprobar_cierre',
  'auditorias.planificar',
  // Planes de acción
  'planes_accion.crear',
  // Reportes
  'reportes.exportar',
  // Administración de la empresa
  'usuarios.invitar',
  'usuarios.gestionar_permisos',
  'perfil_empresa.editar',
]);
export type Permiso = z.infer<typeof PermisoSchema>;

export interface DefinicionPermiso {
  clave: Permiso;
  grupo: string;
  nombre: string;
  descripcion: string;
  /**
   * Marca los permisos cuya concesión tiene consecuencias más allá del propio
   * usuario: aprobar cierres, gestionar permisos de otros, editar el perfil
   * de la empresa. La interfaz los destaca para que no se otorguen por
   * inercia al copiar la configuración de otra persona.
   */
  sensible?: boolean;
}

/**
 * Catálogo de permisos. El agrupamiento es por módulo porque así es como el
 * Admin Empresa piensa el trabajo ("quién puede evaluar la matriz legal"), no
 * por tipo de acción.
 */
export const CATALOGO_PERMISOS: DefinicionPermiso[] = [
  {
    clave: 'matriz_legal.evaluar',
    grupo: 'Matriz Legal',
    nombre: 'Evaluar artículos',
    descripcion: 'Declarar si un artículo se cumple, no se cumple o no aplica.',
  },
  {
    clave: 'matriz_legal.gestionar_normas',
    grupo: 'Matriz Legal',
    nombre: 'Gestionar normas',
    descripcion: 'Cargar RCAs e ISO y asignarlas a plantas.',
  },
  {
    clave: 'obligaciones.crear',
    grupo: 'Obligaciones',
    nombre: 'Crear obligaciones',
    descripcion: 'Dar de alta declaraciones y sus tareas.',
  },
  {
    clave: 'obligaciones.completar_tarea',
    grupo: 'Obligaciones',
    nombre: 'Completar tareas',
    descripcion: 'Marcar tareas como realizadas y cambiar su estado.',
  },
  {
    clave: 'evidencias.editar',
    grupo: 'Evidencias',
    nombre: 'Editar evidencias',
    descripcion: 'Adjuntar o reemplazar los documentos que respaldan el cumplimiento.',
  },
  {
    clave: 'no_conformidades.registrar',
    grupo: 'Auditorías',
    nombre: 'Registrar hallazgos',
    descripcion: 'Levantar no conformidades y documentar el análisis de causa.',
  },
  {
    clave: 'no_conformidades.aprobar_cierre',
    grupo: 'Auditorías',
    nombre: 'Aprobar cierres',
    descripcion: 'Firmar el cierre de una no conformidad (RF-49).',
    // Quien registra un hallazgo no debería poder aprobarlo solo: es el
    // control cruzado que revisa un certificador.
    sensible: true,
  },
  {
    clave: 'auditorias.planificar',
    grupo: 'Auditorías',
    nombre: 'Planificar auditorías',
    descripcion: 'Programar auditorías internas y definir su alcance.',
  },
  {
    clave: 'planes_accion.crear',
    grupo: 'Planes de acción',
    nombre: 'Crear planes de acción',
    descripcion: 'Generar planes a partir de incumplimientos y no conformidades.',
  },
  {
    clave: 'reportes.exportar',
    grupo: 'Reportes',
    nombre: 'Exportar reportes',
    descripcion: 'Descargar informes en CSV o PDF con datos de la empresa.',
  },
  {
    clave: 'usuarios.invitar',
    grupo: 'Administración',
    nombre: 'Invitar usuarios',
    descripcion: 'Incorporar personas nuevas a la empresa.',
    sensible: true,
  },
  {
    clave: 'usuarios.gestionar_permisos',
    grupo: 'Administración',
    nombre: 'Gestionar permisos',
    descripcion: 'Cambiar lo que otras personas pueden hacer en el sistema.',
    sensible: true,
  },
  {
    clave: 'perfil_empresa.editar',
    grupo: 'Administración',
    nombre: 'Editar Perfil Empresa',
    descripcion: 'Modificar plantas, procesos y datos de la empresa.',
    sensible: true,
  },
];

/**
 * Permisos por defecto de cada rol.
 *
 * Son el punto de partida al invitar a alguien, no una jaula: se conceden al
 * crear el usuario y desde ahí se amplían o recortan uno por uno. El Usuario
 * Interno arranca con lo operativo — puede evaluar y completar tareas, pero
 * **no** aprobar cierres ni administrar la empresa.
 */
export const PERMISOS_POR_DEFECTO: Record<Role, Permiso[]> = {
  superadmin: [],
  admin_empresa: CATALOGO_PERMISOS.map((p) => p.clave),
  gestor: CATALOGO_PERMISOS.map((p) => p.clave),
  usuario_interno: [
    'matriz_legal.evaluar',
    'obligaciones.completar_tarea',
    'evidencias.editar',
    'no_conformidades.registrar',
    'planes_accion.crear',
    'reportes.exportar',
  ],
  cliente_invitado: [],
};

/** Permisos efectivos: los explícitos si existen, si no los del rol. */
export function permisosEfectivos(role: Role, permisos?: Permiso[]): Permiso[] {
  return permisos ?? PERMISOS_POR_DEFECTO[role];
}

export function tienePermiso(role: Role, permisos: Permiso[] | undefined, permiso: Permiso): boolean {
  return permisosEfectivos(role, permisos).includes(permiso);
}

export function nombrePermiso(clave: Permiso): string {
  return CATALOGO_PERMISOS.find((p) => p.clave === clave)?.nombre ?? clave;
}
