/**
 * Lo que la persona lee en el detalle de una norma.
 *
 * **Este archivo no existía, y por eso el "No cumple · 0 %" llegó a pantalla.**
 * `lib/legal-matrix.test.ts` cubría el cálculo y `StatusBadge` cubría el badge;
 * lo que nadie probaba era el componente que los junta, que es donde estaba el
 * error. Una prueba de librería no habría impedido que este componente volviera
 * a llamar a `computeNormCompliance` mañana.
 *
 * Por eso todas las afirmaciones de acá son sobre **texto visible**, no sobre
 * funciones ni props.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Articulo, LegalNorm } from '@ambienta/shared';
import { NormDetailView } from './NormDetailView';

// El store solo aporta la norma "viva"; acá se prueba el render, no la carga.
vi.mock('@/lib/legal-matrix-store', () => ({
  useLegalMatrix: () => ({ norms: [], setIncluidoEnCalculo: vi.fn(), updateArticulo: vi.fn() }),
}));
vi.mock('@/lib/plan-accion-store', () => ({
  usePlanAccion: () => ({ createPlan: vi.fn(), findByOrigen: () => undefined }),
}));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@/lib/get-user-name', () => ({ getUserName: () => 'Sin asignar' }));

function articulo(over: Partial<Articulo> = {}): Articulo {
  return {
    id: 'art-1',
    numero: 'Artículo 1º',
    descripcion: 'Texto breve.',
    texto: 'Texto breve.',
    respuesta: 'N_E',
    formaCumplimiento: '',
    responsableId: null,
    evidenciaUrl: null,
    incluidoEnCalculo: true,
    ...over,
  } as Articulo;
}

function norma(articulos: Articulo[]): LegalNorm {
  return {
    id: 'norm-1',
    nombre: 'APRUEBA REGLAMENTO DEL REGISTRO DE EMISIONES Y TRANSFERENCIAS DE CONTAMINANTES, RETC',
    fuente: 'BCN',
    articulos,
  } as LegalNorm;
}

/**
 * El bloque del encabezado, y **no la pantalla entera**.
 *
 * `StatusBadge` se repite por artículo, así que `getByText('No cumple')` sin
 * acotar encuentra varios y falla por ambigüedad — que se lee como si la
 * afirmación fuera falsa cuando es solo imprecisa. Lo que se quiere afirmar es
 * lo que dice el resumen de la norma, que es el que mentía.
 */
function resumen() {
  return within(screen.getByRole('group', { name: /Resumen de cumplimiento/ }));
}

function pintar(n: LegalNorm) {
  return render(<NormDetailView norm={n} activeTenantId="t-1" responsableOptions={[]} />);
}

describe('una norma que nadie evaluo', () => {
  const RECIEN_IMPORTADA = norma([
    articulo({ id: 'a' }),
    articulo({ id: 'b' }),
    articulo({ id: 'c' }),
  ]);

  it('NO dice que la empresa no cumple', () => {
    pintar(RECIEN_IMPORTADA);

    // La afirmación central del archivo. Antes esto fallaba: el encabezado
    // decía "No cumple" sobre una norma que nadie había mirado.
    expect(resumen().queryByText('No cumple')).not.toBeInTheDocument();
  });

  it('no muestra un 0% inventado', () => {
    pintar(RECIEN_IMPORTADA);

    expect(resumen().queryByText(/^0%/)).not.toBeInTheDocument();
  });

  it('dice que esta pendiente y por que no hay numero', () => {
    pintar(RECIEN_IMPORTADA);

    expect(resumen().getByText('Pendiente de evaluar')).toBeInTheDocument();
    expect(resumen().getByText(/todavía no hay artículos evaluados/i)).toBeInTheDocument();
  });

  it('dice cuanto falta, que es la pregunta que la persona tiene', () => {
    pintar(RECIEN_IMPORTADA);

    expect(screen.getByText('0/3')).toBeInTheDocument();
    expect(screen.getByText(/3 artículos sin evaluar/)).toBeInTheDocument();
  });
});

describe('una norma evaluada', () => {
  it('muestra el porcentaje y el semaforo que corresponde', () => {
    pintar(
      norma([
        articulo({ id: 'a', respuesta: 'SI' }),
        articulo({ id: 'b', respuesta: 'SI' }),
        articulo({ id: 'c', respuesta: 'NO' }),
      ]),
    );

    expect(screen.getByText(/67%/)).toBeInTheDocument();
    expect(screen.getByText('3/3')).toBeInTheDocument();
    expect(screen.getByText(/Todos los artículos aplicables están evaluados/)).toBeInTheDocument();
    expect(screen.getByText(/1 en incumplimiento/)).toBeInTheDocument();
  });

  it('un cero medido SI dice que no cumple', () => {
    // El otro lado de la moneda: arreglar el falso positivo no puede tapar el
    // incumplimiento real.
    pintar(norma([articulo({ id: 'a', respuesta: 'NO' })]));

    expect(resumen().getByText('No cumple')).toBeInTheDocument();
  });
});

describe('el texto largo de la BCN', () => {
  // El artículo 3º del DS 13 real, recortado pero por encima del umbral.
  const LARGO =
    'Artículo 3º. Para los efectos de lo dispuesto en este decreto, se entenderá por: a) Termoeléctrica: ' +
    'Instalación compuesta por una o más unidades destinadas a la generación de electricidad mediante un ' +
    'proceso térmico. b) Unidad de generación eléctrica: Unidad conformada por una caldera o una turbina. ' +
    'c) Fuente emisora existente: Unidad de generación eléctrica que se encuentra operando o declarada en ' +
    'construcción, de conformidad a lo dispuesto por el artículo 272 del Reglamento de la Ley Eléctrica.';

  it('se pliega, y el texto sigue estando', () => {
    pintar(norma([articulo({ id: 'a', descripcion: LARGO })]));

    // Plegado es CSS (`line-clamp`), así que el texto está en el DOM — lo que
    // se afirma es que existe el control para desplegarlo.
    expect(screen.getByRole('button', { name: /Ver texto completo/ })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
  });

  it('se despliega y se vuelve a plegar', async () => {
    pintar(norma([articulo({ id: 'a', descripcion: LARGO })]));

    const boton = screen.getByRole('button', { name: /Ver texto completo/ });
    await userEvent.click(boton);

    const abierto = screen.getByRole('button', { name: /Ver menos/ });
    expect(abierto).toHaveAttribute('aria-expanded', 'true');

    await userEvent.click(abierto);
    expect(screen.getByRole('button', { name: /Ver texto completo/ })).toBeInTheDocument();
  });

  it('un texto corto no ofrece plegarse', () => {
    // Un control que no hace nada es ruido: la mitad del articulado son
    // encabezados de dos palabras ("Título I").
    pintar(norma([articulo({ id: 'a', descripcion: 'Título I: Disposiciones generales' })]));

    expect(screen.queryByRole('button', { name: /Ver texto completo/ })).not.toBeInTheDocument();
  });
});
