'use client';

import { useEffect } from 'react';
import { useAuth } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import { registrarProveedorDeToken, registrarSesionExpirada } from '@/lib/api-client';
import { CLERK_JWT_TEMPLATE } from '@/lib/clerk-config';

/**
 * Conecta la sesion de Clerk con el cliente HTTP.
 *
 * `api` es un modulo plano, no un hook, asi que no puede llamar a `useAuth()`.
 * Este componente vive dentro del `ClerkProvider` —donde el hook si es
 * valido— y le deja registrado el `getToken` para que cada request lo use.
 *
 * Registra la **funcion**, no el token: el template emite tokens de 60s y
 * `getToken()` renueva por dentro. Guardar el string daria 401 a los dos
 * minutos.
 *
 * No pinta nada.
 */
export function ClerkApiBridge() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoaded) return;

    // Sin sesion se deja el proveedor en null a proposito: asi `api` cae al
    // camino de X-Tenant-Id en vez de mandar `Authorization: Bearer null`.
    // Con `template`, no `getToken()` pelado: el token de sesion estandar no
    // lleva el claim `tenant_id` y la API lo rechazaria entero. Ver
    // CLERK_JWT_TEMPLATE.
    registrarProveedorDeToken(
      isSignedIn ? () => getToken({ template: CLERK_JWT_TEMPLATE }) : null,
    );

    // Solo se manda al login si **Clerk** dice que ya no hay sesion. Un 401
    // con sesion viva de Clerk no es una sesion vencida: es el JWT Template
    // mal configurado (sin el claim `tenant_id`, la API rechaza todo). Mandar
    // a /login en ese caso arma un bucle, porque `<SignIn />` ve al usuario
    // dentro y lo devuelve al tablero. Se deja el error a la vista.
    registrarSesionExpirada(() => {
      if (isSignedIn) {
        console.error(
          'La API respondio 401 con sesion de Clerk activa. Revisar que el ' +
            'JWT Template incluya el claim tenant_id y que ese tenant exista.',
        );
        return;
      }
      router.replace('/login');
    });

    return () => {
      registrarProveedorDeToken(null);
      registrarSesionExpirada(null);
    };
  }, [getToken, isLoaded, isSignedIn, router]);

  return null;
}
