#!/usr/bin/env python3
"""
ETL Script - Eleições Autárquicas 2021
Versão final com mapeamento completo de nomes
"""

import sqlite3
import os
import unicodedata

try:
    import pandas as pd
except ImportError:
    print("ERRO: pip install pandas openpyxl")
    exit(1)

SQLITE_DB = "portugal_geoms.db"
CNE_FOLDER = "2021al_mapa_oficial"

PARTIDOS = ['A', 'B.E.', 'CDS-PP', 'CH', 'E', 'IL', 'JPP', 'L', 'MAS', 'MPT',
            'NC', 'PAN', 'PCTP/MRPP', 'PDR', 'PPD/PSD', 'PPM', 'PS', 'PTP',
            'R.I.R.', 'VP', 'PCP-PEV']

# Mapeamento de nomes de MUNICÍPIOS: Excel -> BD Geográfica
# Baseado nos códigos DICOFRE para distinguir municípios com mesmo nome
MUNICIPIOS_EXCEL_TO_BD = {
    # Aveiro
    "FEIRA": "Santa Maria da Feira",
    
    # Faro (código 08)
    "LAGOA": "Lagoa",
    
    # Madeira (código 31)
    "CALHETA (R.A.M.)": "Calheta",
    
    # Açores - São Miguel (código 42)
    "LAGOA (R.A.A)": "Lagoa",  # distrito_island = "Ilha de São Miguel"
    
    # Açores - São Jorge (código 45)
    "CALHETA (R.A.A.)": "Calheta de São Jorge",
    
    # Açores - Terceira (código 43)
    "VILA DA PRAIA DA VITÓRIA": "Praia da Vitória",
    
    # Açores - Corvo (código 49)
    "CORVO": "Corvo",
    
    # Açores - Graciosa (código 44)
    "SANTA CRUZ DA GRACIOSA": "Santa Cruz da Graciosa",
}

# Mapeamento de nomes de FREGUESIAS: Excel -> BD Geográfica
# Para casos onde o nome no Excel é diferente do nome na BD geográfica
FREGUESIAS_EXCEL_TO_BD = {
    # Amadora - formato do hífen
    ("Amadora", "FALAGUEIRA - VENDA NOVA"): "Falagueira-Venda Nova",
    
    # Arruda dos Vinhos - abreviatura diferente
    ("Arruda dos Vinhos", "SANTIAGO DOS VELHOS"): "S. Tiago dos Velhos",
    
    # Oleiros - formato do hífen
    ("Oleiros", "ESTREITO - VILAR BARROCO"): "Estreito-Vilar Barroco",
    ("Oleiros", "OLEIROS - AMIEIRA"): "Oleiros-Amieira",
    
    # Pampilhosa da Serra - formato do hífen
    ("Pampilhosa da Serra", "FAJÃO - VIDUAL"): "Fajão-Vidual",
    ("Pampilhosa da Serra", "PORTELA DO FOJO - MACHIO"): "Portela do Fojo-Machio",
    
    # Paços de Ferreira - freguesias unidas (precisa mapear para todas)
    ("Paços de Ferreira", "FRAZÃO ARREIGADA"): "Frazão",
    ("Paços de Ferreira", "SANFINS LAMOSO CODESSOS"): "Sanfins de Ferreira",
    
    # Vieira do Minho - "do" vs "de"
    ("Vieira do Minho", "PARADA DO BOURO"): "Parada de Bouro",
    
    # Fafe - nome diferente
    ("Fafe", "PASSOS"): "Paços",
    
    # Santa Cruz da Graciosa (Açores) - nome simplificado
    ("Santa Cruz da Graciosa", "PRAIA (SÃO MATEUS)"): "São Mateus",
    ("Santa Cruz da Graciosa", "PRAIA (SÃO MATEUS) (R.A.AÇORES)"): "São Mateus",
    
    # Lagoa (Açores) - freguesias com nomes ligeiramente diferentes
    ("Lagoa", "LAGOA (NOSSA SENHORA DO ROSÁRIO)"): "Lagoa (Nossa Senhora do Rosário)",
    ("Lagoa", "LAGOA (SANTA CRUZ)"): "Lagoa (Santa Cruz)",
    
    # Ponte de Lima - Associação de freguesias (usar Bertiandos como referência)
    ("Ponte de Lima", "ASSOCIAÇÃO DE FREGUESIAS DO VALE DO NEIVA"): "Bertiandos",
}

# Mapeamento especial para uniões/associações que englobam múltiplas freguesias
# Chave: (município, nome_no_excel) -> Lista de freguesias na BD
UNIOES_ESPECIAIS = {
    # Paços de Ferreira - cada união mapeia para múltiplas freguesias
    ("Paços de Ferreira", "FRAZÃO ARREIGADA"): ["Frazão", "Arreigada"],
    ("Paços de Ferreira", "SANFINS LAMOSO CODESSOS"): ["Sanfins de Ferreira", "Lamoso", "Codessos"],
    
    # Ponte de Lima - Associação inclui várias freguesias
    ("Ponte de Lima", "ASSOCIAÇÃO DE FREGUESIAS DO VALE DO NEIVA"): ["Bertiandos", "Gaifar", "Sandiães", "Vilar das Almas"],
    
    # Figueira da Foz
    ("Figueira da Foz", "BUARCOS E SÃO JULIÃO"): ["Buarcos", "São Julião da Figueira da Foz"],
}

# Códigos de distrito para regiões (incluindo ilhas específicas)
CODIGO_TO_REGIAO = {
    "01": "Aveiro", "02": "Beja", "03": "Braga", "04": "Bragança",
    "05": "Castelo Branco", "06": "Coimbra", "07": "Évora", "08": "Faro",
    "09": "Guarda", "10": "Leiria", "11": "Lisboa", "12": "Portalegre",
    "13": "Porto", "14": "Santarém", "15": "Setúbal", "16": "Viana do Castelo",
    "17": "Vila Real", "18": "Viseu",
    # Madeira
    "30": "Ilha da Madeira", "31": "Ilha da Madeira", "32": "Ilha de Porto Santo",
    # Açores - cada código corresponde a uma ilha específica
    "41": "Ilha de Santa Maria",
    "42": "Ilha de São Miguel",
    "43": "Ilha Terceira",
    "44": "Ilha da Graciosa",
    "45": "Ilha de São Jorge",
    "46": "Ilha do Pico",
    "47": "Ilha do Faial",
    "48": "Ilha das Flores",
    "49": "Ilha do Corvo",
}

def normalizar(nome):
    """Remove acentos e converte para minúsculas"""
    if not nome:
        return ""
    nome = unicodedata.normalize('NFD', nome)
    nome = ''.join(c for c in nome if unicodedata.category(c) != 'Mn')
    return nome.lower().strip()

def normalizar_preposicoes(nome):
    """Normaliza preposições: do/da/dos/das -> de"""
    import re
    # Substituir "do", "da", "dos", "das" por "de" (quando entre palavras)
    nome = re.sub(r'\bdo\b', 'de', nome, flags=re.IGNORECASE)
    nome = re.sub(r'\bda\b', 'de', nome, flags=re.IGNORECASE)
    nome = re.sub(r'\bdos\b', 'de', nome, flags=re.IGNORECASE)
    nome = re.sub(r'\bdas\b', 'de', nome, flags=re.IGNORECASE)
    return nome

def limpar_prefixo(nome):
    """Remove prefixos comuns de freguesias"""
    prefixos = [
        "uniao das freguesias de ", "uniao de freguesias de ",
        "freguesia de ", "união das freguesias de ", "união de freguesias de "
    ]
    for p in prefixos:
        if nome.startswith(p):
            return nome[len(p):]
    return nome

def safe_int(value):
    """Converte para int de forma segura"""
    if pd.isna(value):
        return None
    if isinstance(value, str):
        # Remover marcadores de dados pendentes
        value = value.replace('(11)', '').replace('(5)', '').strip()
        if value in ['(P)', '', 'nan']:
            return None
        try:
            return int(float(value))
        except:
            return None
    try:
        return int(value)
    except:
        return None

def carregar_coligacoes_anexo(xlsx_path):
    """Carrega informação das coligações do mapa_anexo.xlsx"""
    if not os.path.exists(xlsx_path):
        return {}
    df = pd.read_excel(xlsx_path, sheet_name=0, header=None, skiprows=1)
    coligacoes = {}
    for _, row in df.iterrows():
        dicofre = str(row[0]).zfill(6) if pd.notna(row[0]) else None
        orgao = row[3] if pd.notna(row[3]) else None
        if not dicofre or not orgao:
            continue
        key = (dicofre, orgao)
        colig_list = []
        for col_sigla in [4, 6, 8, 10, 12, 14, 16]:
            col_denom = col_sigla + 1
            if col_sigla < len(row) and pd.notna(row[col_sigla]):
                sigla = str(row[col_sigla]).strip()
                denom = str(row[col_denom]).strip() if col_denom < len(row) and pd.notna(row[col_denom]) else ""
                colig_list.append((sigla, denom))
        if colig_list:
            coligacoes[key] = colig_list
    return coligacoes

def criar_tabelas_eleicoes(cursor):
    """Cria as tabelas de eleições se não existirem"""
    cursor.executescript("""
        -- Tabela de partidos políticos
        CREATE TABLE IF NOT EXISTS partidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sigla TEXT UNIQUE NOT NULL,
            nome TEXT
        );

        -- Tabela de órgãos (CM, AM, AF)
        CREATE TABLE IF NOT EXISTS orgaos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            descricao TEXT
        );

        -- Tabela de coligações (específicas por município)
        CREATE TABLE IF NOT EXISTS coligacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sigla TEXT NOT NULL,
            nome TEXT,
            municipio_nome TEXT,
            distrito_nome TEXT
        );

        -- Tabela de resultados eleitorais
        CREATE TABLE IF NOT EXISTS resultados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            municipio_nome TEXT NOT NULL,
            distrito_nome TEXT NOT NULL,
            freguesia_nome TEXT,
            orgao_id INTEGER NOT NULL,
            dicofre TEXT,
            inscritos INTEGER,
            votantes INTEGER,
            brancos INTEGER,
            nulos INTEGER,
            FOREIGN KEY (orgao_id) REFERENCES orgaos(id)
        );

        -- Tabela de votos por partido/coligação
        CREATE TABLE IF NOT EXISTS votos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resultado_id INTEGER NOT NULL,
            partido_id INTEGER,
            coligacao_id INTEGER,
            num_votos INTEGER NOT NULL,
            FOREIGN KEY (resultado_id) REFERENCES resultados(id),
            FOREIGN KEY (partido_id) REFERENCES partidos(id),
            FOREIGN KEY (coligacao_id) REFERENCES coligacoes(id)
        );

        -- Índices para performance
        CREATE INDEX IF NOT EXISTS idx_resultados_mun ON resultados(municipio_nome, distrito_nome);
        CREATE INDEX IF NOT EXISTS idx_resultados_freg ON resultados(freguesia_nome);
        CREATE INDEX IF NOT EXISTS idx_votos_resultado ON votos(resultado_id);

        -- Órgãos autárquicos
        INSERT OR IGNORE INTO orgaos (codigo, descricao) VALUES ('CM', 'Câmara Municipal');
        INSERT OR IGNORE INTO orgaos (codigo, descricao) VALUES ('AM', 'Assembleia Municipal');
        INSERT OR IGNORE INTO orgaos (codigo, descricao) VALUES ('AF', 'Assembleia de Freguesia');

        -- Partidos políticos (21 partidos das eleições 2021)
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('A', 'Aliança');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('B.E.', 'Bloco de Esquerda');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('CDS-PP', 'CDS - Partido Popular');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('CH', 'Chega');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('E', 'Ergue-te');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('IL', 'Iniciativa Liberal');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('JPP', 'Juntos Pelo Povo');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('L', 'LIVRE');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('MAS', 'Movimento Alternativa Socialista');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('MPT', 'Partido da Terra');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('NC', 'Nós, Cidadãos!');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('PAN', 'Pessoas-Animais-Natureza');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('PCTP/MRPP', 'PCTP/MRPP');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('PDR', 'Partido Democrático Republicano');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('PPD/PSD', 'Partido Social Democrata');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('PPM', 'Partido Popular Monárquico');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('PS', 'Partido Socialista');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('PTP', 'Partido Trabalhista Português');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('R.I.R.', 'Reagir Incluir Reciclar');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('VP', 'Volt Portugal');
        INSERT OR IGNORE INTO partidos (sigla, nome) VALUES ('PCP-PEV', 'CDU - Coligação Democrática Unitária');
    """)

def main():
    print("="*60)
    print("ETL - Eleições Autárquicas 2021")
    print("="*60)
    
    SQL_DUMP = "portugal_geoms_dump.sql"
    
    # Criar BD geográfica se não existir
    if not os.path.exists(SQLITE_DB):
        if not os.path.exists(SQL_DUMP):
            print(f"ERRO: {SQL_DUMP} não encontrado")
            return
        print("\n1. Criando base de dados geográfica...")
        conn = sqlite3.connect(SQLITE_DB)
        with open(SQL_DUMP, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()
        print("   ✓ BD geográfica criada")
    
    xlsx_path = os.path.join(CNE_FOLDER, "mapa_1_resultados.xlsx")
    anexo_path = os.path.join(CNE_FOLDER, "mapa_anexo.xlsx")
    
    if not os.path.exists(xlsx_path):
        print(f"ERRO: {xlsx_path} não encontrado")
        return
    
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    
    # Verificar e criar tabelas se não existirem
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='partidos'")
    if not cursor.fetchone():
        print("\n1. Criando tabelas de eleições...")
        criar_tabelas_eleicoes(cursor)
        conn.commit()
        print("   ✓ Tabelas criadas")
    
    # Limpar dados
    print("\n1. Limpando dados...")
    cursor.execute("DELETE FROM votos")
    cursor.execute("DELETE FROM resultados")
    cursor.execute("DELETE FROM coligacoes")
    conn.commit()
    
    # Carregar coligações
    print("\n2. Carregando coligações...")
    coligacoes_anexo = carregar_coligacoes_anexo(anexo_path)
    print(f"   {len(coligacoes_anexo)} coligações")
    
    # Carregar municípios da BD geográfica
    print("\n3. Carregando geografia...")
    cursor.execute("SELECT name, district_island FROM municipalities")
    municipios_bd = {}  # nome_norm -> lista de (nome, distrito)
    for nome, distrito in cursor.fetchall():
        nome_norm = normalizar(nome)
        if nome_norm not in municipios_bd:
            municipios_bd[nome_norm] = []
        municipios_bd[nome_norm].append((nome, distrito))
    
    # Carregar freguesias da BD
    import re as re_mod
    cursor.execute("SELECT name, municipality_name, district_island FROM parishes")
    freguesias_bd = {}  # (mun_nome, dist_nome) -> {freg_norm: freg_nome}
    for nome, mun, dist in cursor.fetchall():
        key = (mun, dist)
        if key not in freguesias_bd:
            freguesias_bd[key] = {}
        nome_norm = normalizar(nome)
        freguesias_bd[key][nome_norm] = nome
        # Também sem prefixo
        nome_limpo = limpar_prefixo(nome_norm)
        if nome_limpo != nome_norm:
            freguesias_bd[key][nome_limpo] = nome
        # Também sem parêntesis (ex: "Vade (São Tomé)" -> "Vade")
        nome_sem_parent = re_mod.sub(r'\s*\([^)]*\)\s*$', '', nome_norm)
        if nome_sem_parent != nome_norm and nome_sem_parent not in freguesias_bd[key]:
            freguesias_bd[key][nome_sem_parent] = nome
    
    print(f"   {len(municipios_bd)} municípios únicos, {sum(len(v) for v in freguesias_bd.values())} freguesias")
    
    # Ler Excel
    print("\n4. Lendo Excel...")
    df = pd.read_excel(xlsx_path, sheet_name='mapa_I', skiprows=4, header=None)
    
    colunas = ['CÓD', 'CONC', 'FREG', 'ÓRG', 'INSC', 'VOT', 'BR', 'NUL',
               'A', 'B.E.', 'CDS-PP', 'CH', 'E', 'IL', 'JPP', 'L', 'MAS', 'MPT',
               'NC', 'PAN', 'PCTP/MRPP', 'PDR', 'PPD/PSD', 'PPM', 'PS', 'PTP',
               'R.I.R.', 'VP', 'PCP-PEV', 
               'COLIG_A', 'COLIG_B', 'COLIG_C', 'COLIG_D', 'COLIG_E', 'COLIG_F', 'COLIG_G']
    
    if len(df.columns) <= len(colunas):
        df.columns = colunas[:len(df.columns)]
    else:
        df.columns = colunas + [f'EXTRA_{i}' for i in range(len(df.columns) - len(colunas))]
    
    df['dicofre'] = df['CÓD'].astype(str).str.zfill(6)
    df['cod_distrito'] = df['dicofre'].str[:2]
    
    cursor.execute("SELECT id, codigo FROM orgaos")
    orgao_ids = {row[1]: row[0] for row in cursor.fetchall()}
    
    cursor.execute("SELECT id, sigla FROM partidos")
    partido_ids = {row[1]: row[0] for row in cursor.fetchall()}
    
    coligacoes_cache = {}
    
    def get_or_create_coligacao(sigla, nome, mun_nome, dist_nome):
        cache_key = (sigla, mun_nome, dist_nome)
        if cache_key in coligacoes_cache:
            return coligacoes_cache[cache_key]
        cursor.execute("INSERT INTO coligacoes (sigla, nome, municipio_nome, distrito_nome) VALUES (?, ?, ?, ?)",
                      (sigla, nome, mun_nome, dist_nome))
        colig_id = cursor.lastrowid
        coligacoes_cache[cache_key] = colig_id
        return colig_id
    
    def inserir_votos(resultado_id, row, dicofre, orgao, mun_nome, dist_nome):
        for sigla in PARTIDOS:
            if sigla in row.index:
                votos = safe_int(row[sigla])
                if votos and votos > 0:
                    partido_id = partido_ids.get(sigla)
                    if partido_id:
                        cursor.execute("INSERT INTO votos (resultado_id, partido_id, num_votos) VALUES (?, ?, ?)",
                                      (resultado_id, partido_id, votos))
        
        colunas_colig = ['COLIG_A', 'COLIG_B', 'COLIG_C', 'COLIG_D', 'COLIG_E', 'COLIG_F', 'COLIG_G']
        colig_info = coligacoes_anexo.get((dicofre, orgao), [])
        
        for idx, colig_col in enumerate(colunas_colig):
            if colig_col in row.index:
                votos = safe_int(row[colig_col])
                if votos and votos > 0:
                    if idx < len(colig_info):
                        sigla, denom = colig_info[idx]
                    else:
                        sigla, denom = f"COLIG_{chr(65+idx)}", ""
                    colig_id = get_or_create_coligacao(sigla, denom, mun_nome, dist_nome)
                    cursor.execute("INSERT INTO votos (resultado_id, coligacao_id, num_votos) VALUES (?, ?, ?)",
                                  (resultado_id, colig_id, votos))
    
    def encontrar_municipio(nome_excel, cod_distrito):
        """Encontra município na BD usando nome e código de distrito"""
        # 1. Mapeamento manual
        if nome_excel in MUNICIPIOS_EXCEL_TO_BD:
            nome_bd = MUNICIPIOS_EXCEL_TO_BD[nome_excel]
            nome_norm = normalizar(nome_bd)
        else:
            nome_norm = normalizar(nome_excel)
        
        # 2. Determinar região esperada
        regiao_esperada = CODIGO_TO_REGIAO.get(cod_distrito, "")
        
        # 3. Procurar na BD
        if nome_norm in municipios_bd:
            candidatos = municipios_bd[nome_norm]
            # Se só há um, retorna
            if len(candidatos) == 1:
                return candidatos[0]
            # Se há vários, filtrar por região
            for nome, distrito in candidatos:
                if regiao_esperada and (regiao_esperada in distrito or distrito in regiao_esperada):
                    return (nome, distrito)
            # Se não encontrou por região, retorna o primeiro
            return candidatos[0]
        
        # 4. Tentar match parcial
        for key, candidatos in municipios_bd.items():
            if nome_norm in key or key in nome_norm:
                for nome, distrito in candidatos:
                    if regiao_esperada and (regiao_esperada in distrito or distrito in regiao_esperada):
                        return (nome, distrito)
                return candidatos[0]
        
        return None
    
    def extrair_freguesias_da_uniao(nome_uniao):
        """Extrai nomes individuais de uma União de Freguesias"""
        import re
        
        # Remover "UNIÃO DAS FREGUESIAS DE " ou "UNIÃO DE FREGUESIAS DE "
        nome = re.sub(r'^UNI[ÃA]O\s+(DAS?\s+)?FREGUESIAS\s+D[EAO]\s+', '', nome_uniao, flags=re.IGNORECASE)
        
        # Casos especiais com parêntesis como "LOBRIGOS (SÃO MIGUEL E SÃO JOÃO BAPTISTA) E SANHOANE"
        # Precisamos separar cuidadosamente
        
        # Lista para guardar freguesias extraídas
        freguesias = []
        
        # Primeiro, encontrar padrões como "NOME (VARIANTE1 E VARIANTE2)"
        # que representam a MESMA freguesia com múltiplas variantes
        pattern_variantes = r'([A-ZÁÉÍÓÚÀÂÊÔÃÕÇ\s]+)\s*\(([^)]+)\)'
        
        # Separar por " E " mas preservar conteúdo dentro de parêntesis
        # Substituir temporariamente " E " dentro de parêntesis
        temp = nome
        dentro_parent = re.findall(r'\([^)]+\)', temp)
        for i, p in enumerate(dentro_parent):
            temp = temp.replace(p, f'###PARENT{i}###')
        
        # Agora separar por " E " e ","
        partes = re.split(r'\s+E\s+|,\s*', temp)
        
        # Restaurar parêntesis
        for i, parte in enumerate(partes):
            for j, p in enumerate(dentro_parent):
                partes[i] = partes[i].replace(f'###PARENT{j}###', p)
        
        for parte in partes:
            parte = parte.strip()
            if parte and len(parte) > 1:
                # Se tem parêntesis com variantes (ex: "SÃO MARTINHO E SÃO PEDRO"), expandir
                match = re.match(r'^([A-ZÁÉÍÓÚÀÂÊÔÃÕÇ\s]+)\s*\(([^)]+)\)$', parte, re.IGNORECASE)
                if match:
                    base = match.group(1).strip()
                    variantes_str = match.group(2)
                    # Verificar se são variantes separadas por " E "
                    if ' E ' in variantes_str.upper():
                        variantes = re.split(r'\s+E\s+', variantes_str, flags=re.IGNORECASE)
                        for var in variantes:
                            freguesias.append(f"{base} ({var.strip()})")
                    else:
                        # Parêntesis com uma só variante
                        freguesias.append(parte)
                else:
                    freguesias.append(parte)
        
        return freguesias
    
    def normalizar_hifen(nome):
        """Normaliza diferentes formatos de hífen: ' - ' → '-'"""
        return nome.replace(' - ', '-').replace('  ', ' ')
    
    def encontrar_freguesia(nome_freg_excel, mun_nome, dist_nome):
        """Encontra freguesia na BD"""
        import re
        
        # 0. VERIFICAR MAPEAMENTOS MANUAIS PRIMEIRO
        nome_excel_upper = str(nome_freg_excel).strip().upper()
        # Limpar marcadores de dados pendentes para lookup
        nome_para_lookup = re.sub(r'\s*\((?:11|10|9|8|7|6|5|4|3|2|1|P|R\.A\.M\.|R\.A\.A\.|R\.A\.MADEIRA|R\.A\.AÇORES)\)\s*$', '', nome_excel_upper, flags=re.IGNORECASE)
        
        map_key = (mun_nome, nome_para_lookup)
        if map_key in FREGUESIAS_EXCEL_TO_BD:
            nome_mapeado = FREGUESIAS_EXCEL_TO_BD[map_key]
            # Procurar o nome mapeado na BD
            key = (mun_nome, dist_nome)
            if key in freguesias_bd:
                freg_dict = freguesias_bd[key]
                nome_map_norm = normalizar(nome_mapeado)
                if nome_map_norm in freg_dict:
                    return freg_dict[nome_map_norm]
        
        key = (mun_nome, dist_nome)
        if key not in freguesias_bd:
            return None
        
        freg_dict = freguesias_bd[key]
        
        # Limpar nome - remover apenas marcadores específicos, NÃO todos os parêntesis
        nome_excel_limpo = str(nome_freg_excel).strip()
        # Remover apenas marcadores de dados pendentes: (11), (5), (P), (R.A.M.), (R.A.A.), (R.A.MADEIRA), etc.
        nome_excel_limpo = re.sub(r'\s*\((?:11|10|9|8|7|6|5|4|3|2|1|P|R\.A\.M\.|R\.A\.A\.|R\.A\.MADEIRA|R\.A\.AÇORES)\)\s*$', '', nome_excel_limpo, flags=re.IGNORECASE)
        
        # Normalizar hífens: " - " → "-"
        nome_excel_hifen = normalizar_hifen(nome_excel_limpo)
        
        # CASO ESPECIAL: União de Freguesias
        if 'UNIÃO' in nome_excel_limpo.upper():
            freguesias_individuais = extrair_freguesias_da_uniao(nome_excel_limpo)
            # Tentar encontrar cada freguesia individualmente
            for freg_individual in freguesias_individuais:
                freg_norm = normalizar(freg_individual)
                freg_limpo = limpar_prefixo(freg_norm)
                
                # Match exato
                if freg_norm in freg_dict:
                    return freg_dict[freg_norm]
                if freg_limpo in freg_dict:
                    return freg_dict[freg_limpo]
                
                # Match sem parêntesis final
                freg_sem_parent = re.sub(r'\s*\([^)]*\)\s*$', '', freg_individual)
                freg_norm2 = normalizar(freg_sem_parent)
                freg_limpo2 = limpar_prefixo(freg_norm2)
                
                if freg_norm2 in freg_dict:
                    return freg_dict[freg_norm2]
                if freg_limpo2 in freg_dict:
                    return freg_dict[freg_limpo2]
                
                # Match parcial por nome base
                for bd_norm, bd_real in freg_dict.items():
                    if freg_limpo2 in bd_norm or bd_norm.startswith(freg_limpo2):
                        return bd_real
            
            # Se não encontrou nenhuma, continuar com lógica normal abaixo
        
        # Primeiro: tentar match exato COM parêntesis (importante para Vade (São Tomé) vs Vade (São Pedro))
        nome_norm_completo = normalizar(nome_excel_limpo)
        if nome_norm_completo in freg_dict:
            return freg_dict[nome_norm_completo]
        
        # Tentar com hífen normalizado
        nome_norm_hifen = normalizar(nome_excel_hifen)
        if nome_norm_hifen in freg_dict:
            return freg_dict[nome_norm_hifen]
        
        # Segundo: tentar sem prefixo mas COM parêntesis
        nome_limpo_completo = limpar_prefixo(nome_norm_completo)
        if nome_limpo_completo in freg_dict:
            return freg_dict[nome_limpo_completo]
        
        # Terceiro: remover parêntesis e tentar (para casos onde BD não tem parêntesis)
        nome_sem_parent = re.sub(r'\s*\([^)]*\)\s*$', '', nome_excel_limpo)
        nome_norm = normalizar(nome_sem_parent)
        nome_limpo = limpar_prefixo(nome_norm)
        
        if nome_norm in freg_dict:
            return freg_dict[nome_norm]
        if nome_limpo in freg_dict:
            return freg_dict[nome_limpo]
        
        # Match parcial (só se não houver ambiguidade)
        matches = []
        for freg_norm, freg_real in freg_dict.items():
            if nome_limpo in freg_norm or freg_norm in nome_limpo:
                matches.append(freg_real)
            else:
                # Match por partes (separar por vírgulas e "e")
                partes_excel = set(nome_limpo.replace(',', ' e ').split(' e '))
                partes_bd = set(freg_norm.replace(',', ' e ').split(' e '))
                partes_excel = {p.strip() for p in partes_excel if len(p.strip()) > 2}
                partes_bd = {p.strip() for p in partes_bd if len(p.strip()) > 2}
                if partes_excel and partes_bd and len(partes_excel & partes_bd) >= 1:
                    matches.append(freg_real)
        
        # Só retorna se houver exatamente 1 match (evita ambiguidade)
        if len(matches) == 1:
            return matches[0]
        
        return None
    
    # Processar CM
    print("\n5. Processando CM...")
    df_cm = df[df['ÓRG'] == 'CM']
    cm_orgao_id = orgao_ids.get('CM')
    cm_ok = 0
    cm_erros = []
    
    for _, row in df_cm.iterrows():
        nome_mun_excel = row['CONC']
        if pd.isna(nome_mun_excel):
            continue
        
        cod_distrito = row['cod_distrito']
        match = encontrar_municipio(str(nome_mun_excel).strip(), cod_distrito)
        
        if not match:
            cm_erros.append(nome_mun_excel)
            continue
        
        mun_nome, dist_nome = match
        dicofre = row['dicofre']
        
        cursor.execute("""
            INSERT INTO resultados (municipio_nome, distrito_nome, orgao_id, dicofre, inscritos, votantes, brancos, nulos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (mun_nome, dist_nome, cm_orgao_id, dicofre,
              safe_int(row['INSC']), safe_int(row['VOT']), safe_int(row['BR']), safe_int(row['NUL'])))
        
        resultado_id = cursor.lastrowid
        inserir_votos(resultado_id, row, dicofre, 'CM', mun_nome, dist_nome)
        cm_ok += 1
    
    conn.commit()
    print(f"   ✓ {cm_ok} municípios")
    if cm_erros:
        print(f"   ⚠ {len(cm_erros)} sem match:")
        for e in cm_erros[:10]:
            print(f"      - {e}")
    
    # Processar AF
    print("\n6. Processando AF...")
    df_af = df[df['ÓRG'] == 'AF']
    af_orgao_id = orgao_ids.get('AF')
    af_ok = 0
    af_erros = []
    af_skip = 0
    
    for _, row in df_af.iterrows():
        nome_mun_excel = row['CONC']
        nome_freg_excel = row['FREG']
        
        if pd.isna(nome_mun_excel) or pd.isna(nome_freg_excel):
            continue
        
        # Verificar dados pendentes
        freg_str = str(nome_freg_excel)
        if '(11)' in freg_str or '(5)' in freg_str:
            af_skip += 1
            continue
        
        insc = safe_int(row['INSC'])
        vot = safe_int(row['VOT'])
        if insc is None and vot is None:
            af_skip += 1
            continue
        
        cod_distrito = row['cod_distrito']
        match_mun = encontrar_municipio(str(nome_mun_excel).strip(), cod_distrito)
        
        if not match_mun:
            af_erros.append((nome_mun_excel, nome_freg_excel, "Município não encontrado"))
            continue
        
        mun_nome, dist_nome = match_mun
        dicofre = row['dicofre']
        
        # PRIMEIRO: Verificar mapeamentos especiais para uniões/associações
        nome_freg_str = str(nome_freg_excel).strip().upper()
        special_key = (mun_nome, nome_freg_str)
        
        if special_key in UNIOES_ESPECIAIS:
            # Inserir dados para CADA freguesia do mapeamento especial
            freguesias_especiais = UNIOES_ESPECIAIS[special_key]
            for freg_bd in freguesias_especiais:
                cursor.execute("""
                    INSERT INTO resultados (municipio_nome, distrito_nome, freguesia_nome, orgao_id, dicofre, inscritos, votantes, brancos, nulos)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (mun_nome, dist_nome, freg_bd, af_orgao_id, dicofre,
                      insc, vot, safe_int(row['BR']), safe_int(row['NUL'])))
                
                resultado_id = cursor.lastrowid
                inserir_votos(resultado_id, row, dicofre, 'AF', mun_nome, dist_nome)
            af_ok += len(freguesias_especiais)
            continue  # Passar para a próxima linha
        
        # Encontrar freguesia
        freg_nome = encontrar_freguesia(nome_freg_excel, mun_nome, dist_nome)
        
        # Se é uma União de Freguesias, guardar dados em TODAS as freguesias
        if 'UNIÃO' in nome_freg_str or 'ASSOCIAÇÃO' in nome_freg_str:
            # Extrair todas as freguesias da união
            freguesias_da_uniao = extrair_freguesias_da_uniao(nome_freg_excel)
            key = (mun_nome, dist_nome)
            
            if key in freguesias_bd:
                freg_dict = freguesias_bd[key]
                freguesias_encontradas = []
                
                for freg_individual in freguesias_da_uniao:
                    freg_norm = normalizar(freg_individual)
                    freg_limpo = limpar_prefixo(freg_norm)
                    # Também tentar com preposições normalizadas
                    freg_norm_prep = normalizar_preposicoes(freg_norm)
                    freg_limpo_prep = normalizar_preposicoes(freg_limpo)
                    
                    # Tentar encontrar na BD
                    freg_bd_nome = None
                    
                    # Tentativas em ordem
                    tentativas = [freg_norm, freg_limpo, freg_norm_prep, freg_limpo_prep]
                    for tent in tentativas:
                        if tent in freg_dict:
                            freg_bd_nome = freg_dict[tent]
                            break
                        # Também verificar se BD normalizada bate
                        for bd_norm, bd_real in freg_dict.items():
                            bd_norm_prep = normalizar_preposicoes(bd_norm)
                            if tent == bd_norm_prep:
                                freg_bd_nome = bd_real
                                break
                        if freg_bd_nome:
                            break
                    
                    if not freg_bd_nome:
                        # Tentar sem parêntesis
                        import re
                        freg_sem_parent = re.sub(r'\s*\([^)]*\)\s*$', '', freg_individual)
                        freg_norm2 = normalizar(freg_sem_parent)
                        freg_limpo2 = limpar_prefixo(freg_norm2)
                        freg_norm2_prep = normalizar_preposicoes(freg_norm2)
                        freg_limpo2_prep = normalizar_preposicoes(freg_limpo2)
                        
                        tentativas2 = [freg_norm2, freg_limpo2, freg_norm2_prep, freg_limpo2_prep]
                        for tent in tentativas2:
                            if tent in freg_dict:
                                freg_bd_nome = freg_dict[tent]
                                break
                            for bd_norm, bd_real in freg_dict.items():
                                bd_norm_prep = normalizar_preposicoes(bd_norm)
                                if tent == bd_norm_prep:
                                    freg_bd_nome = bd_real
                                    break
                            if freg_bd_nome:
                                break
                        
                        if not freg_bd_nome:
                            # Match parcial
                            for bd_norm, bd_real in freg_dict.items():
                                if freg_limpo2_prep in bd_norm or bd_norm.startswith(freg_limpo2_prep):
                                    freg_bd_nome = bd_real
                                    break
                    
                    if freg_bd_nome and freg_bd_nome not in freguesias_encontradas:
                        freguesias_encontradas.append(freg_bd_nome)
                
                # Inserir dados para CADA freguesia encontrada
                if freguesias_encontradas:
                    for freg_bd in freguesias_encontradas:
                        cursor.execute("""
                            INSERT INTO resultados (municipio_nome, distrito_nome, freguesia_nome, orgao_id, dicofre, inscritos, votantes, brancos, nulos)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (mun_nome, dist_nome, freg_bd, af_orgao_id, dicofre,
                              insc, vot, safe_int(row['BR']), safe_int(row['NUL'])))
                        
                        resultado_id = cursor.lastrowid
                        inserir_votos(resultado_id, row, dicofre, 'AF', mun_nome, dist_nome)
                    af_ok += len(freguesias_encontradas)
                    continue  # Passar para a próxima linha do Excel
        
        # Processamento normal para freguesias individuais
        if not freg_nome:
            # Se não encontrou, usa o nome do Excel (limpo)
            import re
            freg_nome = re.sub(r'\s*\([^)]*\)\s*$', '', str(nome_freg_excel).strip())
            af_erros.append((mun_nome, freg_nome, "Freguesia não encontrada na BD"))
        
        cursor.execute("""
            INSERT INTO resultados (municipio_nome, distrito_nome, freguesia_nome, orgao_id, dicofre, inscritos, votantes, brancos, nulos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (mun_nome, dist_nome, freg_nome, af_orgao_id, dicofre,
              insc, vot, safe_int(row['BR']), safe_int(row['NUL'])))
        
        resultado_id = cursor.lastrowid
        inserir_votos(resultado_id, row, dicofre, 'AF', mun_nome, dist_nome)
        af_ok += 1
    
    conn.commit()
    print(f"   ✓ {af_ok} freguesias")
    if af_skip:
        print(f"   ⚠ {af_skip} ignoradas (dados pendentes)")
    if af_erros:
        print(f"   ⚠ {len(af_erros)} sem match perfeito")
    
    # Estatísticas
    print("\n7. Estatísticas finais:")
    cursor.execute("SELECT COUNT(*) FROM resultados WHERE orgao_id = ?", (cm_orgao_id,))
    print(f"   CM: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM resultados WHERE orgao_id = ?", (af_orgao_id,))
    print(f"   AF: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM votos")
    print(f"   Votos: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM coligacoes")
    print(f"   Coligações: {cursor.fetchone()[0]}")
    
    # Verificar alguns municípios específicos
    print("\n8. Verificação de municípios problemáticos:")
    muns_check = ["Santa Maria da Feira", "Lagoa", "Calheta", "Praia da Vitória", "Corvo"]
    for mun in muns_check:
        cursor.execute("SELECT COUNT(*) FROM resultados WHERE municipio_nome = ?", (mun,))
        count = cursor.fetchone()[0]
        print(f"   {mun}: {count} registos")
    
    conn.close()
    print("\n" + "="*60)
    print("ETL concluído!")
    print("="*60)

if __name__ == '__main__':
    main()
