-- ============================================================
-- DDL - Eleições Autárquicas 2021
-- Base de Dados: SQLite
-- ============================================================

-- ============================================================
-- TABELAS GEOGRÁFICAS
-- ============================================================

-- Distritos / Regiões Autónomas
CREATE TABLE IF NOT EXISTS districts (
    name TEXT PRIMARY KEY,
    geom TEXT  -- Geometria em formato WKT (POLYGON/MULTIPOLYGON)
);

-- Municípios
CREATE TABLE IF NOT EXISTS municipalities (
    name TEXT,
    district_island TEXT,
    geom TEXT,  -- Geometria em formato WKT
    PRIMARY KEY (name, district_island),
    FOREIGN KEY (district_island) REFERENCES districts(name)
);

-- Freguesias
CREATE TABLE IF NOT EXISTS parishes (
    name TEXT,
    municipality_name TEXT,
    district_island TEXT,
    geom TEXT,  -- Geometria em formato WKT
    PRIMARY KEY (name, municipality_name),
    FOREIGN KEY (municipality_name, district_island) 
        REFERENCES municipalities(name, district_island)
);

-- ============================================================
-- TABELAS DE REFERÊNCIA
-- ============================================================

-- Partidos políticos
CREATE TABLE IF NOT EXISTS partidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sigla TEXT UNIQUE NOT NULL,
    nome TEXT
);

-- Órgãos autárquicos (CM, AM, AF)
CREATE TABLE IF NOT EXISTS orgaos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sigla TEXT UNIQUE NOT NULL,
    nome TEXT
);

-- Coligações eleitorais
CREATE TABLE IF NOT EXISTS coligacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sigla TEXT NOT NULL,           -- Sigla única da coligação
    nome_completo TEXT,            -- Nome completo (do mapa_anexo)
    municipio TEXT,                -- Município onde concorreu
    distrito TEXT,                 -- Distrito
    UNIQUE(sigla, municipio, distrito)
);

-- ============================================================
-- TABELAS DE RESULTADOS
-- ============================================================

-- Resultados agregados por autarquia
CREATE TABLE IF NOT EXISTS resultados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    municipio_nome TEXT NOT NULL,
    distrito_nome TEXT NOT NULL,
    freguesia_nome TEXT,           -- NULL para resultados CM
    orgao_id INTEGER NOT NULL,
    dicofre TEXT,                  -- Código DICOFRE
    inscritos INTEGER,
    votantes INTEGER,
    brancos INTEGER,
    nulos INTEGER,
    FOREIGN KEY (orgao_id) REFERENCES orgaos(id)
);

-- Votos por partido/coligação
CREATE TABLE IF NOT EXISTS votos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resultado_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,            -- 'partido' ou 'coligacao'
    sigla TEXT NOT NULL,           -- Sigla do partido ou coligação
    votos INTEGER DEFAULT 0,
    mandatos INTEGER DEFAULT 0,    -- Número de mandatos/seats atribuídos
    FOREIGN KEY (resultado_id) REFERENCES resultados(id)
);

-- ============================================================
-- ÍNDICES PARA PERFORMANCE
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_resultados_orgao 
    ON resultados(orgao_id);

CREATE INDEX IF NOT EXISTS idx_resultados_municipio 
    ON resultados(municipio_nome, distrito_nome);

CREATE INDEX IF NOT EXISTS idx_resultados_freguesia 
    ON resultados(freguesia_nome, municipio_nome);

CREATE INDEX IF NOT EXISTS idx_votos_resultado 
    ON votos(resultado_id);

CREATE INDEX IF NOT EXISTS idx_votos_sigla 
    ON votos(sigla);

CREATE INDEX IF NOT EXISTS idx_parishes_municipality 
    ON parishes(municipality_name);

CREATE INDEX IF NOT EXISTS idx_municipalities_district 
    ON municipalities(district_island);

-- ============================================================
-- DADOS INICIAIS
-- ============================================================

-- Órgãos autárquicos
INSERT OR IGNORE INTO orgaos (sigla, nome) VALUES 
    ('CM', 'Câmara Municipal'),
    ('AM', 'Assembleia Municipal'),
    ('AF', 'Assembleia de Freguesia');

-- Partidos políticos (21 partidos)
INSERT OR IGNORE INTO partidos (sigla, nome) VALUES
    ('A', 'Aliança'),
    ('B.E.', 'Bloco de Esquerda'),
    ('CDS-PP', 'CDS - Partido Popular'),
    ('CH', 'Chega'),
    ('E', 'Ergue-te'),
    ('IL', 'Iniciativa Liberal'),
    ('JPP', 'Juntos pelo Povo'),
    ('L', 'LIVRE'),
    ('MAS', 'Movimento Alternativa Socialista'),
    ('MPT', 'Partido da Terra'),
    ('NC', 'Nós, Cidadãos!'),
    ('PAN', 'Pessoas-Animais-Natureza'),
    ('PCTP/MRPP', 'PCTP/MRPP'),
    ('PDR', 'Partido Democrático Republicano'),
    ('PPD/PSD', 'Partido Social Democrata'),
    ('PPM', 'Partido Popular Monárquico'),
    ('PS', 'Partido Socialista'),
    ('PTP', 'Partido Trabalhista Português'),
    ('R.I.R.', 'Reagir Incluir Reciclar'),
    ('VP', 'Volt Portugal'),
    ('PCP-PEV', 'CDU - Coligação Democrática Unitária');

-- ============================================================
-- VIEWS ÚTEIS
-- ============================================================

-- View: Resultados CM com vencedor
CREATE VIEW IF NOT EXISTS v_cm_vencedores AS
SELECT 
    r.municipio_nome,
    r.distrito_nome,
    r.inscritos,
    r.votantes,
    v.sigla AS vencedor,
    v.votos AS votos_vencedor,
    ROUND(v.votos * 100.0 / (r.votantes - r.brancos - r.nulos), 2) AS percentagem
FROM resultados r
JOIN votos v ON v.resultado_id = r.id
WHERE r.orgao_id = 1
AND v.votos = (
    SELECT MAX(v2.votos) 
    FROM votos v2 
    WHERE v2.resultado_id = r.id
);

-- View: Totais nacionais por partido (CM)
CREATE VIEW IF NOT EXISTS v_totais_nacionais_cm AS
SELECT 
    v.sigla,
    SUM(v.votos) AS total_votos,
    COUNT(DISTINCT r.id) AS municipios_concorreu
FROM votos v
JOIN resultados r ON r.id = v.resultado_id
WHERE r.orgao_id = 1
GROUP BY v.sigla
ORDER BY total_votos DESC;
