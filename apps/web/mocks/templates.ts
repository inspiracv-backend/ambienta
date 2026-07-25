import type { ExcelTemplate } from '@ambienta/shared';

/** Super-repositorio de templates Excel por sistema de declaración (RF-22/RF-23). */
export const mockExcelTemplates: ExcelTemplate[] = [
  {
    id: 'tpl-retc',
    sistema: 'RETC',
    nombre: 'Declaración RETC',
    version: '2026.1',
    pestanas: ['Matriz de códigos y significados', 'Hoja de declaración'],
    archivoUrl: '#',
  },
  {
    id: 'tpl-ley-rep',
    sistema: 'Ley REP',
    nombre: 'Declaración Ley REP',
    version: '2025.3',
    pestanas: ['Matriz de códigos y significados', 'Hoja de declaración'],
    archivoUrl: '#',
  },
  {
    id: 'tpl-sinader',
    sistema: 'SINADER',
    nombre: 'Movimiento de residuos SINADER',
    version: '2026.1',
    pestanas: ['Matriz de códigos y significados', 'Hoja de declaración'],
    archivoUrl: '#',
  },
  {
    id: 'tpl-sidrep',
    sistema: 'SIDREP',
    nombre: 'Declaración SIDREP',
    version: '2026.2',
    pestanas: ['Matriz de códigos y significados', 'Hoja de declaración'],
    archivoUrl: '#',
  },
  {
    id: 'tpl-dae',
    sistema: 'DAE',
    nombre: 'Declaración de Aguas de Emisión (DAE)',
    version: '2025.4',
    pestanas: ['Matriz de códigos y significados', 'Hoja de declaración'],
    archivoUrl: '#',
  },
];
