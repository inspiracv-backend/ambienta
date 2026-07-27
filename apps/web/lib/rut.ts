function computeDv(rut: number): string {
  let sum = 0;
  let multiplier = 2;
  let n = rut;
  while (n > 0) {
    sum += (n % 10) * multiplier;
    n = Math.floor(n / 10);
    multiplier = multiplier === 7 ? 2 : multiplier + 1;
  }
  const remainder = 11 - (sum % 11);
  if (remainder === 11) return '0';
  if (remainder === 10) return 'K';
  return String(remainder);
}

function formatRut(rut: number, dv: string): string {
  const reversedDigits = String(rut).split('').reverse();
  const groups: string[] = [];
  for (let i = 0; i < reversedDigits.length; i += 3) {
    groups.push(reversedDigits.slice(i, i + 3).reverse().join(''));
  }
  return `${groups.reverse().join('.')}-${dv}`;
}

/**
 * RUT plausible (con dígito verificador módulo 11 válido) para el flujo de
 * asignación automática del Cliente Invitado (RF-02, S-02, v1.7) — no es un
 * RUT real, solo simula el formato para que la pantalla se sienta auténtica (H2).
 */
export function generateMockRut(): string {
  const rut = 10_000_000 + Math.floor(Math.random() * 15_000_000);
  return formatRut(rut, computeDv(rut));
}

/** Clave dinámica de un solo uso asignada automáticamente al Cliente Invitado (RF-02, RF-07). */
export function generateDynamicPassword(): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let out = '';
  for (let i = 0; i < 6; i++) out += chars[Math.floor(Math.random() * chars.length)];
  return out;
}
