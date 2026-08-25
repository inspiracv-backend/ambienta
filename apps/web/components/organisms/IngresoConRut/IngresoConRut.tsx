'use client';

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useSignIn } from '@clerk/nextjs';
import { Button, Input } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { normalizarRut, validarRut } from '@/lib/rut';

/**
 * Ingreso con RUT y clave local (RF-06, decisión D1).
 *
 * ## Por qué un formulario propio y no `<SignIn />`
 *
 * El componente prearmado de Clerk no permite transformar el identificador
 * antes de enviarlo, y **hay que transformarlo**: el RUT viaja como `username`
 * con el prefijo `rut`, porque Clerk rechaza los usernames que son solo
 * dígitos. Un RUT lo es salvo cuando el verificador es K — o sea que mandarlo
 * crudo funcionaría en 1 de cada 11 casos, que es peor que no funcionar nunca
 * porque parece que anda.
 *
 * La persona nunca escribe ni ve el prefijo. Lo pone esta pantalla al entrar y
 * lo pone la API al fijar la clave, **con la misma regla en un solo lugar de
 * cada lado**.
 *
 * ## La sesión que se obtiene es la misma
 *
 * No hay un camino de permisos aparte: Clerk emite el mismo tipo de sesión que
 * con Google, con el mismo `tenant_id` del JWT Template. Es el escenario
 * «obtiene la misma sesión y los mismos permisos» del requisito, y sale gratis
 * justamente por no haber inventado un segundo emisor.
 */
export function IngresoConRut() {
  const router = useRouter();
  const { isLoaded, signIn, setActive } = useSignIn();

  const [rut, setRut] = useState('');
  const [clave, setClave] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (!validarRut(rut)) {
      // Se corta acá: mandarlo sería contarle al proveedor un RUT que no
      // existe, y volver con un error genérico que la persona no puede
      // interpretar.
      setError('Ese RUT no es válido. Revisa el dígito verificador.');
      return;
    }
    if (!isLoaded) return;

    setEnviando(true);
    try {
      const resultado = await signIn.create({
        identifier: `rut${normalizarRut(rut)!.toLowerCase()}`,
        password: clave,
      });

      if (resultado.status === 'complete') {
        await setActive({ session: resultado.createdSessionId });
        router.push('/dashboard');
        return;
      }

      // Queda a medias cuando la cuenta pide un segundo factor. No se inventa
      // nada acá: se dice lo que pasa y se ofrece el otro camino.
      setError('Tu cuenta necesita un paso adicional. Ingresa con tu proveedor.');
    } catch {
      // **Un solo mensaje para todos los motivos**: RUT sin cuenta, clave
      // incorrecta, cuenta bloqueada. Distinguirlos le confirmaría a quien
      // prueba al azar que ese RUT sí es de alguien del sistema.
      setError('No pudimos verificar tu RUT y clave.');
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={enviar} noValidate>
      <FormField label="RUT" htmlFor="rut-ingreso" required>
        <Input
          id="rut-ingreso"
          value={rut}
          placeholder="12.345.678-5"
          invalid={!!error}
          onChange={(e) => setRut(e.target.value)}
        />
      </FormField>

      <FormField label="Clave" htmlFor="clave-ingreso" required error={error ?? undefined}>
        <Input
          id="clave-ingreso"
          type="password"
          value={clave}
          invalid={!!error}
          onChange={(e) => setClave(e.target.value)}
        />
      </FormField>

      <Button type="submit" isLoading={enviando} disabled={!isLoaded} className="w-full">
        Entrar
      </Button>
    </form>
  );
}
