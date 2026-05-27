# Bases de Dados Epidemiológicas

**Tags:** `dados`, `info-saude`, `dados-gov`, `colunas`
**Descoberto em:** 2026-05-24

## Base `info-saude/` — Dados Locais do DF

**Formato:** CSV com separador `;` | **Colunas:** 15 | **Período:** 2017-2026 | **10 arquivos**

### Colunas Relevantes para o Projeto
| Coluna | Uso |
|---|---|
| `i_data_prim_sintomas` | Data de início dos sintomas → base para agregação temporal |
| `i_ano_semana_prim_sintomas_svs` | Semana epidemiológica SVS (formato `AAAAMM`) |
| `i_class_final` | Filtro obrigatório: manter apenas `"Caso Provável"` |
| `i_desc_classificacao` | Sempre "Dengue" |
| `i_desc_radf_res` | **Região Administrativa** de residência (colunas chave do projeto) |
| `i_desc_regiao_saude_res` | Região de saúde |
| `i_desc_uf_res` | UF de residência (94-97% são DF) |
| `i_faixa_etaria` | Faixa etária (ex: `10_14_anos`) |
| `i_sexo` | Sexo (`Feminino`, `Masculino`) |
| `i_desc_evolucao` | Evolução clínica (`Cura`, `Óbito`, `Ign/Branco`) |
| `i_desc_hospitalizacao` | Hospitalização (`Sim`, `Não`) |
| `i_desc_raca_cor` | Raça/cor |

### Como ler (script)
```python
df = pd.read_csv(arquivo, sep=';', 
                 usecols=['i_class_final', 'i_data_prim_sintomas', 'i_desc_radf_res'])
df = df[df['i_class_final'] == 'Caso Provável']
```

### Tamanhos dos Arquivos
- 2017: ~1,2 MB | 2018: ~840 KB | 2019: ~10 MB | 2020: ~12 MB
- 2021: ~5 MB | 2022: ~17 MB | 2023: ~12 MB | 2024: **~63 MB** (ano epidêmico)
- 2025: ~5 MB | 2026 (parcial): ~378 KB

---

## Base `dados-gov/` — SINAN Nacional

**Formato:** CSV com separador `,` | **Encoding:** `latin-1` | **Colunas:** 107-119 | **8 arquivos**

### Filtro para DF
```python
df = pd.read_csv(arquivo, sep=',', encoding='latin-1')
df_df = df[df['SG_UF'] == 53]  # ou SG_UF_NOT == 53 para notificação no DF
```

### Colunas Destacadas
**Identificação/Temporal:**
- `DT_NOTIFIC`, `SEM_NOT`, `NU_ANO`, `DT_SIN_PRI`, `SEM_PRI`

**Demográfico:**
- `NU_IDADE_N`, `CS_SEXO`, `CS_GESTANT`, `CS_RACA`, `CS_ESCOL_N`

**Sintomas Clínicos (Preditor de Diagnóstico):**
- `FEBRE`, `MIALGIA`, `CEFALEIA`, `EXANTEMA`, `VOMITO`, `NAUSEA`, `DOR_COSTAS`, `ARTRALGIA`, `PETEQUIA_N`

**Sinais de Alarme (Preditor de Gravidade):**
- `ALRM_HIPOT`, `ALRM_PLAQ`, `ALRM_VOM`, `ALRM_SANG`, `ALRM_HEMAT`, `ALRM_ABDOM`

**Exames Laboratoriais (Alta Relevância Clínica):**
- `PLAQ_MENOR` — contagem de plaquetas (↓ = dengue grave)
- `RESUL_NS1`, `RESUL_SORO`, `RESUL_PCR_`, `SOROTIPO` — confirmação e sorotipo viral

**Evolução:**
- `CLASSI_FIN` — classificação final
- `EVOLUCAO` — cura/óbito
- `HOSPITALIZ` — hospitalização

### Arquivos e Anos Cobertos
| Arquivo | Ano (aprox.) | Tamanho |
|---|---|---|
| DENGBR01.csv | ~2001 | 113 MB |
| DENGBR03.csv | ~2003 | 111 MB |
| DENGBR07.csv | ~2007 | 134 MB |
| DENGBR08.csv | ~2008 | 172 MB |
| DENGBR11.csv | ~2011 | 225 MB |
| DENGBR12.csv | ~2012 | 181 MB |
| DENGBR15.csv | ~2015 | 600 MB |
| DENGBR17.csv | ~2017 | 139 MB |

**DF em 2017:** 6.489 casos notificados de 518.483 nacionais

---

## Base `populacao_historica.csv` — Histórico por RA (2017-2026)

**Formato:** CSV com separador `,` | **Colunas:** 3 | **Período:** 2017-2026 | **352 registros**

Esta base de dados foi gerada a partir do cruzamento da **PDAD-A 2024** (população base por RA em 2024) com as taxas de crescimento anual oficiais descritas no estudo de projeções da Codeplan:
*   **Anos $\geq$ 2020:** Crescimento anual de **$1,20\%$**
*   **Anos $<$ 2020:** Crescimento anual de **$1,39\%$**

### Colunas
| Coluna | Descrição |
|---|---|
| `RA` | Nome da Região Administrativa padronizado |
| `ano` | Ano civil da estimativa (2017 a 2026) |
| `populacao` | População total estimada para a RA naquele ano (arredondada para inteiro) |

### Como integrar ao pipeline `dengue_radf.py`
Para utilizar os dados dinâmicos por ano no cálculo da incidência (evitando o viés de subestimação das taxas históricas):
```python
# 1. Carregar a base histórica
df_pop_hist = pd.read_csv('populacao_historica.csv')

# 2. Ao criar as features, extrair o ano da semana epidemiológica
df_grid['ano'] = df_grid['epi_sunday'].dt.year

# 3. Fazer o merge usando RA + ano
df_grid = pd.merge(df_grid, df_pop_hist, on=['RA', 'ano'], how='inner')
```

