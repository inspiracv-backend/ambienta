from uuid import uuid4

from ambienta_ia.operacion.estado import guardar_estado
from ambienta_ia.proveedores.embeddings import como_vector


async def test_los_fragmentos_pdf_quedan_aislados_por_tenant(base_sincronizador, base_consulta):
    from ambienta_ia.demo.datos import EMPRESA_A, EMPRESA_B

    documento = uuid4()
    version = uuid4()
    async with base_sincronizador.transaccion_de_empresa(EMPRESA_A) as conn:
        await conn.execute(
            "INSERT INTO documento_fragmento "
            "(tenant_id,document_id,version_id,chunk_no,titulo,contenido,checksum_sha256,embedding) "
            "VALUES (%s,%s,%s,0,'RCA prueba','Condición de control de polvo','test',%s)",
            (EMPRESA_A, documento, version, como_vector([0.01] * 256)),
        )

    async with base_consulta.de_empresa(EMPRESA_A) as conn:
        (visible,) = await (await conn.execute(
            "SELECT count(*) FROM documento_fragmento WHERE document_id=%s", (documento,)
        )).fetchone()
    async with base_consulta.de_empresa(EMPRESA_B) as conn:
        (ajena,) = await (await conn.execute(
            "SELECT count(*) FROM documento_fragmento WHERE document_id=%s", (documento,)
        )).fetchone()

    assert visible == 1
    assert ajena == 0


async def test_estado_de_agente_persistido_y_visible_para_consulta(base_de_prueba, base_consulta):
    await guardar_estado(base_de_prueba["sincronizador"], "prueba_estado", "ok", elementos=3)

    estados = await base_consulta.estados_agentes()

    assert any(e["nombre"] == "prueba_estado" and e["estado"] == "ok" and e["elementos"] == 3
               and e["iniciado_en"] is not None and e["finalizado_en"] is not None for e in estados)
