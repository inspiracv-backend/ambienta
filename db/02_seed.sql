-- ═══════════════════════════════════════════════════════════════════════════
--  AMBIENTA — Datos de prueba (seed)
--  Genera un escenario realista para desarrollo y demo.
--
--  Escenario:
--   • Tenant 1: "Minera Andes SpA" (empresa industrial)
--   • Tenant 2: "EcoGestión Ltda" (consultora ambiental)
--   • Contrato entre ambas
--   • Usuarios con roles diferenciados
--   • Normas ambientales chilenas reales
--   • Obligaciones, auditorías y no conformidades de ejemplo
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ───────────────────────────────────────────────────────────────────────────
--  1. PAÍSES
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO countries (id, iso2, iso3, name, default_timezone, metadata) VALUES
  (1, 'CL', 'CHL', 'Chile', 'America/Santiago', '{}'),
  (2, 'PE', 'PER', 'Perú', 'America/Lima', '{}'),
  (3, 'CO', 'COL', 'Colombia', 'America/Bogota', '{}')
ON CONFLICT (id) DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
--  2. TENANTS
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO tenants (id, country_id, tenant_type, rut_tax_id, legal_name, trade_name, business_activity, status, settings) VALUES
  ('a0000000-0000-0000-0000-000000000001', 1, 'company',
   '76.123.456-7', 'Minera Andes SpA', 'Minera Andes',
   'Extracción de minerales metálicos no ferrosos', 'active',
   '{"plan": "enterprise", "max_users": 50, "max_facilities": 10}'),
  ('a0000000-0000-0000-0000-000000000002', 1, 'manager',
   '76.987.654-3', 'EcoGestión Consultoría Ambiental Ltda', 'EcoGestión',
   'Consultoría en gestión ambiental y cumplimiento normativo', 'active',
   '{"plan": "professional", "max_users": 20, "max_facilities": 5}')
ON CONFLICT (id) DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
--  3. INSTALACIONES (Minera Andes)
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO facilities (id, tenant_id, code, name, facility_type, address, region_code, commune_code, latitude, longitude, environmental_identifiers, active) VALUES
  ('b0000000-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'PLT-CALA', 'Planta Calama', 'planta_procesamiento',
   'Ruta 24, Km 35, Calama', 'II', '02101',
   -22.456789, -68.924561,
   '{"rca": "RCA-045/2018", "seia_id": "2018050001"}', true),
  ('b0000000-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000001',
   'MIN-ANTO', 'Faena Antofagasta', 'faena_minera',
   'Sector Sierra Gorda, Antofagasta', 'II', '02101',
   -23.654321, -69.123456,
   '{"rca": "RCA-112/2020", "seia_id": "2020030045"}', true),
  ('b0000000-0000-0000-0000-000000000003',
   'a0000000-0000-0000-0000-000000000001',
   'OFI-SCL', 'Oficina Santiago', 'oficina_administrativa',
   'Av. Apoquindo 4500, Las Condes, Santiago', 'RM', '13114',
   -33.417500, -70.605000,
   '{}', true)
ON CONFLICT (id) DO NOTHING;

-- Instalación de EcoGestión
INSERT INTO facilities (id, tenant_id, code, name, facility_type, address, region_code, commune_code, latitude, longitude, environmental_identifiers, active) VALUES
  ('b0000000-0000-0000-0000-000000000004',
   'a0000000-0000-0000-0000-000000000002',
   'OFI-ECOG', 'Oficina Central EcoGestión', 'oficina_administrativa',
   'Av. Providencia 1208, Providencia, Santiago', 'RM', '13123',
   -33.425000, -70.610000,
   '{}', true)
ON CONFLICT (id) DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
--  4. DEPARTAMENTOS
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO departments (id, tenant_id, facility_id, code, name, active) VALUES
  ('c0000000-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'b0000000-0000-0000-0000-000000000001',
   'DEP-MED', 'Medio Ambiente', true),
  ('c0000000-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000001',
   'b0000000-0000-0000-0000-000000000001',
   'DEP-OPS', 'Operaciones', true),
  ('c0000000-0000-0000-0000-000000000003',
   'a0000000-0000-0000-0000-000000000001',
   'b0000000-0000-0000-0000-000000000003',
   'DEP-LEG', 'Legal y Cumplimiento', true),
  ('c0000000-0000-0000-0000-000000000004',
   'a0000000-0000-0000-0000-000000000002',
   'b0000000-0000-0000-0000-000000000004',
   'DEP-CONS', 'Consultoría', true)
ON CONFLICT (id) DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
--  5. USUARIOS
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO users (id, tenant_id, department_id, rut_tax_id, email, full_name, user_type, status, password_hash, preferences) VALUES
  -- Admin Empresa - Minera Andes
  ('d0000000-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'c0000000-0000-0000-0000-000000000003',
   '12.345.678-9', 'carlos.mendoza@mineraandes.cl', 'Carlos Mendoza Reyes',
   'tenant_admin', 'active',
   '$2b$12$LJ3m5ZQnJPfDLkGjzEKMXeJHvBqMKczKz5Q5Q5Q5Q5Q5Q5Q5Q5Q5Q',
   '{"language": "es", "timezone": "America/Santiago", "notifications": {"email": true, "push": true}}'),

  -- Encargado Medio Ambiente - Minera Andes
  ('d0000000-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000001',
   'c0000000-0000-0000-0000-000000000001',
   '13.456.789-0', 'maria.silva@mineraandes.cl', 'María Silva Contreras',
   'internal', 'active',
   '$2b$12$LJ3m5ZQnJPfDLkGjzEKMXeJHvBqMKczKz5Q5Q5Q5Q5Q5Q5Q5Q5Q5Q',
   '{"language": "es", "timezone": "America/Santiago"}'),

  -- Operador - Minera Andes
  ('d0000000-0000-0000-0000-000000000003',
   'a0000000-0000-0000-0000-000000000001',
   'c0000000-0000-0000-0000-000000000002',
   '14.567.890-1', 'pedro.gonzalez@mineraandes.cl', 'Pedro González Muñoz',
   'internal', 'active',

   '$2b$12$LJ3m5ZQnJPfDLkGjzEKMXeJHvBqMKczKz5Q5Q5Q5Q5Q5Q5Q5Q5Q5Q',
   '{"language": "es", "timezone": "America/Santiago"}'),

  -- Admin Empresa - EcoGestión
  ('d0000000-0000-0000-0000-000000000004',
   'a0000000-0000-0000-0000-000000000002',
   'c0000000-0000-0000-0000-000000000004',
   '15.678.901-2', 'ana.rojas@ecogestion.cl', 'Ana Rojas Figueroa',
   'tenant_admin', 'active',
   '$2b$12$LJ3m5ZQnJPfDLkGjzEKMXeJHvBqMKczKz5Q5Q5Q5Q5Q5Q5Q5Q5Q5Q',
   '{"language": "es", "timezone": "America/Santiago"}'),

  -- Consultor - EcoGestión
  ('d0000000-0000-0000-0000-000000000005',
   'a0000000-0000-0000-0000-000000000002',
   'c0000000-0000-0000-0000-000000000004',
   '16.789.012-3', 'jorge.martinez@ecogestion.cl', 'Jorge Martínez Soto',
   'internal', 'active',
   '$2b$12$LJ3m5ZQnJPfDLkGjzEKMXeJHvBqMKczKz5Q5Q5Q5Q5Q5Q5Q5Q5Q5Q',
   '{"language": "es", "timezone": "America/Santiago"}')
ON CONFLICT (id) DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
--  6. ROLES Y PERMISOS
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO permissions (id, code, module, description) VALUES
  (1, 'dashboard.view', 'dashboard', 'Ver dashboard principal'),
  (2, 'matrix.view', 'compliance', 'Ver matriz legal'),
  (3, 'matrix.edit', 'compliance', 'Editar matriz legal'),
  (4, 'obligations.view', 'obligations', 'Ver obligaciones'),
  (5, 'obligations.edit', 'obligations', 'Crear y editar obligaciones'),
  (6, 'obligations.submit', 'obligations', 'Enviar declaraciones'),
  (7, 'audits.view', 'audits', 'Ver auditorías'),
  (8, 'audits.edit', 'audits', 'Crear y editar auditorías'),
  (9, 'users.view', 'admin', 'Ver usuarios'),
  (10, 'users.edit', 'admin', 'Gestionar usuarios'),
  (11, 'settings.edit', 'admin', 'Editar configuración de empresa'),
  (12, 'reports.view', 'reports', 'Ver reportes'),
  (13, 'reports.export', 'reports', 'Exportar reportes'),
  (14, 'catalog.view', 'catalog', 'Ver catálogo normativo'),
  (15, 'catalog.edit', 'catalog', 'Editar catálogo normativo (admin global)'),
  (16, 'tenants.manage', 'admin', 'Gestionar tenants (admin global)'),
  (17, 'support.view', 'support', 'Ver tickets de soporte'),
  (18, 'support.edit', 'support', 'Gestionar tickets de soporte'),
  (19, 'documents.view', 'documents', 'Ver documentos'),
  (20, 'documents.edit', 'documents', 'Subir y editar documentos')
ON CONFLICT (id) DO NOTHING;

-- Roles para Minera Andes
INSERT INTO roles (id, tenant_id, code, name, is_system, description) VALUES
  ('e0000000-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'admin_empresa', 'Administrador de Empresa', true,
   'Acceso total a la gestión de la empresa'),
  ('e0000000-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000001',
   'encargado_ambiental', 'Encargado Ambiental', true,
   'Gestión de cumplimiento y obligaciones'),
  ('e0000000-0000-0000-0000-000000000003',
   'a0000000-0000-0000-0000-000000000001',
   'operador', 'Operador', true,
   'Acceso de solo lectura y ejecución de tareas asignadas')
ON CONFLICT (id) DO NOTHING;

-- Permisos por rol
INSERT INTO role_permissions (role_id, permission_id, granted) VALUES
  -- Admin empresa: todos los permisos excepto admin global
  ('e0000000-0000-0000-0000-000000000001', 1, true),
  ('e0000000-0000-0000-0000-000000000001', 2, true),
  ('e0000000-0000-0000-0000-000000000001', 3, true),
  ('e0000000-0000-0000-0000-000000000001', 4, true),
  ('e0000000-0000-0000-0000-000000000001', 5, true),
  ('e0000000-0000-0000-0000-000000000001', 6, true),
  ('e0000000-0000-0000-0000-000000000001', 7, true),
  ('e0000000-0000-0000-0000-000000000001', 8, true),
  ('e0000000-0000-0000-0000-000000000001', 9, true),
  ('e0000000-0000-0000-0000-000000000001', 10, true),
  ('e0000000-0000-0000-0000-000000000001', 11, true),
  ('e0000000-0000-0000-0000-000000000001', 12, true),
  ('e0000000-0000-0000-0000-000000000001', 13, true),
  ('e0000000-0000-0000-0000-000000000001', 14, true),
  ('e0000000-0000-0000-0000-000000000001', 17, true),
  ('e0000000-0000-0000-0000-000000000001', 19, true),
  ('e0000000-0000-0000-0000-000000000001', 20, true),
  -- Encargado ambiental
  ('e0000000-0000-0000-0000-000000000002', 1, true),
  ('e0000000-0000-0000-0000-000000000002', 2, true),
  ('e0000000-0000-0000-0000-000000000002', 3, true),
  ('e0000000-0000-0000-0000-000000000002', 4, true),
  ('e0000000-0000-0000-0000-000000000002', 5, true),
  ('e0000000-0000-0000-0000-000000000002', 6, true),
  ('e0000000-0000-0000-0000-000000000002', 7, true),
  ('e0000000-0000-0000-0000-000000000002', 12, true),
  ('e0000000-0000-0000-0000-000000000002', 14, true),
  ('e0000000-0000-0000-0000-000000000002', 19, true),
  ('e0000000-0000-0000-0000-000000000002', 20, true),
  -- Operador
  ('e0000000-0000-0000-0000-000000000003', 1, true),
  ('e0000000-0000-0000-0000-000000000003', 2, true),
  ('e0000000-0000-0000-0000-000000000003', 4, true),
  ('e0000000-0000-0000-0000-000000000003', 7, true),
  ('e0000000-0000-0000-0000-000000000003', 19, true)
ON CONFLICT DO NOTHING;

-- Asignación de roles a usuarios
INSERT INTO user_roles (user_id, role_id, tenant_id) VALUES
  ('d0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001'),
  ('d0000000-0000-0000-0000-000000000002', 'e0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001'),
  ('d0000000-0000-0000-0000-000000000003', 'e0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001')
ON CONFLICT DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
--  7. CATÁLOGO NORMATIVO (normas chilenas reales)
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO legal_sources (id, country_id, code, name, base_url) VALUES
  (1, 1, 'BCN', 'Biblioteca del Congreso Nacional', 'https://www.bcn.cl/leychile'),
  (2, 1, 'SMA', 'Superintendencia del Medio Ambiente', 'https://www.sma.gob.cl'),
  (3, 1, 'RETC', 'Registro de Emisiones y Transferencias de Contaminantes', 'https://www.retc.cl')
ON CONFLICT (id) DO NOTHING;

INSERT INTO sectors (id, code, name) VALUES
  (1, 'MIN', 'Minería'),
  (2, 'IND', 'Industria manufacturera'),
  (3, 'ENE', 'Energía'),
  (4, 'AGR', 'Agricultura y ganadería'),
  (5, 'GEN', 'Aplicación general')
ON CONFLICT (id) DO NOTHING;

INSERT INTO legal_norms (id, country_id, source_id, norm_type, norm_number, title, subjects, publication_date, status) VALUES
  ('f1000000-0000-0000-0000-000000000001', 1,
   1,
   'ley', '19300', 'Ley sobre Bases Generales del Medio Ambiente',
   ARRAY['medio ambiente','protección ambiental','SEIA'],
   '1994-03-09', 'vigente'),
  ('f1000000-0000-0000-0000-000000000002', 1,
   1,
   'decreto_supremo', '40/2012', 'Reglamento del Sistema de Evaluación de Impacto Ambiental',
   ARRAY['SEIA','evaluación ambiental','EIA','DIA'],
   '2013-12-30', 'vigente'),
  ('f1000000-0000-0000-0000-000000000003', 1,
   1,
   'decreto_supremo', '13/2011', 'Norma de Emisión para Centrales Termoeléctricas',
   ARRAY['emisiones atmosféricas','termoeléctricas','calidad del aire'],
   '2011-06-23', 'vigente'),
  ('f1000000-0000-0000-0000-000000000004', 1,
   1,
   'decreto_supremo', '148/2003', 'Reglamento Sanitario sobre Manejo de Residuos Peligrosos',
   ARRAY['residuos peligrosos','RESPEL','SIDREP'],
   '2004-06-16', 'vigente'),
  ('f1000000-0000-0000-0000-000000000005', 1,
   1,
   'ley', '20920', 'Ley Marco para la Gestión de Residuos, la Responsabilidad Extendida del Productor y Fomento al Reciclaje (Ley REP)',
   ARRAY['REP','reciclaje','residuos','responsabilidad extendida'],
   '2016-06-01', 'vigente'),
  ('f1000000-0000-0000-0000-000000000006', 1,
   2,
   'decreto_supremo', '90/2000', 'Norma de Emisión para la Regulación de Contaminantes Asociados a las Descargas de Residuos Líquidos',
   ARRAY['RILes','aguas superficiales','descargas líquidas'],
   '2001-03-07', 'vigente'),
  ('f1000000-0000-0000-0000-000000000007', 1,
   1,
   'decreto_supremo', '38/2011', 'Norma de Emisión de Ruidos',
   ARRAY['ruido','emisión sonora','contaminación acústica'],
   '2011-11-12', 'vigente'),
  ('f1000000-0000-0000-0000-000000000008', 1,
   3,
   'resolucion', 'RE-574/2019', 'Resolución que establece obligaciones de reporte al RETC',
   ARRAY['RETC','reporte','emisiones','transferencias'],
   '2019-08-15', 'vigente')
ON CONFLICT (id) DO NOTHING;

-- Versiones de normas
INSERT INTO legal_norm_versions (id, norm_id, version_label, valid_from, content_hash, is_current, change_summary) VALUES
  ('f2000000-0000-0000-0000-000000000001', 'f1000000-0000-0000-0000-000000000001',
   'Texto refundido 2023', '2023-03-01', 'sha256_placeholder_001', true,
   'Incorpora modificaciones de Ley 21.595'),
  ('f2000000-0000-0000-0000-000000000002', 'f1000000-0000-0000-0000-000000000004',
   'Texto original', '2004-06-16', 'sha256_placeholder_002', true,
   'Texto original del DS 148'),
  ('f2000000-0000-0000-0000-000000000003', 'f1000000-0000-0000-0000-000000000005',
   'Texto original', '2016-06-01', 'sha256_placeholder_003', true,
   'Texto original Ley REP')
ON CONFLICT (id) DO NOTHING;

-- Artículos de ejemplo
INSERT INTO legal_articles (id, norm_version_id, article_type, article_number, heading, content, display_order) VALUES
  ('f3000000-0000-0000-0000-000000000001',
   'f2000000-0000-0000-0000-000000000001',
   'article', '10', 'Proyectos que requieren EIA',
   'Los proyectos o actividades susceptibles de causar impacto ambiental, en cualesquiera de sus fases, que deberán someterse al sistema de evaluación de impacto ambiental...', 1),
  ('f3000000-0000-0000-0000-000000000002',
   'f2000000-0000-0000-0000-000000000001',
   'article', '11', 'Circunstancias que requieren EIA',
   'Los proyectos o actividades enumerados en el artículo precedente requerirán la elaboración de un Estudio de Impacto Ambiental...', 2),
  ('f3000000-0000-0000-0000-000000000003',
   'f2000000-0000-0000-0000-000000000002',
   'article', '5', 'Clasificación de residuos peligrosos',
   'Se considerará residuo peligroso aquel que presente o pueda presentar riesgo para la salud pública y/o efectos adversos al medio ambiente...', 1),
  ('f3000000-0000-0000-0000-000000000004',
   'f2000000-0000-0000-0000-000000000002',
   'article', '25', 'Declaración de residuos peligrosos',
   'Todo generador de residuos peligrosos deberá presentar una Declaración ante la Autoridad Sanitaria...', 2)
ON CONFLICT (id) DO NOTHING;

-- Sectores de normas
INSERT INTO norm_sectors (norm_id, sector_id) VALUES
  ('f1000000-0000-0000-0000-000000000001', 5),
  ('f1000000-0000-0000-0000-000000000002', 5),
  ('f1000000-0000-0000-0000-000000000003', 3),
  ('f1000000-0000-0000-0000-000000000004', 5),
  ('f1000000-0000-0000-0000-000000000005', 5),
  ('f1000000-0000-0000-0000-000000000006', 1),
  ('f1000000-0000-0000-0000-000000000006', 2),
  ('f1000000-0000-0000-0000-000000000007', 5),
  ('f1000000-0000-0000-0000-000000000008', 1),
  ('f1000000-0000-0000-0000-000000000008', 2)
ON CONFLICT DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
--  8. MATRIZ LEGAL (Minera Andes)
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO tenant_legal_matrices (id, tenant_id, name, period_year, status, approved_at, approved_by) VALUES
  ('a0000010-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'Matriz Legal Ambiental 2026', 2026, 'approved',
   '2026-02-15 10:00:00-03', 'd0000000-0000-0000-0000-000000000001')
ON CONFLICT (id) DO NOTHING;

INSERT INTO matrix_norms (id, matrix_id, norm_id, tenant_id, selected_version_id, applicability, applicability_reason, review_frequency) VALUES
  ('a0000011-0000-0000-0000-000000000001',
   'a0000010-0000-0000-0000-000000000001',
   'f1000000-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'f2000000-0000-0000-0000-000000000001',
   'applicable', 'Aplica a todas las operaciones de la minera', 'annual'),
  ('a0000011-0000-0000-0000-000000000002',
   'a0000010-0000-0000-0000-000000000001',
   'f1000000-0000-0000-0000-000000000004',
   'a0000000-0000-0000-0000-000000000001',
   'f2000000-0000-0000-0000-000000000002',
   'applicable', 'Generación de residuos peligrosos en planta Calama', 'semiannual'),
  ('a0000011-0000-0000-0000-000000000003',
   'a0000010-0000-0000-0000-000000000001',
   'f1000000-0000-0000-0000-000000000005',
   'a0000000-0000-0000-0000-000000000001',
   'f2000000-0000-0000-0000-000000000003',
   'applicable', 'Responsabilidad extendida sobre neumáticos y aceites usados', 'annual'),
  ('a0000011-0000-0000-0000-000000000004',
   'a0000010-0000-0000-0000-000000000001',
   'f1000000-0000-0000-0000-000000000006',
   'a0000000-0000-0000-0000-000000000001',
   'f2000000-0000-0000-0000-000000000001',
   'applicable', 'Descargas de riles en planta de procesamiento', 'quarterly'),
  ('a0000011-0000-0000-0000-000000000005',
   'a0000010-0000-0000-0000-000000000001',
   'f1000000-0000-0000-0000-000000000008',
   'a0000000-0000-0000-0000-000000000001',
   'f2000000-0000-0000-0000-000000000001',
   'applicable', 'Reporte anual al RETC', 'annual')
ON CONFLICT (id) DO NOTHING;

-- Asignación de normas a instalaciones
INSERT INTO facility_norm_assignments (id, tenant_id, facility_id, norm_id, assigned_by, assignment_status, source) VALUES
  ('a0000012-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'b0000000-0000-0000-0000-000000000001',
   'f1000000-0000-0000-0000-000000000004',
   'd0000000-0000-0000-0000-000000000002', 'assigned', 'manual'),
  ('a0000012-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000001',
   'b0000000-0000-0000-0000-000000000001',
   'f1000000-0000-0000-0000-000000000006',
   'd0000000-0000-0000-0000-000000000002', 'assigned', 'manual'),
  ('a0000012-0000-0000-0000-000000000003',
   'a0000000-0000-0000-0000-000000000001',
   'b0000000-0000-0000-0000-000000000002',
   'f1000000-0000-0000-0000-000000000007',
   'd0000000-0000-0000-0000-000000000002', 'assigned', 'manual')
ON CONFLICT (id) DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
--  9. OBLIGACIONES Y TAREAS
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO obligation_templates (id, country_id, code, name, authority, frequency_rule, default_lead_days) VALUES
  ('a0000020-0000-0000-0000-000000000001', 1,
   'RETC-ANUAL', 'Declaración anual RETC',
   'Ministerio del Medio Ambiente',
   '{"type": "annual", "month": 3, "day": 31}', 60),
  ('a0000020-0000-0000-0000-000000000002', 1,
   'SIDREP-SEM', 'Declaración semestral SIDREP (residuos peligrosos)',
   'Ministerio de Salud / SEREMI',
   '{"type": "semiannual", "months": [1, 7], "day": 15}', 30),
  ('a0000020-0000-0000-0000-000000000003', 1,
   'DS90-TRIM', 'Monitoreo trimestral de RILes (DS 90)',
   'Superintendencia de Servicios Sanitarios',
   '{"type": "quarterly", "day": 15}', 15)
ON CONFLICT (id) DO NOTHING;

-- **Los vencimientos son relativos a hoy, no fechas fijas.**
--
-- Estaban escritos como '2026-09-30 23:59:00-03' y compania, y eso envejece: el
-- 4-sep-2026 el vencimiento mas cercano quedaba a 27 dias, o sea **fuera de las
-- cuatro ventanas de aviso** (15/7/3/1). El cron de avisos corria sobre esta
-- base y no generaba nada. Unos meses mas y las cinco quedan en el pasado: la
-- demostracion de vencimientos deja de existir sin que nada falle.
--
-- Se conservan las distancias que tenian entre si —el ancla se pone a 15 dias y
-- el resto guarda su separacion original— asi que las relaciones que el autor
-- construyo (que semestre vence antes que cual) siguen valiendo. Lo unico que
-- se mueve es "hoy".
--
-- Efecto buscado: la mas cercana entra hoy en la ventana de 15 y va bajando a 7,
-- 3 y 1 los dias siguientes, asi que la demostracion produce avisos nuevos
-- varias veces y no una sola.
--
-- Ojo: esto corre **al crear la base**. Una base que ya existe se reancla con
-- `python -m app.tareas.sembrar_demo`.
INSERT INTO obligations (id, tenant_id, template_id, matrix_norm_id, facility_id, code, title, period_start, period_end, due_at, status, owner_user_id) VALUES
  ('a0000021-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'a0000020-0000-0000-0000-000000000001',
   'a0000011-0000-0000-0000-000000000005',
   'b0000000-0000-0000-0000-000000000001',
   'OBL-RETC-2026', 'Declaración RETC 2026',
   '2026-01-01', '2026-12-31', ((CURRENT_DATE + 197) + TIME '23:59') AT TIME ZONE 'America/Santiago',
   'in_progress', 'd0000000-0000-0000-0000-000000000002'),

  ('a0000021-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000001',
   'a0000020-0000-0000-0000-000000000002',
   'a0000011-0000-0000-0000-000000000002',
   'b0000000-0000-0000-0000-000000000001',
   'OBL-SIDREP-2026S1', 'Declaración SIDREP 1er Semestre 2026',
   '2026-01-01', '2026-06-30', ((CURRENT_DATE -  62) + TIME '23:59') AT TIME ZONE 'America/Santiago',
   'submitted', 'd0000000-0000-0000-0000-000000000002'),

  ('a0000021-0000-0000-0000-000000000003',
   'a0000000-0000-0000-0000-000000000001',
   'a0000020-0000-0000-0000-000000000002',
   'a0000011-0000-0000-0000-000000000002',
   'b0000000-0000-0000-0000-000000000001',
   'OBL-SIDREP-2026S2', 'Declaración SIDREP 2do Semestre 2026',
   '2026-07-01', '2026-12-31', ((CURRENT_DATE + 122) + TIME '23:59') AT TIME ZONE 'America/Santiago',
   'draft', 'd0000000-0000-0000-0000-000000000002'),

  ('a0000021-0000-0000-0000-000000000004',
   'a0000000-0000-0000-0000-000000000001',
   'a0000020-0000-0000-0000-000000000003',
   'a0000011-0000-0000-0000-000000000004',
   'b0000000-0000-0000-0000-000000000001',
   'OBL-DS90-2026Q3', 'Monitoreo RILes Q3 2026',
   '2026-07-01', '2026-09-30', ((CURRENT_DATE +  30) + TIME '23:59') AT TIME ZONE 'America/Santiago',
   'open', 'd0000000-0000-0000-0000-000000000003'),

  ('a0000021-0000-0000-0000-000000000005',
   'a0000000-0000-0000-0000-000000000001',
   NULL, 'a0000011-0000-0000-0000-000000000003',
   'b0000000-0000-0000-0000-000000000001',
   'OBL-REP-NFU-2026', 'Plan de gestión NFU (Ley REP)',
   '2026-01-01', '2026-12-31', ((CURRENT_DATE +  15) + TIME '23:59') AT TIME ZONE 'America/Santiago',
   -- `open` y no `overdue`: vence en 15 dias. El estado anterior contradecia
   -- a su propia fecha desde el momento en que la fecha dejo de estar en el
   -- pasado, y se veia en pantalla como una obligacion vencida que no lo esta.
   'open', 'd0000000-0000-0000-0000-000000000002')
ON CONFLICT (id) DO NOTHING;

-- Tareas asociadas a obligaciones
INSERT INTO tasks (id, tenant_id, obligation_id, task_type, title, description, status, priority, assignee_user_id, department_id, due_at) VALUES
  ('a0000022-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'a0000021-0000-0000-0000-000000000001',
   'task', 'Recopilar datos de emisiones atmosféricas',
   'Consolidar mediciones de MP10, MP2.5, SO2, NOx de todas las fuentes', 'in_progress', 'high',
   'd0000000-0000-0000-0000-000000000003',
   'c0000000-0000-0000-0000-000000000002',
   '2026-08-31 23:59:00-03'),
  ('a0000022-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000001',
   'a0000021-0000-0000-0000-000000000001',
   'task', 'Recopilar datos de residuos generados',
   'Consolidar manifiestos de residuos peligrosos y no peligrosos', 'todo', 'medium',
   'd0000000-0000-0000-0000-000000000003',
   'c0000000-0000-0000-0000-000000000002',
   '2026-09-30 23:59:00-03'),
  ('a0000022-0000-0000-0000-000000000003',
   'a0000000-0000-0000-0000-000000000001',
   'a0000021-0000-0000-0000-000000000001',
   'approval', 'Revisión final declaración RETC',
   'Validar datos consolidados antes de envío', 'todo', 'high',
   'd0000000-0000-0000-0000-000000000002',
   'c0000000-0000-0000-0000-000000000001',
   '2027-03-15 23:59:00-03'),
  ('a0000022-0000-0000-0000-000000000004',
   'a0000000-0000-0000-0000-000000000001',
   'a0000021-0000-0000-0000-000000000004',
   'task', 'Toma de muestras RILes Q3',
   'Realizar muestreo compuesto en punto de descarga', 'todo', 'high',
   'd0000000-0000-0000-0000-000000000003',
   'c0000000-0000-0000-0000-000000000002',
   '2026-09-20 23:59:00-03')
ON CONFLICT (id) DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
-- 10. AUDITORÍAS
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO audits (id, tenant_id, facility_id, code, audit_type, title, scope, status, planned_start, planned_end, lead_auditor_user_id) VALUES
  ('a0000030-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'b0000000-0000-0000-0000-000000000001',
   'AUD-2026-001', 'internal', 'Auditoría Interna SGA Q2 2026',
   'Revisión de cumplimiento del SGA ISO 14001 en Planta Calama',
   'closed', '2026-06-01', '2026-06-05',
   'd0000000-0000-0000-0000-000000000002'),
  ('a0000030-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000001',
   'b0000000-0000-0000-0000-000000000002',
   'AUD-2026-002', 'regulatory', 'Fiscalización SMA - Faena Antofagasta',
   'Fiscalización programada de la SMA a la faena minera',
   'planned', '2026-09-15', '2026-09-17',
   NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO audit_participants (audit_id, user_id, tenant_id, participant_role) VALUES
  ('a0000030-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'lead_auditor'),
  ('a0000030-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'auditee'),
  ('a0000030-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'auditee')
ON CONFLICT DO NOTHING;

INSERT INTO audit_items (id, audit_id, tenant_id, sequence, question, result, notes) VALUES
  ('a0000031-0000-0000-0000-000000000001',
   'a0000030-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   1, '¿Se han identificado los aspectos ambientales significativos? (ISO 14001:2015 §6.1.2)',
   'conform', 'Matriz de aspectos actualizada, registros de capacitación al día'),
  ('a0000031-0000-0000-0000-000000000002',
   'a0000030-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   2, '¿Se mantienen los controles operacionales de emisiones? (ISO 14001:2015 §8.1)',
   'nonconform', 'Registros de mantenimiento de filtros sin actualizar desde abril'),
  ('a0000031-0000-0000-0000-000000000003',
   'a0000030-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   3, '¿El almacenamiento temporal de RESPEL cumple con DS 148 Art. 25?',
   'observation', 'Señalética de bodega RESPEL parcialmente ilegible')
ON CONFLICT (id) DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
-- 11. NO CONFORMIDADES Y PLANES DE ACCIÓN
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO nonconformities (id, tenant_id, audit_item_id, facility_id, code, title, description, severity, status, detected_at, owner_user_id) VALUES
  ('a0000040-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'a0000031-0000-0000-0000-000000000002',
   'b0000000-0000-0000-0000-000000000001',
   'NC-2026-001', 'Registros de mantenimiento de filtros desactualizados',
   'Los registros de mantenimiento preventivo de filtros de manga no se han actualizado desde abril 2026, incumpliendo el procedimiento PMA-OPS-012.',
   'minor', 'action_plan', '2026-06-03',
   'd0000000-0000-0000-0000-000000000003')
ON CONFLICT (id) DO NOTHING;

INSERT INTO action_plans (id, tenant_id, nonconformity_id, title, root_cause, objective, owner_user_id, target_date, status, priority) VALUES
  ('a0000041-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'a0000040-0000-0000-0000-000000000001',
   'Actualizar registros de mantenimiento de filtros',
   'Falta de supervisión del registro digital de mantenimiento preventivo',
   'Completar los registros pendientes de abril a junio y digitalizar en sistema.',
   'd0000000-0000-0000-0000-000000000003',
   '2026-08-15', 'in_progress', 'high'),
  ('a0000041-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000001',
   'a0000040-0000-0000-0000-000000000001',
   'Capacitación en registro digital de mantenimiento',
   'Personal de operaciones no capacitado en el módulo digital',
   'Capacitar al equipo de operaciones en el uso del módulo de mantenimiento digital.',
   'd0000000-0000-0000-0000-000000000002',
   '2026-09-01', 'draft', 'medium')
ON CONFLICT (id) DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
-- 12. PROCESOS (ISO 14001)
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO processes (id, tenant_id, department_id, code, name, process_type, description, responsible_user_id, display_order, active) VALUES
  ('a0000050-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'c0000000-0000-0000-0000-000000000002',
   'PROC-CHANC', 'Chancado y Molienda', 'operational',
   'Reducción de tamaño del mineral mediante chancadores y molinos',
   'd0000000-0000-0000-0000-000000000003', 1, true),
  ('a0000050-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000001',
   'c0000000-0000-0000-0000-000000000002',
   'PROC-FLOT', 'Flotación', 'operational',
   'Separación de minerales por flotación en celdas',
   'd0000000-0000-0000-0000-000000000003', 2, true),
  ('a0000050-0000-0000-0000-000000000003',
   'a0000000-0000-0000-0000-000000000001',
   'c0000000-0000-0000-0000-000000000001',
   'PROC-MONIT', 'Monitoreo Ambiental', 'support',
   'Monitoreo de calidad de aire, agua y suelo',
   'd0000000-0000-0000-0000-000000000002', 3, true),
  ('a0000050-0000-0000-0000-000000000004',
   'a0000000-0000-0000-0000-000000000001',
   'c0000000-0000-0000-0000-000000000001',
   'PROC-RESPEL', 'Gestión de Residuos Peligrosos', 'support',
   'Manejo, almacenamiento temporal y disposición de RESPEL',
   'd0000000-0000-0000-0000-000000000002', 4, true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO facility_processes (facility_id, process_id, tenant_id, is_primary, scope_notes) VALUES
  ('b0000000-0000-0000-0000-000000000001', 'a0000050-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', true, 'Línea principal de chancado'),
  ('b0000000-0000-0000-0000-000000000001', 'a0000050-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', true, 'Circuito de flotación Cu-Mo'),
  ('b0000000-0000-0000-0000-000000000001', 'a0000050-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', false, NULL),
  ('b0000000-0000-0000-0000-000000000001', 'a0000050-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', false, NULL)
ON CONFLICT DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
-- 13. ASPECTOS AMBIENTALES Y RIESGOS (ISO 14001)
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO environmental_aspects (id, tenant_id, facility_id, process_id, activity, aspect, impact_type, operating_condition, severity_score, frequency_score, legal_score, total_score, significance, controls) VALUES
  ('a0000060-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'b0000000-0000-0000-0000-000000000001',
   'a0000050-0000-0000-0000-000000000001',
   'Chancado de mineral', 'Emisión de material particulado (MP10)',
   'Contaminación atmosférica', 'normal',
   7, 8, 3, 18, 'non_compliant',
   '[{"measure": "Filtros de manga"}, {"measure": "Supresión con agua"}, {"measure": "Monitoreo continuo"}]'),
  ('a0000060-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000001',
   'b0000000-0000-0000-0000-000000000001',
   'a0000050-0000-0000-0000-000000000004',
   'Gestión de residuos', 'Generación de residuos peligrosos',
   'Contaminación de suelo y agua', 'normal',
   8, 6, 6, 20, 'partial',
   '[{"measure": "Bodega RESPEL certificada"}, {"measure": "Manifiestos SIDREP"}, {"measure": "Capacitación anual"}]'),
  ('a0000060-0000-0000-0000-000000000003',
   'a0000000-0000-0000-0000-000000000001',
   'b0000000-0000-0000-0000-000000000001',
   'a0000050-0000-0000-0000-000000000002',
   'Flotación', 'Consumo de agua industrial',
   'Agotamiento del recurso hídrico', 'normal',
   5, 7, 3, 15, 'compliant',
   '[{"measure": "Recirculación de agua"}, {"measure": "Medidores de flujo"}]')
ON CONFLICT (id) DO NOTHING;

INSERT INTO risks_opportunities (id, tenant_id, code, entry_type, description, origin, risk_level, treatment, status, owner_user_id) VALUES
  ('a0000061-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'R-2026-001', 'risk',
   'Riesgo de sanción SMA por no cumplir condiciones de la RCA-045/2018 en planta Calama',
   'compliance', 'critical', 'mitigate',
   'in_treatment', 'd0000000-0000-0000-0000-000000000002'),
  ('a0000061-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000001',
   'O-2026-001', 'opportunity',
   'Obtener certificación ISO 14001 mejora imagen corporativa y acceso a mercados internacionales',
   'context', 'high', 'exploit',
   'identified', 'd0000000-0000-0000-0000-000000000001')
ON CONFLICT (id) DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
-- 14. EQUIPOS REGULADOS
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO regulated_equipment (id, tenant_id, facility_id, name, equipment_type, brand, model, registration_authority, registration_number, registration_expires_at, status, technical_specs) VALUES
  ('a0000070-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'b0000000-0000-0000-0000-000000000001',
   'Caldera de vapor principal', 'caldera',
   'Babcock & Wilcox', 'FW-15',
   'SEC', 'SEC-II-2024-0451', '2026-09-15',
   'operational', '{"capacity": "15 ton/hr", "fuel": "gas_natural", "norm": "DS 48/1984"}'),
  ('a0000070-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000001',
   'b0000000-0000-0000-0000-000000000001',
   'Estanque de petróleo diésel', 'estanque_combustible',
   'Isisan', 'TK-50000',
   'SEC', 'SEC-II-2024-0892', '2027-01-20',
   'operational', '{"capacity_liters": 50000, "type": "superficial", "norm": "DS 160/2008"}')
ON CONFLICT (id) DO NOTHING;

INSERT INTO equipment_operators (equipment_id, user_id, tenant_id, certification_class, certification_number, certification_expires_at, is_primary) VALUES
  ('a0000070-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'Operador Clase B', 'CERT-2024-1234', '2027-03-15', true),
  ('a0000070-0000-0000-0000-000000000002', 'd0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'Operador Clase C', 'CERT-2024-5678', '2027-01-20', true)
ON CONFLICT DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
-- 15. CONTRATO (Minera Andes ↔ EcoGestión)
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO contracts (id, tenant_id, manager_tenant_id, client_tenant_id, contract_number, title, status, start_date, end_date, scope) VALUES
  ('a0000080-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000001',
   'ECOG-2026-001', 'Asesoría en cumplimiento ambiental Minera Andes',
   'active', '2026-01-01', '2026-12-31',
   '{"services": ["Matriz legal", "Auditoría interna", "Reportes RETC", "Capacitación"]}')
ON CONFLICT (id) DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
-- 16. NOTIFICACIONES
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO notification_templates (id, tenant_id, code, name, event_type, channel, subject_template, body_template) VALUES
  ('a0000090-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'OBL_VENCIMIENTO', 'Obligación próxima a vencer', 'obligation_due', 'email',
   'Obligación {{obligation_code}} vence en {{days_remaining}} días',
   'La obligación "{{obligation_title}}" asignada a {{facility_name}} vence el {{due_date}}. Por favor tome las acciones necesarias.'),
  ('a0000090-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000001',
   'AUDIT_PROGRAMADA', 'Auditoría programada', 'audit_scheduled', 'email',
   'Auditoría programada: {{audit_title}}',
   'Se ha programado la auditoría "{{audit_title}}" para el período {{start_date}} - {{end_date}} en {{facility_name}}.'),
  ('a0000090-0000-0000-0000-000000000003',
   'a0000000-0000-0000-0000-000000000001',
   'NC_NUEVA', 'Nueva no conformidad', 'nc_created', 'in_app',
   'No conformidad detectada: {{nc_code}}',
   'Se ha registrado la no conformidad "{{nc_title}}" con severidad {{severity}}. Responsable: {{responsible_name}}.')
ON CONFLICT (id) DO NOTHING;

INSERT INTO notifications (id, tenant_id, recipient_user_id, channel, subject, body, status) VALUES
  ('a0000091-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'd0000000-0000-0000-0000-000000000002',
   'email',
   'Obligación OBL-REP-NFU-2026 vencida',
   'La obligación "Plan de gestión NFU (Ley REP)" asignada a Planta Calama venció el 30/09/2026. Requiere acción inmediata.',
   'sent'),
  ('a0000091-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000001',
   'd0000000-0000-0000-0000-000000000001',
   'in_app',
   'Fiscalización SMA programada para septiembre',
   'Se ha programado la fiscalización de la SMA en Faena Antofagasta del 15 al 17 de septiembre 2026.',
   'delivered'),
  ('a0000091-0000-0000-0000-000000000003',
   'a0000000-0000-0000-0000-000000000001',
   'd0000000-0000-0000-0000-000000000003',
   'in_app',
   'No conformidad NC-2026-001 detectada',
   'Registros de mantenimiento de filtros desactualizados. Severidad: menor. Por favor revise y tome acción.',
   'read')
ON CONFLICT (id) DO NOTHING;

-- Evaluacion de cumplimiento articulo por articulo.
-- Sin estas filas el Dashboard muestra 0% de cumplimiento: un cero correcto,
-- pero que no permite ver si el calculo funciona (riesgo #1 del design de
-- openspec/changes/dashboard-metricas-api).
--
-- Los cinco valores del CHECK quedan representados a proposito, porque cada
-- uno pesa distinto en el porcentaje:
--   compliant      -> numerador y denominador
--   non_compliant  -> solo denominador
--   partial        -> solo denominador (dos parciales no hacen un cumplido)
--   not_applicable -> fuera del calculo
--   pending        -> solo denominador (si no, una matriz a medio evaluar
--                     mostraria 100%)
-- Con estas filas: 6 articulos, 1 no aplica -> denominador 5, cumplen 2,
-- es decir 40,0%.
INSERT INTO article_compliance (id, tenant_id, matrix_norm_id, article_id, facility_id, compliance_status, assessment_reason) VALUES
  ('a0000012-0000-0000-0000-000000000001',
   'a0000000-0000-0000-0000-000000000001',
   'a0000011-0000-0000-0000-000000000001',
   'f3000000-0000-0000-0000-000000000001',
   'b0000000-0000-0000-0000-000000000001',
   'compliant', 'Monitoreo de emisiones al dia, informes trimestrales presentados.'),
  ('a0000012-0000-0000-0000-000000000002',
   'a0000000-0000-0000-0000-000000000001',
   'a0000011-0000-0000-0000-000000000001',
   'f3000000-0000-0000-0000-000000000002',
   'b0000000-0000-0000-0000-000000000001',
   'compliant', 'Registros de calibracion vigentes.'),
  ('a0000012-0000-0000-0000-000000000003',
   'a0000000-0000-0000-0000-000000000001',
   'a0000011-0000-0000-0000-000000000001',
   'f3000000-0000-0000-0000-000000000003',
   'b0000000-0000-0000-0000-000000000001',
   'non_compliant', 'Falta el registro de disposicion final del ultimo semestre.'),
  ('a0000012-0000-0000-0000-000000000004',
   'a0000000-0000-0000-0000-000000000001',
   'a0000011-0000-0000-0000-000000000001',
   'f3000000-0000-0000-0000-000000000004',
   'b0000000-0000-0000-0000-000000000001',
   'not_applicable', 'La faena no opera fuentes fijas de este tipo.'),
  ('a0000012-0000-0000-0000-000000000005',
   'a0000000-0000-0000-0000-000000000001',
   'a0000011-0000-0000-0000-000000000002',
   'f3000000-0000-0000-0000-000000000001',
   'b0000000-0000-0000-0000-000000000001',
   'partial', 'Procedimiento existe pero no se ha capacitado a todo el personal.'),
  ('a0000012-0000-0000-0000-000000000006',
   'a0000000-0000-0000-0000-000000000001',
   'a0000011-0000-0000-0000-000000000002',
   'f3000000-0000-0000-0000-000000000002',
   'b0000000-0000-0000-0000-000000000001',
   'pending', 'Pendiente de evaluar en la revision de agosto.')
ON CONFLICT (id) DO NOTHING;

COMMIT;
