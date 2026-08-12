export interface FilterOption {
  value: string;
  label: string;
}

export interface FilterBarProps {
  filters: {
    id: string;
    label: string;
    value: string;
    onChange: (value: string) => void;
    options: FilterOption[];
  }[];
}
