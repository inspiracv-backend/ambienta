import pymupdf

from ambienta_ia.ingesta.pdf import extraer_texto_pdf, fragmentar


def test_extrae_texto_de_pdf_con_texto_nativo():
    documento = pymupdf.open()
    pagina = documento.new_page()
    pagina.insert_text((72, 72), "Resolución de Calificación Ambiental. Condición de monitoreo de aguas.")
    datos = documento.tobytes()
    documento.close()

    assert "Condición de monitoreo" in extraer_texto_pdf(datos)


def test_fragmenta_con_solapamiento_y_sin_perder_el_contenido():
    texto = "uno dos tres cuatro cinco seis siete ocho nueve diez " * 20
    partes = fragmentar(texto, max_chars=70)

    assert len(partes) > 2
    assert all(len(parte) <= 70 for parte in partes)
    assert all(set(partes[i].split()) & set(partes[i + 1].split()) for i in range(len(partes) - 1))
