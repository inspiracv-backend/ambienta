'use client';

import { useState } from 'react';
import { SignIn } from '@clerk/nextjs';
import { IngresoConRut } from '@/components/organisms/IngresoConRut';

/**
 * Las dos formas de entrar, en la misma pantalla (RF-05, RF-06).
 *
 * ## Por qué dos formularios y no uno
 *
 * El de correo usa `<SignIn />`, el componente prearmado, que trae Google, la
 * recuperación de contraseña y el CAPTCHA sin que haya que mantenerlos. El de
 * RUT **no puede usarlo**: hay que anteponer el prefijo `rut` al identificador
 * antes de enviarlo, y el componente no deja tocar ese dato (decisión D1).
 *
 * Reescribir también el de correo para unificarlos sería cambiar código
 * mantenido por Clerk por código nuestro, sin ganar nada.
 *
 * ## Por qué el correo va primero
 *
 * Es el camino que ya existe y por el que entra todo el mundo hoy. El de RUT
 * solo sirve a quien **ya fijó** su clave local desde su perfil; ponerlo
 * primero le ofrecería a la mayoría un formulario donde va a fallar.
 */
export function PestanasDeIngreso() {
  const [pestana, setPestana] = useState<'correo' | 'rut'>('correo');

  return (
    <div>
      <div
        role="tablist"
        aria-label="Formas de ingresar"
        className="mb-4 flex rounded-lg border border-slate-200 bg-slate-50 p-1"
      >
        {(
          [
            ['correo', 'Correo o usuario'],
            ['rut', 'RUT y clave'],
          ] as const
        ).map(([valor, etiqueta]) => (
          <button
            key={valor}
            role="tab"
            type="button"
            aria-selected={pestana === valor}
            onClick={() => setPestana(valor)}
            className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition ${
              pestana === valor
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {etiqueta}
          </button>
        ))}
      </div>

      {pestana === 'correo' ? (
        <SignIn
          forceRedirectUrl="/dashboard"
          appearance={{ elements: { rootBox: 'mx-auto' } }}
        />
      ) : (
        <div className="rounded-card border border-slate-200 bg-white p-6 shadow-sm">
          <p className="mb-4 text-sm text-slate-500">
            Solo si ya fijaste tu clave local desde tu perfil.
          </p>
          <IngresoConRut />
        </div>
      )}
    </div>
  );
}
