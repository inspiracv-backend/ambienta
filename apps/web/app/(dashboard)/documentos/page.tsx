'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, FilePlus2, RefreshCw } from 'lucide-react';
import { Button, Spinner } from '@/components/atoms';
import {
  CrearDocumentoModal,
  DocumentosLista,
  RevisionesPanel,
} from '@/components/organisms';
import { DocumentosProvider, useDocumentos } from '@/lib/documentos-store';

/**
 * S-34 — Control de información documentada (RF-102 a RF-106, ISO 9001 §7.5).
 *
 * ## Qué resuelve esta pantalla que no resolvía nada
 *
 * El modelo documental existía desde el 27-ago —códigos, revisiones,
 * aprobación firmada, obsolescencia que conserva— y el puente hacia Backblaze
 * también. **Nada de eso era visible**: no había pantalla de documentos, ni
 * botón de subir, ni forma de ver si una revisión regía. Una funcionalidad que
 * no está en la pantalla, para quien usa el sistema, no está.
 *
 * ## Lista a la izquierda, revisiones a la derecha
 *
 * Y no una lista que navega a una página de detalle. El trabajo real acá es
 * comparar: "¿cuál de estos procedimientos está vigente?", "¿este ya lo
 * aprobaron?". Ir y volver entre páginas para responder eso pierde el contexto
 * en cada salto.
 */
function Contenido() {
  const { documentos, cargando, error, recargar, revisionesDe, cargarRevisiones, cargandoRevisiones } =
    useDocumentos();
  const [seleccionado, setSeleccionado] = useState<string | null>(null);
  const [creando, setCreando] = useState(false);

  // El primero, cuando llega la lista. Un panel derecho vacío al entrar hace
  // creer que hay que hacer algo antes de ver nada.
  useEffect(() => {
    if (!seleccionado && documentos.length > 0) {
      setSeleccionado(documentos[0].id);
    }
  }, [documentos, seleccionado]);

  useEffect(() => {
    if (seleccionado && revisionesDe(seleccionado) === undefined) {
      void cargarRevisiones(seleccionado);
    }
  }, [seleccionado, revisionesDe, cargarRevisiones]);

  if (cargando) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Cargando documentos" />
      </div>
    );
  }

  const documento = documentos.find((d) => d.id === seleccionado) ?? null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Documentos</h1>
          <p className="text-sm text-slate-500">
            Información documentada controlada: código, revisiones y vigencia. Sólo la
            revisión vigente sirve como evidencia ante una fiscalización.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={recargar}
            icon={<RefreshCw className="h-4 w-4" aria-hidden />}
          >
            Actualizar
          </Button>
          <Button
            onClick={() => setCreando(true)}
            icon={<FilePlus2 className="h-4 w-4" aria-hidden />}
          >
            Nuevo documento
          </Button>
        </div>
      </div>

      {error && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-card bg-semaforo-no-cumple-bg px-4 py-3 text-sm text-semaforo-no-cumple"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>
            No se pudieron cargar los documentos: {error}
            <br />
            <span className="text-slate-600">
              La lista se muestra vacía en vez de con datos de ejemplo: en un módulo
              documental, un respaldo inventado es peor que ninguno.
            </span>
          </span>
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
        <DocumentosLista
          documentos={documentos}
          seleccionadoId={seleccionado}
          onSeleccionar={setSeleccionado}
        />

        <div className="rounded-card border border-slate-200 bg-slate-50/50 p-4">
          {documento ? (
            <RevisionesPanel
              documento={documento}
              revisiones={revisionesDe(documento.id)}
              cargando={cargandoRevisiones === documento.id}
            />
          ) : (
            <p className="py-10 text-center text-sm text-slate-500">
              Selecciona un documento para ver sus revisiones.
            </p>
          )}
        </div>
      </div>

      <CrearDocumentoModal
        open={creando}
        onOpenChange={setCreando}
        onCreado={setSeleccionado}
      />
    </div>
  );
}

export default function DocumentosPage() {
  return (
    <DocumentosProvider>
      <Contenido />
    </DocumentosProvider>
  );
}
