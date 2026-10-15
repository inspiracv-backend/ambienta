'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { ChatbotPanel } from '@/components/organisms';
import type { Responder } from '@/components/organisms/ChatbotPanel/ChatbotPanel.types';
import { consultarAlAsistente } from '@/lib/chatbot';
import { useSession } from '@/lib/session';
import { mockLegalNorms } from '@/mocks/catalog';
import { mockPrivilegedQA, type ChatbotQA } from '@/mocks/chatbot';

const TENANT_EXAMPLES = ['¿Cuándo vence SIDREP?', '¿Cómo vamos con la Ley REP?', '¿Qué exige la RCA de Rancagua?'];
const PRIVILEGED_EXAMPLES = ['¿Cuántos tenants hay?', '¿Cuántos gestores hay?'];

const SIN_COINCIDENCIA =
  'No encontré información específica para tu pregunta. Intenta reformularla usando otros términos (por ejemplo, el nombre de una norma o de un sistema de declaración).';

/**
 * El asistente de verdad, a través de la API (RF-59 a RF-63).
 *
 * El navegador **no habla con el AI Service**: manda la pregunta a la API, que
 * autoriza con el token de quien pregunta y reenvía. Así ese servicio no se
 * publica a internet y RLS sigue siendo la barrera entre empresas.
 */
function responderConElAsistente(tenantId: string | null): Responder {
  return async ({ pregunta, conversacionId }) => {
    const r = await consultarAlAsistente({
      pregunta,
      conversacionId,
      tenantId: tenantId ?? undefined,
    });
    return {
      texto: r.respuesta,
      conversacionId: r.conversation_id,
      seAbstuvo: r.se_abstuvo,
      citas: r.citas,
    };
  };
}

/**
 * Datos de ejemplo por palabra clave, para la pantalla privilegiada.
 *
 * **Sigue en mocks a propósito.** Lo que se pregunta acá son métricas de la
 * plataforma —cuántas empresas hay, cuántos gestores— y la base de
 * conocimiento del AI Service es normativa y datos de una empresa. Enchufarla
 * al asistente real no daría respuestas: daría una abstención detrás de otra,
 * porque la cuenta global vive en la empresa `platform`, que no tiene matriz
 * legal ni obligaciones. Queda pendiente del lado del AI Service.
 */
function responderConEjemplos(qaBase: ChatbotQA[]): Responder {
  return async ({ pregunta }) => {
    const texto = pregunta.toLowerCase();
    const coincidencia = qaBase.find((qa) => qa.keywords.some((k) => texto.includes(k)));
    const norma = coincidencia?.citaNormId
      ? mockLegalNorms.find((n) => n.id === coincidencia.citaNormId)
      : undefined;

    return {
      texto: coincidencia?.respuesta ?? SIN_COINCIDENCIA,
      // Sin coincidencia **es** una abstención: no se encontró con qué responder.
      seAbstuvo: !coincidencia,
      citas: norma
        ? [
            {
              norma: norma.nombre,
              articulo: null,
              texto: '',
              ruta: '',
              norm_id: norma.id,
              article_id: null,
              norm_version_id: null,
              official_url: null,
              origen: 'catalogo' as const,
            },
          ]
        : [],
    };
  };
}

const responderPrivilegiado = responderConEjemplos(mockPrivilegedQA);

/** S-34/S-35 Chatbot IA — mismo organismo, distinto quién contesta (RF-52/RF-53). */
export default function ChatbotPage() {
  const router = useRouter();
  const { user, cargando } = useSession();

  useEffect(() => {
    if (!cargando && user === null) router.replace('/login');
  }, [cargando, user, router]);

  if (!user) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Cargando sesión" />
      </div>
    );
  }

  const isPrivileged = user.role === 'superadmin';
  // La empresa va en la llamada porque **sin Clerk no hay token**: la cabecera
  // es lo unico que dice de que empresa se pregunta. Con Clerk la API la
  // ignora y lee el token, asi que mandarla de mas no cambia nada.
  const responder = isPrivileged ? responderPrivilegiado : responderConElAsistente(user.tenantId);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-slate-900">Chatbot</h1>
      <ChatbotPanel
        responder={responder}
        privileged={isPrivileged}
        examplePrompts={isPrivileged ? PRIVILEGED_EXAMPLES : TENANT_EXAMPLES}
      />
    </div>
  );
}
