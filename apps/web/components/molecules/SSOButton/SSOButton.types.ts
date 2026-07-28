export interface SSOButtonProps {
  provider: 'microsoft' | 'google';
  onClick: () => void;
  isLoading?: boolean;
  /** Marca visualmente el proveedor prioritario (RF-05: Microsoft Entra ID). */
  recomendado?: boolean;
  disabled?: boolean;
}
