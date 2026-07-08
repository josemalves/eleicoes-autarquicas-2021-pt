# Eleições Autárquicas 2021 - Visualizador Interativo

Sistema de visualização dos resultados das Eleições Autárquicas Portuguesas de 2021, com mapa interativo e análise de dados.

## Grupo

- José Alves
- Mariana Gomes


## Requisitos

- Python 3.8+
- Bibliotecas: `pandas`, `openpyxl`, `matplotlib`

```bash
pip install pandas openpyxl matplotlib
```

## Estrutura do Projeto

```
projeto/
├── README.md
├── db/
│   ├── elections.db          # Base de dados SQLite
│   └── create_tables.sql     # DDL - Schema da BD
├── etl/
│   ├── etl_eleicoes.py       # Script ETL principal
│   └── portugal_geoms_dump.sql  # Geometrias WKT
    └── 2021al_mapa_oficial/   # Dados CNE (Excel)
            ├── mapa_1_resultados.xlsx
            ├── mapa_2_perc_mandatos.xlsx
            ├── mapa_3_eleitos.xlsx
            └── mapa_anexo.xlsx
├── app/
│   └── gui.py                # Aplicação GUI principal
├── docs/
│   ├── ER_diagram.md         # Diagrama Entidade-Relação
│   ├── relatorio.pdf         # Relatório do projeto
│   ├── slides.pdf            # Slides da apresentação
│   └── screenshots/          # Capturas de ecrã

    
```

## Como Executar

### Passo 1: Preparar os dados

Descarregar os dados oficiais da CNE:
```bash
wget https://www.cne.pt/sites/default/files/dl/2021al_mapa_oficial.zip
unzip 2021al_mapa_oficial.zip -d data/
```

Mover a pasta para o diretório etl/, para que o programa corra naturalmente.

### Passo 2: Executar o ETL

```bash
cd etl/
python etl_eleicoes.py
```

O script irá:
- Criar a base de dados SQLite (`elections.db`)
- Carregar as geometrias de Portugal
- Processar os dados eleitorais do Excel
- Popular todas as tabelas

**Output esperado:**
```
============================================================
ETL - Eleições Autárquicas 2021
============================================================
✓ 308 municípios
✓ 3087 freguesias
✓ 10730 votos
============================================================
ETL concluído!
============================================================
```

### Passo 3: Executar a aplicação

```bash
cd ..
cd app/
python gui.py
```

## Funcionalidades

### Mapa Interativo
- **Nível 1**: Distritos de Portugal (+ caixas Açores e Madeira)
- **Nível 2**: Municípios do distrito selecionado
- **Nível 3**: Freguesias do município selecionado

### Visualização de Resultados
- Gráfico de barras com Top 10 partidos/coligações
- Tabela detalhada com votos e percentagens
- Estatísticas de participação (inscritos, votantes, abstenção)

### Cores por Partido
- PS (rosa), PSD (laranja), PCP-PEV (vermelho), CDS-PP (azul)
- BE (roxo), CH (azul escuro), IL (ciano), PAN (verde azulado)
- E mais 13 partidos com cores distintas
- Coligações com cores únicas baseadas em hash

## Schema da Base de Dados

```
districts          - 29 distritos/ilhas com geometrias
municipalities     - 308 municípios com geometrias  
parishes           - 3976 freguesias com geometrias
partidos           - 21 partidos políticos
orgaos             - 3 órgãos (CM, AM, AF)
coligacoes         - 408 coligações únicas
resultados         - Resultados agregados por autarquia
votos              - Votos por partido/coligação
```

## Âmbito dos Dados

- **Órgãos**: Câmara Municipal (CM) e Assembleia de Freguesia (AF)
- **Geografia**: Portugal completo (continente + ilhas)
- **Fonte**: CNE - Comissão Nacional de Eleições

## Limitações Conhecidas

1. Assembleia Municipal (AM) não incluída
2. 4 freguesias com dados pendentes na fonte original
3. Geometrias são simplificadas (apenas anel exterior)

## Referências

- [CNE - Resultados Oficiais](https://www.cne.pt)
- [MAI - Portal Eleitoral](https://www.eleicoes.mai.gov.pt/autarquicas2021/)
- [DGT - CAOP](https://www.dgterritorio.gov.pt/cartografia/cartografia-tematica/caop)
