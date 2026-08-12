'use client';

import { useState } from 'react';
import { Button } from '@/components/atoms';
import { useNotifications } from '@/lib/notifications-store';
import type { NotificationPreferencesFormProps } from './NotificationPreferencesForm.types';

const OPCIONES_ANTICIPACION = [30, 15, 7, 1];

/** S-32 Configuración de Notificaciones: toggles de canal y anticipación de recordatorios. */
export function NotificationPreferencesForm({ preferences }: NotificationPreferencesFormProps) {
  const { updatePreferences } = useNotifications();
  const [canalEmail, setCanalEmail] = useState(preferences.canalEmail);
  const [canalInApp, setCanalInApp] = useState(preferences.canalInApp);
  const [anticipacion, setAnticipacion] = useState<Set<number>>(new Set(preferences.anticipacionDias));
  const [saved, setSaved] = useState(false);

  function toggleAnticipacion(dias: number) {
    setAnticipacion((prev) => {
      const next = new Set(prev);
      if (next.has(dias)) next.delete(dias);
      else next.add(dias);
      return next;
    });
    setSaved(false);
  }

  function handleGuardar() {
    updatePreferences(preferences.userId, {
      canalEmail,
      canalInApp,
      anticipacionDias: Array.from(anticipacion).sort((a, b) => b - a),
    });
    setSaved(true);
  }

  return (
    <div className="flex max-w-md flex-col gap-6">
      <div className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Canales de notificación</h2>
        <div className="flex flex-col gap-3">
          <label className="flex items-center justify-between">
            <span className="text-sm text-slate-700">Correo electrónico</span>
            <input
              type="checkbox"
              checked={canalEmail}
              onChange={(e) => { setCanalEmail(e.target.checked); setSaved(false); }}
              className="h-5 w-5"
            />
          </label>
          <label className="flex items-center justify-between">
            <span className="text-sm text-slate-700">Dentro de la plataforma (in-app)</span>
            <input
              type="checkbox"
              checked={canalInApp}
              onChange={(e) => { setCanalInApp(e.target.checked); setSaved(false); }}
              className="h-5 w-5"
            />
          </label>
        </div>
      </div>

      <div className="rounded-card border border-slate-200 bg-white p-6">
        <h2 className="mb-1 text-sm font-semibold text-slate-700">Anticipación de recordatorios</h2>
        <p className="mb-3 text-xs text-slate-500">Recibe un recordatorio con estos días de anticipación al vencimiento.</p>
        <div className="flex flex-wrap gap-2">
          {OPCIONES_ANTICIPACION.map((dias) => (
            <button
              key={dias}
              type="button"
              onClick={() => toggleAnticipacion(dias)}
              aria-pressed={anticipacion.has(dias)}
              className={
                anticipacion.has(dias)
                  ? 'rounded-full border-2 border-brand-600 bg-brand-50 px-3 py-1.5 text-sm font-medium text-brand-700'
                  : 'rounded-full border border-slate-300 px-3 py-1.5 text-sm text-slate-600'
              }
            >
              {dias} {dias === 1 ? 'día' : 'días'}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button onClick={handleGuardar}>Guardar preferencias</Button>
        {saved && <span className="text-sm text-semaforo-cumple">Guardado.</span>}
      </div>
    </div>
  );
}
