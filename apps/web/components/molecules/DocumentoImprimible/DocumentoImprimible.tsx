'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

/** La marca que, al imprimir, deja en la hoja solo el documento (`globals.css`). */
export const CLASE_IMPRIMIENDO_DOCUMENTO = 'imprimiendo-documento';

/**
 * Un documento que **solo existe en el papel**: no se ve en pantalla y, al
 * imprimir, es lo único que sale.
 *
 * Se monta directo en `<body>` y no donde se declara. Así, mientras dura la
 * impresión, la hoja puede ocultar a todos los demás hijos de `<body>` —la
 * pantalla entera— sin marcar uno por uno lo que no es el documento. Nació en el
 * informe de auditoría (21-sep): el PDF entregable salía precedido por toda la
 * ficha.
 *
 * **Imprimir en una pantalla que lo monta es imprimir el documento**, venga de
 * un botón o de Ctrl+P: se engancha en `beforeprint`, no en un clic. Por eso
 * `onAntesDeImprimir` corre en los dos casos. Y corre **al abrir** el diálogo:
 * el navegador no avisa si la persona lo cancela.
 */
export function DocumentoImprimible({
  children,
  onAntesDeImprimir,
}: {
  children: ReactNode;
  onAntesDeImprimir?: () => void;
}) {
  // El portal necesita `document`, que en el render del servidor no existe.
  const [montado, setMontado] = useState(false);
  useEffect(() => setMontado(true), []);

  // La última versión del callback, sin volver a suscribirse en cada render:
  // un `beforeprint` suelto entre dos suscripciones se perdería.
  const alAbrir = useRef(onAntesDeImprimir);
  alAbrir.current = onAntesDeImprimir;

  useEffect(() => {
    function antes() {
      document.body.classList.add(CLASE_IMPRIMIENDO_DOCUMENTO);
      alAbrir.current?.();
    }
    function despues() {
      document.body.classList.remove(CLASE_IMPRIMIENDO_DOCUMENTO);
    }
    window.addEventListener('beforeprint', antes);
    window.addEventListener('afterprint', despues);
    return () => {
      window.removeEventListener('beforeprint', antes);
      window.removeEventListener('afterprint', despues);
      despues();
    };
  }, []);

  if (!montado) return null;
  return createPortal(<div className="solo-impresion">{children}</div>, document.body);
}
