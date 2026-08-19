'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, Info, ShieldCheck } from 'lucide-react';
import { Spinner } from '@/components/atoms';
import { useSession } from '@/lib/session';
import {
  cargarNormativaAplicable,
  ETIQUETA_DE_NIVEL,
  EXPLICACION_DEL_ESTADO,
  NORMATIVA_VACIA,
  type NormaAplicable,
  type NormativaAplicable,
} from '@/lib/normativa-aplicable';

/**
 * El check de normativa aplicable, antes de generar la matriz (RF-19).
 *
 * ## Por qué es un check y no un botón que genera
 *
 * Calcular y aplicar son operaciones distintas a propósito. El negocio pidió
 * "un check de normativas recomendadas", y un check es una revisión humana
 * antes de comprometerse: generar de golpe le daría a la empresa cientos de
 * artículos que evaluar sin que nadie mirara si tienen sentido.
 *
 * ## Por qué obligatorias y recomendadas van separadas
 *
 * `directa` obliga; `indirecta` y `referencial` se proponen. Mezclarlas
 * convertiría una sugerencia en una obligación dentro de la matriz de la
 * empresa — y quien la revise no tendría cómo distinguir qué tiene que cumplir
 * de qué le conviene mirar.
 *
 * ## Por qué cada norma dice de dónde salió
 *
 * `motivo` y el nivel son la respuesta a la primera pregunta de un
 * fiscalizador: cómo determinaron que esta norma les aplica. Una lista sin eso
 * es una lista que hay que defender de memoria.
 */
export function CheckNormativaAplicable() {
  const { user } = useSession();
  const [datos, setDatos] = useState<NormativaAplicable>(NORMATIVA_VACIA);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (!user?.tenantId) {
      setCargando(false);
      return;
    }
    let vigente = true;
    cargarNormativaAplicable(user.tenantId)
      // Si falla, queda `sin_perfil`: el estado más conservador de los tres.
      // Dice "falta un dato", nunca "no hay obligaciones".
      .catch(() => NORMATIVA_VACIA)
      .then((d) => {
        if (!vigente) return;
        setDatos(d);
        setCargando(false);
      });
    return () => {
      vigente = false;
    };
  }, [user?.tenantId]);

  if (cargando) {
    return (
      <div className="flex justify-center rounded-xl border border-slate-200 bg-white py-12">
        <Spinner />
      </div>
    );
  }

  const explicacion = EXPLICACION_DEL_ESTADO[datos.estado];

  // Los tres estados vacíos se ven idénticos si solo se muestra la lista, y el
  // peor —"nadie clasificó este sector"— se lee como estar en regla.
  if (explicacion) {
    return (
      <div className="flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" aria-hidden />
        <div>
          <p className="font-medium text-amber-900">{explicacion.titulo}</p>
          <p className="mt-1 text-sm text-amber-800">{explicacion.detalle}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <Grupo
        titulo="Obligatorias"
        detalle="Aplicación directa: la empresa debe cumplirlas."
        icono={<ShieldCheck className="h-4 w-4 text-rose-600" aria-hidden />}
        normas={datos.obligatorias}
        vacio="Ninguna norma de aplicación directa para este sector."
      />
      <Grupo
        titulo="Recomendadas"
        detalle="Aplicación indirecta o referencial: se proponen, no obligan."
        icono={<Info className="h-4 w-4 text-slate-500" aria-hidden />}
        normas={datos.recomendadas}
        vacio="Ninguna norma recomendada para este sector."
      />
    </div>
  );
}

function Grupo({
  titulo,
  detalle,
  icono,
  normas,
  vacio,
}: {
  titulo: string;
  detalle: string;
  icono: React.ReactNode;
  normas: NormaAplicable[];
  vacio: string;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white">
      <header className="flex items-start gap-2 border-b border-slate-200 px-4 py-3">
        {icono}
        <div>
          <h3 className="text-sm font-semibold text-slate-900">
            {titulo}{' '}
            <span className="font-normal tabular-nums text-slate-500">({normas.length})</span>
          </h3>
          <p className="text-xs text-slate-500">{detalle}</p>
        </div>
      </header>

      {normas.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-slate-500">{vacio}</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {normas.map((n) => (
            <li key={n.normId} className="px-4 py-3">
              <p className="text-sm font-medium text-slate-900">
                {n.numero ? `${n.numero} — ` : ''}
                {n.titulo}
              </p>
              <p className="mt-0.5 text-xs text-slate-500">
                {ETIQUETA_DE_NIVEL[n.nivel] ?? n.nivel}
                {/* El motivo es lo que hace defendible la lista: sin él, "esta
                    norma me aplica" es una afirmación sin respaldo. */}
                {n.motivo ? ` · ${n.motivo}` : ''}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
