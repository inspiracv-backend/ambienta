import { PlatformDashboard } from '@/components/organisms';

/**
 * Dashboard consolidado del Superadmin. Vive en una ruta propia y no en
 * /dashboard porque son dos pantallas distintas para dos ámbitos distintos:
 * /dashboard filtra por `tenantId` y el Superadmin no pertenece a ninguno.
 * En su menú aparece igualmente como "Dashboard", que es lo que significa
 * para él.
 */
export default function PlataformaPage() {
  return <PlatformDashboard />;
}
