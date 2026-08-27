/**
 * El aviso de normas desactualizadas, y su botón.
 *
 * ## Lo que estas pruebas protegen
 *
 * **Que el aviso no diga "trabajo perdido".** Es la tentación obvia: una norma
 * cambió, luego lo evaluado contra la versión anterior "hay que rehacerlo". Es
 * falso — esas evaluaciones se hicieron sobre el texto que regía entonces y son
 * la respuesta correcta ante una auditoría de ese período— y decirlo empujaría
 * a la gente a rehacer trabajo que ya está bien.
 *
 * Esa promesa vive en el texto de la pantalla, así que se afirma sobre **texto
 * visible** y no sobre funciones. Misma lección que `NormDetailView.test.tsx`.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { AvisoNormasDesactualizadas } from './AvisoNormasDesactualizadas';
import { ToastViewport } from '@/components/organisms/ToastViewport';
import { SessionProvider } from '@/lib/session';
import { ToastProvider } from '@/lib/toast-store';
import { UsersProvider } from '@/lib/users-store';
import { iniciarSesionComo } from '@/test/utils';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/matriz-legal',
}));

const cargarMatrizVigente = vi.fn();
const cargarDesactualizadas = vi.fn();
const actualizarAVersionVigente = vi.fn();

vi.mock('@/lib/normativa-aplicable', async (importarReal) => {
  const real = await importarReal<typeof import('@/lib/normativa-aplicable')>();
  return {
    ...real,
    cargarMatrizVigente: (...a: unknown[]) => cargarMatrizVigente(...a),
    cargarDesactualizadas: (...a: unknown[]) => cargarDesactualizadas(...a),
    actualizarAVersionVigente: (...a: unknown[]) => actualizarAVersionVigente(...a),
  };
});

function wrapper({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <UsersProvider>
        <SessionProvider>{children}</SessionProvider>
      </UsersProvider>
      {/* El visor vive en `app/layout.tsx`, no en el provider. Sin el, los
          avisos existen en el estado y no se pintan: las afirmaciones sobre lo
          que la persona LEE fallarian sin que nada este mal en el codigo. */}
      <ToastViewport />
    </ToastProvider>
  );
}

function norma(over: Record<string, unknown> = {}) {
  return {
    matrixNormId: 'mn-1',
    normId: 'n-1',
    titulo: 'APRUEBA LEY SOBRE BASES GENERALES DEL MEDIO AMBIENTE',
    versionEvaluada: 'v-vieja',
    versionVigente: 'v-nueva',
    evaluacionesSobreLaAnterior: 4,
    ...over,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  iniciarSesionComo('admin_empresa');
  cargarMatrizVigente.mockResolvedValue('matriz-1');
  cargarDesactualizadas.mockResolvedValue([norma()]);
  actualizarAVersionVigente.mockResolvedValue({
    actualizadas: 1,
    articulosNuevos: 151,
    evaluacionesConservadas: 4,
    yaEstabanAlDia: 0,
    titulos: ['APRUEBA LEY SOBRE BASES GENERALES DEL MEDIO AMBIENTE'],
  });
});

describe('lo que el aviso promete', () => {
  it('dice que lo evaluado SIGUE VALIENDO', async () => {
    render(<AvisoNormasDesactualizadas />, { wrapper });

    // Sin esta frase el aviso se lee como "rehaz todo esto".
    expect(await screen.findByText(/siguen siendo válidas/i)).toBeInTheDocument();
  });

  it('explica que actualizar NO borra ni migra lo anterior', async () => {
    render(<AvisoNormasDesactualizadas />, { wrapper });

    expect(await screen.findByText(/no se migran ni se borran/i)).toBeInTheDocument();
  });

  it('sin normas desactualizadas no se muestra nada', async () => {
    cargarDesactualizadas.mockResolvedValue([]);
    const { container } = render(<AvisoNormasDesactualizadas />, { wrapper });

    await waitFor(() => expect(cargarDesactualizadas).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});

describe('el botón', () => {
  it('actualiza SOLO la norma elegida', async () => {
    const usuario = userEvent.setup();
    cargarDesactualizadas.mockResolvedValue([
      norma({ matrixNormId: 'mn-1', titulo: 'Norma A' }),
      norma({ matrixNormId: 'mn-2', titulo: 'Norma B' }),
    ]);
    render(<AvisoNormasDesactualizadas />, { wrapper });

    const botones = await screen.findAllByRole('button', { name: /^actualizar$/i });
    await usuario.click(botones[0]);

    // Una norma con cien evaluaciones se revisa cuando hay tiempo de leerla;
    // obligar a mover todas de golpe empuja a no mover ninguna.
    await waitFor(() =>
      expect(actualizarAVersionVigente).toHaveBeenCalledWith('matriz-1', expect.any(String), [
        'mn-1',
      ]),
    );
  });

  it('"actualizar todas" NO enumera las normas desde el navegador', async () => {
    const usuario = userEvent.setup();
    cargarDesactualizadas.mockResolvedValue([norma({ matrixNormId: 'mn-1' }), norma({ matrixNormId: 'mn-2' })]);
    render(<AvisoNormasDesactualizadas />, { wrapper });

    await usuario.click(await screen.findByRole('button', { name: /actualizar todas/i }));

    // Se deja que lo decida el servidor: entre que se dibuja la pantalla y se
    // aprieta el botón, otra persona pudo actualizar una.
    await waitFor(() =>
      expect(actualizarAVersionVigente).toHaveBeenCalledWith(
        'matriz-1',
        expect.any(String),
        undefined,
      ),
    );
  });

  it('con una sola norma no se ofrece "actualizar todas"', async () => {
    render(<AvisoNormasDesactualizadas />, { wrapper });

    await screen.findByRole('button', { name: /^actualizar$/i });
    // Dos botones que hacen lo mismo obligan a leer los dos para elegir.
    expect(screen.queryByRole('button', { name: /actualizar todas/i })).not.toBeInTheDocument();
  });

  it('al terminar dice CUÁNTAS evaluaciones se conservaron', async () => {
    const usuario = userEvent.setup();
    render(<AvisoNormasDesactualizadas />, { wrapper });

    await usuario.click(await screen.findByRole('button', { name: /^actualizar$/i }));

    // Sin este número, "actualizado" se lee como "se perdió lo que había".
    expect(await screen.findByText(/4 evaluaciones anteriores se conservan/i)).toBeInTheDocument();
  });

  it('si no había nada que actualizar lo dice, en vez de fingir éxito', async () => {
    const usuario = userEvent.setup();
    actualizarAVersionVigente.mockResolvedValue({
      actualizadas: 0,
      articulosNuevos: 0,
      evaluacionesConservadas: 0,
      yaEstabanAlDia: 1,
      titulos: [],
    });
    render(<AvisoNormasDesactualizadas />, { wrapper });

    await usuario.click(await screen.findByRole('button', { name: /^actualizar$/i }));

    // Puede pasar sin que nadie se equivoque: otra persona la actualizó entre
    // medio. Un "listo" de una operación que no ocurrió es peor que el aviso.
    expect(await screen.findByText(/no había nada que actualizar/i)).toBeInTheDocument();
  });

  it('el aviso se recarga después de actualizar', async () => {
    const usuario = userEvent.setup();
    render(<AvisoNormasDesactualizadas />, { wrapper });

    await usuario.click(await screen.findByRole('button', { name: /^actualizar$/i }));

    // Sin recargar, la norma recién actualizada sigue en la lista y el botón
    // invita a repetir una operación que ya no hace nada.
    await waitFor(() => expect(cargarDesactualizadas).toHaveBeenCalledTimes(2));
  });
});
