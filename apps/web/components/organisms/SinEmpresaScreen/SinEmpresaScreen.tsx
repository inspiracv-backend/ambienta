'use client';

import { useState } from 'react';
import { Building2 } from 'lucide-react';
import { Button } from '@/components/atoms';

interface Props {
  /** El correo con que entró, para que sepa con cuál pedir el alta. `null` si no se conoce. */
  correo: string | null;
  onCerrarSesion: () => Promise<void> | void;
}

/**
 * La pantalla de quien entró con su cuenta pero no está dado de alta en ninguna
 * empresa (`acceso-por-sso`, Fase 4).
 *
 * Tres cosas que tiene que cumplir, y por qué:
 *
 * 1. **Dice qué pasa y a quién pedirle el acceso**, en vez de mostrar errores
 *    403 en cada pantalla.
 * 2. **Permite cerrar sesión.** Sin eso, quien entró con la cuenta equivocada
 *    queda atrapado: la sesión sobrevive al refresco.
 * 3. **No revela si la empresa de su dominio existe en el sistema**, y **no
 *    redirige al ingreso** —eso arma un bucle, porque el ingreso la ve adentro y
 *    la devuelve—.
 *
 * El texto es provisional: el cambio lo marca como supuesto por confirmar.
 */
export function SinEmpresaScreen({ correo, onCerrarSesion }: Props) {
  const [cerrando, setCerrando] = useState(false);

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-md rounded-card border border-slate-200 bg-white p-8 text-center shadow-sm">
        <Building2 className="mx-auto h-10 w-10 text-slate-400" aria-hidden />
        <h1 className="mt-4 text-lg font-semibold text-slate-900">Tu cuenta todavía no tiene acceso</h1>
        <p className="mt-2 text-sm text-slate-600">
          Iniciaste sesión correctamente, pero tu cuenta no está asociada a una empresa en Ambienta.
        </p>
        <p className="mt-2 text-sm text-slate-600">
          Pídele a quien administra Ambienta en tu empresa que te dé de alta
          {correo ? (
            <>
              {' '}con el correo <span className="font-medium text-slate-800">{correo}</span>
            </>
          ) : null}
          . Si entraste con otra cuenta por error, cierra sesión y vuelve a ingresar.
        </p>
        <Button
          className="mt-6 w-full"
          variant="secondary"
          disabled={cerrando}
          onClick={async () => {
            setCerrando(true);
            try {
              await onCerrarSesion();
            } finally {
              setCerrando(false);
            }
          }}
        >
          {cerrando ? 'Cerrando sesión…' : 'Cerrar sesión'}
        </Button>
      </div>
    </main>
  );
}
