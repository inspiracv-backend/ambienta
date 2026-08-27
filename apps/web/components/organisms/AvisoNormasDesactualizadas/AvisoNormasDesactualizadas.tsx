'use client';

import { useCallback, useEffect, useState } from 'react';
import { History, Loader2, RefreshCw } from 'lucide-react';
import { Button } from '@/components/atoms';
import { mensajeDeError } from '@/lib/api-client';
import { useSession } from '@/lib/session';
import { useToast } from '@/lib/toast-store';
import {
  actualizarAVersionVigente,
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
 *
 * ## Y por qué ahora tiene un botón
 *
 * Avisar sin ofrecer qué hacer dejaba a la persona con una tarea y sin
 * herramienta. Peor: **la matriz ya mostraba los artículos del texto nuevo**
 * —la pantalla los pide por `/catalog/norms/{id}/articles`, que devuelve los de
 * la versión vigente— así que `selected_version_id` era un dato que sólo miraba
 * este aviso, y las evaluaciones viejas quedaban invisibles sin que nada lo
 * dijera.
 *
 * Actualizar apunta la norma al texto de hoy y siembra sus artículos por
 * evaluar. **No migra las evaluaciones anteriores y no las borra**: migrarlas
 * sería inventar —entre versiones los artículos se renumeran, se parten y
 * desaparecen— y borrarlas destruiría la respuesta ante una auditoría del
 * período en que se hicieron.
 */
export function AvisoNormasDesactualizadas() {
  const { user } = useSession();
  const { mostrarToast } = useToast();
  const [normas, setNormas] = useState<NormaDesactualizada[]>([]);
  const [matrixId, setMatrixId] = useState<string | null>(null);
  const [trabajando, setTrabajando] = useState<string | null>(null);

  const cargar = useCallback(async (tenantId: string) => {
    // La matriz se resuelve acá y no se recibe por prop: el store de la matriz
    // legal no la conoce —trabaja con `matrix_norms`, no con la matriz— y
    // pasarla desde la pantalla obligaría a que la pantalla la buscara.
    const id = await cargarMatrizVigente(tenantId);
    setMatrixId(id);
    if (!id) return [];
    return cargarDesactualizadas(id, tenantId);
  }, []);

  useEffect(() => {
    const tenantId = user?.tenantId;
    if (!tenantId) return;
    let vigente = true;
    cargar(tenantId)
      // Sin matriz o sin permiso, no hay aviso. Un error acá no debe tapar la
      // matriz entera: es información complementaria, no la pantalla.
      .catch(() => [])
      .then((d) => {
        if (vigente) setNormas(d);
      });
    return () => {
      vigente = false;
    };
  }, [user?.tenantId, cargar]);

  async function actualizar(matrixNormIds?: string[]) {
    const tenantId = user?.tenantId;
    if (!tenantId || !matrixId) return;

    setTrabajando(matrixNormIds?.[0] ?? 'todas');
    try {
      const r = await actualizarAVersionVigente(matrixId, tenantId, matrixNormIds);

      if (r.actualizadas === 0) {
        // Puede pasar sin que nadie se equivoque: otra persona las actualizó
        // entre que se dibujó esta pantalla y se apretó el botón. Se dice, en
        // vez de mostrar un "listo" de una operación que no ocurrió.
        mostrarToast({
          tipo: 'info',
          mensaje: 'No había nada que actualizar',
          descripcion: 'Estas normas ya apuntaban a su texto vigente.',
        });
      } else {
        mostrarToast({
          tipo: 'exito',
          mensaje:
            r.actualizadas === 1
              ? 'Norma actualizada al texto vigente'
              : `${r.actualizadas} normas actualizadas al texto vigente`,
          // **Se nombra lo conservado.** Sin esta frase, "actualizado" se lee
          // como "se perdió lo que había evaluado".
          descripcion:
            `${r.articulosNuevos} artículos quedaron por evaluar. ` +
            `Las ${r.evaluacionesConservadas} evaluaciones anteriores se conservan.`,
        });
      }

      setNormas(await cargar(tenantId));
    } catch (e: unknown) {
      mostrarToast({ tipo: 'error', mensaje: mensajeDeError(e) });
    } finally {
      setTrabajando(null);
    }
  }

  if (normas.length === 0) return null;

  const evaluaciones = normas.reduce((n, x) => n + x.evaluacionesSobreLaAnterior, 0);

  return (
    <section className="rounded-xl border border-sky-200 bg-sky-50 p-4">
      <div className="flex gap-3">
        <History className="mt-0.5 h-5 w-5 shrink-0 text-sky-600" aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <h2 className="font-medium text-sky-900">
              {normas.length === 1
                ? 'Una norma tiene una versión más nueva'
                : `${normas.length} normas tienen una versión más nueva`}
            </h2>
            {normas.length > 1 && (
              <Button
                size="sm"
                variant="secondary"
                isLoading={trabajando === 'todas'}
                disabled={trabajando !== null}
                onClick={() => actualizar()}
                icon={<RefreshCw className="h-4 w-4" aria-hidden />}
              >
                Actualizar todas
              </Button>
            )}
          </div>

          <p className="mt-1 text-sm text-sky-800">
            {/* Se dice explícitamente que lo evaluado sigue valiendo. Sin esta
                frase, el aviso se lee como "rehaz todo esto". */}
            Las {evaluaciones} evaluaciones hechas contra la versión anterior siguen siendo válidas
            para el período en que se hicieron. Revisar el texto nuevo indica si algo cambió.
          </p>

          <ul className="mt-3 space-y-2 text-sm text-sky-900">
            {normas.map((n) => (
              <li
                key={n.matrixNormId}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-white/60 px-3 py-2"
              >
                <span className="min-w-0 flex-1 truncate" title={n.titulo}>
                  {n.titulo}
                  <span className="ml-1 tabular-nums text-sky-700">
                    ({n.evaluacionesSobreLaAnterior}{' '}
                    {n.evaluacionesSobreLaAnterior === 1 ? 'evaluación' : 'evaluaciones'})
                  </span>
                </span>
                {/* Una por una y no sólo "todas": una norma con cien
                    evaluaciones se revisa cuando hay tiempo de leerla, y
                    obligar a mover todas de golpe empuja a no mover ninguna. */}
                <Button
                  size="sm"
                  variant="secondary"
                  isLoading={trabajando === n.matrixNormId}
                  disabled={trabajando !== null}
                  onClick={() => actualizar([n.matrixNormId])}
                >
                  Actualizar
                </Button>
              </li>
            ))}
          </ul>

          <p className="mt-3 flex items-start gap-1.5 text-xs text-sky-700">
            {trabajando !== null && (
              <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden />
            )}
            <span>
              Actualizar apunta la norma a su texto vigente y deja sus artículos por evaluar.
              Las evaluaciones anteriores <strong>no se migran ni se borran</strong>: quedan
              como la respuesta del período en que se hicieron.
            </span>
          </p>
        </div>
      </div>
    </section>
  );
}
