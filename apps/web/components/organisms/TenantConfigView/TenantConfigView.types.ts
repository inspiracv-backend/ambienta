import type { Tenant } from '@ambienta/shared';

export interface TenantConfigViewProps {
  tenant: Tenant;
  /**
   * Cuántas personas tiene la empresa, o `null` si **no se puede saber** desde
   * esta sesión. Con Clerk, RLS acota `/users/` a la empresa de quien pregunta,
   * así que el Admin Global no puede contar las de otra. `null` no es cero.
   */
  userCount: number | null;
}
