# Diseño: Acceso por SSO con alta controlada

## 1. La distinción que falta

Hoy `auth.py` responde **401** en dos situaciones que no se parecen en nada:

| Situación | Qué significa | Quién lo arregla |
|---|---|---|
| Token ilegible, vencido, mal firmado, de otro emisor | *No sé quién eres* | La persona, volviendo a entrar |
| Token válido y firmado, **sin `tenant_id`** | *Sé quién eres, no perteneces a ninguna empresa* | Un administrador |

El segundo caso no mejora por reintentar, y hoy el sistema responde como si sí.

### El contrato

**401** se reserva para "no pude verificar la identidad".
**403** pasa a significar "identidad verificada, sin empresa asignada", con un
marcador legible por máquina en el cuerpo para que el frontend no tenga que
adivinar por el texto.

**Por qué un marcador y no el mensaje:** el texto es para personas y se va a
traducir y reescribir. Un frontend que ramifique sobre él se rompe la primera
vez que alguien mejore la redacción — que es exactamente el error que ya se
cometió mapeando errores de PostgreSQL por subcadena.

**Qué se pierde con 403:** deja de ser cierto que "401 = hay que volver a
entrar", que es un atajo mental cómodo. A cambio, el frontend puede distinguir
sin heurísticas, y el atajo era falso de todas formas.

**La alternativa descartada** —mantener 401 y que el frontend consulte a Clerk
si la sesión sigue viva para inferir el caso— es lo que se hace hoy. Funciona,
pero deja la decisión en el cliente: la API sabe la respuesta y no la dice.

### Convivencia con el 403 que ya existe

`exigir_admin_global` ya responde 403 para "no eres admin global". Son dos
negativas distintas y el marcador es lo que las separa. Sin él, la pantalla de
"sin empresa" aparecería ante un simple intento de entrar a una pantalla de
administración.

## 2. Qué ve la persona

Una pantalla propia, no el tablero vacío. Tres cosas y ninguna más:

1. Que su cuenta está autenticada pero no asociada a ninguna empresa
2. Que el acceso lo habilita un administrador de su empresa
3. Un botón de cerrar sesión

**Por qué cerrar sesión es obligatorio:** sin él, alguien que entró con la
cuenta equivocada queda atrapado. La sesión de Clerk sobrevive al refresco de
la página, así que no hay forma de salir sin borrar cookies a mano.

**Por qué no se ofrece "solicitar acceso":** implicaría decidir a quién le
llega esa solicitud, y hoy no hay a quién — la invitación no existe todavía
(`credenciales-de-acceso` Fase 2). Prometerlo en pantalla sería mentir.

**Qué NO debe decir:** si la empresa de ese dominio existe en el sistema. Eso
convertiría la pantalla en un detector de clientes nuestros.

### Dónde se decide

En el punto donde el frontend ya sabe que la sesión de Clerk está viva y la API
la rechazó: el puente que hoy sólo escribe en la consola. Ese componente pasa a
publicar el estado, y el layout del sistema decide qué pintar.

**Qué se pierde frente a resolverlo en el middleware de Next:** el middleware
corre antes y evitaría pintar el tablero un instante. Pero no puede saberlo: el
claim vive en el token del template, y el middleware no lo pide. Averiguarlo ahí
costaría una llamada extra en **cada** navegación, para un caso que es raro.

## 3. Cerrar el registro

Hacen falta **las dos cosas**, y conviene entender por qué ninguna basta sola:

| Dónde | Qué | Qué pasa si falta |
|---|---|---|
| Panel de Clerk | Desactivar el registro | La API de Clerk sigue aceptando altas aunque nuestra pantalla no exista |
| `apps/web` | Retirar la pantalla de registro | Queda una ruta que promete algo que el proveedor rechaza |

La del panel es la que manda. La nuestra evita ofrecer una puerta que no abre.

**Qué pasa con quien ya tiene cuenta creada por el registro abierto:** puede
haber usuarios en Clerk sin fila en nuestra base. No se borran —eso es del
proveedor— pero caen en el estado sin empresa, que a partir de este cambio está
explicado. Conviene revisar la lista antes de encender SSO.

## 4. El alta, mientras no exista la invitación

Con el registro cerrado, alguien tiene que crear la identidad. Hasta que
`credenciales-de-acceso` construya la invitación, el camino es manual:

1. Crear la persona en el panel de Clerk
2. Ponerle `tenant_id` y `role` en su `publicMetadata`
3. El webhook crea la fila al primer ingreso

**Esto es una muleta y hay que decirlo así.** Es la razón por la que este cambio
no puede cerrar el asunto solo: deja el estado visible y explicado, pero el alta
sigue siendo trabajo manual hasta el otro cambio.

## 5. La misma persona en dos proveedores

Alguien invitado con un correo puede entrar con Microsoft una vez y con Google
la siguiente. Si el proveedor trata cada una como identidad distinta, llegan dos
`user.created` con el mismo correo y distinto identificador.

La base ya lo resiste a medias: `users.email` es único y la sincronización busca
primero por identificador del proveedor y después por correo, así que **adopta**
la fila en vez de duplicarla. Lo que no está resuelto es que el segundo ingreso
**pisa** el identificador del primero, dejando la identidad anterior huérfana:
esa persona pierde el acceso por el proveedor con el que empezó.

La forma correcta es que el proveedor vincule ambas cuentas y emita un solo
identificador. **Es configuración, no código**, y hay que verificarla con dos
cuentas reales del mismo correo antes de prometer que funciona.

**Qué se pierde si no se configura:** cada persona queda atada al proveedor con
el que entró la última vez, y eso se descubre cuando alguien no puede entrar.

## 6. Lo que no cambia

- **El modo sin Clerk.** Con `.env` vacío sigue el DevRoleSwitcher y el header
  `X-Tenant-Id`. Este cambio no puede romperlo: es como se levanta el repo.
- **El Cliente Invitado**, que no pasa por Clerk.
- **El aislamiento.** RLS sigue siendo la única barrera. Una sesión sin empresa
  no declara tenant, así que sobre cualquier tabla de empresa vería cero filas
  aunque el 403 no existiera. El 403 es para que la persona **entienda**, no
  para contener la fuga: eso ya está contenido.

## 7. Riesgos

| Riesgo | Mitigación |
|---|---|
| Cambiar 401→403 rompe clientes que ramifican sobre 401 | El único cliente es nuestra web, y se ajusta en este mismo cambio |
| Entra ID de un cliente rechaza cuentas externas | Verificar con una cuenta real **antes** de prometer Microsoft SSO. Es el pendiente que ADR-006 dejó abierto |
| El webhook sigue sin llegar en local | No lo resuelve este cambio. El alta local sigue siendo manual |
| Nadie se entera de quién quedó sin empresa | Registrar el evento. Sin eso, un empleado nuevo bloqueado es invisible hasta que reclama |
