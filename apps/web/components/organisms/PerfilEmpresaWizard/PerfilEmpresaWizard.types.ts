import type { Departamento, Tenant, User } from '@ambienta/shared';

export interface PerfilEmpresaWizardProps {
  tenant: Tenant;
  departamentos: Departamento[];
  usuarios: User[];
  onUpdateDatosBasicos: (datos: { giro: string; direccion: string }) => void;
  onAddPlant: (input: { nombre: string; comuna: string; region: string }) => void;
  onAddDepartamento: (nombre: string) => void;
  onCompletar: () => void;
}
