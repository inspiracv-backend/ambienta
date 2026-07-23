export interface SSOButtonProps {
  provider: 'microsoft' | 'google';
  onClick: () => void;
  isLoading?: boolean;
}
