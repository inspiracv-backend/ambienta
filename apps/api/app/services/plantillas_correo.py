"""Rellena las plantillas de notificacion (#121).

## Por que no es React Email, que es lo que pedia la issue

React Email es Node. ADR-005 unifico `api`, `worker` y `ai-service` **en
Python**, y montar un servicio en Node solo para pintar correos es exactamente
lo que ese ADR rechazo. Ademas la tabla ya existe: `notification_templates`
tiene `subject_template`, `body_template`, `variables_schema`, `locale` y
`version_no`, y **viene con tres plantillas sembradas** usando la sintaxis
`{{variable}}`. Lo que faltaba no era un motor: era que alguien las usara.

## Por que un sustituidor propio y no Jinja2

Esta es la decision importante y no es por evitar una dependencia.

**Las plantillas son dato de empresa.** `notification_templates` lleva
`tenant_id` y RLS, o sea que un Admin Empresa las edita. Un motor de plantillas
completo —Jinja2, Mako— evalua expresiones: `{{ ''.__class__.__mro__ }}` es la
primera linea de una cadena bien conocida que termina en ejecucion de codigo
dentro del proceso de la API. Se llama SSTI y no es teorico; es de las cosas
que se buscan primero en cualquier sistema que deje editar plantillas.

Aca solo se reemplaza `{{nombre}}` por un valor de un diccionario. **No hay
expresiones, no hay atributos, no hay llamadas.** Lo que se pierde son los
condicionales y los bucles en la plantilla; lo que se gana es que el peor caso
de una plantilla maliciosa sea un correo feo.

## Que pasa con una variable que falta

Se deja el marcador tal cual y **se informa cual falto**. Las dos alternativas
obvias son peores:

- Reemplazar por vacio produce "La obligacion  vence el ", que se manda igual y
  llega asi al cliente.
- Reventar deja el aviso sin salir por un dato cosmetico, y el aviso importa
  mas que la plantilla.

Dejar `{{nombre}}` visible es feo a proposito: se nota en la primera prueba y
`faltantes` lo dice sin tener que leer el correo.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.notifications import NotificationTemplate

#: `{{ nombre }}`, con o sin espacios. Nombres de variable acotados a lo que un
#: identificador puede ser: sin esto, `{{ algo raro }}` seria una "variable" y
#: los errores de tipeo se convertirian en marcadores mudos.
MARCADOR = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

IDIOMA_POR_DEFECTO = "es-CL"


@dataclass
class Rellenada:
    asunto: str
    cuerpo: str
    #: Variables que la plantilla pedia y el contexto no traia. Su marcador
    #: quedo visible en el texto.
    faltantes: list[str] = field(default_factory=list)
    #: Variables que el contexto traia y la plantilla no usa. No es un error
    #: —el contexto es el mismo para todas— pero delata una plantilla que se
    #: quedo vieja cuando se agrego un dato.
    sin_usar: list[str] = field(default_factory=list)


def rellenar(texto: str, variables: dict, *, escapar_html: bool = False) -> tuple[str, list[str]]:
    """Reemplaza los `{{marcadores}}`. Devuelve el texto y lo que falto."""
    faltantes: list[str] = []

    def uno(m: re.Match) -> str:
        nombre = m.group(1)
        if nombre not in variables or variables[nombre] is None:
            faltantes.append(nombre)
            return m.group(0)
        valor = str(variables[nombre])
        # El escape va **aca y no en el llamador**: es el unico punto por donde
        # un valor entra al texto. Escapar antes obligaria a recordarlo en cada
        # sitio, y el que se olvide no falla — produce un correo con HTML
        # inyectado desde un campo que escribio un usuario.
        return html.escape(valor) if escapar_html else valor

    return MARCADOR.sub(uno, texto or ""), faltantes


def variables_de(texto: str) -> set[str]:
    """Que variables pide una plantilla."""
    return {m.group(1) for m in MARCADOR.finditer(texto or "")}


def buscar(
    db: Session,
    *,
    tenant_id: UUID,
    event_type: str,
    channel: str,
    locale: str = IDIOMA_POR_DEFECTO,
) -> NotificationTemplate | None:
    """La plantilla activa de esta empresa para este evento y canal.

    Devuelve None si no hay. **No se inventa una por defecto aca**: quien llama
    decide si sigue con el texto que ya sabe armar o no manda nada, y esa
    decision depende del canal.
    """
    return db.scalars(
        select(NotificationTemplate)
        .where(
            NotificationTemplate.tenant_id == tenant_id,
            NotificationTemplate.event_type == event_type,
            NotificationTemplate.channel == channel,
            NotificationTemplate.locale == locale,
            NotificationTemplate.active.is_(True),
            NotificationTemplate.deleted_at.is_(None),
        )
        # La mas nueva. Editar una plantilla sube `version_no`, y la anterior
        # se conserva para poder leer con que texto se aviso en su momento.
        .order_by(NotificationTemplate.version_no.desc())
        .limit(1)
    ).first()


def aplicar(
    plantilla: NotificationTemplate, variables: dict, *, escapar_html: bool = False
) -> Rellenada:
    """Rellena asunto y cuerpo, y dice que falto y que sobro."""
    asunto, faltan_asunto = rellenar(
        plantilla.subject_template or "", variables, escapar_html=escapar_html
    )
    cuerpo, faltan_cuerpo = rellenar(
        plantilla.body_template or "", variables, escapar_html=escapar_html
    )

    pedidas = variables_de(plantilla.subject_template or "") | variables_de(
        plantilla.body_template or ""
    )
    return Rellenada(
        asunto=asunto,
        cuerpo=cuerpo,
        faltantes=sorted(set(faltan_asunto) | set(faltan_cuerpo)),
        sin_usar=sorted(k for k in variables if k not in pedidas),
    )
