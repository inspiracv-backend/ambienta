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
import { api } from '@/lib/api-client';

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

function mapApiTenant(raw: Record<string, unknown>): Tenant | null {
  try {
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
      suscripcion: {
        plan: 'contrato' as Plan,
        fechaInicio: String(raw.created_at ?? new Date().toISOString()),
        fechaTermino: new Date(Date.now() + 365 * 86400000).toISOString(),
        limiteUsuarios: 50,
      },
      modulosActivos: [],
      certificaciones: [],
      plants: [],
    };
  } catch {
    return null;
  }
}

export function TenantsProvider({ children }: { children: ReactNode }) {
  const [tenants, setTenants] = useState<Tenant[]>(mockTenants);
  const [loading, setLoading] = useState(true);
  const registrar = useRegistrarAuditoria();

  useEffect(() => {
    let cancelled = false;
    api
      .get<Record<string, unknown>[]>('/tenants/')
      .then((data) => {
        if (cancelled) return;
        const mapped = data.map(mapApiTenant).filter((t): t is Tenant => t !== null);
        if (mapped.length > 0) setTenants(mapped);
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

  function setLimiteUsuarios(tenantId: string, limite: number) {
    const anterior = tenants.find((t) => t.id === tenantId);
    if (!anterior || anterior.suscripcion.limiteUsuarios === limite) return;

    setTenants((prev) =>
      prev.map((t) => (t.id === tenantId ? { ...t, suscripcion: { ...t.suscripcion, limiteUsuarios: limite } } : t)),
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

    setTenants((prev) => prev.map((t) => (t.id === tenantId ? { ...t, logoUrl } : t)));

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

    setTenants((prev) => prev.map((t) => (t.id === tenantId ? { ...t, modulosActivos: modulos } : t)));

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
