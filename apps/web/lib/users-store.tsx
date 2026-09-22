'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Role, User, UserEstado } from '@ambienta/shared';
import { mockUsers } from '@/mocks/users';
import { useToast } from '@/lib/toast-store';
import { api, mensajeDeError } from '@/lib/api-client';
import { CLERK_HABILITADO } from '@/lib/clerk-config';

interface UsersContextValue {
  users: User[];
  loading: boolean;
  /**
   * Registra a la persona **con su rol** y le manda la invitación de Clerk, en
   * un solo acto (`POST /users/invitaciones`). Rechaza si no salió: en ese
   * caso la API no dejó nada escrito.
   */
  inviteUser: (input: NuevaInvitacion) => Promise<User>;
  updateRole: (userId: string, role: Role) => void;
  /** Las plantas a las que está acotada. Vacía = todas. Rechaza si falla. */
  leerAlcance: (userId: string, tenantId: string) => Promise<string[]>;
  /** Una planta, o `null` para todas. Rechaza si la base no lo guardó. */
  fijarAlcance: (userId: string, tenantId: string, facilityId: string | null) => Promise<string[]>;
  updateDepartamento: (userId: string, departamentoId: string | null) => void;
  updateNombre: (userId: string, nombre: string) => void;
  setEstado: (
    userId: string,
    estado: UserEstado,
  ) => Promise<{ ok: boolean; error?: string }>;
}

export interface NuevaInvitacion {
  tenantId: string;
  nombre: string;
  email: string;
  role: Role;
  departamentoId: string | null;
}

/**
 * El cuerpo de `POST /users/invitaciones`, literal.
 *
 * **El rol va explícito**: sin rol la persona entra y recibe 403 en todo. El
 * criterio es el de `db/09` —administrador → `admin_empresa`, el resto →
 * `encargado_ambiental`— y se ajusta después en la pantalla de permisos.
 */
export function cuerpoDeInvitacion(input: NuevaInvitacion) {
  const esAdmin = input.role === 'admin_empresa';
  return {
    full_name: input.nombre,
    email: input.email,
    user_type: esAdmin ? 'tenant_admin' : 'internal',
    department_id: input.departamentoId ?? null,
    role_code: esAdmin ? 'admin_empresa' : 'encargado_ambiental',
  };
}

const UsersContext = createContext<UsersContextValue | null>(null);

const USER_TYPE_TO_ROLE: Record<string, Role> = {
  platform_admin: 'superadmin',
  tenant_admin: 'admin_empresa',
  internal: 'usuario_interno',
  guest: 'cliente_invitado',
  manager: 'gestor',
};

/**
 * Los cuatro estados de `users.status` a los tres de la pantalla.
 *
 * `blocked` y `disabled` se muestran igual —desactivado— porque para quien
 * administra son lo mismo: la persona no entra. La distincion importa en la
 * base (uno lo pone un administrador, el otro puede ponerlo el sistema), no en
 * la tabla.
 *
 * **Lo que estaba mal:** cualquier estado distinto de `active` se mostraba como
 * `invitado`. Una persona desactivada aparecia como alguien a quien se le
 * mando una invitacion y no la acepto — dos situaciones opuestas, y la segunda
 * invita a reenviarle la invitacion a quien acaba de ser dado de baja.
 */
const DE_ESTADO_DE_LA_API: Record<string, UserEstado> = {
  active: 'activo',
  invited: 'invitado',
  blocked: 'desactivado',
  disabled: 'desactivado',
};

/**
 * Y la vuelta. `disabled` y no `inactive`: **`inactive` no existe** en el
 * CHECK de `users`, asi que la version anterior hacia que Postgres rechazara
 * cada desactivacion.
 *
 * Reactivar deja a la persona en `active` y no en `invited`: ya acepto en su
 * momento, y devolverla a "invitada" le pediria aceptar de nuevo.
 */
const A_ESTADO_DE_LA_API: Record<UserEstado, string> = {
  activo: 'active',
  invitado: 'invited',
  desactivado: 'disabled',
};

function mapApiUser(raw: Record<string, unknown>): User | null {
  try {
    const role = USER_TYPE_TO_ROLE[String(raw.user_type)] ?? 'usuario_interno';
    return {
      id: String(raw.id),
      tenantId: raw.tenant_id ? String(raw.tenant_id) : null,
      nombre: String(raw.full_name ?? raw.display_name ?? ''),
      email: String(raw.email ?? ''),
      role,
      departamentoId: raw.department_id ? String(raw.department_id) : null,
      estado: DE_ESTADO_DE_LA_API[String(raw.status)] ?? 'invitado',
      ultimaActividad: raw.last_login_at ? String(raw.last_login_at) : null,
    };
  } catch {
    return null;
  }
}

export function UsersProvider({ children }: { children: ReactNode }) {
  // **Este store se queda con datos de ejemplo a proposito, y es el unico**
  // (#208). No son registros inventados sobre la empresa: son la **fuente de
  // identidad** del modo sin Clerk. `SessionProvider` resuelve quien eres
  // buscando aca el id que el DevRoleSwitcher guardo en `localStorage`
  // (`users.find((u) => u.id === userId)`), asi que con la lista vacia no hay
  // sesion posible y el conmutador de rol deja de funcionar.
  //
  // Vaciarlo no arregla nada: quita el mecanismo de autenticacion de
  // desarrollo que CLAUDE.md documenta como el camino soportado sin Clerk.
  // Reemplazarlo exige decidir con que se identifica uno en desarrollo, y esa
  // es una decision aparte.
  //
  // Con la API arriba se reemplazan por los usuarios reales, que es lo que
  // pasa en cualquier entorno con backend.
  const [users, setUsers] = useState<User[]>(mockUsers);
  const { mostrarToast } = useToast();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    /**
     * Con Clerk el tenant lo fija el JWT, asi que `/users/` ya viene acotado
     * por RLS a la empresa de quien pregunta y **no hay que recorrer tenants**:
     * hacerlo pediria N veces la misma lista, porque la API ignora
     * X-Tenant-Id cuando hay token (apps/api/app/deps.py).
     *
     * Sin Clerk no existe sesion que declare un tenant, asi que se enumeran
     * todos para poder cambiar de rol con el DevRoleSwitcher.
     */
    async function fetchUsuariosDelTenant() {
      const data = await api.get<Record<string, unknown>[]>('/users/');
      return data.map(mapApiUser).filter((u): u is User => u !== null);
    }

    async function fetchUsuariosDeTodosLosTenants() {
      const tenants = await api.get<{ id: string }[]>('/tenants/');
      const seen = new Set<string>();
      const allUsers: User[] = [];
      for (const tenant of tenants) {
        try {
          const data = await api.get<Record<string, unknown>[]>('/users/', { tenantId: tenant.id });
          const mapped = data.map(mapApiUser).filter((u): u is User => u !== null);
          for (const u of mapped) {
            if (!seen.has(u.id)) {
              seen.add(u.id);
              allUsers.push(u);
            }
          }
        } catch {
          // skip tenant if users fail
        }
      }
      return allUsers;
    }

    async function fetchAllUsers() {
      try {
        const cargados = CLERK_HABILITADO
          ? await fetchUsuariosDelTenant()
          : await fetchUsuariosDeTodosLosTenants();
        if (!cancelled && cargados.length > 0) setUsers(cargados);
      } catch {
        // Fallback a mocks
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchAllUsers();
    return () => { cancelled = true; };
  }, []);

  async function inviteUser(input: NuevaInvitacion): Promise<User> {
    // **Sin fila optimista.** Antes se agregaba a la lista con un id inventado
    // y se hacía solo `POST /users/`: la persona quedaba "Invitada" en pantalla
    // y **nunca recibía el correo**, porque nadie le pedía la invitación a
    // Clerk. Ahora la lista muestra lo que la API confirmó.
    const respuesta = await api.post<{ user: Record<string, unknown> }>(
      '/users/invitaciones',
      cuerpoDeInvitacion(input),
      { tenantId: input.tenantId },
    );
    const creado = mapApiUser(respuesta.user);
    if (!creado) throw new Error('La API respondió sin la persona invitada.');
    setUsers((prev) => [...prev, creado]);
    return creado;
  }

  /**
   * **No llega a la base, y ya no finge que sí.**
   *
   * Antes mandaba `user_type` a `PATCH /users/{id}`. Ese campo **no está en
   * `UserUpdate`**, así que la API respondía 200 y no cambiaba nada: el rol
   * volvía al recargar y ningún error lo delataba.
   *
   * Pero el arreglo no es renombrar el campo. `users.user_type` es una
   * etiqueta; **los permisos salen de `user_roles`**, que es otra tabla con
   * su propia vigencia. Escribir `user_type` cambiaría lo que dice la ficha
   * sin cambiar lo que la persona puede hacer — que es exactamente el tipo de
   * mentira que este repo ya pagó caro.
   *
   * El endpoint que asigna rol contra `user_roles` es el alcance de #140. Hasta
   * entonces esto queda en local y **se dice en pantalla**, en vez de escribir
   * a un campo que no manda.
   */
  /**
   * **Esto cambia el tipo de cuenta en la vista, no los permisos.**
   *
   * `User.role` sale de `users.user_type` y decide el menú; lo que la guarda de
   * cada ruta consulta es `user_roles`, que se administra en el modal «Rol»
   * (`RolDePermisosModal`) contra `PUT /users/{id}/roles`.
   *
   * El aviso anterior decía «el cambio de rol no se guardó» y era cierto por
   * una razón que ya no aplica: `user_roles` no tenía ni una ruta. Ahora la
   * tiene (#140), así que el mensaje pasa a decir **dónde** se cambia el
   * permiso en vez de dejar a la persona sin salida.
   */
  function updateRole(userId: string, role: Role) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role } : u)));
    mostrarToast({
      tipo: 'info',
      mensaje: 'Cambiaste el tipo de cuenta, no los permisos',
      descripcion:
        'Lo que esta persona puede hacer lo decide su rol de permisos. Se asigna en el botón «Rol» de su fila.',
    });
  }

  /**
   * El alcance por planta (#25), contra `GET/PUT /users/{id}/alcance`.
   *
   * Hasta el 13-sep esto era `updatePlants`: tocaba solo el estado local y se
   * perdía al recargar, mientras la API **sí** acotaba por planta — así que
   * nadie podía asignar lo que el sistema aplicaba, salvo con SQL.
   *
   * **Una planta o todas**, no varias: el alcance se guarda en las filas de
   * rol, y la clave `(user_id, role_id)` no admite el mismo rol en dos plantas.
   */
  async function leerAlcance(userId: string, tenantId: string): Promise<string[]> {
    const r = await api.get<{ facility_ids: string[] }>(`/users/${userId}/alcance`, { tenantId });
    return r.facility_ids.map(String);
  }

  async function fijarAlcance(userId: string, tenantId: string, facilityId: string | null): Promise<string[]> {
    const r = await api.put<{ facility_ids: string[] }>(
      `/users/${userId}/alcance`,
      { facility_id: facilityId },
      { tenantId },
    );
    const plantIds = r.facility_ids.map(String);
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, plantIds } : u)));
    return plantIds;
  }

  function updateDepartamento(userId: string, departamentoId: string | null) {
    const anterior = users.find((u) => u.id === userId);
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, departamentoId } : u)));

    if (!anterior?.tenantId) return;
    const previo = anterior.departamentoId;

    api
      .patch(`/users/${userId}`, { department_id: departamentoId }, { tenantId: anterior.tenantId })
      .catch((error) => {
        setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, departamentoId: previo } : u)));
        mostrarToast({
          tipo: 'error',
          mensaje: 'No se pudo cambiar el departamento',
          descripcion: mensajeDeError(error),
        });
      });
  }

  function updateNombre(userId: string, nombre: string) {
    const anterior = users.find((u) => u.id === userId);
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, nombre } : u)));
    if (!anterior?.tenantId) return;

    // `full_name`, no `display_name`. Con el nombre equivocado la API
    // respondia **200 sin cambiar nada** —Pydantic descarta los campos que no
    // declara y `exclude_unset` deja el UPDATE vacio—, que es peor que un 422:
    // nadie revierte y nadie se entera hasta recargar.
    api
      .patch(`/users/${userId}`, { full_name: nombre }, { tenantId: anterior.tenantId })
      .catch((error) => {
        setUsers((prev) =>
          prev.map((u) => (u.id === userId ? { ...u, nombre: anterior.nombre } : u)),
        );
        mostrarToast({
          tipo: 'error',
          mensaje: 'No se pudo cambiar el nombre',
          descripcion: mensajeDeError(error),
        });
      });
  }



  /**
   * **No llega a la base.** Los permisos individuales tienen tabla
   * (`user_permissions`) pero **ninguna API**: dependen de que se apruebe el
   * cambio de RBAC, hoy en 0 de 33 tareas.
   */
  /**
   * Activar o desactivar a alguien, **y decir la verdad sobre si funciono**.
   *
   * Esto estaba roto de tres maneras a la vez, y las tres se tapaban entre si:
   *
   * 1. **Mandaba `status: 'inactive'`, que no existe.** El CHECK de `users`
   *    admite `invited`, `active`, `blocked` y `disabled`. Postgres rechazaba
   *    la fila **siempre**: desactivar a una persona no llegaba nunca a la
   *    base.
   * 2. **`.catch(() => {})` se comia el rechazo.** La pantalla mostraba
   *    "fue desactivado" y un aviso diciendo "el cambio quedo registrado en el
   *    historial" mientras la base no tenia nada. Recargar lo devolvia todo.
   * 3. Y con eso, tampoco se veria el **409** que la API responde cuando la
   *    desactivacion dejaria a la empresa sin nadie que administre usuarios
   *    (#141): la guarda existiria y seria invisible.
   *
   * Ahora devuelve una promesa con el resultado: la vista optimista se
   * revierte si el servidor rechaza, y quien llama puede mostrar el motivo.
   */
  async function setEstado(
    userId: string,
    estado: UserEstado,
  ): Promise<{ ok: boolean; error?: string }> {
    const user = users.find((u) => u.id === userId);
    const anterior = user?.estado;
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, estado } : u)));

    if (!user?.tenantId) {
      // Sin tenant no hay a donde escribir. Se dice, en vez de dejar la
      // pantalla afirmando un cambio que no sale del navegador.
      return { ok: false, error: 'La persona no pertenece a ninguna empresa.' };
    }

    try {
      await api.patch(
        `/users/${userId}`,
        { status: A_ESTADO_DE_LA_API[estado] },
        { tenantId: user.tenantId },
      );
      return { ok: true };
    } catch (e) {
      if (anterior) {
        setUsers((prev) =>
          prev.map((u) => (u.id === userId ? { ...u, estado: anterior } : u)),
        );
      }
      return { ok: false, error: mensajeDeError(e) };
    }
  }

  return (
    <UsersContext.Provider
      value={{
        users,
        loading,
        inviteUser,
        updateRole,
        leerAlcance,
        fijarAlcance,
        updateDepartamento,
        updateNombre,
        setEstado,
      }}
    >
      {children}
    </UsersContext.Provider>
  );
}

export function useUsers() {
  const ctx = useContext(UsersContext);
  if (!ctx) throw new Error('useUsers debe usarse dentro de <UsersProvider>');
  return ctx;
}

/**
 * Como `useUsers`, pero devuelve `null` fuera del provider en vez de lanzar.
 * Lo usa `useNombreDeUsuario`, que tiene que funcionar también en componentes
 * que se prueban sin montar el store de usuarios.
 */
export function useUsersOpcional() {
  return useContext(UsersContext);
}
