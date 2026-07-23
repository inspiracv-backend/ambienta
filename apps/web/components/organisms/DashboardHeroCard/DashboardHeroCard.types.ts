import type { Obligation } from '@ambienta/shared';

export interface DashboardHeroCardProps {
  obligation: Obligation | null;
  cumplimientoPct: number;
}
