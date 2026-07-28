'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { ModuloPlataforma, Plant, Tenant } from '@ambienta/shared';
import { mockTenants } from '@/mocks/tenants';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { MODULO_LABEL } from '@/lib/tenant-status';

interface TenantsContextValue {
  tenants: Tenant[];
  setEstado: (tenantId: string, estado: Tenant['estado']) => void;
  setLimiteUsuarios: (tenantId: string, limite: number) => void;
  setModulosActivos: (tenantId: string, modulos: ModuloPlataforma[]) => void;
  updateDatosBasicos: (tenantId: string, datos: { giro: string; direccion: string }) => void;
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
    if (!anterior || anterior.limiteUsuarios === limite) return;

    setTenants((prev) => prev.map((t) => (t.id === tenantId ? { ...t, limiteUsuarios: limite } : t)));

    registrar({
      entidadTipo: 'tenant',
      entidadId: tenantId,
      entidadLabel: anterior.nombre,
      tenantId: null,
      accion: 'actualizado',
      resumen: 'Cambió el límite de usuarios contratado',
      cambios: [{ campo: 'Límite de usuarios', antes: String(anterior.limiteUsuarios), despues: String(limite) }],
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
      value={{ tenants, setEstado, setLimiteUsuarios, setModulosActivos, updateDatosBasicos, addPlant, completarPerfilEmpresa }}
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
