/**
 * Reemplazo del `DevRoleSwitcher` en builds que no son de desarrollo.
 *
 * `next.config.js` sustituye el módulo real por este mediante
 * `NormalModuleReplacementPlugin`, de modo que el código de la herramienta
 * (y los datos de usuarios mock que muestra) no llega al bundle: no queda
 * como código muerto, directamente no se compila.
 *
 * Un `if (process.env.NODE_ENV === 'production') return null` dentro del
 * componente no basta: evita que renderice, pero webpack igual incluye el
 * módulo completo en el bundle.
 */
export function DevRoleSwitcher() {
  return null;
}
