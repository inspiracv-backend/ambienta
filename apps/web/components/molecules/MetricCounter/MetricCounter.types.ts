import type { LucideIcon } from 'lucide-react';

export interface MetricCounterProps {
  label: string;
  value: number;
  icon: LucideIcon;
  tone?: 'neutral' | 'warning' | 'danger';
}
