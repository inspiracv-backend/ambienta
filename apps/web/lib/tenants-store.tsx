'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type {
  Certificacion,
  ContactoComercial,
  ModuloPlataforma,
  Pais,
  Plan,
  Plant,
  Tenant,
} from '@ambienta/shared';
import { documentoDePais, nombreDePais } from '@ambienta/shared';
import { mockTenants } from '@/mocks/tenants';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { MODULO_LABEL } from '@/lib/tenant-status';
import { useToast } from '@/lib/toast-store';
import { api, mensajeDeError } from '@/lib/api-client';

export interface NuevoTenantInput {
  nombre: string;
  pais: Pais;
  numeroIdentificacion: string;
  sector: string;
  giro?: string;
  direccion?: string;
  sitioWeb?: string;
  numeroTrabajadores?: number;
  certificaciones: Certificacion[];
  contactoComercial?: ContactoComercial;
  notasComerciales?: string;
  esGestor: boolean;
  plan: Plan;
  /** Días de vigencia desde hoy: la demo por defecto son 10 (RF-82). */
  diasVigencia: number;
  limiteUsuarios: number;
  modulosActivos: ModuloPlataforma[];
}

interface TenantsContextValue {
  tenants: Tenant[];
  loading: boolean;
  createTenant: (input: NuevoTenantInput) => Tenant;
  setEstado: (tenantId: string, estado: Tenant['estado']) => void;
  setLimiteUsuarios: (tenantId: string, limite: number) => void;
  setModulosActivos: (tenantId: string, modulos: ModuloPlataforma[]) => void;
  updateDatosBasicos: (tenantId: string, datos: { giro: string; direccion: string }) => void;
  updateLogo: (tenantId: string, logoUrl: string) => void;
  addPlant: (tenantId: string, input: { nombre: string; comuna: string; region: string }) => void;
  completarPerfilEmpresa: (tenantId: string) => void;
}

const TenantsContext = createContext<TenantsContextValue | null>(null);

/**
 * Tres campos de empresa no tienen columna propia y viven en `settings`, el
 * jsonb del tenant: el límite de usuarios, los módulos activos y el logo.
 *
 * Antes se leían de valores fijos escritos aquí (`limiteUsuarios: 50`,
 * `modulosActivos: []`), así que **cambiarlos desde la pantalla no sobrevivía a
 * recargar** aunque la escritura hubiera funcionado. Leer y escribir tienen que
 * apuntar al mismo lugar; hacer solo uno de los dos lados cambia un engaño por
 * otro.
 */
const LIMITE_USUARIOS_POR_DEFECTO = 50;

/** Clave de `settings` donde esta pantalla guarda lo suyo. */
function ajustesDe(raw: Record<string, unknown>): Record<string, unknown> {
  const s = raw.settings;
  return s && typeof s === 'object' && !Array.isArray(s) ? (s as Record<string, unknown>) : {};
}

function mapApiTenant(raw: Record<string, unknown>): Tenant | null {
  try {
    const ajustes = ajustesDe(raw);
    return {
      id: String(raw.id),
      nombre: String(raw.legal_name ?? raw.trade_name ?? ''),
      identificacion: { tipo: 'RUT', numero: String(raw.rut_tax_id ?? '') },
      pais: 'CL' as Pais,
      sector: String(raw.business_activity ?? ''),
      giro: raw.business_activity ? String(raw.business_activity) : undefined,
      direccion: undefined,
      estado: raw.status === 'active' ? 'activo' : raw.status === 'suspended' ? 'suspendido' : 'activo',
      perfilEmpresaCompleto: Boolean(raw.business_activity && raw.rut_tax_id),
      esGestor: raw.tenant_type === 'manager',
      logoUrl: ajustes.logoUrl ? String(ajustes.logoUrl) : undefined,
      suscripcion: {
        plan: 'contrato' as Plan,
        fechaInicio: String(raw.created_at ?? new Date().toISOString()),
        fechaTermino: new Date(Date.now() + 365 * 86400000).toISOString(),
        limiteUsuarios:
          typeof ajustes.limiteUsuarios === 'number' ? ajustes.limiteUsuarios : LIMITE_USUARIOS_POR_DEFECTO,
      },
      modulosActivos: Array.isArray(ajustes.modulosActivos)
        ? (ajustes.modulosActivos as ModuloPlataforma[])
        : [],
      certificaciones: [],
      plants: [],
    };
  } catch {
    return null;
  }
}

/**
 * Instalacion de la API. `comuna` y `region` salen de los codigos que guarda
 * la base; si no estan, se dejan vacios en vez de inventar un lugar.
 */
function mapApiPlant(raw: Record<string, unknown>): Plant | null {
  try {
    return {
      id: String(raw.id),
      tenantId: String(raw.tenant_id ?? ''),
      nombre: String(raw.name ?? raw.code ?? ''),
      comuna: raw.commune_code ? String(raw.commune_code) : '',
      region: raw.region_code ? String(raw.region_code) : '',
    };
  } catch {
    return null;
  }
}

export function TenantsProvider({ children }: { children: ReactNode }) {
  const [tenants, setTenants] = useState<Tenant[]>(mockTenants);
  const [loading, setLoading] = useState(true);
  const registrar = useRegistrarAuditoria();
  const { mostrarToast } = useToast();

  useEffect(() => {
    let cancelled = false;
    // Las instalaciones se piden junto con la empresa y no aparte porque
    // `plants` venia siempre vacio, y **21 pantallas sacan de ahi su lista de
    // plantas**. Con la lista vacia esas pantallas caian a `mockTenants`, cuyos
    // identificadores son `planta-rancagua` mientras la API usa UUID: los datos
    // reales llegaban y no cruzaban con nada, asi que las pantallas se veian
    // vacias aunque la API respondiera bien.
    Promise.all([
      api.get<Record<string, unknown>[]>('/tenants/'),
      api.get<Record<string, unknown>[]>('/facilities/').catch(() => []),
    ])
      .then(([datosTenants, datosPlantas]) => {
        if (cancelled) return;
        const mapped = datosTenants.map(mapApiTenant).filter((t): t is Tenant => t !== null);
        if (mapped.length === 0) return;

        const plantasPorTenant = new Map<string, Plant[]>();
        for (const cruda of datosPlantas) {
          const planta = mapApiPlant(cruda);
          if (!planta) continue;
          const lista = plantasPorTenant.get(planta.tenantId) ?? [];
          lista.push(planta);
          plantasPorTenant.set(planta.tenantId, lista);
        }

        setTenants(
          mapped.map((t) => ({ ...t, plants: plantasPorTenant.get(t.id) ?? [] })),
        );
      })
      .catch(() => {
        // Fallback a mocks si la API no responde
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  function createTenant(input: NuevoTenantInput): Tenant {
    const ahora = new Date();
    const termino = new Date(ahora);
    termino.setDate(termino.getDate() + input.diasVigencia);

    const nuevo: Tenant = {
      id: `tenant-${Date.now()}`,
      nombre: input.nombre,
      identificacion: { tipo: documentoDePais(input.pais), numero: input.numeroIdentificacion },
      pais: input.pais,
      sector: input.sector,
      giro: input.giro,
      direccion: input.direccion,
      sitioWeb: input.sitioWeb,
      numeroTrabajadores: input.numeroTrabajadores,
      certificaciones: input.certificaciones,
      contactoComercial: input.contactoComercial,
      notasComerciales: input.notasComerciales,
      esGestor: input.esGestor,
      estado: 'activo',
      perfilEmpresaCompleto: false,
      suscripcion: {
        plan: input.plan,
        fechaInicio: ahora.toISOString(),
        fechaTermino: termino.toISOString(),
        limiteUsuarios: input.limiteUsuarios,
      },
      modulosActivos: input.modulosActivos,
      plants: [],
    };

    setTenants((prev) => [...prev, nuevo]);

    api.post('/tenants/', {
      legal_name: input.nombre,
      rut_tax_id: input.numeroIdentificacion,
      tenant_type: input.esGestor ? 'manager' : 'company',
      business_activity: input.sector,
      country_id: 1,
    }).catch(() => {});

    registrar({
      entidadTipo: 'tenant',
      entidadId: nuevo.id,
      entidadLabel: nuevo.nombre,
      tenantId: null,
      accion: 'creado',
      resumen: input.plan === 'demo' ? 'Dio de alta una demo' : 'Dio de alta la empresa',
      cambios: [
        { campo: 'País', antes: null, despues: nombreDePais(input.pais) },
        { campo: documentoDePais(input.pais), antes: null, despues: input.numeroIdentificacion },
        { campo: 'Plan', antes: null, despues: input.plan === 'demo' ? `Demo (${input.diasVigencia} días)` : 'Contrato' },
        { campo: 'Límite de usuarios', antes: null, despues: String(input.limiteUsuarios) },
        { campo: 'Módulos habilitados', antes: null, despues: String(input.modulosActivos.length) },
      ],
    });

    return nuevo;
  }

  function setEstado(tenantId: string, estado: Tenant['estado']) {
    const anterior = tenants.find((t) => t.id === tenantId);
    if (!anterior || anterior.estado === estado) return;

    setTenants((prev) => prev.map((t) => (t.id === tenantId ? { ...t, estado } : t)));

    api.patch(`/tenants/${tenantId}`, {
      status: estado === 'activo' ? 'active' : 'suspended',
    }).catch(() => {});

    registrar({
      entidadTipo: 'tenant',
      entidadId: tenantId,
      entidadLabel: anterior.nombre,
      tenantId: null,
      accion: estado === 'suspendido' ? 'suspendido' : 'reactivado',
      resumen: estado === 'suspendido' ? 'Suspendió la empresa' : 'Reactivó la empresa',
      cambios: [
        {
          campo: 'Estado de la cuenta',
          antes: anterior.estado === 'activo' ? 'Activa' : 'Suspendida',
          despues: estado === 'activo' ? 'Activa' : 'Suspendida',
        },
      ],
    });
  }

  /**
   * Guarda en `settings` **fusionando**, nunca reemplazando.
   *
   * `settings` es un jsonb compartido por varias pantallas. Mandar el objeto
   * entero desde una de ellas borraría las claves que escribieron las otras, y
   * el destrozo solo se vería al recargar otra pantalla.
   *
   * Se manda el estado que la interfaz ya tiene completo, no un fragmento: si
   * llegara a haber claves que este store no conoce, hay que traerlas del
   * registro antes de escribir.
   */
  function guardarAjustes(
    tenantId: string,
    parche: Record<string, unknown>,
    alFallar: () => void,
    queFallo: string,
  ) {
    const t = tenants.find((x) => x.id === tenantId);
    if (!t) return;

    const ajustes = {
      limiteUsuarios: t.suscripcion.limiteUsuarios,
      modulosActivos: t.modulosActivos,
      ...(t.logoUrl ? { logoUrl: t.logoUrl } : {}),
      ...parche,
    };

    api
      .patch(`/tenants/${tenantId}`, { settings: ajustes })
      .catch((error) => {
        alFallar();
        mostrarToast({
          tipo: 'error',
          mensaje: queFallo,
          descripcion: mensajeDeError(error),
        });
      });
  }

  function setLimiteUsuarios(tenantId: string, limite: number) {
    const anterior = tenants.find((t) => t.id === tenantId);
    if (!anterior || anterior.suscripcion.limiteUsuarios === limite) return;

    const previo = anterior.suscripcion.limiteUsuarios;
    setTenants((prev) =>
      prev.map((t) => (t.id === tenantId ? { ...t, suscripcion: { ...t.suscripcion, limiteUsuarios: limite } } : t)),
    );

    guardarAjustes(
      tenantId,
      { limiteUsuarios: limite },
      () =>
        setTenants((prev) =>
          prev.map((t) =>
            t.id === tenantId ? { ...t, suscripcion: { ...t.suscripcion, limiteUsuarios: previo } } : t,
          ),
        ),
      'No se pudo cambiar el límite de usuarios',
    );

    registrar({
      entidadTipo: 'tenant',
      entidadId: tenantId,
      entidadLabel: anterior.nombre,
      tenantId: null,
      accion: 'actualizado',
      resumen: 'Cambió el límite de usuarios contratado',
      cambios: [
        { campo: 'Límite de usuarios', antes: String(anterior.suscripcion.limiteUsuarios), despues: String(limite) },
      ],
    });
  }

  function updateLogo(tenantId: string, logoUrl: string) {
    const anterior = tenants.find((t) => t.id === tenantId);
    if (!anterior || anterior.logoUrl === logoUrl) return;

    const previo = anterior.logoUrl;
    setTenants((prev) => prev.map((t) => (t.id === tenantId ? { ...t, logoUrl } : t)));

    guardarAjustes(
      tenantId,
      { logoUrl },
      () => setTenants((prev) => prev.map((t) => (t.id === tenantId ? { ...t, logoUrl: previo } : t))),
      'No se pudo guardar el logo',
    );

    registrar({
      entidadTipo: 'tenant',
      entidadId: tenantId,
      entidadLabel: anterior.nombre,
      tenantId,
      accion: 'actualizado',
      resumen: anterior.logoUrl ? 'Cambió el logo de la empresa' : 'Cargó el logo de la empresa',
      cambios: [{ campo: 'Logo', antes: anterior.logoUrl ?? null, despues: logoUrl }],
    });
  }

  function setModulosActivos(tenantId: string, modulos: ModuloPlataforma[]) {
    const anterior = tenants.find((t) => t.id === tenantId);
    if (!anterior) return;

    const antes = new Set(anterior.modulosActivos);
    const despues = new Set(modulos);
    const activados = modulos.filter((m) => !antes.has(m));
    const desactivados = anterior.modulosActivos.filter((m) => !despues.has(m));
    if (activados.length === 0 && desactivados.length === 0) return;

    const previos = anterior.modulosActivos;
    setTenants((prev) => prev.map((t) => (t.id === tenantId ? { ...t, modulosActivos: modulos } : t)));

    guardarAjustes(
      tenantId,
      { modulosActivos: modulos },
      () => setTenants((prev) => prev.map((t) => (t.id === tenantId ? { ...t, modulosActivos: previos } : t))),
      'No se pudieron guardar los módulos',
    );

    const cambios = [
      ...(activados.length > 0
        ? [{ campo: 'Módulos activados', antes: null, despues: activados.map((m) => MODULO_LABEL[m]).join(', ') }]
        : []),
      ...(desactivados.length > 0
        ? [{ campo: 'Módulos desactivados', antes: desactivados.map((m) => MODULO_LABEL[m]).join(', '), despues: null }]
        : []),
    ];

    registrar({
      entidadTipo: 'tenant',
      entidadId: tenantId,
      entidadLabel: anterior.nombre,
      tenantId: null,
      accion: 'actualizado',
      resumen: 'Cambió los módulos habilitados',
      cambios,
    });
  }

  function updateDatosBasicos(tenantId: string, datos: { giro: string; direccion: string }) {
    const anterior = tenants.find((t) => t.id === tenantId);
    if (!anterior) return;

    setTenants((prev) => prev.map((t) => (t.id === tenantId ? { ...t, ...datos } : t)));

    api.patch(`/tenants/${tenantId}`, {
      business_activity: datos.giro,
    }).catch(() => {});

    const cambios = [
      ...(anterior.giro !== datos.giro ? [{ campo: 'Giro', antes: anterior.giro ?? null, despues: datos.giro }] : []),
      ...(anterior.direccion !== datos.direccion
        ? [{ campo: 'Dirección', antes: anterior.direccion ?? null, despues: datos.direccion }]
        : []),
    ];
    if (cambios.length === 0) return;

    registrar({
      entidadTipo: 'tenant',
      entidadId: tenantId,
      entidadLabel: anterior.nombre,
      tenantId,
      accion: 'actualizado',
      resumen: 'Actualizó los datos de la empresa',
      cambios,
    });
  }

  function addPlant(tenantId: string, input: { nombre: string; comuna: string; region: string }) {
    const tenant = tenants.find((t) => t.id === tenantId);
    if (!tenant) return;

    const plant: Plant = { id: `planta-${Date.now()}`, tenantId, ...input };
    setTenants((prev) => prev.map((t) => (t.id === tenantId ? { ...t, plants: [...t.plants, plant] } : t)));

    api.post('/facilities/', {
      code: `PLT-${Date.now()}`,
      name: input.nombre,
      facility_type: 'plant',
      region_code: input.region,
      commune_code: input.comuna,
    }, { tenantId }).catch(() => {});

    registrar({
      entidadTipo: 'planta',
      entidadId: plant.id,
      entidadLabel: plant.nombre,
      tenantId,
      accion: 'creado',
      resumen: `Agregó la planta ${plant.nombre}`,
      cambios: [{ campo: 'Ubicación', antes: null, despues: `${input.comuna}, ${input.region}` }],
    });
  }

  /**
   * **No llega a la base, y el motivo es de fondo.**
   *
   * El Perfil Empresa se considera completo cuando la empresa tiene giro y RUT
   * (ver el mapper: `Boolean(raw.business_activity && raw.rut_tax_id)`). No es
   * una bandera guardada, es una condicion derivada.
   *
   * `TenantUpdate` acepta `business_activity` pero **no acepta `rut_tax_id`**,
   * asi que la API no permite completar lo que esta pantalla ofrece marcar como
   * completo. Requiere decidir si el RUT se vuelve editable o si el perfil se
   * completa por otro camino.
   */
  function completarPerfilEmpresa(tenantId: string) {
    const tenant = tenants.find((t) => t.id === tenantId);
    if (!tenant || tenant.perfilEmpresaCompleto) return;

    setTenants((prev) => prev.map((t) => (t.id === tenantId ? { ...t, perfilEmpresaCompleto: true } : t)));

    registrar({
      entidadTipo: 'tenant',
      entidadId: tenantId,
      entidadLabel: tenant.nombre,
      tenantId,
      accion: 'actualizado',
      resumen: 'Completó el Perfil Empresa',
      cambios: [{ campo: 'Perfil Empresa', antes: 'Incompleto', despues: 'Completo' }],
    });
  }

  return (
    <TenantsContext.Provider
      value={{
        tenants,
        loading,
        createTenant,
        setEstado,
        setLimiteUsuarios,
        setModulosActivos,
        updateDatosBasicos,
        updateLogo,
        addPlant,
        completarPerfilEmpresa,
      }}
    >
      {children}
    </TenantsContext.Provider>
  );
}

export function useTenants() {
  const ctx = useContext(TenantsContext);
  if (!ctx) throw new Error('useTenants debe usarse dentro de <TenantsProvider>');
  return ctx;
}
