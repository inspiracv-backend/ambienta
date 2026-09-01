'use client';

import { Handshake, RefreshCw } from 'lucide-react';
import { Button, Spinner } from '@/components/atoms';
import { EmptyState, PageHeader } from '@/components/molecules';
import { PipelineKanban } from '@/components/organisms';
import { useCrmPipeline } from '@/lib/crm-store';

/**
 * El pipeline comercial (#81, épica #32).
 *
 * ## Qué muestra
 *
 * Las etapas de la empresa como columnas, sus oportunidades como tarjetas, y
 * en cada cabecera **cuántas hay y cuánto suman por moneda**. Los dos números
 * vienen calculados del servidor: las columnas llegan cortadas en un tope, así
 * que contar o sumar lo visible daría menos que lo real sin que nada lo diga.
 *
 * ## Por qué no hay datos de ejemplo
 *
 * Un pipeline vacío es una respuesta legítima —una empresa que recién parte no
 * tiene oportunidades— y taparlo con ejemplos haría creer que hay negocio donde
 * no lo hay. Es la lección de #208, y en un módulo comercial es la más cara de
 * todas.
 *
 * ## Ámbito
 *
 * Va en el menú de empresa y no en el de plataforma. `crm_companies` lleva
 * `tenant_id`: el CRM de una consultora ambiental son **sus** prospectos, no
 * los clientes de Ambienta.
 */
export default function CrmPage() {
  const { pipeline, cargando, error, mover, recargar } = useCrmPipeline();

  const sinEtapas = !cargando && pipeline.columnas.length === 0;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        titulo="Pipeline comercial"
        descripcion="Las oportunidades de la empresa por etapa. Arrastra una tarjeta, o usa «Mover a» en cada una."
        acciones={
          <Button
            variant="secondary"
            icon={<RefreshCw className="h-4 w-4" aria-hidden />}
            onClick={() => void recargar()}
            disabled={cargando}
          >
            Actualizar
          </Button>
        }
      />

      {error && (
        <p className="rounded-card border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </p>
      )}

      {cargando ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : sinEtapas ? (
        <EmptyState
          icono={Handshake}
          titulo={error ? 'No se pudo cargar el pipeline' : 'Todavía no hay pipeline'}
          descripcion={
            error
              ? 'El tablero se deja vacío a propósito: mostrar las tarjetas anteriores se leería como el estado actual del negocio.'
              : 'Toda empresa nace con seis etapas por defecto. Si no ves ninguna, es que se retiraron todas: crea al menos una para poder registrar oportunidades.'
          }
        />
      ) : (
        <PipelineKanban pipeline={pipeline} onMover={mover} />
      )}
    </div>
  );
}
