'use client';

import { useId, useState, type FormEvent } from 'react';
import { KeyRound } from 'lucide-react';
import { Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { api, mensajeDeError } from '@/lib/api-client';
import { validarRut } from '@/lib/rut';

/**
 * S-42 · Fijar RUT y clave local (RF-06).
 *
 * Quien entró con Google puede fijar su RUT y una clave, y desde entonces
 * ingresar con ellos. **No reemplaza el acceso anterior, lo suma**: el ingreso
 * por el proveedor sigue funcionando igual.
 *
 * ## El RUT se valida acá y allá
 *
 * No es duplicación por descuido. Acá evita un viaje de ida y vuelta por un
 * dígito mal tecleado, que es el error más común; la API lo vuelve a validar
 * porque **el navegador no es una barrera**, y porque la API tiene clientes que
 * no son esta pantalla.
 *
 * Los dos lados comparten la tabla de casos de prueba (`lib/rut.test.ts` y
 * `apps/api/tests/test_rut.py`), que es lo único que impide que se
 * desincronicen: no pueden importarse entre sí.
 *
 * ## Lo que esta pantalla NO hace
 *
 * No muestra si la persona ya tiene clave local fijada. Saberlo exige
 * preguntárselo a Clerk, y `GET /me` hoy no lo trae. Volver a fijarla funciona
 * igual —es el mismo POST—, así que la ausencia molesta pero no bloquea.
 */
export function ClaveLocalCard() {
  const formId = useId();
  const [rut, setRut] = useState('');
  const [clave, setClave] = useState('');
  const [confirmacion, setConfirmacion] = useState('');
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [enviando, setEnviando] = useState(false);
  const [listo, setListo] = useState<string | null>(null);

  function validar(): boolean {
    const next: Record<string, string> = {};
    if (!validarRut(rut)) next.rut = 'Ese RUT no es válido. Revisa el dígito verificador.';
    if (clave.length < 8) next.clave = 'La clave debe tener al menos 8 caracteres.';
    // Se pide dos veces porque **una clave mal tecleada no se puede recuperar
    // desde acá**: la guarda el proveedor de identidad, y esta pantalla no
    // tiene forma de mostrarla ni de compararla después.
    if (clave !== confirmacion) next.confirmacion = 'Las claves no coinciden.';
    setErrores(next);
    return Object.keys(next).length === 0;
  }

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!validar()) return;

    setEnviando(true);
    try {
      const r = await api.post<{ rut: string; mensaje: string }>('/me/clave-local', {
        rut,
        clave,
      });
      setListo(r.rut);
      setClave('');
      setConfirmacion('');
    } catch (error) {
      // `mensajeDeError` distingue el 409 del RUT ocupado del 422 de una clave
      // que el proveedor rechaza — y el texto del proveedor explica mejor que
      // uno nuestro ("esa contraseña aparece en filtraciones conocidas").
      setErrores({ clave: mensajeDeError(error) });
    } finally {
      setEnviando(false);
    }
  }

  if (listo) {
    return (
      <section className="rounded-card border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
          <KeyRound className="h-4 w-4 text-brand-600" aria-hidden />
          Ingreso con RUT activado
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          Desde ahora puedes entrar con <span className="font-mono">{listo}</span> y tu
          clave. <strong>Tu acceso con Google sigue funcionando igual.</strong>
        </p>
        <button
          type="button"
          onClick={() => setListo(null)}
          className="mt-4 text-xs font-medium text-brand-600 hover:underline"
        >
          Cambiar la clave
        </button>
      </section>
    );
  }

  return (
    <section className="rounded-card border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
        <KeyRound className="h-4 w-4 text-brand-600" aria-hidden />
        Ingresar con RUT y clave
      </h2>
      <p className="mt-1 text-sm text-slate-500">
        Para poder entrar sin depender de Google. Se suma a lo que ya tienes: no
        reemplaza nada.
      </p>

      <form className="mt-5 flex flex-col gap-4" onSubmit={enviar} noValidate>
        <FormField label="RUT" htmlFor={`${formId}-rut`} required error={errores.rut}>
          <Input
            id={`${formId}-rut`}
            value={rut}
            placeholder="12.345.678-5"
            invalid={!!errores.rut}
            onChange={(e) => setRut(e.target.value)}
          />
        </FormField>

        <FormField label="Clave" htmlFor={`${formId}-clave`} required error={errores.clave}>
          <Input
            id={`${formId}-clave`}
            type="password"
            value={clave}
            invalid={!!errores.clave}
            onChange={(e) => setClave(e.target.value)}
          />
        </FormField>

        <FormField
          label="Repite la clave"
          htmlFor={`${formId}-confirmacion`}
          required
          error={errores.confirmacion}
        >
          <Input
            id={`${formId}-confirmacion`}
            type="password"
            value={confirmacion}
            invalid={!!errores.confirmacion}
            onChange={(e) => setConfirmacion(e.target.value)}
          />
        </FormField>

        <Button type="submit" isLoading={enviando} className="mt-1 w-full">
          Fijar clave
        </Button>
      </form>
    </section>
  );
}
