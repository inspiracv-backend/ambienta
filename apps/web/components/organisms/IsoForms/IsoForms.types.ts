export interface OpcionIso {
  value: string;
  label: string;
}

export interface CampoIso {
  /** El nombre **de la API**, no uno propio: se manda tal cual en el cuerpo. */
  nombre: string;
  etiqueta: string;
  tipo: 'texto' | 'textarea' | 'select' | 'numero' | 'fecha';
  opciones?: OpcionIso[];
  requerido?: boolean;
  ayuda?: string;
  min?: number;
  max?: number;
}

export interface FormularioIsoProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  titulo: string;
  descripcion?: string;
  campos: CampoIso[];
  /** Los valores actuales al editar. Ausente = alta. */
  valores?: Record<string, unknown> | null;
  /** Devuelve `true` si se guardó: el formulario sólo cierra entonces. */
  onGuardar: (datos: Record<string, unknown>) => Promise<boolean>;
}

/** Confirmación de borrado. */
export interface ConfirmarBorradoProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  queSeBorra: string;
  advertencia?: string;
  onConfirmar: () => Promise<boolean>;
}
