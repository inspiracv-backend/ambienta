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
