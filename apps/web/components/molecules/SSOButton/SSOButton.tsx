import { Button } from '@/components/atoms';
import type { SSOButtonProps } from './SSOButton.types';

const PROVIDER_LABEL: Record<SSOButtonProps['provider'], string> = {
  microsoft: 'Continuar con Microsoft',
  google: 'Continuar con Google',
};

/** S-01: Microsoft es prioridad (variant primary), Google es secundario. */
export function SSOButton({ provider, onClick, isLoading }: SSOButtonProps) {
  return (
    <Button
      type="button"
      variant={provider === 'microsoft' ? 'primary' : 'secondary'}
      size="lg"
      className="w-full"
      onClick={onClick}
      isLoading={isLoading}
    >
      {PROVIDER_LABEL[provider]}
    </Button>
  );
}
