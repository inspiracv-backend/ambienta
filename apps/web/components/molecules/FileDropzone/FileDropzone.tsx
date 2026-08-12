'use client';

import { useRef, useState, type DragEvent } from 'react';
import { UploadCloud, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { FileDropzoneProps } from './FileDropzone.types';

/** S-03: zona de adjuntos drag & drop, máx. 3 archivos (prevención de errores — H5). */
export function FileDropzone({ id, maxFiles = 3, files, onChange, error }: FileDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function addFiles(incoming: FileList | null) {
    if (!incoming) return;
    const next = [...files, ...Array.from(incoming)].slice(0, maxFiles);
    onChange(next);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
    addFiles(e.dataTransfer.files);
  }

  return (
    <div className="flex flex-col gap-2">
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={cn(
          'flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed p-6 text-center text-sm text-slate-500',
          isDragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300',
        )}
      >
        <UploadCloud className="h-6 w-6 text-brand-500" aria-hidden />
        <span>Arrastra archivos aquí o haz clic para seleccionar (máx. {maxFiles})</span>
        <input
          ref={inputRef}
          id={id}
          type="file"
          multiple
          className="sr-only"
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>
      {files.length > 0 && (
        <ul className="flex flex-col gap-1">
          {files.map((file, i) => (
            <li key={`${file.name}-${i}`} className="flex items-center justify-between rounded bg-slate-50 px-3 py-1.5 text-sm">
              <span className="truncate">{file.name}</span>
              <button
                type="button"
                aria-label={`Quitar ${file.name}`}
                onClick={() => onChange(files.filter((_, idx) => idx !== i))}
                className="text-slate-400 hover:text-slate-700"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p role="alert" className="text-xs font-medium text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
