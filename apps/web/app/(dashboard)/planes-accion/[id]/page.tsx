'use client';

import { notFound } from 'next/navigation';
import { Breadcrumbs } from '@/components/molecules';
import { PlanAccionDetailView } from '@/components/organisms';
import { usePlanAccion } from '@/lib/plan-accion-store';

export default function PlanAccionDetailPage({ params }: { params: { id: string } }) {
  const { plans } = usePlanAccion();
  const plan = plans.find((p) => p.id === params.id);

  if (!plan) return notFound();

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Plan de Acción', href: undefined }, { label: plan.titulo }]} />
      <PlanAccionDetailView plan={plan} />
    </div>
  );
}
