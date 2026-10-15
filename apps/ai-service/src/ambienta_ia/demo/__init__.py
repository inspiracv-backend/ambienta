"""
Backend simulado de Ambienta, para pruebas y demo.

Implementa las rutas del handoff del 08/09 con sus reglas (paginación por cabecera,
`updated_since` estricto, 404 para lo ajeno, hilo ordenado, citas guardadas), sobre datos en
memoria. **No reemplaza al backend real**: sirve para desarrollar y probar el AI Service sin
depender de él, y para que las pruebas de contrato tengan contra qué correr.
"""
