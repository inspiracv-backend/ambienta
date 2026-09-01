'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { Documento, RevisionDocumental } from '@ambienta/shared';
import { mensajeDeError } from '@/lib/api-client';
import {
  crearDocumento,
  listarDocumentos,
  listarRevisiones,
  moverRevision,
  subirArchivo,
  urlDeDescarga,
  type AccionDocumental,
  type PasoDeSubida,
} from '@/lib/documentos';
import { useSession } from '@/lib/session';
import { useToast } from '@/lib/toast-store';

/**
 * Documentos y revisiones (RF-102 a RF-106).
 *
 * ## No hay datos de ejemplo, y es deliberado
 *
 * Nueve stores de esta aplicación caían a `mocks/` cuando la API respondía
 * cero, y eso produjo el peor error posible de esta serie: pantallas que
 * mostraban datos inventados como si fueran de la empresa. Acá **cero
 * documentos se ve como cero documentos**.
 *
 * En un módulo documental el daño de un respaldo falso es todavía mayor: una
 * persona que ve "Procedimiento de manejo de residuos · Vigente" en la lista
 * asume que existe y que puede mostrarlo en una fiscalización.
 *
 * ## Las revisiones se cargan por documento, cuando se abre
 *
 * No se traen todas de entrada: son N+1 llamadas para una pantalla en la que
 * casi siempre se mira un documento a la vez. Se cachean por id para que
 * cerrar y volver a abrir no repita la consulta.
 */

interface EstadoDeSubida {
  documentoId: string;
  paso: PasoDeSubida;
  nombreArchivo: string;
}

interface DocumentosContextValue {
  documentos: Documento[];
  cargando: boolean;
  error: string | null;
  recargar: () => void;

  revisionesDe: (documentoId: string) => RevisionDocumental[] | undefined;
  cargarRevisiones: (documentoId: string) => Promise<void>;
  cargandoRevisiones: string | null;

  crear: (input: { titulo: string; tipo: string }) => Promise<Documento | null>;
  subir: (documentoId: string, archivo: File) => Promise<boolean>;
  subiendo: EstadoDeSubida | null;
  mover: (
    documentoId: string,
    revisionId: string,
    accion: AccionDocumental,
    cuerpo?: { motivo?: string },
  ) => Promise<boolean>;
  descargar: (documentoId: string, revisionId: string) => Promise<void>;
}

const DocumentosContext = createContext<DocumentosContextValue | null>(null);

export function DocumentosProvider({ children }: { children: ReactNode }) {
  const { user, cargando: cargandoSesion } = useSession();
  const { mostrarToast } = useToast();
  const tenantId = user?.tenantId ?? null;

  const [documentos, setDocumentos] = useState<Documento[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reintento, setReintento] = useState(0);
  const [revisiones, setRevisiones] = useState<Record<string, RevisionDocumental[]>>({});
  const [cargandoRevisiones, setCargandoRevisiones] = useState<string | null>(null);
  const [subiendo, setSubiendo] = useState<EstadoDeSubida | null>(null);

  useEffect(() => {
    if (!tenantId) {
      if (!cargandoSesion) setCargando(false);
      return;
    }
    let vigente = true;
    setCargando(true);
    setError(null);

    listarDocumentos(tenantId)
      .then((d) => {
        if (vigente) setDocumentos(d);
      })
      .catch((e: unknown) => {
        if (vigente) setError(mensajeDeError(e));
      })
      .finally(() => {
        if (vigente) setCargando(false);
      });

    return () => {
      vigente = false;
    };
  }, [tenantId, cargandoSesion, reintento]);

  const recargar = useCallback(() => setReintento((n) => n + 1), []);

  const cargarRevisiones = useCallback(
    async (documentoId: string) => {
      if (!tenantId) return;
      setCargandoRevisiones(documentoId);
      try {
        const filas = await listarRevisiones(documentoId, tenantId);
        setRevisiones((prev) => ({ ...prev, [documentoId]: filas }));
      } catch (e: unknown) {
        mostrarToast({ tipo: 'error', mensaje: mensajeDeError(e) });
      } finally {
        setCargandoRevisiones(null);
      }
    },
    [tenantId, mostrarToast],
  );

  const revisionesDe = useCallback(
    (documentoId: string) => revisiones[documentoId],
    [revisiones],
  );

  const crear = useCallback(
    async (input: { titulo: string; tipo: string }) => {
      if (!tenantId) return null;
      try {
        const doc = await crearDocumento(input, tenantId);
        setDocumentos((prev) => [doc, ...prev]);
        mostrarToast({ tipo: 'exito', mensaje: `Documento "${doc.titulo}" creado.` });
        return doc;
      } catch (e: unknown) {
        mostrarToast({ tipo: 'error', mensaje: mensajeDeError(e) });
        return null;
      }
    },
    [tenantId, mostrarToast],
  );

  const subir = useCallback(
    async (documentoId: string, archivo: File) => {
      if (!tenantId) return false;
      try {
        const revision = await subirArchivo(documentoId, archivo, tenantId, (paso) =>
          setSubiendo({ documentoId, paso, nombreArchivo: archivo.name }),
        );
        setRevisiones((prev) => ({
          ...prev,
          [documentoId]: [revision, ...(prev[documentoId] ?? [])],
        }));
        mostrarToast({
          tipo: 'exito',
          mensaje: `Revisión ${revision.numero} subida`,
          descripcion: archivo.name,
        });
        return true;
      } catch (e: unknown) {
        // `subirArchivo` lanza un `Error` normal cuando el que rechaza es el
        // bucket, y un `ApiError` cuando es la nuestra. `mensajeDeError`
        // devuelve un texto genérico para lo primero, así que se prefiere el
        // mensaje propio cuando existe: el del bucket explica qué revisar.
        const mensaje =
          e instanceof Error && !('status' in e) ? e.message : mensajeDeError(e);
        mostrarToast({ tipo: 'error', mensaje });
        return false;
      } finally {
        setSubiendo(null);
      }
    },
    [tenantId, mostrarToast],
  );

  const mover = useCallback(
    async (
      documentoId: string,
      revisionId: string,
      accion: AccionDocumental,
      cuerpo?: { motivo?: string },
    ) => {
      if (!tenantId) return false;
      try {
        await moverRevision(documentoId, revisionId, accion, tenantId, cuerpo);
        // Se recargan **todas** las revisiones del documento y no solo la que
        // cambió: publicar una deja obsoleta a la anterior en el mismo paso, y
        // parchear en memoria solo la tocada dejaría a la otra mintiendo en
        // pantalla hasta que alguien recargue.
        await cargarRevisiones(documentoId);
        // Y el documento, porque su estado y su revisión vigente cambian con
        // esto.
        setReintento((n) => n + 1);
        mostrarToast({ tipo: 'exito', mensaje: 'Revisión actualizada.' });
        return true;
      } catch (e: unknown) {
        mostrarToast({ tipo: 'error', mensaje: mensajeDeError(e) });
        return false;
      }
    },
    [tenantId, mostrarToast, cargarRevisiones],
  );

  const descargar = useCallback(
    async (documentoId: string, revisionId: string) => {
      if (!tenantId) return;
      try {
        const url = await urlDeDescarga(documentoId, revisionId, tenantId);
        // Se abre en otra pestaña en vez de navegar: el enlace firmado vence en
        // minutos, y reemplazar la pantalla actual por él dejaría a la persona
        // sin dónde volver si el archivo ya expiró.
        window.open(url, '_blank', 'noopener,noreferrer');
      } catch (e: unknown) {
        mostrarToast({ tipo: 'error', mensaje: mensajeDeError(e) });
      }
    },
    [tenantId, mostrarToast],
  );

  const value = useMemo<DocumentosContextValue>(
    () => ({
      documentos,
      cargando,
      error,
      recargar,
      revisionesDe,
      cargarRevisiones,
      cargandoRevisiones,
      crear,
      subir,
      subiendo,
      mover,
      descargar,
    }),
    [
      documentos,
      cargando,
      error,
      recargar,
      revisionesDe,
      cargarRevisiones,
      cargandoRevisiones,
      crear,
      subir,
      subiendo,
      mover,
      descargar,
    ],
  );

  return (
    <DocumentosContext.Provider value={value}>{children}</DocumentosContext.Provider>
  );
}

export function useDocumentos(): DocumentosContextValue {
  const ctx = useContext(DocumentosContext);
  if (!ctx) {
    throw new Error('useDocumentos debe usarse dentro de <DocumentosProvider>');
  }
  return ctx;
}
