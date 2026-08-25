'use client';

import { useId, useState, type FormEvent } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { Button, Input } from '@/components/atoms';
import { FormField, FileDropzone } from '@/components/molecules';
import { useSession } from '@/lib/session';
import { useSupportTickets } from '@/lib/support-tickets-store';
import {
  abrirSolicitud,
  categoriaDesdeTipo,
  empresaDelEnlace,
  leerToken,
} from '@/lib/acceso-invitado';

const TIPOS_SOLICITUD = [
  { value: 'declaracion', label: 'Consulta sobre una declaración' },
  { value: 'evidencia', label: 'Carga de evidencia' },
  { value: 'general', label: 'Otra solicitud' },
] as const;

interface FormState {
  tipo: string;
  asunto: string;
  descripcion: string;
  nombreContacto: string;
  correoContacto: string;
}

const EMPTY_STATE: FormState = { tipo: '', asunto: '', descripcion: '', nombreContacto: '', correoContacto: '' };

/**
 * S-03 Crear Ticket/Solicitud. Accesible sin cuenta (link público) o tras
 * login RUT+clave — si ya hay sesión de Cliente Invitado, se omiten los
 * campos de nombre/correo de contacto (H6: no pedir de nuevo lo que ya se sabe).
 * Persiste en SupportTicketsProvider (elevado a app/layout.tsx) para que el
 * ticket aparezca en Soporte/Tickets internos (Sección L, S-38).
 *
 * **Hay dos caminos, y solo uno llega a la base todavía.**
 *
 * Con sesión de Cliente Invitado el ticket se abre contra la API, ligado a su
 * credencial (`guest_credential_id`). Ese vínculo es lo que después le permite
 * volver a encontrarlo y lo que impide que otro lo vea: filtrar por el correo
 * no serviría, porque el correo lo escribe la misma persona en este formulario.
 *
 * Sin esa sesión —un usuario con cuenta— sigue el camino simulado del
 * provider. Conectarlo es otra tarea: `POST /support/tickets` existe, pero
 * requiere resolver el autor desde la sesión de Clerk.
 */
export function TicketForm() {
  const { user } = useSession();
  const { createTicket } = useSupportTickets();
  const isAuthenticated = !!user;
  const formId = useId();

  const [values, setValues] = useState<FormState>(EMPTY_STATE);
  const [files, setFiles] = useState<File[]>([]);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [ticketNumber, setTicketNumber] = useState<string | null>(null);

  function validate(): boolean {
    const next: Partial<Record<keyof FormState, string>> = {};
    if (!values.tipo) next.tipo = 'Selecciona el tipo de solicitud.';
    if (!values.asunto.trim()) next.asunto = 'El asunto es obligatorio.';
    if (!values.descripcion.trim()) next.descripcion = 'Describe brevemente tu solicitud.';
    if (!isAuthenticated && !values.nombreContacto.trim()) next.nombreContacto = 'Indica tu nombre.';
    if (!isAuthenticated && !/^\S+@\S+\.\S+$/.test(values.correoContacto)) {
      next.correoContacto = 'Ingresa un correo válido.';
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    setIsSubmitting(true);

    const empresaId = empresaDelEnlace();
    const esInvitado = !!leerToken() && !!empresaId;

    if (esInvitado) {
      abrirSolicitud(empresaId!, {
        subject: values.asunto.trim(),
        description: values.descripcion.trim(),
        category: categoriaDesdeTipo(values.tipo),
        guest_name: values.nombreContacto.trim() || null,
        guest_email: values.correoContacto.trim() || null,
      })
        // **El número viene de la base, no se inventa acá.** La secuencia es
        // global, así que calcularlo en el navegador daría números repetidos
        // entre empresas.
        .then((solicitud) => setTicketNumber(solicitud.ticket_number))
        .catch((e) =>
          setErrors({
            descripcion:
              e instanceof Error ? e.message : 'No se pudo enviar la solicitud.',
          }),
        )
        .finally(() => setIsSubmitting(false));
      return;
    }

    setTimeout(() => {
      const ticket = createTicket({
        tenantId: user?.tenantId ?? null,
        tipoSolicitud: values.tipo,
        asunto: values.asunto.trim(),
        descripcion: values.descripcion.trim(),
        contactoNombre: isAuthenticated ? user!.nombre : values.nombreContacto.trim(),
        contactoEmail: isAuthenticated ? user!.email : values.correoContacto.trim(),
      });
      setIsSubmitting(false);
      setTicketNumber(ticket.numero);
    }, 500);
  }

  if (ticketNumber) {
    return (
      <div className="flex w-full max-w-md flex-col items-center gap-3 rounded-card border border-slate-200 bg-white p-8 text-center shadow-sm">
        <CheckCircle2 className="h-10 w-10 text-semaforo-cumple" aria-hidden />
        <h2 className="text-lg font-semibold text-slate-900">Solicitud enviada</h2>
        <p className="text-sm text-slate-500">
          Tu número de ticket es <span className="font-medium text-slate-800">{ticketNumber}</span>. Te contactaremos a la brevedad.
        </p>
        <Button variant="secondary" onClick={() => { setValues(EMPTY_STATE); setFiles([]); setTicketNumber(null); }}>
          Volver
        </Button>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md rounded-card border border-slate-200 bg-white p-8 shadow-sm">
      <h1 className="text-xl font-semibold text-slate-900">Crear ticket / solicitud</h1>
      <p className="mt-1 text-sm text-slate-500">Cuéntanos qué necesitas y te contactaremos a la brevedad.</p>

      <form className="mt-6 flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
        <FormField label="Tipo de solicitud" htmlFor={`${formId}-tipo`} required error={errors.tipo}>
          <select
            id={`${formId}-tipo`}
            className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm"
            value={values.tipo}
            onChange={(e) => setValues((v) => ({ ...v, tipo: e.target.value }))}
          >
            <option value="">Selecciona una opción</option>
            {TIPOS_SOLICITUD.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </FormField>

        <FormField label="Asunto" htmlFor={`${formId}-asunto`} required error={errors.asunto}>
          <Input
            id={`${formId}-asunto`}
            value={values.asunto}
            invalid={!!errors.asunto}
            onChange={(e) => setValues((v) => ({ ...v, asunto: e.target.value }))}
          />
        </FormField>

        <FormField label="Descripción" htmlFor={`${formId}-descripcion`} required error={errors.descripcion}>
          <textarea
            id={`${formId}-descripcion`}
            rows={4}
            className="w-full rounded-lg border border-slate-300 p-3 text-sm"
            value={values.descripcion}
            onChange={(e) => setValues((v) => ({ ...v, descripcion: e.target.value }))}
          />
        </FormField>

        <FormField label="Adjuntos" htmlFor={`${formId}-adjuntos`}>
          <FileDropzone id={`${formId}-adjuntos`} files={files} onChange={setFiles} maxFiles={3} />
        </FormField>

        {!isAuthenticated && (
          <>
            <FormField label="Nombre de contacto" htmlFor={`${formId}-nombre`} required error={errors.nombreContacto}>
              <Input
                id={`${formId}-nombre`}
                value={values.nombreContacto}
                invalid={!!errors.nombreContacto}
                onChange={(e) => setValues((v) => ({ ...v, nombreContacto: e.target.value }))}
              />
            </FormField>
            <FormField label="Correo de contacto" htmlFor={`${formId}-correo`} required error={errors.correoContacto}>
              <Input
                id={`${formId}-correo`}
                type="email"
                value={values.correoContacto}
                invalid={!!errors.correoContacto}
                onChange={(e) => setValues((v) => ({ ...v, correoContacto: e.target.value }))}
              />
            </FormField>
          </>
        )}

        <Button type="submit" isLoading={isSubmitting} className="mt-2 w-full">
          Enviar solicitud
        </Button>
      </form>
    </div>
  );
}
