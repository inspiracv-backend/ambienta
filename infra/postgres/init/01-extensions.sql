-- Extensiones requeridas por Ambienta.
-- Este script lo ejecuta automáticamente la imagen de Postgres SOLO la primera
-- vez que se inicializa el volumen de datos (si el volumen ya existe, no corre).

-- pgvector: embeddings del catálogo normativo y del RAG del chatbot
-- (decisión cerrada #1 del Análisis Funcional v1.7 — una sola base de datos
-- con pgvector, sin vector store externo).
CREATE EXTENSION IF NOT EXISTS vector;

-- gen_random_uuid() para las claves primarias del modelo de actores.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Búsqueda por similitud de texto (nombres de normas, búsqueda de usuarios).
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Schema separado para la capa agentica (decisión cerrada #2 del funcional
-- v1.7: los embeddings y el historial de agentes viven en la misma instancia,
-- bajo el schema `ai`).
CREATE SCHEMA IF NOT EXISTS ai;
