import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.clearAllMocks();
});

/**
 * jsdom no implementa matchMedia ni las APIs de observación que usan varios
 * componentes de Radix; sin estos stubs los tests fallan por el entorno, no
 * por el código bajo prueba.
 */
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }),
});

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;

// Radix usa estas dos en menús y selects; jsdom no las trae.
Element.prototype.scrollIntoView = vi.fn();
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = vi.fn(() => false) as unknown as Element['hasPointerCapture'];
  Element.prototype.setPointerCapture = vi.fn() as unknown as Element['setPointerCapture'];
  Element.prototype.releasePointerCapture = vi.fn() as unknown as Element['releasePointerCapture'];
}

/**
 * El alcance por planta de la sesión, por defecto **sin acotar**.
 *
 * `lib/session.tsx` pide `GET /me` para saber a qué instalaciones está acotada
 * la persona, y hasta que lo sabe la sesión no se resuelve. Sin este stub cada
 * test que inicia sesión tendría que simular esa llamada, o la sesión quedaría
 * en `'fallo'` y `user` en `null` — que es lo que pasó al conectar el
 * acotamiento: 23 pruebas se cayeron de golpe por el entorno, no por el código.
 *
 * El valor por defecto es `[]`, que en este dominio significa **«sin acotar»**
 * y no «ninguna planta». Es lo que asumían todas estas pruebas antes de que el
 * alcance existiera, así que ninguna cambia de significado.
 *
 * Un test que quiera probar el acotamiento lo redefine con
 * `vi.mocked(cargarAlcance).mockResolvedValue(...)`.
 */
vi.mock('@/lib/alcance', () => ({
  cargarAlcance: vi.fn(async () => ({
    acotado: false,
    instalaciones: [] as string[],
    departamentos: [] as string[],
  })),
}));
