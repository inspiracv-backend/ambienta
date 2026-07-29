import type { Departamento, Tenant, TipoProceso, User } from '@ambienta/shared';

export interface PerfilEmpresaWizardProps {
  tenant: Tenant;
  departamentos: Departamento[];
  usuarios: User[];
  onUpdateDatosBasicos: (datos: { giro: string; direccion: string }) => void;
  /** El logo se usa en los reportes impresos, por eso vive en el Perfil Empresa. */
  onUpdateLogo: (logoUrl: string) => void;
  onAddPlant: (input: { nombre: string; comuna: string; region: string }) => void;
  onAddDepartamento: (input: { nombre: string; tipo: TipoProceso; descripcion?: string }) => void;
  onCompletar: () => void;
}
