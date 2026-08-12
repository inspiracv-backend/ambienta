'use client';

import { useId, useState, type FormEvent } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Building2, Info, X } from 'lucide-react';
import {
  CERTIFICACIONES,
  DIAS_DEMO_POR_DEFECTO,
  MODULOS_PLATAFORMA,
  PAISES,
  documentoDePais,
  type Certificacion,
  type ModuloPlataforma,
  type Pais,
  type Plan,
} from '@ambienta/shared';
import { Button, Input, Textarea } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { useTenants } from '@/lib/tenants-store';
import { useUsers } from '@/lib/users-store';
import { useToast } from '@/lib/toast-store';
import { useRegistrarAuditoria } from '@/lib/audit-log-store';
import { eventoUsuarioInvitado } from '@/lib/user-audit';
import { MODULO_LABEL } from '@/lib/tenant-status';
import { cn } from '@/lib/utils';

const SECTORES = [
  'Industrial',
  'Minería',
  'Agroindustria',
  'Alimentos y bebidas',
  'Gestión de residuos',
  'Energía',
  'Construcción',
  'Forestal',
  'Acuicultura',
  'Otro',
];

/** Duración de un contrato anual. La demo usa `DIAS_DEMO_POR_DEFECTO`. */
const DIAS_CONTRATO_ANUAL = 365;

/**
 * Alta de una empresa cliente (RF-82).
 *
 * No existía forma de crear un tenant: solo podían nacer como mocks. Este
 * formulario cubre lo que el equipo señaló que faltaba — país, información
 * del cliente para el CRM, plan de demo, y la creación del usuario
 * administrador — más el contexto que ISO 9001 §4.1 considera relevante para
 * entender a la organización.
 *
 * **Qué se pide y qué no.** Se piden los datos que determinan cómo opera el
 * sistema para ese cliente:
 * - *País* → define el documento tributario (RF-87) y, a futuro, la normativa
 *   aplicable.
 * - *Sector y nº de trabajadores* → hay umbrales normativos por tamaño y
 *   actividad; es lo que decide qué obligaciones le aplican.
 * - *Certificaciones* → determinan qué se le audita: una empresa con ISO
 *   14001 tiene un programa distinto al de una que solo cumple ley.
 *
 * Deliberadamente **no** se piden plantas ni departamentos: eso es Perfil
 * Empresa y lo declara el Admin Empresa (RF-10 a RF-12). Que el Superadmin
 * los cargue contradiría CLAUDE.md.
 */
export function NuevoTenantModal({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const formId = useId();
  const { createTenant } = useTenants();
  const { inviteUser } = useUsers();
  const { mostrarToast } = useToast();
  const registrar = useRegistrarAuditoria();

  // Identificación
  const [nombre, setNombre] = useState('');
  const [pais, setPais] = useState<Pais>('CL');
  const [numeroIdentificacion, setNumeroIdentificacion] = useState('');
  const [sector, setSector] = useState(SECTORES[0]!);
  const [giro, setGiro] = useState('');
  const [direccion, setDireccion] = useState('');
  const [sitioWeb, setSitioWeb] = useState('');

  // Contexto (ISO 9001 §4.1)
  const [numeroTrabajadores, setNumeroTrabajadores] = useState('');
  const [certificaciones, setCertificaciones] = useState<Certificacion[]>([]);

  // Comercial
  const [contactoNombre, setContactoNombre] = useState('');
  const [contactoCargo, setContactoCargo] = useState('');
  const [contactoEmail, setContactoEmail] = useState('');
  const [contactoTelefono, setContactoTelefono] = useState('');
  const [notasComerciales, setNotasComerciales] = useState('');

  // Suscripción
  const [plan, setPlan] = useState<Plan>('demo');
  const [diasVigencia, setDiasVigencia] = useState(String(DIAS_DEMO_POR_DEFECTO));
  const [limiteUsuarios, setLimiteUsuarios] = useState('3');
  const [esGestor, setEsGestor] = useState(false);
  const [modulos, setModulos] = useState<ModuloPlataforma[]>(['matriz-legal', 'obligaciones', 'calendario']);

  // Administrador inicial
  const [adminNombre, setAdminNombre] = useState('');
  const [adminEmail, setAdminEmail] = useState('');

  const [errors, setErrors] = useState<Record<string, string>>({});

  function cambiarPlan(nuevo: Plan) {
    setPlan(nuevo);
    // La vigencia se ajusta al plan para no dejar una demo de 365 días por
    // olvido, pero sigue siendo editable.
    setDiasVigencia(String(nuevo === 'demo' ? DIAS_DEMO_POR_DEFECTO : DIAS_CONTRATO_ANUAL));
    if (nuevo === 'demo') setLimiteUsuarios('3');
  }

  function toggleCertificacion(codigo: Certificacion) {
    setCertificaciones((prev) => (prev.includes(codigo) ? prev.filter((c) => c !== codigo) : [...prev, codigo]));
  }

  function toggleModulo(modulo: ModuloPlataforma) {
    setModulos((prev) => (prev.includes(modulo) ? prev.filter((m) => m !== modulo) : [...prev, modulo]));
  }

  function resetForm() {
    setNombre('');
    setPais('CL');
    setNumeroIdentificacion('');
    setSector(SECTORES[0]!);
    setGiro('');
    setDireccion('');
    setSitioWeb('');
    setNumeroTrabajadores('');
    setCertificaciones([]);
    setContactoNombre('');
    setContactoCargo('');
    setContactoEmail('');
    setContactoTelefono('');
    setNotasComerciales('');
    setPlan('demo');
    setDiasVigencia(String(DIAS_DEMO_POR_DEFECTO));
    setLimiteUsuarios('3');
    setEsGestor(false);
    setModulos(['matriz-legal', 'obligaciones', 'calendario']);
    setAdminNombre('');
    setAdminEmail('');
    setErrors({});
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const next: Record<string, string> = {};

    if (!nombre.trim()) next.nombre = 'Ingresa la razón social.';
    if (!numeroIdentificacion.trim()) next.identificacion = `Ingresa el ${documentoDePais(pais)}.`;
    if (!adminNombre.trim()) next.adminNombre = 'Ingresa el nombre del administrador.';
    if (!/^\S+@\S+\.\S+$/.test(adminEmail)) next.adminEmail = 'Ingresa un correo válido.';
    if (Number(diasVigencia) <= 0) next.diasVigencia = 'La vigencia debe ser mayor a 0 días.';
    if (Number(limiteUsuarios) <= 0) next.limiteUsuarios = 'El límite debe ser al menos 1.';
    if (modulos.length === 0) next.modulos = 'Habilita al menos un módulo.';

    setErrors(next);
    if (Object.keys(next).length > 0) return;

    const tenant = createTenant({
      nombre: nombre.trim(),
      pais,
      numeroIdentificacion: numeroIdentificacion.trim(),
      sector,
      giro: giro.trim() || undefined,
      direccion: direccion.trim() || undefined,
      sitioWeb: sitioWeb.trim() || undefined,
      numeroTrabajadores: numeroTrabajadores ? Number(numeroTrabajadores) : undefined,
      certificaciones,
      contactoComercial: contactoNombre.trim()
        ? {
            nombre: contactoNombre.trim(),
            cargo: contactoCargo.trim(),
            email: contactoEmail.trim(),
            telefono: contactoTelefono.trim(),
          }
        : undefined,
      notasComerciales: notasComerciales.trim() || undefined,
      esGestor,
      plan,
      diasVigencia: Number(diasVigencia),
      limiteUsuarios: Number(limiteUsuarios),
      modulosActivos: modulos,
    });

    // El administrador se crea junto con la empresa: un tenant sin nadie que
    // pueda entrar no sirve de nada, y era el paso que faltaba para poder
    // entregar una demo.
    const admin = inviteUser({
      tenantId: tenant.id,
      nombre: adminNombre.trim(),
      email: adminEmail.trim(),
      role: 'admin_empresa',
      plantIds: [],
      departamentoId: null,
    });
    registrar(eventoUsuarioInvitado(admin));

    mostrarToast({
      tipo: 'exito',
      mensaje: `${tenant.nombre} dada de alta`,
      descripcion: `${plan === 'demo' ? `Demo de ${diasVigencia} días` : 'Contrato'} · ${adminNombre.trim()} quedó como administrador.`,
    });

    resetForm();
    onOpenChange(false);
  }

  const etiquetaDocumento = documentoDePais(pais);

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) resetForm();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[92vh] w-full max-w-2xl -translate-x-1/2 -translate-y-1/2 flex-col rounded-card bg-white shadow-lg">
          <div className="flex items-start justify-between border-b border-slate-200 p-6">
            <div className="flex items-center gap-2">
              <Building2 className="h-5 w-5 text-brand-600" aria-hidden />
              <div>
                <Dialog.Title className="text-lg font-semibold text-slate-900">Dar de alta una empresa</Dialog.Title>
                <Dialog.Description className="mt-0.5 text-xs text-slate-500">
                  Las plantas y los departamentos los declara después el administrador en su Perfil Empresa.
                </Dialog.Description>
              </div>
            </div>
            <Dialog.Close aria-label="Cerrar" className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" aria-hidden />
            </Dialog.Close>
          </div>

          <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
            <div className="flex-1 overflow-y-auto p-6">
              <div className="flex flex-col gap-6">
                {/* ── Identificación ─────────────────────────────────── */}
                <section className="flex flex-col gap-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Identificación</h3>

                  <FormField label="Razón social" htmlFor={`${formId}-nombre`} error={errors.nombre} required>
                    <Input
                      id={`${formId}-nombre`}
                      value={nombre}
                      invalid={!!errors.nombre}
                      onChange={(e) => setNombre(e.target.value)}
                      placeholder="Ej: Recicladora del Sur SpA"
                    />
                  </FormField>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <FormField label="País" htmlFor={`${formId}-pais`} required>
                      <select
                        id={`${formId}-pais`}
                        className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                        value={pais}
                        onChange={(e) => setPais(e.target.value as Pais)}
                      >
                        {PAISES.map((p) => (
                          <option key={p.codigo} value={p.codigo}>
                            {p.nombre}
                          </option>
                        ))}
                      </select>
                    </FormField>

                    <FormField
                      label={etiquetaDocumento}
                      htmlFor={`${formId}-doc`}
                      error={errors.identificacion}
                      hint="Cambia según el país seleccionado"
                      required
                    >
                      <Input
                        id={`${formId}-doc`}
                        value={numeroIdentificacion}
                        invalid={!!errors.identificacion}
                        onChange={(e) => setNumeroIdentificacion(e.target.value)}
                      />
                    </FormField>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <FormField label="Sector" htmlFor={`${formId}-sector`} required>
                      <select
                        id={`${formId}-sector`}
                        className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                        value={sector}
                        onChange={(e) => setSector(e.target.value)}
                      >
                        {SECTORES.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </FormField>

                    <FormField
                      label="N.º de trabajadores"
                      htmlFor={`${formId}-trabajadores`}
                      hint="Hay obligaciones con umbral por tamaño"
                    >
                      <Input
                        id={`${formId}-trabajadores`}
                        type="number"
                        min={0}
                        value={numeroTrabajadores}
                        onChange={(e) => setNumeroTrabajadores(e.target.value)}
                      />
                    </FormField>
                  </div>

                  <FormField label="Giro" htmlFor={`${formId}-giro`}>
                    <Input id={`${formId}-giro`} value={giro} onChange={(e) => setGiro(e.target.value)} />
                  </FormField>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <FormField label="Dirección" htmlFor={`${formId}-direccion`}>
                      <Input id={`${formId}-direccion`} value={direccion} onChange={(e) => setDireccion(e.target.value)} />
                    </FormField>
                    <FormField label="Sitio web" htmlFor={`${formId}-web`}>
                      <Input id={`${formId}-web`} value={sitioWeb} onChange={(e) => setSitioWeb(e.target.value)} placeholder="https://" />
                    </FormField>
                  </div>
                </section>

                {/* ── Contexto ISO ───────────────────────────────────── */}
                <section className="flex flex-col gap-2 border-t border-slate-100 pt-5">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Sistemas de gestión certificados
                  </h3>
                  <p className="text-xs text-slate-500">
                    Determina qué se le audita. Una empresa certificada tiene un programa de auditoría distinto al de
                    una que solo cumple normativa legal.
                  </p>
                  <div className="mt-1 grid gap-2 sm:grid-cols-2">
                    {CERTIFICACIONES.map((c) => (
                      <label
                        key={c.codigo}
                        className={cn(
                          'flex cursor-pointer items-start gap-2 rounded-lg border p-2.5 text-sm transition',
                          certificaciones.includes(c.codigo)
                            ? 'border-brand-400 bg-brand-50'
                            : 'border-slate-200 hover:border-slate-300',
                        )}
                      >
                        <input
                          type="checkbox"
                          className="mt-0.5"
                          checked={certificaciones.includes(c.codigo)}
                          onChange={() => toggleCertificacion(c.codigo)}
                        />
                        <span>
                          <span className="font-medium text-slate-800">{c.nombre}</span>
                          <span className="block text-xs text-slate-500">{c.descripcion}</span>
                        </span>
                      </label>
                    ))}
                  </div>
                </section>

                {/* ── Contacto comercial ─────────────────────────────── */}
                <section className="flex flex-col gap-3 border-t border-slate-100 pt-5">
                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Contacto comercial</h3>
                    <p className="mt-0.5 text-xs text-slate-500">
                      Quien firma el contrato. No siempre es quien usa el sistema, por eso va aparte del administrador.
                    </p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <FormField label="Nombre" htmlFor={`${formId}-cc-nombre`}>
                      <Input id={`${formId}-cc-nombre`} value={contactoNombre} onChange={(e) => setContactoNombre(e.target.value)} />
                    </FormField>
                    <FormField label="Cargo" htmlFor={`${formId}-cc-cargo`}>
                      <Input id={`${formId}-cc-cargo`} value={contactoCargo} onChange={(e) => setContactoCargo(e.target.value)} />
                    </FormField>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <FormField label="Email" htmlFor={`${formId}-cc-email`}>
                      <Input id={`${formId}-cc-email`} type="email" value={contactoEmail} onChange={(e) => setContactoEmail(e.target.value)} />
                    </FormField>
                    <FormField label="Teléfono" htmlFor={`${formId}-cc-tel`} hint="Incluye el prefijo del país">
                      <Input id={`${formId}-cc-tel`} value={contactoTelefono} onChange={(e) => setContactoTelefono(e.target.value)} placeholder="+56 9 ..." />
                    </FormField>
                  </div>
                  <FormField label="Notas comerciales" htmlFor={`${formId}-notas`}>
                    <Textarea
                      id={`${formId}-notas`}
                      rows={2}
                      value={notasComerciales}
                      onChange={(e) => setNotasComerciales(e.target.value)}
                      placeholder="Cómo llegó, qué le interesa, condiciones acordadas…"
                    />
                  </FormField>
                </section>

                {/* ── Suscripción ────────────────────────────────────── */}
                <section className="flex flex-col gap-3 border-t border-slate-100 pt-5">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Suscripción</h3>

                  <div className="grid gap-2 sm:grid-cols-2">
                    {(['demo', 'contrato'] as const).map((p) => (
                      <label
                        key={p}
                        className={cn(
                          'flex cursor-pointer items-start gap-2 rounded-lg border p-3 text-sm transition',
                          plan === p ? 'border-brand-400 bg-brand-50' : 'border-slate-200 hover:border-slate-300',
                        )}
                      >
                        <input type="radio" name={`${formId}-plan`} className="mt-1" checked={plan === p} onChange={() => cambiarPlan(p)} />
                        <span>
                          <span className="font-medium text-slate-800">{p === 'demo' ? 'Demo' : 'Contrato'}</span>
                          <span className="block text-xs text-slate-500">
                            {p === 'demo' ? `${DIAS_DEMO_POR_DEFECTO} días, usuarios limitados` : 'Vigencia anual renovable'}
                          </span>
                        </span>
                      </label>
                    ))}
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <FormField label="Días de vigencia" htmlFor={`${formId}-dias`} error={errors.diasVigencia} required>
                      <Input
                        id={`${formId}-dias`}
                        type="number"
                        min={1}
                        value={diasVigencia}
                        invalid={!!errors.diasVigencia}
                        onChange={(e) => setDiasVigencia(e.target.value)}
                      />
                    </FormField>
                    <FormField label="Límite de usuarios" htmlFor={`${formId}-limite`} error={errors.limiteUsuarios} required>
                      <Input
                        id={`${formId}-limite`}
                        type="number"
                        min={1}
                        value={limiteUsuarios}
                        invalid={!!errors.limiteUsuarios}
                        onChange={(e) => setLimiteUsuarios(e.target.value)}
                      />
                    </FormField>
                  </div>

                  <label className="flex cursor-pointer items-start gap-2 rounded-lg border border-slate-200 p-3 text-sm hover:border-slate-300">
                    <input type="checkbox" className="mt-1" checked={esGestor} onChange={(e) => setEsGestor(e.target.checked)} />
                    <span>
                      <span className="font-medium text-slate-800">Es un Gestor</span>
                      <span className="block text-xs text-slate-500">
                        Administra residuos o servicios de sus propios clientes (sub-tenants).
                      </span>
                    </span>
                  </label>

                  <div>
                    <p className="text-sm font-medium text-slate-700">
                      Módulos habilitados
                      {errors.modulos && <span className="ml-2 text-xs font-medium text-red-600">{errors.modulos}</span>}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {MODULOS_PLATAFORMA.map((m) => (
                        <button
                          key={m}
                          type="button"
                          onClick={() => toggleModulo(m)}
                          aria-pressed={modulos.includes(m)}
                          className={cn(
                            'rounded-full border px-2.5 py-1 text-xs font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
                            modulos.includes(m)
                              ? 'border-brand-400 bg-brand-50 text-brand-700'
                              : 'border-slate-200 text-slate-500 hover:border-slate-300',
                          )}
                        >
                          {MODULO_LABEL[m]}
                        </button>
                      ))}
                    </div>
                  </div>
                </section>

                {/* ── Administrador ──────────────────────────────────── */}
                <section className="flex flex-col gap-3 border-t border-slate-100 pt-5">
                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Usuario administrador</h3>
                    <p className="mt-0.5 flex items-start gap-1.5 text-xs text-slate-500">
                      <Info className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden />
                      Queda como Admin Empresa y será quien complete el Perfil Empresa. Sin él, nadie puede entrar.
                    </p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <FormField label="Nombre" htmlFor={`${formId}-admin-nombre`} error={errors.adminNombre} required>
                      <Input
                        id={`${formId}-admin-nombre`}
                        value={adminNombre}
                        invalid={!!errors.adminNombre}
                        onChange={(e) => setAdminNombre(e.target.value)}
                      />
                    </FormField>
                    <FormField label="Email" htmlFor={`${formId}-admin-email`} error={errors.adminEmail} required>
                      <Input
                        id={`${formId}-admin-email`}
                        type="email"
                        value={adminEmail}
                        invalid={!!errors.adminEmail}
                        onChange={(e) => setAdminEmail(e.target.value)}
                      />
                    </FormField>
                  </div>
                </section>
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t border-slate-200 p-4">
              <Dialog.Close asChild>
                <Button type="button" variant="secondary">
                  Cancelar
                </Button>
              </Dialog.Close>
              <Button type="submit">Dar de alta</Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
