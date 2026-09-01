'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { useClerk, useUser } from '@clerk/nextjs';
import type { User } from '@ambienta/shared';
import { useUsers } from '@/lib/users-store';
import { CLERK_HABILITADO } from '@/lib/clerk-config';
import { cargarAlcance } from '@/lib/alcance';

/**
 * El usuario de la sesion **si** sabe a que plantas esta acotado.
 *
 * En la lista de usuarios `plantIds` viene `undefined` —el listado no trae el
 * alcance de cada uno— pero para quien tiene la sesion se pide a `GET /me`.
 * Tiparlo aparte deja que las pantallas hagan `user.plantIds.length > 0` sin
 * un `?.` que las obligaria a decidir que hacer con "no se sabe".
 */
export type UsuarioDeLaSesion = User & { plantIds: string[] };

/**
 * Pide el alcance de la sesion a `GET /me`.
 *
 * ## Tres resultados, y los tres hacen falta
 *
 * - `'cargando'` — todavia no se sabe.
 * - `'fallo'` — se pregunto y no se pudo saber.
 * - `string[]` — la respuesta. **Vacio significa "sin acotar"**, o sea que ve
 *   todas las plantas.
 *
 * `'cargando'` y `'fallo'` **no se pueden colapsar**: si un fallo se dejara
 * como "cargando", la pantalla se quedaria girando para siempre y nadie
 * saldria de ahi.
 *
 * ## Que pasa ante un fallo, y por que
 *
 * **La identidad no depende del alcance.** Si `/me` falla, la persona entra
 * igual y queda sin acotar, que es exactamente como se comportaba el sistema
 * antes de este cambio.
 *
 * Se considero lo contrario —dejar la sesion sin resolver— y se descarto: el
 * acotamiento por planta es **dentro** de una empresa, y la separacion entre
 * empresas la sigue garantizando RLS, que no depende de esto. Dejar a alguien
 * sin poder trabajar porque una llamada fallo es un precio mas alto que
 * mostrarle una planta de su propia empresa.
 *
 * Lo que **si** se evita es el parpadeo: mientras el alcance no se sabe, la
 * sesion se declara `cargando`, y las pantallas ya esperan a eso. Asi nadie
 * acotado ve de mas mientras carga.
 */
type Alcance = 'cargando' | 'fallo' | string[];

/**
 * El alcance como lista, para cuando todavia no se sabe o no se pudo saber.
 *
 * Devuelve `[]` —"sin acotar"— en los dos casos. Es una concesion consciente y
 * no un descuido: durante la carga nadie la ve, porque la sesion se declara
 * `cargando`; ante un fallo se prefiere que la persona trabaje sin acotar
 * antes que dejarla afuera, por lo que dice el bloque de arriba.
 */
function plantasDe(alcance: Alcance): string[] {
  return Array.isArray(alcance) ? alcance : [];
}

function useAlcance(tenantId: string | null): Alcance {
  const [alcance, setAlcance] = useState<Alcance>('cargando');

  useEffect(() => {
    if (!tenantId) {
      setAlcance('cargando');
      return;
    }
    let cancelado = false;
    setAlcance('cargando');
    cargarAlcance(tenantId)
      .then((a) => {
        if (!cancelado) setAlcance(a.instalaciones);
      })
      .catch(() => {
        if (!cancelado) setAlcance('fallo');
      });
    return () => {
      cancelado = true;
    };
  }, [tenantId]);

  return alcance;
}

/**
 * Quien es el usuario de la sesion.
 *
 * `user` se deriva en vivo de `UsersProvider` (no de una copia propia) para
 * que editar el nombre/rol/estado de un usuario (S-41/S-42, Seccion N) se
 * refleje de inmediato en `AppHeader` y en el resto de la app sin duplicar el
 * dato. Lo unico que cambia entre los dos modos es **de donde sale la
 * identidad**: de Clerk o de localStorage.
 */
interface SessionContextValue {
  user: UsuarioDeLaSesion | null;
  /**
   * La sesión todavía se está resolviendo.
   *
   * Existe porque `user === null` significaba dos cosas distintas —"no hay
   * sesión" y "todavía no sé"— y las pantallas las trataban igual: 24 páginas
   * hacían `if (user === null) router.replace('/login')`. Con Clerk eso
   * rebotaba **toda** carga directa por URL, porque el usuario tarda un
   * instante en resolverse contra la lista de la API.
   */
  cargando: boolean;
  login: (userId: string) => void;
  logout: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);
const STORAGE_KEY = 'ambienta.mockUserId';

/**
 * Sesion real. El identificador estable entre Clerk y nuestra base es el
 * **email**: `users.clerk_user_id` solo se llena cuando el webhook procesa el
 * alta (Fase 2), y una persona que ya existia en la base no lo tiene. Es el
 * mismo criterio que usa `clerk_sync` para adoptar usuarios preexistentes.
 *
 * Si Clerk conoce a la persona pero la base no, `user` queda null: tener
 * cuenta no da acceso por si solo (RF-03). Aca no se inventa un usuario.
 */
function SessionDesdeClerk({ children }: { children: ReactNode }) {
  const { users, loading: cargandoUsuarios } = useUsers();
  const { user: clerkUser, isLoaded } = useUser();
  const { signOut } = useClerk();

  const email = clerkUser?.primaryEmailAddress?.emailAddress?.toLowerCase() ?? null;
  const encontrado =
    isLoaded && email ? (users.find((u) => u.email.toLowerCase() === email) ?? null) : null;

  const alcance = useAlcance(encontrado?.tenantId ?? null);
  const user = encontrado ? { ...encontrado, plantIds: plantasDe(alcance) } : null;

  // Tres esperas, no una: Clerk resuelve quien entro, hay que encontrar a esa
  // persona en la lista de la empresa, y hay que saber a que plantas esta
  // acotada. Hasta que las tres terminen, `user === null` no significa "no hay
  // sesion". Un `'fallo'` **si** termina la espera: si no, el spinner no baja
  // nunca.
  const cargando =
    !isLoaded ||
    (email !== null && cargandoUsuarios) ||
    (encontrado !== null && alcance === 'cargando');

  // `login` no existe con proveedor real: la pantalla de ingreso es de Clerk.
  // Queda como no-op en vez de lanzar, para que ningun componente tenga que
  // conocer los dos caminos.
  const value: SessionContextValue = {
    user,
    cargando,
    login: () => {},
    logout: () => void signOut({ redirectUrl: '/login' }),
  };

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

/** Sesion simulada: el rol lo elige el DevRoleSwitcher y vive en localStorage. */
function SessionMock({ children }: { children: ReactNode }) {
  const { users } = useUsers();
  const [userId, setUserId] = useState<string | null>(null);
  // El id vive en localStorage, que solo se puede leer despues de montar. Ese
  // primer render tambien es "todavia no se", igual que con Clerk.
  const [leido, setLeido] = useState(false);

  useEffect(() => {
    const storedId = window.localStorage.getItem(STORAGE_KEY);
    if (storedId) setUserId(storedId);
    setLeido(true);
  }, []);

  const encontrado = users.find((u) => u.id === userId) ?? null;
  const alcance = useAlcance(encontrado?.tenantId ?? null);
  const user = encontrado ? { ...encontrado, plantIds: plantasDe(alcance) } : null;

  function login(userIdToLogin: string) {
    const found = users.find((u) => u.id === userIdToLogin) ?? null;
    if (found) {
      setUserId(found.id);
      window.localStorage.setItem(STORAGE_KEY, found.id);
    } else {
      setUserId(null);
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }

  function logout() {
    setUserId(null);
    window.localStorage.removeItem(STORAGE_KEY);
  }

  return (
    <SessionContext.Provider
      value={{
        user,
        cargando: !leido || (encontrado !== null && alcance === 'cargando'),
        login,
        logout,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

/**
 * Son dos componentes y no un condicional dentro de uno porque `useUser()`
 * solo es valido bajo `ClerkProvider`: llamarlo despues de un `if` seria un
 * hook condicional, que es justo lo que ya rompio el build una vez.
 */
export function SessionProvider({ children }: { children: ReactNode }) {
  if (CLERK_HABILITADO) return <SessionDesdeClerk>{children}</SessionDesdeClerk>;
  return <SessionMock>{children}</SessionMock>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession debe usarse dentro de <SessionProvider>');
  return ctx;
}
