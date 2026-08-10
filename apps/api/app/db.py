"""Acceso a Postgres con SQLAlchemy.

El patron (engine + sessionmaker + dependencia `get_db`) viene de la referencia
que paso el mentor. Lo que se agrega encima es el aislamiento multi-tenant, que
en Ambienta no es opcional.

## Por que hay dos dependencias y no una

`get_db` abre una sesion normal. Sirve para el catalogo global (paises, normas,
sectores), que no lleva `tenant_id` y es compartido por todas las empresas.

`get_tenant_db` ademas declara el tenant de la sesion con

    SET LOCAL ambienta.tenant_id = '<uuid>'

que es lo que activan las 37 policies de Row Level Security del esquema. Sin
ese SET LOCAL las tablas con `tenant_id` no devuelven **ninguna** fila: falla
cerrado a proposito, porque una pantalla vacia es preferible a una fuga de
datos entre clientes.

## Dos condiciones para que RLS realmente proteja

1. Conectarse con un rol que NO sea superusuario. Un superusuario ignora RLS
   por completo, aunque las policies esten ahi.
2. El SET LOCAL vive en la transaccion, asi que la sesion debe usar una
   transaccion explicita.

La condicion 1 estuvo incumplida hasta el 10-ago-2026: la API se conectaba con
el dueno de la base, superusuario con BYPASSRLS, y lo unico que protegia era el
`SET LOCAL ROLE ambienta_app` de cada transaccion. Se perdia en cada commit.
Ahora la barrera vive en la conexion: aunque alguien olvide el SET LOCAL, las
policies se evaluan igual.

## Por que hay dos motores

`engine` usa `ambienta_app`, que **no** puede saltarse RLS. Es el de todos los
requests.

`engine_admin` usa el dueno de la base. Existe para lo que legitimamente cruza
empresas —el webhook de Clerk, que recibe un alta y todavia no sabe de que
empresa es hasta leer el payload— y para el health check del esquema. Es una
excepcion nombrada y greppable, en vez de que todo corra sin barrera.
"""
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    # Verifica la conexion antes de usarla: evita el error de "server closed
    # the connection" cuando una conexion del pool quedo colgada.
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=settings.sql_echo,
)

# `expire_on_commit=False` no es una optimizacion, es aislamiento.
#
# Con el valor por defecto (True), leer cualquier atributo despues de
# `db.commit()` dispara un SELECT de refresco. Ese SELECT cae en una
# transaccion nueva, donde el `SET LOCAL ROLE ambienta_app` y el tenant ya no
# existen: corre como `ambienta`, que es superusuario y salta RLS. Pasa en cada
# POST y PATCH, al serializar la respuesta.
#
# Hoy no filtra datos porque el refresco es por clave primaria de una fila que
# ya se habia leido con permiso. Pero deja la puerta abierta a que cualquier
# consulta agregada despues de un commit vea todas las empresas, sin que nada
# lo advierta. Verificado: tras `commit()` se pasa de 4 usuarios visibles a 6.
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
)

# Conexion con el dueno de la base. Salta RLS, asi que se usa solo donde
# cruzar empresas es el proposito: ver `get_admin_db` en deps.py.
#
# Si no hay una URL de administracion configurada cae a la de la aplicacion.
# Eso degrada el webhook —fallara al escribir usuarios— en vez de degradar el
# aislamiento, que es el orden correcto para equivocarse.
engine_admin = create_engine(
    settings.database_admin_url or settings.database_url,
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=2,
    echo=settings.sql_echo,
)

AdminSessionLocal = sessionmaker(
    bind=engine_admin, autoflush=False, autocommit=False, expire_on_commit=False
)


def get_db() -> Generator[Session, None, None]:
    """Sesion sin tenant. Solo para catalogo global y health checks."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def tenant_session(tenant_id: str) -> Generator[Session, None, None]:
    """Sesion con el tenant declarado, dentro de una transaccion.

    Para trabajo fuera de un request (tareas, scripts). Hoy no la usa nadie.

    `SET LOCAL` solo dura lo que dura la transaccion, por eso la sesion se abre
    con `begin()`: al salir hace commit, o rollback si algo revento.

    **El cambio de rol no es opcional.** Esta funcion declaraba el tenant pero
    seguia corriendo como `ambienta`, que es superusuario y salta RLS por
    completo: parecia la version segura y no aislaba nada. Declarar el tenant
    sin cambiar de rol no protege, porque las policies ni se evaluan.
    """
    db = SessionLocal()
    try:
        with db.begin():
            db.execute(text("SET LOCAL ROLE ambienta_app"))
            # El uuid va como parametro y no interpolado en el string: aunque
            # venga de un token ya validado, construir SQL por concatenacion es
            # como se abren las inyecciones.
            db.execute(
                text("SELECT set_config('ambienta.tenant_id', :tid, true)"),
                {"tid": tenant_id},
            )
            yield db
    finally:
        db.close()


def check_database() -> dict:
    """Verifica que la base responde y que el esquema esta cargado.

    Cuenta las tablas del schema public: si el init corrio bien deberian ser
    las 51 del modelo. Es la forma mas barata de distinguir 'la base esta viva'
    de 'la base esta viva y ademas migrada'.
    """
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
        table_count = db.scalar(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
        )
        rls_policies = db.scalar(
            text("SELECT count(*) FROM pg_policies WHERE schemaname = 'public'")
        )
    return {
        "connected": True,
        "public_tables": table_count,
        "rls_policies": rls_policies,
    }
