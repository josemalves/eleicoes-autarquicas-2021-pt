#!/usr/bin/env python3
"""
Aplicação de Visualização - Eleições Autárquicas 2021
Versão final com todos os partidos e legenda completa
"""

import sqlite3
import tkinter as tk
from tkinter import ttk
import os
import hashlib
import unicodedata
import re

import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# ---------------------- Config ----------------------
# Determinar caminho da BD
def find_database():
    """Encontra a base de dados em vários locais possíveis"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    possible_paths = [
        os.path.join(script_dir, "..", "db", "elections.db"),
        os.path.join(script_dir, "elections.db"),
        "elections.db",
        "portugal_geoms.db",
        "../db/elections.db",
        "db/elections.db",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

SQLITE_DB = find_database()
if SQLITE_DB is None:
    print("ERRO: Base de dados não encontrada!")
    print("Execute primeiro o ETL: python etl/etl_eleicoes.py")
    print("Ou certifique-se que 'elections.db' está na pasta db/")
    exit(1)

CANVAS_W, CANVAS_H = 700, 650
PADDING = 25
BG_COLOR = "white"
OUTLINE_COLOR = "#333333"
OUTLINE_WIDTH = 1
HOVER_COLOR = "#ffff99"

REGION_COLORS = {"Continent": "#377eb8", "Açores": "#4daf4a", "Madeira": "#ff7f00"}
DEFAULT_FILL = "#999999"

# TODOS os partidos com cores definidas
CORES_PARTIDOS = {
    # Partidos principais
    "PS": "#ff66b2",          # Rosa
    "PPD/PSD": "#ff9933",     # Laranja
    "PSD": "#ff9933",         # Laranja (alias)
    "PCP-PEV": "#ff0000",     # Vermelho
    "CDU": "#ff0000",         # Vermelho (alias)
    "B.E.": "#8b0000",        # Vermelho escuro
    "BE": "#8b0000",          # (alias)
    "CDS-PP": "#0066cc",      # Azul
    "CDS": "#0066cc",         # (alias)
    "CH": "#1a1a6b",          # Azul escuro
    "IL": "#00bfff",          # Azul claro
    "PAN": "#006400",         # Verde escuro
    "L": "#32cd32",           # Verde lima (LIVRE)
    "LIVRE": "#32cd32",       # (alias)
    
    # Partidos menores - TODOS definidos
    "A": "#9932cc",           # Roxo (Aliança)
    "JPP": "#003366",         # Azul marinho
    "NC": "#ff6600",          # Laranja escuro (Nós, Cidadãos!)
    "PPM": "#4169e1",         # Azul royal
    "MPT": "#2e8b57",         # Verde mar
    "PDR": "#daa520",         # Dourado
    "PCTP/MRPP": "#cc0000",   # Vermelho escuro
    "VP": "#8fbc8f",          # Verde escuro claro
    "PTP": "#cd853f",         # Peru
    "R.I.R.": "#9acd32",      # Verde amarelado
    "RIR": "#9acd32",         # (alias)
    "E": "#808080",           # Cinza (Ergue-te)
    "MAS": "#dc143c",         # Carmesim
}

# Cores para coligações - TODAS distintas das cores de partidos
# Evitamos: rosa, laranja, vermelho, azul claro/escuro, verde lima, roxo
CORES_COLIGACOES_BASE = [
    "#8B4513",  # Castanho sela
    "#2F4F4F",  # Cinza ardósia escuro
    "#556B2F",  # Verde oliva escuro
    "#8B008B",  # Magenta escuro
    "#B8860B",  # Dourado escuro
    "#483D8B",  # Azul ardósia escuro
    "#008B8B",  # Ciano escuro
    "#9400D3",  # Violeta escuro
    "#5F9EA0",  # Azul cadete
    "#D2691E",  # Chocolate
    "#6B8E23",  # Verde oliveira
    "#708090",  # Cinza ardósia
    "#7B68EE",  # Azul ardósia médio
    "#3CB371",  # Verde mar médio
    "#BC8F8F",  # Rosa rosado
    "#4682B4",  # Azul aço
    "#D2B48C",  # Bronzeado
    "#5D478B",  # Púrpura médio
    "#CD5C5C",  # Vermelho indiano (mais suave)
    "#20B2AA",  # Verde mar claro
    "#778899",  # Cinza ardósia claro
    "#BDB76B",  # Caqui escuro
    "#8FBC8F",  # Verde mar escuro claro
    "#E9967A",  # Salmão escuro
]

_coligacao_cores_cache = {}

def normalizar(nome):
    """Remove acentos e converte para minúsculas"""
    if not nome:
        return ""
    nome = unicodedata.normalize('NFD', nome)
    nome = ''.join(c for c in nome if unicodedata.category(c) != 'Mn')
    return nome.lower().strip()

def limpar_prefixo(nome):
    """Remove prefixos de uniões de freguesias"""
    prefixos = ["uniao das freguesias de ", "uniao de freguesias de ", "freguesia de "]
    for p in prefixos:
        if nome.startswith(p):
            return nome[len(p):]
    return nome

def cor_partido(sigla, is_colig=False):
    """
    Retorna cor para partido ou coligação.
    IMPORTANTE: Coligações têm SEMPRE cores diferentes dos partidos individuais.
    """
    if not sigla:
        return DEFAULT_FILL
    
    sigla_upper = sigla.upper().strip()
    sigla_clean = sigla.strip()
    
    # PRIMEIRO: Verificar match exato com partidos conhecidos
    # Isto inclui partidos com / e - no nome (PPD/PSD, PCP-PEV, CDS-PP, etc.)
    if sigla_clean in CORES_PARTIDOS:
        return CORES_PARTIDOS[sigla_clean]
    
    # Verificar com case insensitive
    for p, cor in CORES_PARTIDOS.items():
        if p.upper() == sigla_upper:
            return cor
    
    # Lista de partidos conhecidos (para verificar se é coligação)
    partidos_conhecidos = set(CORES_PARTIDOS.keys())
    
    # Detectar se é coligação baseado em separador "."
    # Nota: "/" e "-" NÃO são separadores de coligação (existem em nomes de partidos)
    tem_ponto = '.' in sigla
    
    # Contar quantos partidos conhecidos aparecem na sigla
    partidos_encontrados = []
    for p in partidos_conhecidos:
        # Verificar se o partido aparece como componente separado por "."
        partes = sigla_upper.replace('.', '|').split('|')
        for parte in partes:
            if parte.strip() == p.upper():
                partidos_encontrados.append(p)
                break
    
    # É coligação se: marcado como tal, tem ".", ou tem 2+ partidos distintos
    e_coligacao = is_colig or tem_ponto or len(partidos_encontrados) >= 2
    
    # Se NÃO é coligação e não encontrámos match exato, verificar partidos curtos
    if not e_coligacao:
        # Partidos de 1-2 letras que podem estar no nome
        for p in ["PS", "BE", "IL", "CH", "NC", "VP", "A", "L", "E"]:
            if sigla_upper == p:
                return CORES_PARTIDOS.get(p, DEFAULT_FILL)
    
    # Para COLIGAÇÕES: sempre usar cor única baseada em hash
    if sigla not in _coligacao_cores_cache:
        hash_val = int(hashlib.md5(sigla.encode()).hexdigest(), 16)
        _coligacao_cores_cache[sigla] = CORES_COLIGACOES_BASE[hash_val % len(CORES_COLIGACOES_BASE)]
    return _coligacao_cores_cache[sigla]

# ---------------------- WKT parsing ----------------------
def parse_wkt_polygons(wkt):
    """Parse WKT geometry to list of polygon coordinates"""
    if not wkt or not wkt.strip():
        return []
    
    def strip_srid(s):
        s = s.strip()
        if s.upper().startswith("SRID="):
            i = s.find(";")
            if i != -1:
                return s[i+1:].lstrip()
        return s
    
    def outer_content(s):
        s = s.lstrip()
        if not s or s[0] != "(":
            return ""
        depth, start = 0, None
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
                if depth == 1:
                    start = i + 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return s[start:i]
        return ""
    
    def split_top(s):
        parts, depth, last = [], 0, 0
        for i, ch in enumerate(s):
            if ch == "(": depth += 1
            elif ch == ")": depth -= 1
            elif ch == "," and depth == 0:
                parts.append(s[last:i].strip())
                last = i + 1
        parts.append(s[last:].strip())
        return parts
    
    def parse_ring(r):
        pts = []
        for pair in r.strip().split(","):
            xy = pair.strip().split()
            if len(xy) >= 2:
                pts.append((float(xy[0]), float(xy[1])))
        return pts
    
    def parse_polygon(content):
        rings = []
        for ring_block in split_top(content):
            rings.append(parse_ring(outer_content(ring_block)))
        return rings
    
    s = strip_srid(wkt)
    up = s.upper()
    
    for prefix in ["ZM", "Z", "M"]:
        for gtype in ["MULTIPOLYGON", "POLYGON", "GEOMETRYCOLLECTION"]:
            if up.startswith(gtype + " " + prefix):
                s = s[len(gtype)+1+len(prefix):].lstrip()
                up = gtype
                break
            elif up.startswith(gtype + prefix):
                s = s[len(gtype)+len(prefix):].lstrip()
                up = gtype
                break
    
    if up.startswith("POLYGON"):
        s = s[7:].lstrip()
        if s.upper().startswith("EMPTY"):
            return []
        return [parse_polygon(outer_content(s))]
    elif up.startswith("MULTIPOLYGON"):
        s = s[12:].lstrip()
        if s.upper().startswith("EMPTY"):
            return []
        content = outer_content(s)
        return [parse_polygon(outer_content(p)) for p in split_top(content)]
    elif up.startswith("GEOMETRYCOLLECTION"):
        s = s[18:].lstrip()
        content = outer_content(s)
        polys = []
        for comp in split_top(content):
            try:
                polys.extend(parse_wkt_polygons(comp))
            except:
                pass
        return polys
    
    return []

# ---------------------- DB ----------------------
def q(sql, args=()):
    conn = sqlite3.connect(SQLITE_DB)
    try:
        cur = conn.cursor()
        cur.execute(sql, args)
        rows = cur.fetchall()
    finally:
        conn.close()
    return rows

def fetch_districts():
    rows = q("SELECT name, region, geom FROM districts ORDER BY region, name")
    return [(str(n), str(r), parse_wkt_polygons(w or "")) for n, r, w in rows]

def fetch_municipalities(district_name):
    rows = q("SELECT name, geom FROM municipalities WHERE district_island = ? ORDER BY name", (district_name,))
    return [(str(n), parse_wkt_polygons(w or "")) for n, w in rows]

def fetch_parishes(district_name, municipality_name):
    rows = q("SELECT name, geom FROM parishes WHERE district_island = ? AND municipality_name = ? ORDER BY name",
             (district_name, municipality_name))
    return [(str(n), parse_wkt_polygons(w or "")) for n, w in rows]

# --- Eleições CM ---
def fetch_vencedor_municipio(distrito, municipio):
    rows = q("""
        SELECT COALESCE(p.sigla, c.sigla), v.num_votos, CASE WHEN c.id IS NOT NULL THEN 1 ELSE 0 END, c.nome
        FROM votos v JOIN resultados r ON v.resultado_id = r.id JOIN orgaos o ON r.orgao_id = o.id
        LEFT JOIN partidos p ON v.partido_id = p.id LEFT JOIN coligacoes c ON v.coligacao_id = c.id
        WHERE r.municipio_nome = ? AND r.distrito_nome = ? AND o.codigo = 'CM' AND r.freguesia_nome IS NULL
        ORDER BY v.num_votos DESC LIMIT 1
    """, (municipio, distrito))
    return rows[0] if rows else None

def fetch_votos_municipio(distrito, municipio, orgao='CM'):
    return q("""
        SELECT COALESCE(p.sigla, c.sigla), v.num_votos, CASE WHEN c.id IS NOT NULL THEN 1 ELSE 0 END, c.nome, COALESCE(v.mandatos, 0)
        FROM votos v JOIN resultados r ON v.resultado_id = r.id JOIN orgaos o ON r.orgao_id = o.id
        LEFT JOIN partidos p ON v.partido_id = p.id LEFT JOIN coligacoes c ON v.coligacao_id = c.id
        WHERE r.municipio_nome = ? AND r.distrito_nome = ? AND o.codigo = ? AND r.freguesia_nome IS NULL
        ORDER BY v.num_votos DESC
    """, (municipio, distrito, orgao))

def fetch_resultado_municipio(distrito, municipio, orgao='CM'):
    rows = q("""
        SELECT r.inscritos, r.votantes, r.brancos, r.nulos FROM resultados r JOIN orgaos o ON r.orgao_id = o.id
        WHERE r.municipio_nome = ? AND r.distrito_nome = ? AND o.codigo = ? AND r.freguesia_nome IS NULL
    """, (municipio, distrito, orgao))
    return rows[0] if rows else None

def fetch_votos_distrito(distrito, orgao='CM'):
    rows = q("""
        SELECT COALESCE(p.sigla, c.sigla), SUM(v.num_votos), MAX(CASE WHEN c.id IS NOT NULL THEN 1 ELSE 0 END), SUM(COALESCE(v.mandatos, 0))
        FROM votos v JOIN resultados r ON v.resultado_id = r.id JOIN orgaos o ON r.orgao_id = o.id
        LEFT JOIN partidos p ON v.partido_id = p.id LEFT JOIN coligacoes c ON v.coligacao_id = c.id
        WHERE r.distrito_nome = ? AND o.codigo = ? AND r.freguesia_nome IS NULL
        GROUP BY COALESCE(p.sigla, c.sigla) ORDER BY SUM(v.num_votos) DESC
    """, (distrito, orgao))
    return [(r[0], r[1], r[2], None, r[3]) for r in rows]

# --- Eleições AF ---
def buscar_freguesia_resultado(distrito, municipio, nome_bd):
    """Busca freguesia nos resultados usando vários métodos de matching"""
    nome_norm = normalizar(nome_bd)
    nome_limpo = limpar_prefixo(nome_norm)
    
    rows = q("""
        SELECT DISTINCT r.freguesia_nome FROM resultados r JOIN orgaos o ON r.orgao_id = o.id
        WHERE r.municipio_nome = ? AND r.distrito_nome = ? AND o.codigo = 'AF' AND r.freguesia_nome IS NOT NULL
    """, (municipio, distrito))
    
    for (freg_resultado,) in rows:
        freg_norm = normalizar(freg_resultado)
        freg_limpo = limpar_prefixo(freg_norm)
        
        # Match exato
        if nome_norm == freg_norm or nome_limpo == freg_limpo:
            return freg_resultado
        
        # Match por contenção
        if nome_limpo in freg_limpo or freg_limpo in nome_limpo:
            return freg_resultado
        if nome_norm in freg_norm or freg_norm in nome_norm:
            return freg_resultado
        
        # Match por partes
        partes_bd = set(nome_limpo.replace(',', ' e ').split(' e '))
        partes_res = set(freg_limpo.replace(',', ' e ').split(' e '))
        partes_bd = {p.strip() for p in partes_bd if len(p.strip()) > 2}
        partes_res = {p.strip() for p in partes_res if len(p.strip()) > 2}
        
        if partes_bd and partes_res and partes_bd & partes_res:
            return freg_resultado
    
    return None

def fetch_vencedor_freguesia(distrito, municipio, freguesia_bd):
    freg_res = buscar_freguesia_resultado(distrito, municipio, freguesia_bd)
    if not freg_res:
        return None
    rows = q("""
        SELECT COALESCE(p.sigla, c.sigla), v.num_votos, CASE WHEN c.id IS NOT NULL THEN 1 ELSE 0 END, c.nome
        FROM votos v JOIN resultados r ON v.resultado_id = r.id JOIN orgaos o ON r.orgao_id = o.id
        LEFT JOIN partidos p ON v.partido_id = p.id LEFT JOIN coligacoes c ON v.coligacao_id = c.id
        WHERE r.municipio_nome = ? AND r.distrito_nome = ? AND r.freguesia_nome = ? AND o.codigo = 'AF'
        ORDER BY v.num_votos DESC LIMIT 1
    """, (municipio, distrito, freg_res))
    return rows[0] if rows else None

def fetch_votos_freguesia(distrito, municipio, freguesia_bd):
    freg_res = buscar_freguesia_resultado(distrito, municipio, freguesia_bd)
    if not freg_res:
        return []
    return q("""
        SELECT COALESCE(p.sigla, c.sigla), v.num_votos, CASE WHEN c.id IS NOT NULL THEN 1 ELSE 0 END, c.nome, COALESCE(v.mandatos, 0)
        FROM votos v JOIN resultados r ON v.resultado_id = r.id JOIN orgaos o ON r.orgao_id = o.id
        LEFT JOIN partidos p ON v.partido_id = p.id LEFT JOIN coligacoes c ON v.coligacao_id = c.id
        WHERE r.municipio_nome = ? AND r.distrito_nome = ? AND r.freguesia_nome = ? AND o.codigo = 'AF'
        ORDER BY v.num_votos DESC
    """, (municipio, distrito, freg_res))

def fetch_resultado_freguesia(distrito, municipio, freguesia_bd):
    freg_res = buscar_freguesia_resultado(distrito, municipio, freguesia_bd)
    if not freg_res:
        return None
    rows = q("""
        SELECT r.inscritos, r.votantes, r.brancos, r.nulos FROM resultados r JOIN orgaos o ON r.orgao_id = o.id
        WHERE r.municipio_nome = ? AND r.distrito_nome = ? AND r.freguesia_nome = ? AND o.codigo = 'AF'
    """, (municipio, distrito, freg_res))
    return rows[0] if rows else None

# ---------------------- Geometry ----------------------
def compute_bounds(list_of_polys):
    minx = miny = float("inf")
    maxx = maxy = float("-inf")
    for polys in list_of_polys:
        for rings in polys:
            if rings:
                for x, y in rings[0]:
                    minx, miny = min(minx, x), min(miny, y)
                    maxx, maxy = max(maxx, x), max(maxy, y)
    return (minx, miny, maxx, maxy) if minx != float("inf") else None

def make_transform(bounds, w, h, pad, offset_x=0, offset_y=0):
    minx, miny, maxx, maxy = bounds
    dx, dy = (maxx - minx) or 1.0, (maxy - miny) or 1.0
    scale = min((w - 2*pad) / dx, (h - 2*pad) / dy)
    scaled_w, scaled_h = dx * scale, dy * scale
    ox = offset_x + (w - scaled_w) / 2
    oy = offset_y + (h - scaled_h) / 2
    def project(x, y):
        return (ox + (x - minx) * scale, h + offset_y - oy - (y - miny) * scale)
    return project

def draw_polygon(canvas, pts, fill, outline=OUTLINE_COLOR, width=OUTLINE_WIDTH):
    if len(pts) >= 6:
        return canvas.create_polygon(*pts, fill=fill, outline=outline, width=width)

# ---------------------- App ----------------------
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Portugal - Eleições Autárquicas 2021")
        self.root.configure(bg=BG_COLOR)
        self.root.geometry("1400x820")

        self.main_frame = tk.Frame(self.root, bg=BG_COLOR)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Coluna esquerda
        self.left_frame = tk.Frame(self.main_frame, bg=BG_COLOR)
        self.left_frame.pack(side="left", fill="both")

        # Header
        self.header = tk.Frame(self.left_frame, bg=BG_COLOR)
        self.header.pack(fill="x", pady=(0, 5))
        self.title_lbl = tk.Label(self.header, text="", bg=BG_COLOR, font=("Helvetica", 13, "bold"))
        self.title_lbl.pack(side="left")
        self.back_btn = tk.Button(self.header, text="Voltar", command=self.on_back, state="disabled")
        self.back_btn.pack(side="right")
        
        # Seletor de Órgão
        self.organ_frame = tk.Frame(self.header, bg=BG_COLOR)
        self.organ_frame.pack(side="right", padx=20)
        tk.Label(self.organ_frame, text="Órgão:", bg=BG_COLOR, font=("Helvetica", 10)).pack(side="left")
        self.organ_var = tk.StringVar(value="CM")
        self.organ_combo = ttk.Combobox(self.organ_frame, textvariable=self.organ_var, 
                                         values=["CM", "AF"], state="readonly", width=8)
        self.organ_combo.pack(side="left", padx=5)
        self.organ_combo.bind("<<ComboboxSelected>>", self.on_organ_change)

        # Canvas
        self.canvas = tk.Canvas(self.left_frame, width=CANVAS_W, height=CANVAS_H,
                                background=BG_COLOR, highlightthickness=1, highlightbackground="#ccc")
        self.canvas.pack()

        # Info
        self.info_lbl = tk.Label(self.left_frame, text="", bg=BG_COLOR, font=("Helvetica", 10))
        self.info_lbl.pack(pady=3)

        # Legenda (ABAIXO do mapa) - 2 linhas
        self.legend_frame1 = tk.Frame(self.left_frame, bg=BG_COLOR)
        self.legend_frame1.pack(fill="x", pady=2)
        self.legend_frame2 = tk.Frame(self.left_frame, bg=BG_COLOR)
        self.legend_frame2.pack(fill="x", pady=2)

        # Coluna direita
        self.right_frame = tk.Frame(self.main_frame, bg=BG_COLOR, width=620)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=(15, 0))

        self.chart_title = tk.Label(self.right_frame, text="Resultados Eleitorais", bg=BG_COLOR, font=("Helvetica", 12, "bold"))
        self.chart_title.pack(pady=(0, 5))

        self.chart_frame = tk.Frame(self.right_frame, bg=BG_COLOR)
        self.chart_frame.pack(fill="both", expand=True)
        self.fig = Figure(figsize=(5.5, 3.5), dpi=100, facecolor='white')
        self.ax = self.fig.add_subplot(111)
        self.chart_canvas = FigureCanvasTkAgg(self.fig, master=self.chart_frame)
        self.chart_canvas.get_tk_widget().pack(fill="both", expand=True)

        self.table_title = tk.Label(self.right_frame, text="Tabela de Resultados", bg=BG_COLOR, font=("Helvetica", 11, "bold"))
        self.table_title.pack(pady=(10, 5))

        self.table_frame = tk.Frame(self.right_frame, bg=BG_COLOR)
        self.table_frame.pack(fill="both", expand=True)
        columns = ("partido", "descricao", "votos", "percentagem", "mandatos")
        self.tree = ttk.Treeview(self.table_frame, columns=columns, show="headings", height=10)
        self.tree.heading("partido", text="Sigla")
        self.tree.heading("descricao", text="Descrição")
        self.tree.heading("votos", text="Votos")
        self.tree.heading("percentagem", text="%")
        self.tree.heading("mandatos", text="Seats")
        self.tree.column("partido", width=100)
        self.tree.column("descricao", width=200)
        self.tree.column("votos", width=80, anchor="e")
        self.tree.column("percentagem", width=55, anchor="e")
        self.tree.column("mandatos", width=50, anchor="e")
        scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.stats_lbl = tk.Label(self.right_frame, text="", bg=BG_COLOR, font=("Helvetica", 9), justify="left", anchor="w")
        self.stats_lbl.pack(fill="x", pady=5)

        self.level = "districts"
        self.selected_district = None
        self.selected_municipality = None
        self.polygon_colors = {}
        self.polygon_names = {}

        self.draw_districts()
        self.show_welcome()
        self.root.mainloop()

    def clear_canvas(self):
        self.canvas.delete("all")
        self.polygon_colors = {}
        self.polygon_names = {}

    def clear_legend(self):
        for w in self.legend_frame1.winfo_children():
            w.destroy()
        for w in self.legend_frame2.winfo_children():
            w.destroy()

    def update_info(self, text):
        self.info_lbl.config(text=text)

    def clear_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def on_hover_enter(self, event):
        item = self.canvas.find_withtag("current")
        if item and item[0] in self.polygon_colors:
            self.canvas.itemconfig(item[0], fill=HOVER_COLOR)
            if item[0] in self.polygon_names:
                self.update_info(f"→ {self.polygon_names[item[0]]}")

    def on_hover_leave(self, event):
        item = self.canvas.find_withtag("current")
        if item and item[0] in self.polygon_colors:
            self.canvas.itemconfig(item[0], fill=self.polygon_colors[item[0]])

    def show_welcome(self):
        self.ax.clear()
        self.ax.text(0.5, 0.5, "Selecione um distrito\npara ver os resultados", ha='center', va='center', fontsize=12, color='gray', transform=self.ax.transAxes)
        self.ax.axis('off')
        self.chart_title.config(text="Resultados Eleitorais - 2021")
        self.chart_canvas.draw()
        self.clear_table()
        self.stats_lbl.config(text="")

    def on_organ_change(self, event=None):
        """Atualiza resultados quando o órgão é alterado"""
        orgao = self.organ_var.get()
        if self.level == "districts" and self.selected_district:
            # Nível distrito - mostrar agregado
            self.show_results(fetch_votos_distrito(self.selected_district, orgao), None, 
                            f"Distrito: {self.selected_district}", orgao)
        elif self.level == "municipalities" and self.selected_district:
            # Nível municípios - mostrar distrito
            self.show_results(fetch_votos_distrito(self.selected_district, orgao), None, 
                            f"Distrito: {self.selected_district}", orgao)
        elif self.level == "parishes" and self.selected_municipality:
            # Nível freguesias - mostrar município
            self.show_results(fetch_votos_municipio(self.selected_district, self.selected_municipality, orgao),
                            fetch_resultado_municipio(self.selected_district, self.selected_municipality, orgao),
                            self.selected_municipality, orgao)

    def show_results(self, votos, resultado, titulo, orgao="CM"):
        self.clear_table()
        if not votos:
            self.ax.clear()
            self.ax.text(0.5, 0.5, "Sem dados disponíveis", ha='center', va='center', fontsize=12, color='gray', transform=self.ax.transAxes)
            self.ax.axis('off')
            self.chart_canvas.draw()
            self.stats_lbl.config(text="")
            return

        total = sum(v[1] for v in votos if v[1])
        top = votos[:8]
        siglas = [v[0][:12] if v[0] else "?" for v in top]
        valores = [v[1] for v in top]
        cores = [cor_partido(v[0], v[2]) for v in top]

        self.ax.clear()
        bars = self.ax.barh(range(len(siglas)), valores, color=cores, edgecolor='black', linewidth=0.5)
        self.ax.set_yticks(range(len(siglas)))
        self.ax.set_yticklabels(siglas, fontsize=9)
        self.ax.invert_yaxis()
        self.ax.set_xlabel('Votos', fontsize=10)
        max_val = max(valores) if valores else 1
        for bar, val in zip(bars, valores):
            self.ax.text(val + max_val*0.02, bar.get_y() + bar.get_height()/2, f'{val:,}', va='center', fontsize=8)
        self.chart_title.config(text=f"{titulo} - {orgao} 2021")
        self.fig.tight_layout()
        self.chart_canvas.draw()

        for row in votos:
            sigla = row[0]
            num = row[1]
            is_colig = row[2]
            nome_colig = row[3] if len(row) > 3 else None
            mandatos = row[4] if len(row) > 4 else 0
            if num and num > 0:
                pct = (num / total * 100) if total > 0 else 0
                if is_colig and nome_colig:
                    desc = nome_colig[:35] + "..." if len(nome_colig) > 35 else nome_colig
                else:
                    desc = "Coligação" if is_colig else "Partido"
                mand_str = str(mandatos) if mandatos else "-"
                self.tree.insert("", "end", values=(sigla or "?", desc, f"{num:,}", f"{pct:.1f}%", mand_str))

        if resultado:
            insc, vot, br, nul = resultado
            if insc and vot:
                part = vot / insc * 100
                self.stats_lbl.config(text=f"Inscritos: {insc:,} | Votantes: {vot:,} | Participação: {part:.1f}% | Abstenção: {100-part:.1f}%\nBrancos: {br:,} | Nulos: {nul:,}")
        self.table_title.config(text=f"Tabela de Resultados - {orgao}")

    def draw_legend_partidos(self, titulo):
        """Desenha legenda com todos os partidos principais em 2 linhas"""
        self.clear_legend()
        
        # Usar fonte compatível com macOS e Windows
        font_bold = ("Helvetica", 9, "bold")
        font_normal = ("Helvetica", 8)
        box_size = 12  # Ligeiramente maior para melhor visibilidade
        
        # Linha 1
        lbl = tk.Label(self.legend_frame1, text=titulo, bg=BG_COLOR, font=font_bold)
        lbl.pack(side="left", padx=(0, 8))
        
        linha1 = [
            ("PS", CORES_PARTIDOS["PS"]), 
            ("PSD", CORES_PARTIDOS["PPD/PSD"]), 
            ("PCP", CORES_PARTIDOS["PCP-PEV"]), 
            ("CDS", CORES_PARTIDOS["CDS-PP"]), 
            ("BE", CORES_PARTIDOS["B.E."]), 
            ("CH", CORES_PARTIDOS["CH"]),
            ("IL", CORES_PARTIDOS["IL"]),
            ("PAN", CORES_PARTIDOS["PAN"]),
            ("L", CORES_PARTIDOS["L"]),
        ]
        for label, color in linha1:
            f = tk.Frame(self.legend_frame1, bg=BG_COLOR)
            f.pack(side="left", padx=3)
            c = tk.Canvas(f, width=box_size, height=box_size, bg=BG_COLOR, highlightthickness=0, bd=0)
            c.pack(side="left")
            c.create_rectangle(1, 1, box_size-1, box_size-1, fill=color, outline="#333", width=1)
            tk.Label(f, text=label, bg=BG_COLOR, font=font_normal).pack(side="left", padx=(2, 0))
        
        # Linha 2
        linha2 = [
            ("JPP", CORES_PARTIDOS["JPP"]),
            ("A", CORES_PARTIDOS["A"]),
            ("NC", CORES_PARTIDOS["NC"]),
            ("PPM", CORES_PARTIDOS["PPM"]),
            ("MPT", CORES_PARTIDOS["MPT"]),
            ("PDR", CORES_PARTIDOS["PDR"]),
            ("Colig", CORES_COLIGACOES_BASE[0]),
            ("S/Dados", DEFAULT_FILL),
        ]
        for label, color in linha2:
            f = tk.Frame(self.legend_frame2, bg=BG_COLOR)
            f.pack(side="left", padx=3)
            c = tk.Canvas(f, width=box_size, height=box_size, bg=BG_COLOR, highlightthickness=0, bd=0)
            c.pack(side="left")
            c.create_rectangle(1, 1, box_size-1, box_size-1, fill=color, outline="#333", width=1)
            tk.Label(f, text=label, bg=BG_COLOR, font=font_normal).pack(side="left", padx=(2, 0))
        
        # Forçar atualização visual (importante para macOS)
        self.legend_frame1.update_idletasks()
        self.legend_frame2.update_idletasks()

    def draw_legend_regioes(self):
        """Desenha legenda das regiões"""
        self.clear_legend()
        
        # Usar fonte compatível com macOS e Windows
        font_bold = ("Helvetica", 10, "bold")
        font_normal = ("Helvetica", 9)
        box_size = 14
        
        tk.Label(self.legend_frame1, text="Eleições Autárquicas 2021", bg=BG_COLOR, font=font_bold).pack(side="left", padx=(0, 10))
        for label, region in [("Continente", "Continent"), ("Açores", "Açores"), ("Madeira", "Madeira")]:
            f = tk.Frame(self.legend_frame1, bg=BG_COLOR)
            f.pack(side="left", padx=4)
            c = tk.Canvas(f, width=box_size, height=box_size, bg=BG_COLOR, highlightthickness=0, bd=0)
            c.pack(side="left")
            c.create_rectangle(1, 1, box_size-1, box_size-1, fill=REGION_COLORS.get(region, DEFAULT_FILL), outline="#333", width=1)
            tk.Label(f, text=label, bg=BG_COLOR, font=font_normal).pack(side="left", padx=(2, 0))
        
        # Forçar atualização visual (importante para macOS)
        self.legend_frame1.update_idletasks()

    def draw_districts(self):
        self.level = "districts"
        self.selected_district = None
        self.selected_municipality = None
        self.back_btn.config(state="disabled")
        self.title_lbl.config(text="Distritos de Portugal")
        self.update_info("Clique num distrito para ver municípios")
        self.show_welcome()
        self.draw_legend_regioes()

        data = fetch_districts()
        if not data:
            return

        continente = [(n, r, p) for n, r, p in data if r == "Continent"]
        acores = [(n, r, p) for n, r, p in data if r == "Açores"]
        madeira = [(n, r, p) for n, r, p in data if r == "Madeira"]

        # Continente
        cont_polys = [p for _, _, p in continente if p]
        cont_bounds = compute_bounds(cont_polys)
        if cont_bounds:
            project = make_transform(cont_bounds, CANVAS_W - 30, CANVAS_H, PADDING, offset_x=30)
            for name, region, polys in continente:
                fill = REGION_COLORS.get(region, DEFAULT_FILL)
                for rings in polys:
                    if not rings: continue
                    pts = []
                    for x, y in rings[0]:
                        X, Y = project(x, y)
                        pts.extend([X, Y])
                    pid = draw_polygon(self.canvas, pts, fill=fill)
                    if pid:
                        self.polygon_colors[pid] = fill
                        self.polygon_names[pid] = name
                        self.canvas.tag_bind(pid, "<Enter>", self.on_hover_enter)
                        self.canvas.tag_bind(pid, "<Leave>", self.on_hover_leave)
                        self.canvas.tag_bind(pid, "<Button-1>", lambda e, n=name: self.on_click_district(n))
                    for hole in rings[1:]:
                        pts_h = [coord for x, y in hole for coord in project(x, y)]
                        draw_polygon(self.canvas, pts_h, fill=BG_COLOR)

        # Açores
        if acores:
            ac_polys = [p for _, _, p in acores if p]
            ac_bounds = compute_bounds(ac_polys)
            if ac_bounds:
                ax, ay, aw, ah = 5, CANVAS_H - 120, 160, 90
                self.canvas.create_rectangle(ax, ay, ax+aw, ay+ah, outline="#888")
                self.canvas.create_text(ax+aw/2, ay+10, text="Açores", font=("Helvetica", 8, "bold"))
                minx, miny, maxx, maxy = ac_bounds
                scale = min((aw-10)/(maxx-minx or 1), (ah-20)/(maxy-miny or 1)) * 0.85
                for name, region, polys in acores:
                    fill = REGION_COLORS.get(region, DEFAULT_FILL)
                    for rings in polys:
                        if not rings: continue
                        pts = []
                        for x, y in rings[0]:
                            pts.extend([ax+5+(x-minx)*scale, ay+ah-5-(y-miny)*scale])
                        pid = draw_polygon(self.canvas, pts, fill=fill, width=0.5)
                        if pid:
                            self.polygon_colors[pid] = fill
                            self.polygon_names[pid] = name
                            self.canvas.tag_bind(pid, "<Enter>", self.on_hover_enter)
                            self.canvas.tag_bind(pid, "<Leave>", self.on_hover_leave)
                            self.canvas.tag_bind(pid, "<Button-1>", lambda e, n=name: self.on_click_district(n))

        # Madeira
        if madeira:
            ma_polys = [p for _, _, p in madeira if p]
            ma_bounds = compute_bounds(ma_polys)
            if ma_bounds:
                mx, my, mw, mh = 5, CANVAS_H - 220, 70, 85
                self.canvas.create_rectangle(mx, my, mx+mw, my+mh, outline="#888")
                self.canvas.create_text(mx+mw/2, my+10, text="Madeira", font=("Helvetica", 8, "bold"))
                minx, miny, maxx, maxy = ma_bounds
                scale = min((mw-8)/(maxx-minx or 1), (mh-18)/(maxy-miny or 1)) * 0.85
                for name, region, polys in madeira:
                    fill = REGION_COLORS.get(region, DEFAULT_FILL)
                    for rings in polys:
                        if not rings: continue
                        pts = []
                        for x, y in rings[0]:
                            pts.extend([mx+4+(x-minx)*scale, my+mh-4-(y-miny)*scale])
                        pid = draw_polygon(self.canvas, pts, fill=fill, width=0.5)
                        if pid:
                            self.polygon_colors[pid] = fill
                            self.polygon_names[pid] = name
                            self.canvas.tag_bind(pid, "<Enter>", self.on_hover_enter)
                            self.canvas.tag_bind(pid, "<Leave>", self.on_hover_leave)
                            self.canvas.tag_bind(pid, "<Button-1>", lambda e, n=name: self.on_click_district(n))

    def draw_municipalities(self, district_name):
        self.level = "municipalities"
        self.selected_district = district_name
        self.selected_municipality = None
        self.back_btn.config(state="normal")
        self.title_lbl.config(text=f"Municípios - {district_name}")
        self.clear_canvas()
        orgao = self.organ_var.get()
        self.draw_legend_partidos(f"Vencedor {orgao}:")
        
        data = fetch_municipalities(district_name)
        if not data: return

        bounds = compute_bounds([p for _, p in data if p])
        if not bounds: return
        project = make_transform(bounds, CANVAS_W, CANVAS_H, PADDING)

        self.update_info("Clique num município para ver freguesias")
        self.show_results(fetch_votos_distrito(district_name, orgao), None, f"Distrito: {district_name}", orgao)

        for name, polys in data:
            venc = fetch_vencedor_municipio(district_name, name)
            fill = cor_partido(venc[0], venc[2]) if venc else DEFAULT_FILL
            for rings in polys:
                if not rings: continue
                pts = []
                for x, y in rings[0]:
                    X, Y = project(x, y)
                    pts.extend([X, Y])
                pid = draw_polygon(self.canvas, pts, fill=fill)
                if pid:
                    self.polygon_colors[pid] = fill
                    self.polygon_names[pid] = name
                    self.canvas.tag_bind(pid, "<Enter>", self.on_hover_enter)
                    self.canvas.tag_bind(pid, "<Leave>", self.on_hover_leave)
                    self.canvas.tag_bind(pid, "<Button-1>", lambda e, n=name: self.on_click_municipality(n))
                for hole in rings[1:]:
                    pts_h = [coord for x, y in hole for coord in project(x, y)]
                    draw_polygon(self.canvas, pts_h, fill=BG_COLOR)

    def draw_parishes(self, district_name, municipality_name):
        self.level = "parishes"
        self.selected_district = district_name
        self.selected_municipality = municipality_name
        self.back_btn.config(state="normal")
        self.title_lbl.config(text=f"Freguesias - {municipality_name}")
        self.clear_canvas()
        orgao = self.organ_var.get()
        self.draw_legend_partidos(f"Vencedor {orgao}:")
        
        data = fetch_parishes(district_name, municipality_name)
        self.show_results(fetch_votos_municipio(district_name, municipality_name, orgao), 
                         fetch_resultado_municipio(district_name, municipality_name, orgao), municipality_name, orgao)
        
        if not data: return
        self.update_info("Clique numa freguesia para ver resultados AF")

        bounds = compute_bounds([p for _, p in data if p])
        if not bounds: return
        project = make_transform(bounds, CANVAS_W, CANVAS_H, PADDING)

        for name, polys in data:
            venc = fetch_vencedor_freguesia(district_name, municipality_name, name)
            fill = cor_partido(venc[0], venc[2]) if venc else DEFAULT_FILL
            for rings in polys:
                if not rings: continue
                pts = []
                for x, y in rings[0]:
                    X, Y = project(x, y)
                    pts.extend([X, Y])
                pid = draw_polygon(self.canvas, pts, fill=fill)
                if pid:
                    self.polygon_colors[pid] = fill
                    self.polygon_names[pid] = name
                    self.canvas.tag_bind(pid, "<Enter>", self.on_hover_enter)
                    self.canvas.tag_bind(pid, "<Leave>", self.on_hover_leave)
                    self.canvas.tag_bind(pid, "<Button-1>", lambda e, n=name: self.on_click_parish(n))
                for hole in rings[1:]:
                    pts_h = [coord for x, y in hole for coord in project(x, y)]
                    draw_polygon(self.canvas, pts_h, fill=BG_COLOR)

    def on_click_district(self, name):
        self.draw_municipalities(name)

    def on_click_municipality(self, name):
        if self.selected_district:
            self.draw_parishes(self.selected_district, name)

    def on_click_parish(self, name):
        if self.selected_district and self.selected_municipality:
            orgao = self.organ_var.get()
            self.update_info(f"Freguesia: {name}")
            if orgao == "CM":
                # CM só existe a nível de município, mostrar dados do município
                self.show_results(fetch_votos_municipio(self.selected_district, self.selected_municipality, "CM"),
                                 fetch_resultado_municipio(self.selected_district, self.selected_municipality, "CM"), 
                                 f"{self.selected_municipality} (CM)", "CM")
            else:
                # AF existe a nível de freguesia
                self.show_results(fetch_votos_freguesia(self.selected_district, self.selected_municipality, name),
                                 fetch_resultado_freguesia(self.selected_district, self.selected_municipality, name), name, "AF")

    def on_back(self):
        if self.level == "parishes":
            self.draw_municipalities(self.selected_district)
        elif self.level == "municipalities":
            self.clear_canvas()
            self.draw_districts()

if __name__ == "__main__":
    App()
