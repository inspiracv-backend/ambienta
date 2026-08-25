"""El acceso del Cliente Invitado, de punta a punta (RF-01, RF-02, RF-07).

Cuatro endpoints y ni uno mas, y esa es la contencion del diseno:

    POST /acceso-invitado/{empresa_id}/credenciales     generar RUT y clave
    POST /acceso-invitado/{empresa_id}/sesion           entrar y recibir el token
    POST /acceso-invitado/{empresa_id}/solicitudes      abrir una solicitud
    GET  /acceso-invitado/{empresa_id}/mis-solicitudes  ver lo propio

Los dos primeros son **publicos** — esa es la funcionalidad, no un descuido:
RF-02 pide que una persona sin cuenta pueda abrir una solicitud. Los otros dos
exigen el token que emite el segundo.

## Por que el invitado abre su solicitud por aca y no por `/support/tickets`

Porque ese endpoint pide sesion de Clerk, y ademas **dejaria el ticket sin
`guest_credential_id`**: quedaria abierto a nombre de un correo escrito a mano,
sin forma de comprobar despues que es de quien dice ser. Un ticket asi no lo
puede recuperar nadie — que es justo lo que RF-07 pide poder hacer.

## Este router no cuelga de `get_tenant_db`, y hay que saber que implica

`get_tenant_db` resuelve la identidad con Clerk. Aca no hay Clerk, asi que se
usan `sesion_publica_de_empresa` y `get_invitado_actual`. Dos consecuencias
reales:

1. **El registro de actividades no se escribe solo.** El observador de
   `before_flush` solo actua cuando la sesion trae contexto de request, y ese
   contexto lo pone `get_tenant_db`. Por eso los eventos de aca se anotan a
   mano. Si alguien agrega un endpoint a este router y se olvida, **no deja
   rastro y nada avisa** — es la limitacion que `auditoria_automatica.py`
   declara en su docstring.
2. **No hay guarda de permisos.** `exigir_permiso_de_la_ruta` deriva el permiso
   del recurso y de quien llama; un invitado no tiene rol ni permisos. Lo que
   acota a un invitado es que **estos cuatro endpoints son todo lo que puede
   tocar**, no una lista de permisos.

## Por que el `empresa_id` va en la URL

El link es de una empresa: el escenario del requisito dice *"el acceso de
invitado de una empresa"*. Sin el en la URL no hay forma de saber a que empresa
pertenece quien nunca inicio sesion.

El UUID no es una contrasena y no pretende serlo. Es v4, asi que adivinarlo no
es un camino; compartir el enlace si — y eso es exactamente lo que un link
publico significa.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..limite_de_peticiones import (
    TOPE_DE_CREDENCIALES,
    TOPE_DE_INGRESO,
    exigir_cupo,
)
from ..deps import get_invitado_actual, sesion_publica_de_empresa
from ..services.auditoria import registrar
from ..services.invitado import DIAS_DE_VIGENCIA, autenticar, emitir
from ..services.token_invitado import SecretoSinConfigurar, SesionDeInvitado
from ..services.token_invitado import emitir as emitir_token

router = APIRouter(prefix="/acceso-invitado", tags=["acceso-invitado"])


class CredencialGenerada(BaseModel):
    """Lo que se le muestra a la persona **una sola vez**."""

    rut: str = Field(description="RUT asignado, normalizado y con verificador.")
    clave: str = Field(
        description=(
            "Clave de un solo uso practico. **No se puede volver a consultar**: "
            "en la base queda su hash. Si se pierde, se genera un acceso nuevo."
        )
    )
    valido_hasta: str = Field(description="Fecha ISO hasta la que sirven.")
    dias_de_vigencia: int = Field(
        description="Para que la pantalla lo pueda decir sin recalcularlo."
    )


class Entrada(BaseModel):
    rut: str = Field(description="Con puntos, sin puntos o sin guion: da igual.")
    clave: str


class SesionIniciada(BaseModel):
    token: str = Field(
        description=(
            "JWT emitido por **esta API**, no por Clerk. Va en "
            "`Authorization: Bearer`. Solo sirve en este router."
        )
    )
    expira: str
    rut: str


class NuevaSolicitud(BaseModel):
    """Lo que el invitado escribe. **El autor no esta aca**, sale de su token."""

    subject: str = Field(min_length=3, max_length=240)
    description: str = Field(min_length=3)
    category: str = Field(
        default="other",
        description="technical, access, data, legal, billing u other.",
    )
    guest_name: str | None = Field(default=None, max_length=180)
    guest_email: str | None = Field(
        default=None,
        description=(
            "Para poder responderle por fuera del sistema. **No identifica**: "
            "quien identifica es la credencial."
        ),
    )


class SolicitudDelInvitado(BaseModel):
    id: UUID
    ticket_number: str
    subject: str
    status: str
    created_at: str


def _empresa_valida(db: Session, empresa_id: UUID) -> None:
    """Que la empresa exista y este operativa, o 404.

    Sin esto, el endpoint acepta cualquier UUID y crea credenciales colgando de
    una empresa que no existe: filas que nadie va a mirar y un "tu acceso esta
    listo" que no sirve para nada.

    `tenants` no lleva `tenant_id` ni policy, asi que esta consulta la ve toda —
    es el unico dato que este router lee fuera de la empresa del enlace, y es el
    minimo para poder responder 404.
    """
    fila = db.execute(
        text(
            "SELECT status FROM tenants WHERE id = :i AND deleted_at IS NULL"
        ),
        {"i": empresa_id},
    ).first()

    if fila is None or fila[0] in ("suspended", "closed"):
        # **El mismo 404 para las dos cosas.** Distinguir "no existe" de "esta
        # suspendida" le confirmaria a cualquiera que una empresa es cliente
        # nuestro, que no es asunto de quien pregunta.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay un acceso de invitado disponible en este enlace.",
        )


def _anotar(
    db: Session,
    request: Request,
    empresa_id: UUID,
    accion: str,
    credencial_id: UUID | None,
    extra: dict[str, Any],
) -> None:
    """Deja el evento en `audit_log`. **A mano, porque aca nadie lo hace por vos.**"""
    registrar(
        db,
        tenant_id=empresa_id,
        action=accion,
        entity_type="guest_credentials",
        entity_id=credencial_id,
        metadata={
            "ip": request.client.host if request.client else None,
            "ruta": f"{request.method} {request.url.path}",
            **extra,
        },
    )


@router.post(
    "/{empresa_id}/credenciales",
    response_model=CredencialGenerada,
    status_code=status.HTTP_201_CREATED,
    summary="Generar un acceso de invitado",
    description=(
        "Entrega un RUT y una clave temporales para que una persona **sin "
        "cuenta** pueda abrir una solicitud y volver a consultarla (RF-02).\n\n"
        "**La clave se devuelve una sola vez.** En la base queda su hash: no hay "
        "forma de recuperarla, y eso es la propiedad, no una limitacion.\n\n"
        "Es publico a proposito. Lo que acota el dano es que estas credenciales "
        "**no abren ningun endpoint de negocio**: solo el seguimiento de las "
        "solicitudes propias."
    ),
)
def generar_credenciales(
    empresa_id: UUID,
    request: Request,
    db: Session = Depends(sesion_publica_de_empresa),
) -> CredencialGenerada:
    exigir_cupo(TOPE_DE_CREDENCIALES, request, "credenciales")
    _empresa_valida(db, empresa_id)

    credencial = emitir(db, empresa_id)
    db.flush()

    fila_id = db.execute(
        text("SELECT id FROM guest_credentials WHERE tenant_id = :t AND rut = :r"),
        {"t": empresa_id, "r": credencial.rut},
    ).scalar_one()

    _anotar(db, request, empresa_id, "create", fila_id, {"rut": credencial.rut})
    db.commit()

    return CredencialGenerada(
        rut=credencial.rut,
        clave=credencial.clave,
        valido_hasta=credencial.valido_hasta.isoformat(),
        dias_de_vigencia=DIAS_DE_VIGENCIA,
    )


@router.post(
    "/{empresa_id}/sesion",
    response_model=SesionIniciada,
    summary="Entrar con RUT y clave",
    description=(
        "Valida las credenciales y devuelve un token propio de esta API, con la "
        "**misma vigencia que la credencial** (RF-01).\n\n"
        "Responde 401 sin distinguir el motivo: RUT inexistente, clave "
        "incorrecta, credencial vencida y credencial de otra empresa dan lo "
        "mismo hacia afuera. Decir cual fallo le confirmaria a quien prueba al "
        "azar que un RUT existe en esa empresa."
    ),
)
def iniciar_sesion(
    empresa_id: UUID,
    datos: Entrada,
    request: Request,
    db: Session = Depends(sesion_publica_de_empresa),
) -> SesionIniciada:
    exigir_cupo(TOPE_DE_INGRESO, request, "sesion")

    if not get_settings().token_invitado_configurado:
        # Se niega en vez de firmar con una llave por defecto. Un secreto en el
        # codigo es un secreto publicado: cualquiera podria emitirse una sesion
        # de la empresa que quiera.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "El acceso de invitado no esta habilitado en este entorno: "
                "falta configurar el secreto de firma."
            ),
        )

    _empresa_valida(db, empresa_id)

    quien = autenticar(db, empresa_id, datos.rut, datos.clave)
    if quien is None:
        # No se anota el intento fallido con el RUT tecleado: la tabla de
        # auditoria se exporta, y guardar RUT ajenos que alguien probo seria
        # coleccionar datos personales de terceros sin ninguna necesidad.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="RUT o clave incorrectos.",
        )

    try:
        token, expira = emitir_token(
            tenant_id=empresa_id,
            credencial_id=quien.credencial_id,
            rut=quien.rut,
            # La vigencia del token es la de la credencial, no una constante
            # aparte: un token que sobrevive a su credencial es un acceso que ya
            # no se puede cortar.
            dias=DIAS_DE_VIGENCIA,
        )
    except SecretoSinConfigurar as exc:  # pragma: no cover - lo cubre el 503
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    # `autenticar()` ya dejo el evento `login` y actualizo `last_used_at`.
    db.commit()

    return SesionIniciada(token=token, expira=expira.isoformat(), rut=quien.rut)


#: Las mismas que acepta el CHECK de `support_tickets.category`.
#:
#: Se validan aca para responder 422 con un mensaje util, en vez de un 500 por
#: violacion de restriccion a mitad del commit — que se lee como un problema de
#: la base y no de lo que mando quien llama.
CATEGORIAS = frozenset({"technical", "access", "data", "legal", "billing", "other"})


@router.post(
    "/{empresa_id}/solicitudes",
    response_model=SolicitudDelInvitado,
    status_code=status.HTTP_201_CREATED,
    summary="Abrir una solicitud como invitado",
    description=(
        "Crea el ticket **ligado a la credencial** con la que se entro (RF-02). "
        "Ese vinculo es lo que despues permite que la persona lo vuelva a "
        "encontrar, y lo que impide que otro lo vea.\n\n"
        "El numero de ticket lo pone la base, no quien llama."
    ),
)
def abrir_solicitud(
    datos: NuevaSolicitud,
    request: Request,
    invitado_y_sesion: tuple[SesionDeInvitado, Session] = Depends(get_invitado_actual),
) -> SolicitudDelInvitado:
    invitado, db = invitado_y_sesion

    if datos.category not in CATEGORIAS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Categoria no valida. Opciones: {', '.join(sorted(CATEGORIAS))}.",
        )

    fila = db.execute(
        text(
            # `ticket_number` **no se pasa**: lo pone el DEFAULT de la columna
            # con una secuencia (`db/06_ticket_number.sql`). Calcularlo en
            # Python abriria una carrera entre peticiones de empresas
            # distintas, porque la unicidad del numero es global.
            "INSERT INTO support_tickets "
            "(tenant_id, guest_name, guest_email, category, "
            " subject, description, guest_credential_id) "
            "VALUES (:t, :n, :e, :c, :s, :d, :cred) "
            "RETURNING id, ticket_number, subject, status, created_at"
        ),
        {
            "t": invitado.tenant_id,
            "n": datos.guest_name,
            # El CHECK de la tabla exige autor: usuario registrado **o** correo.
            # El invitado no es usuario, asi que si no dejo correo se usa uno
            # derivado del RUT — no sirve para escribirle, pero deja constancia
            # de con que credencial se abrio y satisface la restriccion.
            "e": datos.guest_email or f"{invitado.rut}@invitado.ambienta.local",
            "c": datos.category,
            "s": datos.subject,
            "d": datos.description,
            "cred": invitado.credencial_id,
        },
    ).one()

    _anotar(
        db,
        request,
        invitado.tenant_id,
        "create",
        invitado.credencial_id,
        {"ticket": fila[1], "rut": invitado.rut},
    )
    db.commit()

    return SolicitudDelInvitado(
        id=fila[0],
        ticket_number=fila[1],
        subject=fila[2],
        status=fila[3],
        created_at=fila[4].isoformat(),
    )


@router.get(
    "/{empresa_id}/mis-solicitudes",
    response_model=list[SolicitudDelInvitado],
    summary="Ver las solicitudes propias",
    description=(
        "Las solicitudes abiertas **con esta credencial** (RF-07). Exige el "
        "token que devuelve `/sesion`.\n\n"
        "El filtro es por credencial y no por correo: el correo lo escribe la "
        "misma persona en el formulario, asi que filtrar por el permitiria ver "
        "los tickets de otro con solo poner su direccion."
    ),
)
def mis_solicitudes(
    invitado_y_sesion: tuple[SesionDeInvitado, Session] = Depends(get_invitado_actual),
) -> list[SolicitudDelInvitado]:
    invitado, db = invitado_y_sesion

    filas = db.execute(
        text(
            "SELECT id, ticket_number, subject, status, created_at "
            "FROM support_tickets "
            "WHERE guest_credential_id = :c AND deleted_at IS NULL "
            "ORDER BY created_at DESC"
        ),
        {"c": invitado.credencial_id},
    ).all()

    return [
        SolicitudDelInvitado(
            id=f[0],
            ticket_number=f[1],
            subject=f[2],
            status=f[3],
            created_at=f[4].isoformat(),
        )
        for f in filas
    ]
