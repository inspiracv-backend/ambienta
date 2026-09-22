# Design: la normativa propia

## La política tiene dos lados distintos, y no es un descuido

```
USING       (tenant_id IS NULL OR tenant_id = current_tenant_id())
WITH CHECK  (tenant_id = current_tenant_id())
```

El `USING` deja **leer** lo público; el `WITH CHECK` **no** deja que una
empresa lo escriba. Si los dos dijeran lo mismo, cualquier empresa podría
insertar una norma con `tenant_id` nulo y quedaría en el catálogo de todas — o
sea, escribirle la ley a los demás.

### La corrección que apareció probando

La primera versión del `WITH CHECK` decía sólo
`tenant_id = current_tenant_id()`, apoyada en que la sincronización de la BCN
escribe con `AdminSessionLocal` —el rol `ambienta`, superusuario con
`BYPASSRLS`— y por lo tanto no pasaría por la política.

**Eso es falso cuando `DATABASE_ADMIN_URL` no está configurada.** `engine_admin`
cae a la URL de la aplicación (está dicho en `app/db.py`), así que la "sesión de
administración" conecta como `ambienta_app`, que no se salta nada. Medido: con
la variable vacía, `current_user` es `ambienta_app`.

El compose de este repositorio sí la define, así que dentro del contenedor la
premisa se sostenía; `.env.example` la trae vacía. Un despliegue que la olvidara
habría dejado **el catálogo sin actualizarse**, y antes esa misma omisión sólo
degradaba el webhook de Clerk.

La política nombra entonces los dos casos legítimos:

| quién escribe | qué puede escribir |
|---|---|
| sesión con tenant declarado | **sólo lo suyo** |
| sesión sin tenant (tareas, catálogo) | **sólo lo público** |

Lo que importa queda entero: una empresa **nunca** puede escribir una norma
pública ni una de otra empresa. Y ninguna ruta de empresa escribe
`legal_norms`: las del catálogo exigen Admin Global y tocan `norm_sectors`.

La lección general no es sobre RLS: **verificar el rol en `pg_roles` no dice con
qué rol conecta el proceso.** Lo primero se midió y lo segundo se supuso.

## Estas tres tablas van SIN `FORCE ROW LEVEL SECURITY`

Y es lo contrario de lo que hacen las otras migraciones de este repositorio,
así que conviene entender por qué antes de "arreglarlo".

`FORCE` hace que el **dueño** de la tabla también quede sujeto a la política.
En el resto de las tablas eso es lo correcto: las tareas que corren como dueño
no tienen por qué ver todas las empresas.

Acá se deja sin `FORCE` para **no depender de que la configuración sea la
correcta**. Con el `WITH CHECK` de dos casos la sincronización funciona con
cualquiera de los dos roles; sin `FORCE`, además sigue funcionando si algún día
`DATABASE_ADMIN_URL` apunta de verdad al superusuario. Es la diferencia entre
que algo funcione y que funcione por dos motivos independientes.

Hay una prueba que **escribe una norma global por el camino de la
sincronización** después de la migración, y otra que comprueba que las tres
tablas sigan sin `FORCE`. Sin ellas, agregar `FORCE` por simetría con `25` y
`28` dejaría el catálogo sin actualizarse, y el síntoma sería "la BCN no trae
nada" — que no se parece a la causa.

## Qué pasa con las consultas que ya existen

| sesión | `current_tenant_id()` | qué ve |
|---|---|---|
| `get_db` (catálogo global) | `NULL` | sólo lo público — **igual que hoy** |
| `get_tenant_db` | el tenant | lo público **más lo suyo** |
| `AdminSessionLocal` | irrelevante | todo, por `BYPASSRLS` |

O sea que activar RLS acá **no cambia ninguna lectura existente**: las amplía.
El endpoint `/catalog/norms` sigue devolviendo el catálogo compartido, que es
lo que debe hacer — una RCA no es catálogo.

## `norm_type` no recibe un CHECK

Es `varchar(80)` sin restricción, y se queda así. Los valores los asigna la BCN
al sincronizar y **no controlamos su vocabulario**: un CHECK escrito hoy
rechazaría el tipo que traiga la próxima norma importada, y el fallo aparecería
en una tarea de fondo. La aplicación decide qué ofrecer al cargar una norma
propia (`rca`, `iso_interna`); la base no lo estrecha.

## Una norma propia necesita una versión, como cualquier otra

`matrix_norms.selected_version_id` es `NOT NULL`, así que registrar una RCA
crea también su `legal_norm_versions`. No es burocracia: una RCA se modifica
por resolución posterior, y sin versión no habría dónde poner que la matriz se
evaluó contra el texto de 2019 y no contra el de 2024.

## Los artículos son lo que importa proteger

Una RCA sin sus considerandos es un título. Los compromisos —caudales,
horarios, monitoreos— viven en `legal_articles`, así que esa tabla lleva
`tenant_id` y RLS igual que la norma. Dejarla afuera sería poner la puerta y
olvidar la pared.
