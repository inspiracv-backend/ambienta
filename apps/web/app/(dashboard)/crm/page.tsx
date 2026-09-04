'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Building2, Handshake, RefreshCw, SlidersHorizontal } from 'lucide-react';
import { Button, Spinner } from '@/components/atoms';
import { buttonVariants } from '@/components/atoms/Button/Button';
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
  const { pipeline, cargando, errorDeCarga, mover, recargar } = useCrmPipeline();
  const router = useRouter();

  const sinEtapas = !cargando && pipeline.columnas.length === 0;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        titulo="Pipeline comercial"
        descripcion="Las oportunidades de la empresa por etapa. Arrastra una tarjeta, o usa «Mover a» en cada una."
        acciones={
          <div className="flex gap-2">
            {/* Las oportunidades del tablero nacen en una ficha de empresa: sin
                este paso el kanban solo se puede mirar. */}
            <Link href="/crm/empresas" className={buttonVariants({ variant: 'secondary' })}>
              <Building2 className="h-4 w-4" aria-hidden />
              Empresas
            </Link>
            <Link href="/crm/etapas" className={buttonVariants({ variant: 'secondary' })}>
              <SlidersHorizontal className="h-4 w-4" aria-hidden />
              Etapas
            </Link>
            <Button
              variant="secondary"
              icon={<RefreshCw className="h-4 w-4" aria-hidden />}
              onClick={() => void recargar()}
              disabled={cargando}
            >
              Actualizar
            </Button>
          </div>
        }
      />

      {errorDeCarga && (
        <p className="rounded-card border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {errorDeCarga}
        </p>
      )}

      {cargando ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : sinEtapas ? (
        <EmptyState
          icono={Handshake}
          titulo={errorDeCarga ? 'No se pudo cargar el pipeline' : 'Todavía no hay pipeline'}
          descripcion={
            errorDeCarga
              ? 'El tablero se deja vacío a propósito: mostrar las tarjetas anteriores se leería como el estado actual del negocio.'
              : 'Toda empresa nace con seis etapas por defecto. Si no ves ninguna, es que se retiraron todas: crea al menos una para poder registrar oportunidades.'
          }
        />
      ) : (
        <PipelineKanban
          pipeline={pipeline}
          onMover={mover}
          /* La tarjeta lleva a la ficha de SU empresa, no a un detalle del
             trato: lo que hace falta para seguir la venta —el teléfono, lo
             último que se habló, las otras oportunidades— vive ahí. El prop
             existía desde que se escribió el tablero y nadie lo pasaba, así que
             el título no era clicable. */
          onAbrirTrato={(trato) => router.push(`/crm/empresas/${trato.empresaId}`)}
        />
      )}
    </div>
  );
}
