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
   por completo, aunque las policies esten ahi. El esquema crea `ambienta_app`
   justo para esto.
2. El SET LOCAL vive en la transaccion, asi que la sesion debe usar una
   transaccion explicita — de ahi el `begin()` en `get_tenant_db`.
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

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """Sesion sin tenant. Solo para catalogo global y health checks."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def tenant_session(tenant_id: str) -> Generator[Session, None, None]:
    """Sesion con el tenant declarado, dentro de una transaccion.

    `SET LOCAL` solo dura lo que dura la transaccion, por eso la sesion se abre
    con `begin()`: al salir hace commit, o rollback si algo revento.
    """
    db = SessionLocal()
    try:
        with db.begin():
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
