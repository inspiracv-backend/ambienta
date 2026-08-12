import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { SSOButtonProps } from './SSOButton.types';

const PROVIDER_LABEL: Record<SSOButtonProps['provider'], string> = {
  microsoft: 'Continuar con Microsoft',
  google: 'Continuar con Google',
};

/** Logos oficiales de cada proveedor, inline para no depender de assets externos. */
function MicrosoftIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-[18px] w-[18px]" aria-hidden>
      <path fill="#F25022" d="M1 1h8.5v8.5H1z" />
      <path fill="#7FBA00" d="M10.5 1H19v8.5h-8.5z" />
      <path fill="#00A4EF" d="M1 10.5h8.5V19H1z" />
      <path fill="#FFB900" d="M10.5 10.5H19V19h-8.5z" />
    </svg>
  );
}

function GoogleIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-[18px] w-[18px]" aria-hidden>
      <path
        fill="#4285F4"
        d="M19.6 10.23c0-.68-.06-1.34-.18-1.96H10v3.72h5.38a4.6 4.6 0 0 1-2 3.02v2.5h3.24c1.89-1.74 2.98-4.3 2.98-7.28Z"
      />
      <path
        fill="#34A853"
        d="M10 20c2.7 0 4.96-.9 6.62-2.43l-3.24-2.51c-.9.6-2.04.96-3.38.96-2.6 0-4.8-1.76-5.59-4.12H1.07v2.59A10 10 0 0 0 10 20Z"
      />
      <path fill="#FBBC05" d="M4.41 11.9a5.99 5.99 0 0 1 0-3.82V5.49H1.07a10 10 0 0 0 0 8.98l3.34-2.58Z" />
      <path
        fill="#EA4335"
        d="M10 3.96c1.47 0 2.79.51 3.83 1.5l2.87-2.87C14.96.99 12.7 0 10 0A10 10 0 0 0 1.07 5.49l3.34 2.59C5.2 5.72 7.4 3.96 10 3.96Z"
      />
    </svg>
  );
}

/**
 * S-01 / RF-05: Microsoft Entra ID es el proveedor prioritario y Google el
 * secundario.
 *
 * Ambos botones son ahora visualmente equivalentes (borde neutro sobre
 * blanco). Antes Microsoft usaba `variant="primary"`, o sea verde corporativo
 * sólido: eso lo hacía leer como "el botón de acción principal de la app" en
 * vez de "iniciar sesión con mi cuenta Microsoft", que es la convención que
 * la gente reconoce de otros productos. La prioridad se comunica con el orden
 * y la etiqueta "Recomendado", no con el color.
 */
export function SSOButton({ provider, onClick, isLoading, recomendado, disabled }: SSOButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || isLoading}
      aria-busy={isLoading}
      className={cn(
        'flex h-12 w-full items-center gap-3 rounded-lg border border-slate-300 bg-white px-4',
        'text-sm font-medium text-slate-700 transition',
        'hover:border-slate-400 hover:bg-slate-50',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2',
        'disabled:cursor-not-allowed disabled:opacity-60',
      )}
    >
      <span className="flex h-5 w-5 shrink-0 items-center justify-center">
        {isLoading ? (
          <Loader2 className="h-[18px] w-[18px] animate-spin text-slate-400" aria-hidden />
        ) : provider === 'microsoft' ? (
          <MicrosoftIcon />
        ) : (
          <GoogleIcon />
        )}
      </span>

      <span className="flex-1 text-left">{PROVIDER_LABEL[provider]}</span>

      {recomendado && !isLoading && (
        <span className="shrink-0 rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-semibold text-brand-700">
          Recomendado
        </span>
      )}
    </button>
  );
}
