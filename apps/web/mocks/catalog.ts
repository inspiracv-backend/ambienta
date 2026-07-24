import type { LegalNorm } from '@ambienta/shared';

/**
 * Catálogo normativo en 3 capas (RF-42): BCN público, ISO interno, RCA del
 * tenant. Cruza los mismos tenant/plantas que mocks/tenants.ts para
 * consistencia visual (Dashboard → Matriz Legal → Calendario).
 */
export const mockLegalNorms: LegalNorm[] = [
  {
    id: 'norm-1',
    tenantId: null,
    plantIds: ['planta-rancagua', 'planta-talca', 'planta-concepcion'],
    tipoDocumento: 'Ley',
    nombre: 'Ley 20.920 — Marco para la Gestión de Residuos (Ley REP)',
    fuente: 'BCN',
    fuenteUrl: 'https://www.bcn.cl/leychile/navegar?idNorma=1090894',
    responsableId: 'user-especialista',
    sincronizacion: { estado: 'sincronizado', fecha: new Date().toISOString() },
    articulos: [
      { id: 'art-1a', normId: 'norm-1', numero: 'Art. 3', descripcion: 'Metas de recolección y valorización', respuesta: 'SI', formaCumplimiento: 'Reporte trimestral a gestor autorizado', responsableId: 'user-especialista', incluidoEnCalculo: true },
      { id: 'art-1b', normId: 'norm-1', numero: 'Art. 10', descripcion: 'Registro de productores', respuesta: 'NO', responsableId: 'user-especialista', incluidoEnCalculo: true },
      { id: 'art-1c', normId: 'norm-1', numero: 'Art. 32', descripcion: 'Sistema de gestión colectivo', respuesta: 'SI', formaCumplimiento: 'Adherido a sistema colectivo Rembre', responsableId: 'user-especialista', incluidoEnCalculo: true },
      { id: 'art-1d', normId: 'norm-1', numero: 'Art. 40', descripcion: 'Fondo para el reciclaje', respuesta: 'N_E', incluidoEnCalculo: true },
    ],
  },
  {
    id: 'norm-2',
    tenantId: 'tenant-1',
    plantIds: ['planta-rancagua'],
    tipoDocumento: 'Resolucion',
    nombre: 'RCA Planta Rancagua N° 145/2019',
    fuente: 'RCA',
    responsableId: 'user-interno',
    articulos: [
      { id: 'art-2a', normId: 'norm-2', numero: 'Considerando 7', descripcion: 'Monitoreo de emisiones atmosféricas', respuesta: 'N_E', incluidoEnCalculo: true },
      { id: 'art-2b', normId: 'norm-2', numero: 'Considerando 12', descripcion: 'Plan de manejo de residuos peligrosos', respuesta: 'SI', formaCumplimiento: 'Plan vigente aprobado por SMA', responsableId: 'user-interno', incluidoEnCalculo: true },
    ],
  },
  {
    id: 'norm-3',
    tenantId: 'tenant-1',
    plantIds: ['planta-rancagua', 'planta-talca', 'planta-concepcion'],
    tipoDocumento: 'NCh',
    nombre: 'ISO 14001:2015 — Sistema de Gestión Ambiental',
    fuente: 'ISO',
    responsableId: 'user-admin-empresa',
    articulos: [
      { id: 'art-3a', normId: 'norm-3', numero: 'Cláusula 6.1', descripcion: 'Acciones para abordar riesgos y oportunidades', respuesta: 'SI', formaCumplimiento: 'Matriz de riesgos actualizada anualmente', responsableId: 'user-admin-empresa', incluidoEnCalculo: true },
      { id: 'art-3b', normId: 'norm-3', numero: 'Cláusula 9.1', descripcion: 'Seguimiento, medición, análisis y evaluación', respuesta: 'NO', responsableId: 'user-admin-empresa', incluidoEnCalculo: true },
      { id: 'art-3c', normId: 'norm-3', numero: 'Cláusula 8.2', descripcion: 'Preparación y respuesta ante emergencias', respuesta: 'SI', formaCumplimiento: 'Simulacro anual documentado', responsableId: 'user-admin-empresa', incluidoEnCalculo: true },
    ],
  },
  {
    id: 'norm-4',
    tenantId: null,
    plantIds: ['planta-talca', 'planta-concepcion'],
    tipoDocumento: 'Decreto',
    nombre: 'DS 148/2003 — Reglamento Sanitario de Residuos Peligrosos (SINADER)',
    fuente: 'BCN',
    fuenteUrl: 'https://www.bcn.cl/leychile/navegar?idNorma=209235',
    responsableId: 'user-especialista',
    sincronizacion: { estado: 'desactualizado', fecha: '2026-05-10T00:00:00.000Z' },
    articulos: [
      { id: 'art-4a', normId: 'norm-4', numero: 'Art. 15', descripcion: 'Declaración de generación de residuos peligrosos', respuesta: 'SI', formaCumplimiento: 'Declarado en SINADER mensualmente', responsableId: 'user-especialista', incluidoEnCalculo: true },
      { id: 'art-4b', normId: 'norm-4', numero: 'Art. 27', descripcion: 'Almacenamiento temporal autorizado', respuesta: 'NA', incluidoEnCalculo: false },
    ],
  },
  {
    id: 'norm-5',
    tenantId: null,
    plantIds: [],
    tipoDocumento: 'Ley',
    nombre: 'Ley 19.300 — Bases Generales del Medio Ambiente',
    fuente: 'BCN',
    fuenteUrl: 'https://www.bcn.cl/leychile/navegar?idNorma=30667',
    sincronizacion: { estado: 'sincronizado', fecha: new Date().toISOString() },
    articulos: [
      { id: 'art-5a', normId: 'norm-5', numero: 'Art. 10', descripcion: 'Proyectos que deben someterse al SEIA', respuesta: 'N_E', incluidoEnCalculo: true },
    ],
  },
];
