import type { Audit, NonConformity } from '@ambienta/shared';

function addDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

/** Auditorías (planificación de revisiones internas/externas) — Sección G. */
export const mockAudits: Audit[] = [
  {
    id: 'audit-1',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    plantId: 'planta-rancagua',
    tipo: 'interna',
    fecha: addDays(20),
    estado: 'planificada',
    procesos: ['Gestión de residuos peligrosos'],
    normativaIds: ['norm-2'],
  },
  {
    id: 'audit-2',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    plantId: 'planta-talca',
    tipo: 'externa',
    fecha: addDays(-15),
    estado: 'cerrada',
    procesos: ['Emisiones atmosféricas'],
    normativaIds: [],
  },
  {
    id: 'audit-3',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    plantId: 'planta-concepcion',
    tipo: 'interna',
    fecha: addDays(-2),
    estado: 'en_curso',
    procesos: ['Gestión de residuos', 'Emisiones atmosféricas'],
    normativaIds: ['norm-4'],
  },
];

/** No Conformidades (hallazgos, RF-34 a RF-41) — casos límite: abierta, en tratamiento y cerrada con firma. */
export const mockNonConformities: NonConformity[] = [
  {
    id: 'nc-1',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    plantId: 'planta-talca',
    auditId: 'audit-2',
    hallazgo: 'Discrepancia entre kilogramos declarados y retirados de residuo peligroso',
    criticidad: 'alta',
    estado: 'en_tratamiento',
    fechaDeteccion: addDays(-14),
    responsableId: 'user-interno',
    cincoPorques: [
      '¿Por qué hay discrepancia? Porque el peso declarado se estimó, no se pesó en báscula.',
      '¿Por qué se estimó? Porque la báscula de la planta estaba fuera de servicio ese mes.',
    ],
  },
  {
    id: 'nc-2',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    plantId: 'planta-rancagua',
    hallazgo: 'Falta certificado de calibración de balanza de pesaje',
    criticidad: 'media',
    estado: 'abierta',
    fechaDeteccion: addDays(-3),
    responsableId: 'user-especialista',
    cincoPorques: [],
  },
  {
    id: 'nc-3',
    tenantId: 'a0000000-0000-0000-0000-000000000001',
    plantId: 'planta-concepcion',
    auditId: 'audit-3',
    hallazgo: 'Bitácora de mantenimiento de fuentes fijas incompleta',
    criticidad: 'baja',
    estado: 'cerrada',
    fechaDeteccion: addDays(-40),
    responsableId: 'user-especialista',
    cincoPorques: [
      '¿Por qué está incompleta? Porque el registro es manual en papel.',
      '¿Por qué es manual? Porque no había un formato digital asignado.',
      '¿Por qué no había formato? Porque no se definió responsable de digitalizarlo.',
    ],
    cierre: {
      fecha: addDays(-10),
      responsableId: 'user-especialista',
      firmada: true,
    },
  },
];
