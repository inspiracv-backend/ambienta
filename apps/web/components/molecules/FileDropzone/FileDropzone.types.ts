export interface FileDropzoneProps {
  id: string;
  maxFiles?: number;
  files: File[];
  onChange: (files: File[]) => void;
  error?: string;
}
