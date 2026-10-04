# Proposal: Una empresa suspendida queda en solo lectura

Decisión del 21-sep-2026 (`docs/plan-de-cierre-v1.md`, §6, decisión 2).

## Lo que hay hoy, medido

`tenants.status` admite `trial`, `active`, `suspended` y `closed`, el Admin
Global lo cambia desde la cartera, y **el servidor no lo mira en ningún lado
salvo en el acceso de invitados**. Una empresa suspendida sigue creando
obligaciones, subiendo documentos y recibiendo avisos por correo exactamente
igual que una activa. La marca se ve en pantalla y no hace nada.

## Lo que se propone

Una empresa `suspended` —y también una `closed`— queda en **solo lectura**:

- **Toda escritura responde 403** con un código propio,
  `empresa_en_solo_lectura`, y un mensaje que dice qué se puede hacer.
- **Leer y exportar sigue funcionando.** Suspender no es quitarle los datos a la
  empresa: tiene que poder sacar lo suyo y regularizar.
- **Se pausan los avisos**: el cron no genera ni despacha para esa empresa, y el
  informe de la corrida dice cuántas empresas quedaron en pausa.
- **El Admin Global no queda bloqueado**: reactiva la empresa desde la
  plataforma, y la plataforma no está suspendida.

`closed` entra por el mismo camino aunque la decisión nombró solo `suspended`:
que una empresa dada de baja siga escribiendo no tiene sentido, y bloquearle
también la lectura le impediría llevarse sus datos.

## Lo que exige del resto del sistema

| Pieza | Qué cambia |
|---|---|
| `deps.exigir_permiso_de_la_ruta` | Mira el estado de la empresa antes que el permiso, también sin Clerk |
| `tareas/avisos.py` | Salta las empresas en solo lectura y lo informa |
| Web | Un aviso en el tablero que explica el estado; los errores ya muestran el mensaje de la API |
| `acceso_invitado` | Nada: ya rechazaba a las empresas suspendidas o cerradas |

## Lo que NO entra

- **Topes de usuarios y módulos activos.** Siguen siendo marcas: son otra
  decisión.
- **Qué pasa con los avisos encolados al reactivar.** Quedan en la cola y salen
  cuando la empresa vuelve; si la suspensión fue larga, pueden llegar tarde.

## Preguntas abiertas

1. ¿Los avisos encolados durante la suspensión deben descartarse al reactivar,
   en vez de salir tarde?
2. ¿Una empresa en `trial` vencido debe pasar sola a `suspended`? Hoy no hay
   fecha de fin de prueba en el modelo.
