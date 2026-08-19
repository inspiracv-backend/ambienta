'use client';

import { useEffect, useState } from 'react';
import { History } from 'lucide-react';
import { useSession } from '@/lib/session';
import {
  cargarDesactualizadas,
  cargarMatrizVigente,
  type NormaDesactualizada,
} from '@/lib/normativa-aplicable';

/**
 * Qué normas de la matriz se evaluaron contra un texto que ya no rige (7.4).
 *
 * ## Por qué esto no dice "trabajo perdido"
 *
 * Es la tentación obvia: una norma cambió, luego las evaluaciones hechas contra
 * la versión anterior "hay que rehacerlas". **Es falso, y decirlo sería
 * dañino.** Esas evaluaciones se hicieron sobre el texto que regía entonces, y
 * son exactamente la respuesta correcta ante una auditoría de ese período.
 *
 * El número está para dimensionar el esfuerzo de revisar, no para alarmar. Por
 * eso el aviso es informativo y no rojo: nada está mal, hay algo que mirar.
 */
export function AvisoNormasDesactualizadas() {
  const { user } = useSession();
  const [normas, setNormas] = useState<NormaDesactualizada[]>([]);

  useEffect(() => {
    const tenantId = user?.tenantId;
    if (!tenantId) return;
    let vigente = true;
    // La matriz se resuelve acá y no se recibe por prop: el store de la matriz
    // legal no la conoce —trabaja con `matrix_norms`, no con la matriz— y
    // pasarla desde la pantalla obligaria a que la pantalla la buscara.
    cargarMatrizVigente(tenantId)
      .then((matrixId) => (matrixId ? cargarDesactualizadas(matrixId, tenantId) : []))
      // Sin matriz o sin permiso, no hay aviso. Un error acá no debe tapar la
      // matriz entera: es información complementaria, no la pantalla.
      .catch(() => [])
      .then((d) => {
        if (vigente) setNormas(d);
      });
    return () => {
      vigente = false;
    };
  }, [user?.tenantId]);

  if (normas.length === 0) return null;

  const evaluaciones = normas.reduce((n, x) => n + x.evaluacionesSobreLaAnterior, 0);

  return (
    <section className="rounded-xl border border-sky-200 bg-sky-50 p-4">
      <div className="flex gap-3">
        <History className="mt-0.5 h-5 w-5 shrink-0 text-sky-600" aria-hidden />
        <div className="min-w-0">
          <h2 className="font-medium text-sky-900">
            {normas.length === 1
              ? 'Una norma tiene una versión más nueva'
              : `${normas.length} normas tienen una versión más nueva`}
          </h2>
          <p className="mt-1 text-sm text-sky-800">
            {/* Se dice explícitamente que lo evaluado sigue valiendo. Sin esta
                frase, el aviso se lee como "rehaz todo esto". */}
            Las {evaluaciones} evaluaciones hechas contra la versión anterior siguen siendo válidas
            para el período en que se hicieron. Revisar el texto nuevo indica si algo cambió.
          </p>
          <ul className="mt-2 space-y-1 text-sm text-sky-900">
            {normas.map((n) => (
              <li key={n.matrixNormId} className="truncate">
                {n.titulo}
                <span className="ml-1 tabular-nums text-sky-700">
                  ({n.evaluacionesSobreLaAnterior}{' '}
                  {n.evaluacionesSobreLaAnterior === 1 ? 'evaluación' : 'evaluaciones'})
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
