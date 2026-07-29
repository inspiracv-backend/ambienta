'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
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
 * Gestión de Tenants (RF-81, Sección L) — Superadmin solo administra los
 * campos de plataforma (estado/límites/módulos), nunca contenido de negocio
 * del tenant (CLAUDE.md). Los mutadores de Perfil Empresa (RF-10 a RF-12,
 * v1.7: datos básicos, plantas, completar) son del Admin Empresa —
 * conviven en el mismo store porque ambos mutan la misma entidad Tenant.
 *
 * Todas las mutaciones quedan en el audit log (RF-32, RNF-08). Las de
 * plataforma se registran con `tenantId: null` porque son actos del
 * Superadmin *sobre* una empresa, no actividad *dentro* de ella: mezclarlas
 * con el historial del tenant confundiría a quien audita a la empresa.
 */
export function TenantsProvider({ children }: { children: ReactNode }) {
  const [tenants, setTenants] = useState<Tenant[]>(mockTenants);
  const registrar = useRegistrarAuditoria();

  /**
   * Alta de una empresa (RF-82). No existía: los tenants solo podían nacer
   * como mocks, así que no había forma de incorporar un cliente nuevo ni de
   * dar una demo.
   *
   * El tenant nace con `perfilEmpresaCompleto: false` a propósito: el
   * Superadmin registra la empresa y su contrato, pero plantas, departamentos
   * y trabajadores los declara el Admin Empresa en su flujo obligatorio
   * (RF-10 a RF-12). Que el Superadmin los cargue por él contradiría
   * CLAUDE.md — "Admin Global NO puede editar contenido de tenants".
   */
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
      // El logo aparece en los informes impresos, así que cambiarlo altera
      // documentos que salen de la empresa: es un hecho auditable.
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

    // Se listan los módulos por nombre y no solo el total: "de 9 a 8 módulos"
    // no le sirve a quien audita, necesita saber cuál se apagó.
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
