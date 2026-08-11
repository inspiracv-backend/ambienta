'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/atoms';
import { ChatbotPanel } from '@/components/organisms';
import { useSession } from '@/lib/session';
import { mockChatbotQA, mockPrivilegedQA } from '@/mocks/chatbot';

const TENANT_EXAMPLES = ['¿Cuándo vence SIDREP?', '¿Cómo vamos con la Ley REP?', '¿Qué exige la RCA de Rancagua?'];
const PRIVILEGED_EXAMPLES = ['¿Cuántos tenants hay?', '¿Cuántos gestores hay?'];

/** S-34/S-35 Chatbot IA — mismo organismo, distinta base de conocimiento según rol (RF-52/RF-53). */
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

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-slate-900">Chatbot</h1>
      <ChatbotPanel
        qaBase={isPrivileged ? mockPrivilegedQA : mockChatbotQA}
        privileged={isPrivileged}
        examplePrompts={isPrivileged ? PRIVILEGED_EXAMPLES : TENANT_EXAMPLES}
      />
    </div>
  );
}
