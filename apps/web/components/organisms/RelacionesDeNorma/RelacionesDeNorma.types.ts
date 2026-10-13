export interface RelacionDeNorma {
  relation_type: string;
  /** `saliente` = esta norma se la hace a la otra; `entrante` = al revés. */
  sentido: 'saliente' | 'entrante';
  norm_id: string;
  norm_type: string | null;
  norm_number: string | null;
  title: string;
  publication_date: string | null;
}

export interface RelacionesDeNormaProps {
  normId: string;
  tenantId: string | null;
}
