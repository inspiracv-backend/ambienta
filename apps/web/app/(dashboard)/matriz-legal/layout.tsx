import type { ReactNode } from 'react';
import { LegalMatrixProvider } from '@/lib/legal-matrix-store';

export default function MatrizLegalLayout({ children }: { children: ReactNode }) {
  return <LegalMatrixProvider>{children}</LegalMatrixProvider>;
}
