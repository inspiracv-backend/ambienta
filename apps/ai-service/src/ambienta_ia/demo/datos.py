"""
Datos de ejemplo del backend simulado.

⚠️ Los textos de los artículos son **resúmenes redactados para pruebas**, no el texto oficial de
las normas. La estructura (qué artículo cuelga de qué título, qué versiones hay) imita la del
catálogo real para ejercitar las mismas reglas. Para consultar una norma, Ley Chile.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")
EMPRESA_B = uuid.UUID("a0000000-0000-0000-0000-000000000002")
USUARIO_A = uuid.UUID("d0000000-0000-0000-0000-000000000001")
USUARIO_B = uuid.UUID("d0000000-0000-0000-0000-000000000002")

PERMISOS_COMPLETOS = [
    "catalog.read", "chatbot.use", "document.read", "legal_matrix.read", "obligation.read",
    "audit.read", "nonconformity.read", "company_profile.read", "notification.configure",
]


def _id(texto: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"ambienta-demo/{texto}")


def _ts(dia: str) -> str:
    return datetime.fromisoformat(dia).replace(tzinfo=UTC).isoformat()


def _norma(clave: str, norm_type: str, number: str, title: str, updated: str, **extra: Any) -> dict:
    return {
        "id": str(_id(f"norma/{clave}")),
        "country_id": 1,
        "source_id": 1,
        "external_norm_id": extra.pop("external_norm_id", None),
        "norm_type": norm_type,
        "norm_number": number,
        "title": title,
        "issuing_body": extra.pop("issuing_body", None),
        "publication_date": None,
        "promulgation_date": None,
        "effective_from": None,
        "repeal_date": None,
        "status": "vigente",
        "official_url": extra.pop("official_url", None),
        "subjects": [],
        "last_source_sync_at": None,
        "created_at": _ts("2026-08-26"),
        "updated_at": _ts(updated),
        **extra,
    }


class _Arbol:
    """Arma artículos con parent_article_id y display_order como los devuelve el backend."""

    def __init__(self, norma_clave: str, version_id: uuid.UUID):
        self.norma_clave = norma_clave
        self.version_id = version_id
        self.filas: list[dict] = []
        self._orden = 0

    def nodo(self, tipo: str, numero: str | None, contenido: str | None = None,
             padre: dict | None = None, heading: str | None = None) -> dict:
        self._orden += 1
        fila = {
            "id": str(_id(f"art/{self.norma_clave}/{self.version_id}/{tipo}/{numero}/{self._orden}")),
            "norm_version_id": str(self.version_id),
            "parent_article_id": padre["id"] if padre else None,
            "external_article_id": None,
            "article_type": tipo,
            "article_number": numero,
            "heading": heading,
            "content": contenido,
            "display_order": self._orden,
            "effective_from": None,
            "effective_to": None,
            "created_at": _ts("2026-08-26"),
            "updated_at": _ts("2026-08-26"),
        }
        self.filas.append(fila)
        return fila


def construir() -> dict[str, Any]:
    normas: list[dict] = []
    versiones: dict[str, list[dict]] = {}
    articulos: dict[str, list[dict]] = {}  # por version_id

    # -- Ley 19.300 (dos versiones marcadas vigentes, como pasa en la BCN) ------
    ley = _norma(
        "ley19300", "ley", "19.300", "Aprueba Ley sobre Bases Generales del Medio Ambiente",
        "2026-08-26", external_norm_id="30667",
        official_url="https://www.bcn.cl/leychile/navegar?idNorma=30667",
    )
    normas.append(ley)
    v1994 = _id("version/ley19300/1994")
    v2010 = _id("version/ley19300/2010")
    versiones[ley["id"]] = [
        {"id": str(v2010), "norm_id": ley["id"], "valid_from": "2010-01-26", "valid_to": None,
         "is_current": True, "content_hash": "ley19300-2010-a"},
        {"id": str(v1994), "norm_id": ley["id"], "valid_from": "1994-03-09", "valid_to": None,
         "is_current": True, "content_hash": "ley19300-1994"},
    ]

    a = _Arbol("ley19300", v2010)
    t1 = a.nodo("titulo", "I", heading="Disposiciones generales")
    a.nodo("articulo", "1", "El derecho a vivir en un medio ambiente libre de contaminación, la "
           "protección del medio ambiente, la preservación de la naturaleza y la conservación del "
           "patrimonio ambiental se regulan por esta ley.", t1)
    a.nodo("articulo", "2", "Para todos los efectos legales se entiende por evaluación de impacto "
           "ambiental el procedimiento que determina si el impacto ambiental de una actividad o "
           "proyecto se ajusta a las normas vigentes.", t1)
    t2 = a.nodo("titulo", "II", heading="De los instrumentos de gestión ambiental")
    p2 = a.nodo("parrafo", "2º", heading="Del sistema de evaluación de impacto ambiental", padre=t2)
    a.nodo("articulo", "8", "Los proyectos o actividades señalados en el artículo 10 sólo podrán "
           "ejecutarse o modificarse previa evaluación de su impacto ambiental.", p2)
    a.nodo("articulo", "10", "Los proyectos o actividades susceptibles de causar impacto ambiental "
           "que deberán someterse al sistema de evaluación son, entre otros: acueductos, embalses, "
           "centrales generadoras de energía, aeropuertos, puertos, proyectos de desarrollo minero, "
           "plantas industriales y proyectos en áreas protegidas.", p2)
    a.nodo("articulo", "10 bis", "Los proyectos que se ejecuten por etapas se evaluarán "
           "considerando el proyecto en su conjunto.", p2)
    a.nodo("articulo", "11", "Los proyectos o actividades enumerados en el artículo 10 requerirán "
           "la elaboración de un estudio de impacto ambiental si generan riesgo para la salud de la "
           "población, efectos adversos significativos sobre recursos naturales renovables, "
           "reasentamiento de comunidades humanas, localización en o próxima a áreas protegidas, "
           "alteración significativa del paisaje o alteración del patrimonio cultural.", p2)
    a.nodo("articulo", "12", "Los estudios de impacto ambiental considerarán una descripción del "
           "proyecto, la línea de base, la predicción y evaluación del impacto ambiental y un plan "
           "de medidas de mitigación, reparación y compensación.", p2)
    p5 = a.nodo("parrafo", "5º", heading="De la responsabilidad por daño ambiental", padre=t2)
    a.nodo("articulo", "51", "Todo el que culposa o dolosamente cause daño ambiental responderá "
           "del mismo en conformidad a la presente ley.", p5)
    articulos[str(v2010)] = a.filas

    b = _Arbol("ley19300", v1994)
    t1b = b.nodo("titulo", "I", heading="Disposiciones generales")
    b.nodo("articulo", "1", "El derecho a vivir en un medio ambiente libre de contaminación se "
           "regula por esta ley.", t1b)
    t2b = b.nodo("titulo", "II", heading="De los instrumentos de gestión ambiental")
    p2b = b.nodo("parrafo", "2º", padre=t2b)
    b.nodo("articulo", "11", "Los proyectos enumerados en el artículo 10 requerirán un estudio de "
           "impacto ambiental si presentan riesgo para la salud de la población o efectos adversos "
           "sobre recursos naturales renovables. (Redacción original de 1994.)", p2b)
    articulos[str(v1994)] = b.filas

    # -- DS 40/2012, Reglamento del SEIA -----------------------------------------
    ds40 = _norma("ds40", "decreto_supremo", "40/2012",
                  "Aprueba Reglamento del Sistema de Evaluación de Impacto Ambiental", "2026-08-27",
                  external_norm_id="1053563")
    normas.append(ds40)
    v40 = _id("version/ds40/2013")
    versiones[ds40["id"]] = [{"id": str(v40), "norm_id": ds40["id"], "valid_from": "2013-12-24",
                             "valid_to": None, "is_current": True, "content_hash": "ds40-2013"}]
    c = _Arbol("ds40", v40)
    t = c.nodo("titulo", "I")
    c.nodo("articulo", "3", "Tipos de proyectos o actividades. Se someterán al sistema de "
           "evaluación los proyectos listados, como centrales generadoras mayores a 3 MW y "
           "proyectos de desarrollo minero que extraigan más de 5.000 toneladas mensuales.", t)
    c.nodo("articulo", "15", "La declaración de impacto ambiental deberá contener la descripción "
           "del proyecto, los antecedentes que justifican la inexistencia de efectos que requieran "
           "un estudio y el plan de cumplimiento de la legislación ambiental aplicable.", t)
    articulos[str(v40)] = c.filas

    # -- DS 1/2013, Reglamento del RETC --------------------------------------------
    ds1 = _norma("ds1", "decreto_supremo", "1/2013",
                 "Aprueba Reglamento del Registro de Emisiones y Transferencias de Contaminantes",
                 "2026-08-28")
    normas.append(ds1)
    v1 = _id("version/ds1/2013")
    versiones[ds1["id"]] = [{"id": str(v1), "norm_id": ds1["id"], "valid_from": "2013-05-02",
                            "valid_to": None, "is_current": True, "content_hash": "ds1-2013"}]
    d = _Arbol("ds1", v1)
    t = d.nodo("titulo", "II", heading="De la declaración")
    d.nodo("articulo", "18", "Los establecimientos obligados deberán declarar anualmente sus "
           "emisiones y transferencias de contaminantes a través del sistema de ventanilla única, "
           "antes del 30 de abril de cada año, respecto del año calendario anterior.", t)
    d.nodo("articulo", "19", "Los antecedentes que respaldan la declaración deberán conservarse "
           "por un plazo de cinco años.", t)
    articulos[str(v1)] = d.filas

    # -- Normativa propia de la empresa A (una RCA) --------------------------------
    rca = _norma("rca-a-2019", "resolucion_exenta", "123/2019",
                 "RCA Proyecto Ampliación Planta Norte", "2026-09-01",
                 tenant_id=str(EMPRESA_A))
    vr = _id("version/rca-a")
    versiones[rca["id"]] = [{"id": str(vr), "norm_id": rca["id"], "valid_from": "2019-06-01",
                            "valid_to": None, "is_current": True, "content_hash": "rca-a"}]
    e = _Arbol("rca-a", vr)
    cons = e.nodo("considerando", "9", heading="Condiciones")
    e.nodo("articulo", "9.1", "El titular deberá monitorear material particulado MP10 en tres "
           "estaciones y reportar trimestralmente a la Superintendencia del Medio Ambiente.", cons)
    e.nodo("articulo", "9.2", "El titular deberá mantener una cortina vegetal perimetral de al "
           "menos 20 metros de ancho.", cons)
    articulos[str(vr)] = e.filas

    obligaciones = [
        {"id": str(_id("obl/a/retc")), "tenant_id": str(EMPRESA_A), "code": "OBL-RETC-2026",
         "title": "Declaración RETC anual", "status": "open", "due_at": _ts("2026-09-30"),
         "period_start": "2025-01-01", "period_end": "2025-12-31", "owner_user_id": str(USUARIO_A),
         "data": {}, "created_at": _ts("2026-01-10"), "updated_at": _ts("2026-09-01")},
        {"id": str(_id("obl/a/mp10")), "tenant_id": str(EMPRESA_A), "code": "OBL-RCA-MP10-Q3",
         "title": "Reporte trimestral MP10 (RCA 123/2019)", "status": "in_progress",
         "due_at": _ts("2026-09-10"), "period_start": "2026-07-01", "period_end": "2026-09-30",
         "owner_user_id": str(USUARIO_A), "data": {}, "created_at": _ts("2026-07-01"),
         "updated_at": _ts("2026-09-11")},
        {"id": str(_id("obl/b/retc")), "tenant_id": str(EMPRESA_B), "code": "OBL-RETC-2026",
         "title": "Declaración RETC anual (empresa B)", "status": "open",
         "due_at": _ts("2026-09-30"), "period_start": None, "period_end": None,
         "owner_user_id": str(USUARIO_B), "data": {}, "created_at": _ts("2026-01-10"),
         "updated_at": _ts("2026-09-01")},
    ]

    doc_vig = _id("doc/a/informe-mp10")
    doc_bor = _id("doc/a/procedimiento-borrador")
    documentos = [
        {"id": str(doc_vig), "tenant_id": str(EMPRESA_A), "document_type": "informe",
         "current_version_id": str(_id("docv/a/informe-mp10/2")), "title": "Informe MP10 segundo trimestre",
         "classification": "interno", "status": "activo", "tags": [],
         "created_at": _ts("2026-07-15"), "updated_at": _ts("2026-07-15")},
        {"id": str(doc_bor), "tenant_id": str(EMPRESA_A), "document_type": "procedimiento",
         "current_version_id": str(_id("docv/a/proc/1")), "title": "Procedimiento de monitoreo MP10",
         "classification": "interno", "status": "activo", "tags": [],
         "created_at": _ts("2026-08-01"), "updated_at": _ts("2026-08-01")},
    ]
    versiones_documento = {
        str(doc_vig): [{"id": str(_id("docv/a/informe-mp10/2")), "tenant_id": str(EMPRESA_A),
                        "document_id": str(doc_vig), "version_no": 2, "file_name": "informe-mp10-q2.pdf",
                        "mime_type": "application/pdf", "checksum_sha256": "9f86d081884c7d65",
                        "lifecycle_status": "vigente", "created_at": _ts("2026-07-15")}],
        str(doc_bor): [{"id": str(_id("docv/a/proc/1")), "tenant_id": str(EMPRESA_A),
                        "document_id": str(doc_bor), "version_no": 1, "file_name": "procedimiento.docx",
                        "mime_type": "application/msword", "checksum_sha256": "aa11",
                        "lifecycle_status": "borrador", "created_at": _ts("2026-08-01")}],
    }
    vinculos = {
        ("obligation", obligaciones[1]["id"]): [str(doc_vig), str(doc_bor)],
    }
    comentarios = {
        ("obligation", obligaciones[1]["id"]): [
            {"id": 1, "tenant_id": str(EMPRESA_A), "body": "Se atrasó porque la estación 2 estuvo "
             "fuera de servicio dos semanas; el laboratorio entrega el 20/09.",
             "created_at": _ts("2026-09-11")},
        ],
    }

    instalaciones = [
        # Vinculada a SNIFA por el id del proyecto en el SEA (el de una RCA real de la unidad 1078).
        {"id": str(_id("fac/a/norte")), "tenant_id": str(EMPRESA_A), "code": "PLT-NORTE", "name": "Planta Norte",
         "facility_type": "planta_procesamiento", "address": "Ruta 5 km 800", "region_code": "III",
         "commune_code": "03301", "latitude": -29.28, "longitude": -70.06,
         "environmental_identifiers": {"rca": "RCA-138/2006", "seia_id": "1392521"}, "active": True,
         "created_at": _ts("2026-01-10"), "updated_at": _ts("2026-01-10")},
        # Sin vínculo cargado: solo se pueden sugerir candidatas.
        {"id": str(_id("fac/a/oficina")), "tenant_id": str(EMPRESA_A), "code": "OFI-SCL", "name": "Mall Plaza Egaña",
         "facility_type": "oficina_administrativa", "address": "Av. Larraín", "region_code": "RM",
         "commune_code": "13119", "latitude": -33.4531, "longitude": -70.5701,
         "environmental_identifiers": {}, "active": True,
         "created_at": _ts("2026-01-10"), "updated_at": _ts("2026-01-10")},
    ]

    # Qué normas tiene cada empresa en su matriz legal, y quién las sigue.
    matriz = [
        {"id": str(_id("mn/a/ds1")), "tenant_id": str(EMPRESA_A), "matrix_id": str(_id("matriz/a")),
         "norm_id": ds1["id"], "selected_version_id": str(v1), "applicability": "aplica",
         "owner_user_id": str(USUARIO_A)},
        {"id": str(_id("mn/b/ley")), "tenant_id": str(EMPRESA_B), "matrix_id": str(_id("matriz/b")),
         "norm_id": ley["id"], "selected_version_id": str(v2010), "applicability": "aplica",
         "owner_user_id": str(USUARIO_B)},
    ]

    return {
        "matriz": matriz,
        "notificaciones": [],
        "tickets": [],
        "instalaciones": instalaciones,
        "empresas": {
            str(EMPRESA_A): {"id": str(EMPRESA_A), "nombre": "Minera Andes SpA", "sector_id": 3, "tramo": "mediana"},
            str(EMPRESA_B): {"id": str(EMPRESA_B), "nombre": "Pesquera Sur Ltda.", "sector_id": 1, "tramo": "pequeña"},
        },
        "usuarios": {
            "user_demo_a": {"id": str(USUARIO_A), "clerk_id": "user_demo_a", "email": "a@ejemplo.cl",
                            "nombre": "Usuaria A", "tenant_id": str(EMPRESA_A)},
            "user_demo_b": {"id": str(USUARIO_B), "clerk_id": "user_demo_b", "email": "b@ejemplo.cl",
                            "nombre": "Usuario B", "tenant_id": str(EMPRESA_B)},
            "user_demo_plataforma": {"id": str(_id("usuario/plataforma")), "clerk_id": "user_demo_plataforma",
                                     "email": "plataforma@ejemplo.cl", "nombre": "Admin Global",
                                     "tenant_id": str(_id("empresa/plataforma")), "admin_global": True},
        },
        "normas": normas + [rca],
        "versiones": versiones,
        "articulos": articulos,
        "obligaciones": obligaciones,
        "documentos": documentos,
        "versiones_documento": versiones_documento,
        "vinculos": vinculos,
        "comentarios": comentarios,
        "vigencia": {
            # qué versión rige a una fecha, para articles?vigente_el=
            ley["id"]: [(date(1994, 3, 9), date(2010, 1, 25), str(v1994)), (date(2010, 1, 26), None, str(v2010))],
            ds40["id"]: [(date(2013, 12, 24), None, str(v40))],
            ds1["id"]: [(date(2013, 5, 2), None, str(v1))],
            rca["id"]: [(date(2019, 6, 1), None, str(vr))],
        },
    }
