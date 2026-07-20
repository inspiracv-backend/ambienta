# Documentación — Ambienta

Este directorio contiene la **documentación estable y de alto nivel** del proyecto Ambienta.

> **Importante:**  
> Las especificaciones vivas de features (proposal, design, tasks, specs) viven en la carpeta `openspec/`.  
> Este directorio `docs/` se usa para documentación de producto, arquitectura y estándares de desarrollo.

---

## 1. Producto

Documentación de negocio, mercado y análisis funcional.

| Documento | Descripción | Estado |
|-----------|-------------|--------|
| [Análisis Funcional v1.2](./producto/analisis-funcional-v1.2.md) | Requisitos funcionales y no funcionales del sistema | Completo |
| [Oportunidad de Mercado](./producto/oportunidad-de-mercado.md) | Análisis de mercado, TAM/SAM/SOM, competidores y pricing | Completo |
| [Segmentos Objetivo](./producto/segmentos-objetivo.md) | Definición de ICP, segmentos prioritarios e hipótesis | Completo |
| [Glosario](./producto/glosario.md) | Términos del dominio (RETC, RCA, no conformidad, etc.) | Pendiente |

---

## 2. Arquitectura

Decisiones de diseño, diagramas y documentos técnicos de arquitectura.

| Documento | Descripción | Estado |
|-----------|-------------|--------|
| [ADD — Backend Separado](./arquitectura/ADD-backend-separado.md) | Architecture Design Document del backend separado | Completo |
| [ADRs](./arquitectura/ADRs/) | Architecture Decision Records | En progreso |
| [Diagramas C4](./arquitectura/c4/) | Context, Container y Component diagrams | Pendiente |
| [Diagrama de Base de Datos](./arquitectura/diagrama-base-datos.md) | Modelo de datos principal | Pendiente |
| [Stack Tecnológico](./arquitectura/stack.md) | Tecnologías utilizadas y justificación | Pendiente |

---

## 3. Desarrollo

Estándares, convenciones y guías para el equipo de desarrollo.

| Documento | Descripción | Estado |
|-----------|-------------|--------|
| [Setup Local](./development/setup-local.md) | Cómo levantar el proyecto en local | Pendiente |
| [Flujo de Git](./development/flujo-git.md) | Ramas (main / develop / feature), convenciones de commits | Pendiente |
| [Convenciones de Código](./development/convenciones.md) | Estilo de código, naming, estructura de carpetas | Pendiente |
| [Estrategia de Testing](./development/testing.md) | Tipos de pruebas y criterios de calidad | Pendiente |

---

## 4. Metodología

- Usamos **OpenSpec** (Spec-Driven Development) como metodología principal.
- Las features se especifican primero en `openspec/` antes de implementar.
- Los ADRs documentan las decisiones de arquitectura importantes.
- Todo cambio relevante debe quedar reflejado en esta documentación.

---

## Cómo contribuir a la documentación

1. Mantén los documentos cortos y claros.
2. Usa Markdown.
3. Actualiza el estado (Completo / En progreso / Pendiente) cuando corresponda.
4. Si creas un nuevo documento importante, agrégalo a este índice.

---

*Última actualización: 20 de Julio 2026*