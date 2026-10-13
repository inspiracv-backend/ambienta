import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FichaNoDisponible } from './FichaNoDisponible';

/**
 * Hasta el 19-sep, abrir o recargar el enlace de una ficha daba 404: la
 * página decidía "no existe" antes de que el store cargara, y `notFound()` la
 * desmontaba para siempre. Medido en el navegador con una auditoría y una no
 * conformidad reales.
 */

const sesion = { cargando: false, user: { id: 'u-1' } as unknown };
vi.mock('@/lib/session', () => ({ useSession: () => sesion }));

beforeEach(() => {
  sesion.cargando = false;
  sesion.user = { id: 'u-1' };
});

describe('mientras no se sabe', () => {
  it('con el store cargando no afirma que no existe', () => {
    render(<FichaNoDisponible cargando que="esta auditoría" volverA="/auditorias" />);
    expect(screen.queryByText(/No encontramos/)).toBeNull();
    expect(screen.getByText(/Cargando esta auditoría/)).toBeTruthy();
  });

  it('con la sesión cargando tampoco: los stores bajan `loading` sin sesión', () => {
    sesion.cargando = true;
    render(<FichaNoDisponible cargando={false} que="esta auditoría" />);
    expect(screen.queryByText(/No encontramos/)).toBeNull();
  });
});

describe('cuando ya se sabe', () => {
  it('lo dice y ofrece volver', () => {
    render(<FichaNoDisponible cargando={false} que="esta auditoría" volverA="/auditorias" volverEtiqueta="Volver a auditorías" />);
    expect(screen.getByText('No encontramos esta auditoría')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Volver a auditorías' }).getAttribute('href')).toBe('/auditorias');
  });
});

describe('ninguna ficha vuelve a usar notFound()', () => {
  function archivos(dir: string): string[] {
    return readdirSync(dir).flatMap((nombre) => {
      const ruta = join(dir, nombre);
      return statSync(ruta).isDirectory() ? archivos(ruta) : ruta.endsWith('page.tsx') ? [ruta] : [];
    });
  }

  it('las páginas del tablero esperan su store en vez de desmontarse', () => {
    const raiz = resolve(__dirname, '../../../app/(dashboard)');
    const paginas = archivos(raiz);
    // Sin esto, una ruta equivocada recorre cero archivos y pasa en verde.
    expect(paginas.length).toBeGreaterThan(20);
    const conNotFound = paginas
      .filter((f) => /notFound\(\)/.test(readFileSync(f, 'utf-8')))
      .map((f) => f.slice(raiz.length));
    expect(conNotFound).toEqual([]);
  });
});
