import type { ReactNode } from 'react';
import { AuthLayout } from '@/components/templates';

export default function AuthRouteLayout({ children }: { children: ReactNode }) {
  return <AuthLayout>{children}</AuthLayout>;
}
