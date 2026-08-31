from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud.documents import (
    crud_document,
    crud_document_version,
    crud_entity_document,
)
from ..auth import CurrentUser
from ..deps import get_current_user, get_tenant_db, get_tenant_id
from ..models.documents import DocumentVersion, EntityDocument
from ..models.organization import User
from ..services import control_documental as cd
from ._paginacion import Pagina, paginacion, recortar
from ._comun import borrar_o_404, listar_por_padre, obtener_o_404, verificar_padre
from ..schemas.documents import (
    ConfirmarSubida,
    MotivoDeObsolescencia,
    PuestaEnVigencia,
    EnlaceDeDescarga,
    EnlaceDeSubida,
    PedirSubida,
    DocumentCreate,
    DocumentVersionUpdate,
    EntityDocumentCreate,
    EntityDocumentCreateAnidado,
    EntityDocumentRead,
    EntityDocumentUpdate,
    DocumentRead,
    DocumentUpdate,
    DocumentVersionCreate,
    DocumentVersionRead,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=list[DocumentRead])
def list_documents(respuesta: Response, pagina: Pagina = Depends(paginacion), db: Session = Depends(get_tenant_db)):
    return recortar(respuesta, crud_document.get_multi(db, skip=pagina.skip, limit=pagina.pedir), pagina)


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_document.get(db, document_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return obj


@router.post("/", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def create_document(
    data: DocumentCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_document.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{document_id}", response_model=DocumentRead)
def update_document(document_id: UUID, data: DocumentUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_document.get(db, document_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    obj = crud_document.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.get("/{document_id}/versions", response_model=list[DocumentVersionRead])
def list_versions(document_id: UUID, db: Session = Depends(get_tenant_db)):
    from sqlalchemy import select
    from ..models.documents import DocumentVersion
    stmt = select(DocumentVersion).where(DocumentVersion.document_id == document_id)
    return list(db.scalars(stmt).all())


@router.post("/{document_id}/versions", response_model=DocumentVersionRead, status_code=status.HTTP_201_CREATED)
def create_version(
    document_id: UUID,
    data: DocumentVersionCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    from ..models.documents import DocumentVersion
    version_data = data.model_dump(exclude_unset=True)
    version_data["document_id"] = document_id
    obj = DocumentVersion(**version_data, tenant_id=tenant_id)
    db.add(obj)
    db.flush()
    db.refresh(obj)
    db.commit()
    return obj


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira un documento. Sus versiones no se exponen para borrado: son la
    evidencia que respalda el cumplimiento, y eliminarlas dejaria sin sustento
    a las evaluaciones que las citan."""
    borrar_o_404(crud_document, db, document_id, recurso="Document")


# ── Vinculos del documento con las entidades que respalda ──────────────────

@router.get("/{document_id}/entities", response_model=list[EntityDocumentRead])
def list_entity_documents(document_id: UUID, db: Session = Depends(get_tenant_db)):
    """A que entidades respalda este documento."""
    obtener_o_404(crud_document, db, document_id, recurso="Document")
    return listar_por_padre(EntityDocument, db, document_id, campo="document_id")


@router.post("/{document_id}/entities", response_model=EntityDocumentRead, status_code=status.HTTP_201_CREATED)
def create_entity_document(
    document_id: UUID,
    data: EntityDocumentCreateAnidado,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """Vincula el documento con la entidad que respalda.

    `document_id` sale del path y se ignora del cuerpo: si viniera del cuerpo,
    la URL podria decir un documento y la fila apuntar a otro.
    """
    obtener_o_404(crud_document, db, document_id, recurso="Document")
    datos = data.model_dump()
    datos["document_id"] = document_id
    obj = crud_entity_document.create(
        db, obj_in=EntityDocumentCreate(**datos), tenant_id=tenant_id
    )
    db.commit()
    return obj


@router.patch("/{document_id}/entities/{vinculo_id}", response_model=EntityDocumentRead)
def update_entity_document(
    document_id: UUID, vinculo_id: int, data: EntityDocumentUpdate, db: Session = Depends(get_tenant_db)
):
    obj = obtener_o_404(crud_entity_document, db, vinculo_id, recurso="EntityDocument")
    verificar_padre(obj, document_id, campo="document_id")
    obj = crud_entity_document.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/{document_id}/entities/{vinculo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entity_document(document_id: UUID, vinculo_id: int, db: Session = Depends(get_tenant_db)):
    """Desvincula el documento de esa entidad. El documento no se toca."""
    obj = obtener_o_404(crud_entity_document, db, vinculo_id, recurso="EntityDocument")
    verificar_padre(obj, document_id, campo="document_id")
    borrar_o_404(crud_entity_document, db, vinculo_id, recurso="EntityDocument")


@router.get("/{document_id}/entities/{vinculo_id}", response_model=EntityDocumentRead)
def get_entity_document(document_id: UUID, vinculo_id: int, db: Session = Depends(get_tenant_db)):
    obj = obtener_o_404(crud_entity_document, db, vinculo_id, recurso="EntityDocument")
    return verificar_padre(obj, document_id, campo="document_id")


@router.get("/{document_id}/versions/{version_id}", response_model=DocumentVersionRead)
def get_document_version(document_id: UUID, version_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = obtener_o_404(crud_document_version, db, version_id, recurso="DocumentVersion")
    return verificar_padre(obj, document_id, campo="document_id")


@router.patch("/{document_id}/versions/{version_id}", response_model=DocumentVersionRead)
def update_document_version(
    document_id: UUID, version_id: UUID, data: DocumentVersionUpdate, db: Session = Depends(get_tenant_db)
):
    """Corrige los metadatos de una version. El archivo no se reemplaza."""
    obj = obtener_o_404(crud_document_version, db, version_id, recurso="DocumentVersion")
    verificar_padre(obj, document_id, campo="document_id")
    obj = crud_document_version.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/{document_id}/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_version(document_id: UUID, version_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira una version.

    Va contra el criterio inicial —era evidencia y estaba fuera del borrado—
    pero se expone porque una version subida por error tambien es un caso real.
    El borrado es logico: la fila queda y las evaluaciones que la citaban
    siguen teniendo a que apuntar.
    """
    obj = obtener_o_404(crud_document_version, db, version_id, recurso="DocumentVersion")
    verificar_padre(obj, document_id, campo="document_id")
    borrar_o_404(crud_document_version, db, version_id, recurso="DocumentVersion")


# ── Subida y descarga de archivos (RF-110, ADR-005) ──────────────────────
#
# **Row Level Security no cubre el almacenamiento de objetos.** Un enlace
# firmado es una credencial temporal: quien la tenga baja el archivo sin pasar
# por la base. Por eso los tres endpoints leen primero la fila con la sesion del
# tenant — si RLS no la ve, para esta empresa no existe y no hay URL.

@router.post(
    "/{document_id}/upload-url",
    response_model=EnlaceDeSubida,
    tags=["business-logic"],
    summary="Pedir un enlace para subir un archivo",
    description=(
        "Devuelve un enlace firmado para que el navegador suba el archivo "
        "**directo al almacenamiento**, sin pasar por la API.\n\n"
        "Es asi porque un PDF de 40 MB atravesando FastAPI ocupa un worker "
        "durante toda la subida. Lo que se cede: el archivo llega sin que "
        "nosotros lo hayamos visto, asi que el tamano y el tipo declarados hay "
        "que verificarlos **despues** — para eso esta `/confirm-upload`.\n\n"
        "El `Content-Type` va dentro de la firma: si el navegador manda otro, "
        "el almacenamiento rechaza la subida. Sin eso, un enlace firmado para "
        "un PDF serviria para subir cualquier cosa.\n\n"
        "**503 si no hay credenciales configuradas**, y no un respaldo a disco: "
        "un archivo que la empresa cree subido y no esta es peor que un error."
    ),
)
def pedir_enlace_de_subida(
    document_id: UUID,
    datos: PedirSubida,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    from ..services import almacenamiento as alm

    # **Primero la pertenencia.** Firmar sin esto emitiria una credencial para
    # escribir en la carpeta de otra empresa.
    doc = obtener_o_404(crud_document, db, document_id, recurso="Document")

    try:
        alm.validar_archivo(
            nombre=datos.file_name, mime=datos.mime_type, tamano=datos.size_bytes
        )
    except alm.ArchivoRechazado as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    proxima = _proxima_version(db, document_id)
    try:
        enlace = alm.url_para_subir(
            tenant_id=tenant_id,
            document_id=doc.id,
            version_no=proxima,
            nombre=datos.file_name,
            mime=datos.mime_type,
        )
    except alm.SinConfigurar as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )

    return EnlaceDeSubida(
        url=enlace.url,
        storage_key=enlace.clave,
        expires_in=enlace.expira_en,
        headers=enlace.cabeceras,
    )


@router.post(
    "/{document_id}/confirm-upload",
    response_model=DocumentVersionRead,
    status_code=status.HTTP_201_CREATED,
    tags=["business-logic"],
    summary="Cerrar la subida creando la revision",
    description=(
        "Comprueba contra el almacenamiento que el archivo **llego de verdad** "
        "y crea la revision con su tamano y tipo reales.\n\n"
        "Es imprescindible: con enlaces firmados, si el `PUT` del navegador "
        "falla a la mitad la API no se entera de nada, y sin esta comprobacion "
        "quedaria una revision apuntando a un objeto que no existe.\n\n"
        "Se guardan los datos que devuelve el almacenamiento, **no los que "
        "declaro el navegador**: son los unicos que se pueden sostener.\n\n"
        "La revision nace en `borrador`. Aprobarla y ponerla en vigencia son "
        "pasos aparte (RF-104/RF-105)."
    ),
)
def confirmar_subida(
    document_id: UUID,
    datos: ConfirmarSubida,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    from ..models.documents import DocumentVersion
    from ..services import almacenamiento as alm

    doc = obtener_o_404(crud_document, db, document_id, recurso="Document")

    # **La clave tiene que estar dentro del prefijo de este documento.** Sin
    # esta comprobacion, alguien podria confirmar una subida apuntando a la
    # clave de otra empresa y quedarse con una revision que la descarga.
    prefijo = f"tenants/{tenant_id}/documents/{doc.id}/"
    if not datos.storage_key.startswith(prefijo):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La ruta del archivo no corresponde a este documento.",
        )

    try:
        real = alm.confirmar_subida(clave=datos.storage_key)
    except alm.SinConfigurar as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    except alm.ErrorDeAlmacenamiento as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    version = DocumentVersion(
        tenant_id=tenant_id,
        document_id=doc.id,
        version_no=_proxima_version(db, document_id),
        storage_provider="backblaze",
        storage_key=datos.storage_key,
        file_name=datos.file_name,
        mime_type=real.get("mime_type") or "application/octet-stream",
        size_bytes=real["size_bytes"],
        source="upload",
    )
    db.add(version)
    db.flush()
    db.refresh(version)
    db.commit()
    return version


@router.get(
    "/{document_id}/versions/{version_id}/download-url",
    response_model=EnlaceDeDescarga,
    tags=["business-logic"],
    summary="Pedir un enlace para descargar una revision",
    description=(
        "Enlace firmado de corta duracion. **Mas corto que el de subida a "
        "proposito**: una descarga se pide y se usa en el acto, y el enlace da "
        "acceso al contenido.\n\n"
        "La revision tiene que pertenecer al documento de la URL: anidar la "
        "ruta no ata al hijo con el padre por si solo."
    ),
)
def pedir_enlace_de_descarga(
    document_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_tenant_db),
):
    from ..models.documents import DocumentVersion
    from ..services import almacenamiento as alm

    obtener_o_404(crud_document, db, document_id, recurso="Document")

    version = db.get(DocumentVersion, version_id)
    if version is None or version.document_id != document_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Version not found"
        )

    try:
        enlace = alm.url_para_descargar(
            clave=version.storage_key, nombre=version.file_name
        )
    except alm.SinConfigurar as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )

    return EnlaceDeDescarga(url=enlace.url, expires_in=enlace.expira_en)


def _proxima_version(db: Session, document_id: UUID) -> int:
    """El numero de la revision siguiente.

    Se mira el **maximo** y no la cantidad: `document_versions` es de solo
    agregar, pero contar filas se rompe en cuanto exista cualquier hueco.
    """
    from sqlalchemy import func, select

    from ..models.documents import DocumentVersion

    ultima = db.scalar(
        select(func.max(DocumentVersion.version_no)).where(
            DocumentVersion.document_id == document_id
        )
    )
    return (ultima or 0) + 1


# ── Ciclo de vida de la revision (RF-104 a RF-106, #121 del control documental) ──
#
# `services/control_documental.py` existia desde el 27-ago con las transiciones,
# la aprobacion firmada y la obsolescencia, **y ningun router lo llamaba**. Es el
# mismo patron que tuvo `bcn.sincronizar()`: escrito, probado y sin llamador, o
# sea invisible desde fuera y sin forma de saberlo mirando la API.


def _traducir(exc: cd.ErrorDocumental) -> HTTPException:
    """Cada error documental a su codigo HTTP.

    `TransicionInvalida` es **409 y no 422**: el cuerpo esta bien formado y la
    peticion es legitima; lo que pasa es que el recurso esta en un estado que no
    admite ese salto. Un 422 le diria a la pantalla "corrige lo que mandaste", y
    no hay nada que corregir — hay que mirar en que estado esta el documento.
    """
    if isinstance(exc, cd.TransicionInvalida):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
    )


def _revision_de(db: Session, document_id: UUID, version_id: UUID):
    """La revision, comprobando que sea **de ese documento**.

    RLS ya impide ver las de otra empresa. Lo que RLS no comprueba es que la
    revision pertenezca al documento de la URL: sin esto, `/documents/A/versions/B`
    con B de otro documento aprobaria B mientras la pantalla cree estar
    trabajando sobre A.
    """
    revision = db.get(DocumentVersion, version_id)
    if revision is None or revision.document_id != document_id:
        # Mismo mensaje para los dos casos: distinguirlos seria un oraculo para
        # enumerar identificadores ajenos.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La revision no corresponde a este documento.",
        )
    return revision


@router.post(
    "/{document_id}/versions/{version_id}/submit-review",
    response_model=DocumentVersionRead,
    summary="Enviar la revision a revisar",
    description=(
        "El borrador queda listo para que alguien lo revise. Desde `en_revision` "
        "se puede aprobar o devolver a borrador."
    ),
)
def enviar_a_revision(
    document_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_tenant_db),
):
    _revision_de(db, document_id, version_id)
    try:
        revision = cd.enviar_a_revision(db, version_id=version_id)
    except cd.ErrorDocumental as exc:
        raise _traducir(exc) from None
    db.commit()
    return revision


@router.post(
    "/{document_id}/versions/{version_id}/return-to-draft",
    response_model=DocumentVersionRead,
    summary="Devolver la revision a borrador",
    description=(
        "Quien revisa encontro algo que corregir. **Es la unica salida sana de "
        "`en_revision` que no aprueba ni retira**: sin ella, revisar algo "
        "incompleto obliga a aprobarlo igual o a marcarlo obsoleto, y ninguna "
        "de las dos es lo que corresponde."
    ),
)
def devolver_a_borrador(
    document_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_tenant_db),
):
    _revision_de(db, document_id, version_id)
    try:
        revision = cd.devolver_a_borrador(db, version_id=version_id)
    except cd.ErrorDocumental as exc:
        raise _traducir(exc) from None
    db.commit()
    return revision


@router.post(
    "/{document_id}/versions/{version_id}/approve",
    response_model=DocumentVersionRead,
    summary="Aprobar la revision, dejando quien y cuando",
    description=(
        "**Quien aprueba queda escrito.** La base tiene un CHECK que lo exige, "
        "asi que ni un UPDATE a mano puede dejar una revision aprobada sin firma: "
        "ante una auditoria la pregunta no es si se aprobo, es quien. "
        "Aprobada **todavia no rige** — para eso esta `publish`."
    ),
)
def aprobar_revision(
    document_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_tenant_db),
    usuario: CurrentUser = Depends(get_current_user),
):
    _revision_de(db, document_id, version_id)

    aprobador = (
        db.scalar(select(User).where(User.clerk_id == usuario.user_id))
        if usuario.user_id
        else None
    )
    if aprobador is None:
        # **No se inventa un aprobador.** La alternativa —tomar al primer
        # administrador de la empresa— dejaria escrito que esa persona aprobo
        # algo que no aprobo, y eso es exactamente lo que un auditor lee.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No se puede registrar quien aprueba: la sesion no esta asociada "
                "a un usuario de esta empresa. Aprobar exige una sesion "
                "identificada."
            ),
        )

    try:
        revision = cd.aprobar(db, version_id=version_id, aprobador_id=aprobador.id)
    except cd.ErrorDocumental as exc:
        raise _traducir(exc) from None
    db.commit()
    return revision


@router.post(
    "/{document_id}/versions/{version_id}/publish",
    response_model=DocumentVersionRead,
    summary="Poner la revision en vigencia",
    description=(
        "Empieza a regir, y **la anterior queda obsoleta en el mismo paso**: hay "
        "una restriccion en la base que impide dos revisiones vigentes del mismo "
        "documento. Solo una revision vigente sirve como evidencia."
    ),
)
def poner_en_vigencia(
    document_id: UUID,
    version_id: UUID,
    datos: PuestaEnVigencia | None = None,
    db: Session = Depends(get_tenant_db),
):
    _revision_de(db, document_id, version_id)
    try:
        revision = cd.poner_en_vigencia(
            db,
            version_id=version_id,
            desde=datos.desde if datos else None,
            motivo=datos.motivo if datos else None,
        )
    except cd.ErrorDocumental as exc:
        raise _traducir(exc) from None
    db.commit()
    return revision


@router.post(
    "/{document_id}/versions/{version_id}/obsolete",
    response_model=DocumentVersionRead,
    summary="Retirar la revision conservandola",
    description=(
        "RF-106: un documento controlado **no se borra**, se marca obsoleto. "
        "El motivo es obligatorio — un obsoleto sin explicacion obliga a quien "
        "lo encuentre a adivinar si todavia sirve, y en la duda se usa. "
        "Obsoleto **no tiene salida**: para volver se emite una revision nueva."
    ),
)
def marcar_obsoleta(
    document_id: UUID,
    version_id: UUID,
    datos: MotivoDeObsolescencia,
    db: Session = Depends(get_tenant_db),
):
    _revision_de(db, document_id, version_id)
    try:
        revision = cd.marcar_obsoleta(db, version_id=version_id, motivo=datos.motivo)
    except cd.ErrorDocumental as exc:
        raise _traducir(exc) from None
    db.commit()
    return revision
