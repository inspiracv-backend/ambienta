-- ═══════════════════════════════════════════════════════════════════════════
--  Datos semilla de los catalogos globales.
--
--  Solo catalogo compartido: paises, fuentes normativas, permisos, sectores y
--  plantillas de obligacion. Nada de datos de tenant.
--
--  Es idempotente (ON CONFLICT DO NOTHING): se puede volver a ejecutar sin
--  duplicar. Ejecutar despues de 01_schema.sql.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ── Paises ────────────────────────────────────────────────────────────────
-- Los cinco de PAISES en packages/shared. El sistema es multi-pais desde el
-- inicio (§3.2.2 del funcional), aunque Chile sea el primero.

INSERT INTO countries (iso2, iso3, name, default_timezone) VALUES
    ('CL','CHL','Chile',    'America/Santiago'),
    ('PE','PER','Peru',     'America/Lima'),
    ('CO','COL','Colombia', 'America/Bogota'),
    ('MX','MEX','Mexico',   'America/Mexico_City'),
    ('AR','ARG','Argentina','America/Argentina/Buenos_Aires')
ON CONFLICT (iso2) DO NOTHING;


-- ── Fuentes normativas ────────────────────────────────────────────────────

INSERT INTO legal_sources (country_id, code, name, base_url, connector_config)
SELECT c.id, v.code, v.name, v.base_url, v.cfg::jsonb
FROM (VALUES
    ('BCN_LEYCHILE', 'Biblioteca del Congreso Nacional — LeyChile',
     'https://www.leychile.cl',
     '{"xml_endpoint":"https://www.leychile.cl/Consulta/obtxml?opt=7","sparql":"https://datos.bcn.cl/sparql"}'),
    ('ISO',      'Normas ISO adquiridas por el tenant', NULL, '{"carga":"manual_pdf"}'),
    ('RCA',      'Resoluciones de Calificacion Ambiental', 'https://seia.sea.gob.cl', '{"carga":"manual_pdf"}'),
    ('INTERNAL', 'Normativa interna de la empresa', NULL, '{}')
) AS v(code, name, base_url, cfg)
CROSS JOIN countries c
WHERE c.iso2 = 'CL'
ON CONFLICT (code) DO NOTHING;


-- ── Permisos ──────────────────────────────────────────────────────────────
-- Un permiso por accion sensible de cada modulo. La matriz rol -> permiso la
-- define cada tenant; esto es solo el vocabulario disponible.

INSERT INTO permissions (code, module, description) VALUES
    ('company_profile.read',         'perfil_empresa',   'Ver el perfil de la empresa'),
    ('company_profile.write',        'perfil_empresa',   'Editar plantas, departamentos y datos de la empresa'),
    ('legal_matrix.read',            'matriz_legal',     'Ver la matriz legal'),
    ('legal_matrix.write',           'matriz_legal',     'Agregar o quitar normas de la matriz'),
    ('legal_matrix.article.evaluate','matriz_legal',     'Evaluar el cumplimiento de un articulo'),
    ('legal_matrix.approve',         'matriz_legal',     'Aprobar una matriz legal del periodo'),
    ('catalog.read',                 'catalogo',         'Consultar el catalogo normativo'),
    ('catalog.write',                'catalogo',         'Cargar RCAs e ISO del tenant'),
    ('obligation.read',              'obligaciones',     'Ver obligaciones y declaraciones'),
    ('obligation.write',             'obligaciones',     'Crear y editar obligaciones'),
    ('obligation.submit',            'obligaciones',     'Marcar una declaracion como presentada'),
    ('task.read',                    'tareas',           'Ver tareas del calendario y Gantt'),
    ('task.write',                   'tareas',           'Crear y reasignar tareas'),
    ('audit.read',                   'auditorias',       'Ver auditorias'),
    ('audit.write',                  'auditorias',       'Planificar y ejecutar auditorias'),
    ('nonconformity.read',           'no_conformidades', 'Ver hallazgos'),
    ('nonconformity.write',          'no_conformidades', 'Registrar y tratar hallazgos'),
    ('nonconformity.close',          'no_conformidades', 'Cerrar un hallazgo con firma'),
    ('action_plan.read',             'planes_accion',    'Ver planes de accion'),
    ('action_plan.write',            'planes_accion',    'Crear y verificar planes de accion'),
    ('document.read',                'documentos',       'Ver documentos y evidencias'),
    ('document.write',               'documentos',       'Subir y versionar evidencias'),
    ('environmental_aspect.read',    'iso_14001',        'Ver aspectos ambientales'),
    ('environmental_aspect.write',   'iso_14001',        'Registrar y evaluar aspectos ambientales'),
    ('risk_opportunity.read',        'iso_14001',        'Ver riesgos y oportunidades'),
    ('risk_opportunity.write',       'iso_14001',        'Registrar y tratar riesgos y oportunidades'),
    ('equipment.read',               'iso_14001',        'Ver equipos regulados'),
    ('equipment.write',              'iso_14001',        'Administrar equipos regulados y sus operadores'),
    ('report.generate',              'reportes',         'Generar y exportar reportes'),
    ('notification.configure',       'notificaciones',   'Configurar reglas y plantillas de notificacion'),
    ('user.read',                    'usuarios',         'Ver usuarios de la empresa'),
    ('user.write',                   'usuarios',         'Invitar, editar y desactivar usuarios'),
    ('role.manage',                  'usuarios',         'Administrar roles y permisos'),
    ('manager.read',                 'gestores',         'Ver clientes sub-tenant'),
    ('manager.write',                'gestores',         'Administrar contratos y sub-tenants'),
    ('chatbot.use',                  'chatbot',          'Usar el chatbot del tenant'),
    ('audit_log.read',               'historial',        'Consultar el historial de cambios'),
    ('platform.tenant.manage',       'plataforma',       'Administrar tenants (solo Superadmin)'),
    ('platform.support.manage',      'plataforma',       'Atender tickets de soporte (solo Superadmin)')
ON CONFLICT (code) DO NOTHING;


-- ── Sectores ──────────────────────────────────────────────────────────────
-- Taxonomia minima alineada a CIIU rev.4 a nivel de seccion. El detalle por
-- clase se carga cuando exista la tabla de mapeo CIIU -> normas, que hoy es
-- trabajo de datos pendiente.

INSERT INTO sectors (country_id, code, name, description)
SELECT c.id, v.code, v.name, v.descr
FROM (VALUES
    ('A', 'Agricultura, ganaderia, silvicultura y pesca', 'CIIU rev.4 seccion A'),
    ('B', 'Explotacion de minas y canteras',              'CIIU rev.4 seccion B'),
    ('C', 'Industria manufacturera',                      'CIIU rev.4 seccion C'),
    ('D', 'Suministro de electricidad y gas',             'CIIU rev.4 seccion D'),
    ('E', 'Suministro de agua y gestion de residuos',     'CIIU rev.4 seccion E'),
    ('F', 'Construccion',                                 'CIIU rev.4 seccion F'),
    ('G', 'Comercio al por mayor y menor',                'CIIU rev.4 seccion G'),
    ('H', 'Transporte y almacenamiento',                  'CIIU rev.4 seccion H')
) AS v(code, name, descr)
CROSS JOIN countries c
WHERE c.iso2 = 'CL'
ON CONFLICT (code) DO NOTHING;


-- ── Plantillas de obligacion ──────────────────────────────────────────────
-- Los sistemas sectoriales del RETC que nombra el funcional (§1.1).
-- `frequency_rule` usa RRULE; `default_lead_days` es la anticipacion del aviso.

INSERT INTO obligation_templates (country_id, code, name, authority, frequency_rule, default_lead_days, template_config)
SELECT c.id, v.code, v.name, v.authority, v.rrule, v.lead, v.cfg::jsonb
FROM (VALUES
    ('SIDREP',  'Declaracion de residuos peligrosos (SIDREP)',
     'Seremi de Salud', 'FREQ=MONTHLY;BYMONTHDAY=15', 15,
     '{"pestanas":["matriz_codigos","hoja_declaracion"]}'),
    ('SINADER', 'Declaracion de residuos no peligrosos (SINADER)',
     'Ministerio del Medio Ambiente', 'FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=1', 30,
     '{"pestanas":["matriz_codigos","hoja_declaracion"]}'),
    ('RETC',    'Reporte al Registro de Emisiones y Transferencias de Contaminantes',
     'Ministerio del Medio Ambiente', 'FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=1', 30,
     '{"pestanas":["matriz_codigos","hoja_declaracion"]}'),
    ('DAE',     'Declaracion de Emisiones Atmosfericas',
     'Superintendencia del Medio Ambiente', 'FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=31', 30,
     '{"pestanas":["matriz_codigos","hoja_declaracion"]}'),
    ('LEY_REP', 'Reporte Ley REP (Ley 20.920)',
     'Ministerio del Medio Ambiente', 'FREQ=YEARLY;BYMONTH=6;BYMONTHDAY=30', 45,
     '{"pestanas":["matriz_codigos","hoja_declaracion"]}'),
    ('RUEA',    'Registro Unico de Emisiones Atmosfericas',
     'Ministerio del Medio Ambiente', 'FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=1', 30, '{}')
) AS v(code, name, authority, rrule, lead, cfg)
CROSS JOIN countries c
WHERE c.iso2 = 'CL'
ON CONFLICT (code) DO NOTHING;

COMMIT;

-- Resumen de lo cargado
SELECT 'countries'            AS catalogo, count(*) FROM countries
UNION ALL SELECT 'legal_sources',        count(*) FROM legal_sources
UNION ALL SELECT 'permissions',          count(*) FROM permissions
UNION ALL SELECT 'sectors',              count(*) FROM sectors
UNION ALL SELECT 'obligation_templates', count(*) FROM obligation_templates;
