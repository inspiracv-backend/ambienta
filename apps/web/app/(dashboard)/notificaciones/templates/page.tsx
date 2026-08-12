'use client';

import { Breadcrumbs } from '@/components/molecules';
import { ExcelTemplatesList } from '@/components/organisms';
import { mockExcelTemplates } from '@/mocks/templates';

/** S-33 Super-repositorio de Templates Excel. */
export default function TemplatesPage() {
  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs items={[{ label: 'Notificaciones', href: '/notificaciones' }, { label: 'Templates Excel' }]} />
      <h1 className="text-2xl font-semibold text-slate-900">Super-repositorio de templates Excel</h1>
      <ExcelTemplatesList templates={mockExcelTemplates} />
    </div>
  );
}
