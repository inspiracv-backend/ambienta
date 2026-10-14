# Cambios

## 1.0.0 — 13-oct-2026

**Primera versión que se despliega.** Sale como `1.0.0` y no como beta por
decisión del 13-oct; lo que eso **no** significa está en «Lo que esta versión
deliberadamente no trae» y en «Lo que hay que hacer para que funcione»: hay
huecos conocidos y escritos, y la operación todavía no tiene ensayo de
restauración, aviso de respaldo fallido ni entorno de staging. Lo que sigue no es la lista de commits: es
**qué puede hacer una empresa con esto, qué no, y qué falta decidir** — que es
lo que hace falta saber antes de ponerle datos de un cliente adentro.

### Lo que una empresa puede hacer de punta a punta

- **Declarar su perfil** (giro, RUT, plantas, departamentos, sector CIIU) y
  recibir del sistema **qué normativa le aplica**, obligatoria y recomendada,
  calculada a partir de su sector y tramo — no escrita a mano.
- **Evaluar su Matriz Legal** artículo por artículo, con evidencia, por planta,
  con el porcentaje de cumplimiento y la cobertura derivados del servidor.
- **Colgar obligaciones de una evaluación**, con responsable y plazo, y recibir
  **avisos de vencimiento por correo** a 15, 7, 3 y 1 día — escalados a los
  administradores cuando la obligación no tiene responsable.
- **Declarar ante los portales del Estado** con el flujo completo de RF-31:
  presentar, aceptar con folio, rechazar con motivo.
- **Correr una auditoría**: planificarla, ejecutar su checklist anclado a los
  artículos evaluados, derivar el informe y emitirlo en PDF.
- **Tratar un hallazgo** por el ciclo de ISO 9001 §10.2.1 completo —reacción,
  corrección, causa raíz, acción correctiva, verificación de eficacia—, con
  **retorno automático a la acción correctiva si la verificación dice que no fue
  eficaz** y con las salidas de la verificación convertidas en compromisos que
  sobreviven al cierre del registro.
- **Recorrer la cadena de ISO 14001 §6.1**: aspecto ambiental → significancia →
  riesgo → plan de acción, con el requisito legal enlazado al artículo evaluado.
- **Controlar sus documentos** (RF-102 a RF-106): ciclo de vida en la revisión,
  aprobación firmada con quién y cuándo, una sola revisión vigente, y los
  archivos en almacenamiento de objetos por enlace firmado.
- **Dar acceso a un Cliente Invitado** sin cuenta, con credenciales que emite la
  API y una sesión propia de 30 días.
- **Ver su registro de actividades**: se escribe solo, incluidas las emisiones
  de PDF y CSV, y es **inmutable por la base**, no por la aplicación.

Y un Gestor puede trabajar **por sus clientes** declarando la empresa en la que
actúa, sin que eso toque el aislamiento: la barrera sigue siendo Row Level
Security y delante hay una llave que se comprueba en cada petición.

### Lo que esta versión deliberadamente no trae

Ninguna de estas es falta de tiempo. Cada una tiene su motivo escrito donde
corresponde, y casi todas son lo mismo: **inventar un dato que no tenemos es
peor que no tenerlo**, porque en cumplimiento un dato falso se cita como un
hecho.

| | Por qué |
|---|---|
| Entrar con Microsoft | Exige registro en Entra ID, y ahí el tipo de cuenta tiene que ser *cualquier directorio + cuentas personales* |
| Las plantillas Excel de las declaraciones | Son contenido oficial de cada portal del Estado. Una estructura inventada se rechaza cuando ya no hay plazo |
| Las periodicidades del RETC | El portal lista los sistemas y no sus plazos, que cambian por resolución cada año. Un calendario inventado produce vencimientos falsos |
| Los 9 sistemas de la SMA | ADR-004 los cita y la fuente no está en el repositorio. Los 12 de la Ventanilla Única sí, y van **inactivos**: son un borrador que negocio tiene que firmar |
| Los plazos por severidad del ciclo de mejora | Sembrar 60/30/15 sería inventarle el compromiso a la empresa. Mientras estén vacíos, la fecha límite se pide a mano |
| La clasificación por sector de 4 normas | DS 13, DS 90, DS 38 y la Ley 20.920 tienen alcance acotado, y a qué rubros llegan es criterio legal |
| `worker` y `ai-service` | El trabajo de fondo vive en `app/tareas/` y lo dispara el servicio `cron`. La capa de agente es de otra épica |

### Lo que hay que hacer para que funcione, y no está en el repositorio

Está en `docs/development/despliegue.md`. En orden:

1. El `.env`, que se revisa antes de levantar con
   `python herramientas/comprobar_env.py`.
2. **Clerk** (§2.1): instancia de producción, el **JWT Template con
   `tenant_id`** —sin él la API responde 401 a todo—, el webhook de usuarios y
   cerrar el registro público.
3. **Resend** con el dominio verificado (SPF y DKIM).
4. **Crear el primer Admin Global** (§4.10): sin él queda desplegado y nadie
   puede entrar.
5. **Cargar el catálogo normativo** (§4.12): producción arranca con **cero
   normas**, y después de sincronizar hay que reaplicar `db/23`.

### Las cinco decisiones abiertas, cerradas

Estuvieron escritas desde el 21-sep y se tomaron el 13-oct. El detalle está en
`docs/plan-de-cierre-v1.md` §6.3; lo que cambia para una empresa:

- **Una evaluación de la matriz ya no se borra.** El `DELETE` responde 403 y
  apunta a reevaluar, marcar el artículo como no aplicable o retirar la norma.
  Es evidencia de que ese artículo se revisó, y con qué resultado. De paso se
  arregló el índice único, que al cubrir las filas retiradas dejaba el artículo
  con **409 para siempre** — 9 artículos estaban así.
- **Una norma que dejó de aplicarle a la empresa ya no pesa en su porcentaje**,
  en los tres lugares que lo calculan, incluido el promedio por planta del
  documento que se entrega. El sistema era incoherente consigo mismo: un
  artículo marcado «no aplica» ya salía del cálculo y una norma entera no.
- **El D.S. 609 quedó clasificado** en los ocho sectores, con el nivel que
  corresponde a cada uno: entró al catálogo el 21-sep sin ninguno, así que el
  sistema no se lo proponía a nadie.
- **La severidad se sigue pidiendo en todo registro**, no solo en las no
  conformidades: calificar la de un riesgo no es un error conceptual.
- **Los «decretos 40 y 48»** de la reunión quedan **fuera de esta versión**: las
  tres normas candidatas son de seguridad laboral y minera, y este producto
  modela cumplimiento ambiental.

### Lo que se arregló para poder desplegar

El camino de producción se mantuvo a mano durante meses sin que nadie corriera
el `up` —no había servidor— y al ensayarlo completo con las imágenes reales
tenía **nueve fallas**, cinco de ellas invisibles hasta después de desplegar: la
imagen del frontend no se podía construir, el Caddyfile era inválido, el proxy
apuntaba al puerto equivocado, el frontend no recibía la llave secreta de Clerk,
la API se conectaba como dueño de la base —lo que dejaba sin efecto la
inmutabilidad del registro de auditoría—, la auditoría archivada se escribía en
disco efímero, el servicio de avisos no tenía salida a internet, el runbook
mandaba a verificar un endpoint que no existe y nada decía que había que crear
el primer Admin Global. El detalle está en el estado del runbook y en las
trampas conocidas de `CLAUDE.md`.

Y se agregó lo que no existía: **respaldo automático diario** de la base y de la
auditoría archivada, verificado restaurándolo, con 30 días de retención fuera de
la máquina (RNF-19).

### Las etiquetas

Las dos apuntan al mismo trabajo y se conservan las dos:

| Etiqueta | Qué es |
|---|---|
| `v1.0.0-beta.1` | El commit de merge del PR #237, etiquetado al integrar |
| `v1.0.0` | La misma versión, publicada sin el sufijo de beta |

El `git tag` se crea siempre sobre el commit que **de verdad se despliega**,
después de integrar la rama: etiquetar antes deja la etiqueta apuntando a un
commit que no quedó en la rama principal si la integración se hace con squash.
