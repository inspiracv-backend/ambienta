'use client';

import { ArrowRight, Compass, Cog, LifeBuoy, User2 } from 'lucide-react';
import type { Departamento, TipoProceso, User } from '@ambienta/shared';
import { TIPOS_PROCESO } from '@ambienta/shared';
import { EmptyState } from '@/components/molecules';
import { cn } from '@/lib/utils';

const ICONO: Record<TipoProceso, typeof Compass> = {
  estrategico: Compass,
  operativo: Cog,
  apoyo: LifeBuoy,
};

const ESTILO: Record<TipoProceso, { franja: string; tarjeta: string; texto: string }> = {
  estrategico: { franja: 'bg-brand-50/60 border-brand-200', tarjeta: 'border-brand-200 bg-white', texto: 'text-brand-700' },
  operativo: { franja: 'bg-slate-50 border-slate-200', tarjeta: 'border-slate-300 bg-white', texto: 'text-slate-700' },
  apoyo: { franja: 'bg-slate-50/60 border-slate-200', tarjeta: 'border-slate-200 bg-white', texto: 'text-slate-600' },
};

/**
 * Mapa de procesos (ISO 9001 §4.4).
 *
 * Se **genera** desde los departamentos declarados en el Perfil Empresa: no es
 * un diagrama que alguien dibuje aparte y que quede desactualizado al mes
 * siguiente. Si se agrega un proceso, aparece aquí.
 *
 * El orden de las franjas no es estético sino la convención del mapa: los
 * estratégicos arriba porque dirigen, los operativos al centro porque son la
 * cadena de valor que el cliente percibe, y los de apoyo abajo porque
 * sostienen a los otros dos. Leerlo de arriba abajo cuenta cómo funciona la
 * organización.
 *
 * Las entradas y salidas hacen visible la **interacción**, que es lo que la
 * norma pide representar además de la secuencia — un mapa de cajas sueltas no
 * cumple §4.4.
 */
export function MapaProcesos({
  departamentos,
  usuarios,
  className,
}: {
  departamentos: Departamento[];
  usuarios: User[];
  className?: string;
}) {
  if (departamentos.length === 0) {
    return (
      <EmptyState
        icono={Cog}
        titulo="Todavía no hay procesos declarados"
        descripcion="Al agregar departamentos y clasificarlos, el mapa de procesos se genera solo."
      />
    );
  }

  return (
    <div className={cn('flex flex-col gap-3', className)}>
      {TIPOS_PROCESO.map((tipo) => {
        const delTipo = departamentos.filter((d) => d.tipo === tipo.codigo);
        const estilo = ESTILO[tipo.codigo];
        const Icono = ICONO[tipo.codigo];

        return (
          <section
            key={tipo.codigo}
            aria-labelledby={`franja-${tipo.codigo}`}
            className={cn('rounded-card border p-4', estilo.franja)}
          >
            <div className="flex items-baseline gap-2">
              <Icono className={cn('h-4 w-4 shrink-0 self-center', estilo.texto)} aria-hidden />
              <h3 id={`franja-${tipo.codigo}`} className={cn('text-sm font-semibold', estilo.texto)}>
                {tipo.titulo}
              </h3>
              <span className="text-xs text-slate-500">· {tipo.descripcion}</span>
            </div>

            {delTipo.length === 0 ? (
              <p className="mt-2 text-xs italic text-slate-400">
                Sin procesos de este tipo declarados todavía.
              </p>
            ) : (
              <ul className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {delTipo.map((d) => {
                  const responsable = usuarios.find((u) => u.id === d.responsableId);
                  return (
                    <li key={d.id} className={cn('rounded-lg border p-3 shadow-sm', estilo.tarjeta)}>
                      <p className="text-sm font-semibold text-slate-800">{d.nombre}</p>
                      {d.descripcion && <p className="mt-0.5 text-xs text-slate-500">{d.descripcion}</p>}

                      <p className="mt-2 flex items-center gap-1 text-xs text-slate-500">
                        <User2 className="h-3.5 w-3.5 shrink-0" aria-hidden />
                        {responsable ? (
                          responsable.nombre
                        ) : (
                          // Un proceso sin dueño es un hallazgo esperando ocurrir:
                          // en la auditoría no hay a quién preguntarle.
                          <span className="font-medium text-semaforo-parcial">Sin responsable asignado</span>
                        )}
                      </p>

                      {(d.entradas.length > 0 || d.salidas.length > 0) && (
                        <div className="mt-2 border-t border-slate-100 pt-2 text-[11px] leading-relaxed">
                          {d.entradas.length > 0 && (
                            <p className="text-slate-500">
                              <span className="font-medium text-slate-600">Entradas:</span> {d.entradas.join(' · ')}
                            </p>
                          )}
                          {d.salidas.length > 0 && (
                            <p className="mt-0.5 flex items-start gap-1 text-slate-500">
                              <ArrowRight className="mt-0.5 h-3 w-3 shrink-0 text-slate-400" aria-hidden />
                              <span>
                                <span className="font-medium text-slate-600">Salidas:</span> {d.salidas.join(' · ')}
                              </span>
                            </p>
                          )}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}
