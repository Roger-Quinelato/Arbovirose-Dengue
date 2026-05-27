# Visão Geral do Repositório DocML

**Tags:** `estrutura`, `visão-geral`, `scripts`
**Descoberto em:** 2026-05-24

## Estrutura de Diretórios

```
c:\arbodf\DocML\
├── .claude/skills/codenavi/    # skill de navegação de código
├── .notebook/                  # inteligência acumulada (este diretório)
├── artigos/                    # 5 artigos científicos sobre dengue/ML
│   ├── Artificial Intelligence In Medicine.pdf
│   ├── MLeDengueCeará.pdf
│   ├── MLeDengueNaAmericaLatina.pdf
│   ├── Sisamob Barbosa et al 2023.pdf
│   └── informatics-12-00015.pdf
├── dados-gov/                  # SINAN nacional (~8 arquivos, 110-600 MB cada)
│   └── DENGBR{01,03,07,08,11,12,15,17}.csv
├── info-saude/                 # Dados locais DF (2017-2026, 10 arquivos)
│   └── dados_dengue-{data}-ano_{ano}.csv
├── resultados_graficos/        # Gráficos de saída do pipeline
├── scripts/                    # Scripts auxiliares, utilitários e experimentais
│   ├── dengue.py               # Script de séries hierárquicas (EXPERIMENTAL)
│   ├── fetch_nasa_power.py     # Download de dados do NASA POWER
│   └── gerar_populacao_historica.py # Gerador de população histórica (PDAD-A)
├── .venv/                      # Ambiente virtual Python 3.10
├── dados_clima_cache.csv       # Cache climático Open-Meteo (Brasília, semanal)
├── dados_clima_nasa/           # Dados climáticos brutos diários da NASA
├── dengue.ipynb                # Notebook Jupyter com exploração interativa
├── dengue_radf.py              # Pipeline principal (previsão por RA do DF - PRODUÇÃO)
├── populacao.csv               # População das RAs do DF (PDAD-A 2024)
├── populacao_historica.csv     # População por RA dinâmica (2017-2026)
├── previsoes_finais_radf.csv   # Saída do pipeline RF+XGBoost por RA
├── requirements.txt            # Dependências do projeto
└── sintese_dengue_df.md        # Síntese completa dos artigos + análise das bases
```

## Scripts Principais

### `dengue_radf.py` — Pipeline de Previsão por RA (PRODUÇÃO)
O script mais completo. Executa o pipeline completo:
1. Carrega e concatena todos os CSVs do `info-saude/`
2. Filtra `Caso Provável`, agrega por semana epidemiológica + RA
3. Busca/carrega dados climáticos (Open-Meteo via cache)
4. Cria grid completo (todas as datas × todas as RAs)
5. Engenharia de features: lags climáticos (2-8 semanas) + lags de casos (1-4 semanas)
6. Divide treino (2017-2024) × teste (2025-2026)
7. Treina `RandomForestRegressor` + `XGBRegressor` em escala log
8. Gera métricas (MAE, RMSE, R²) e 3 tipos de gráficos

### `scripts/dengue.py` — Hierarquia Nacional (EXPERIMENTAL)
Usa as bibliotecas `statsforecast`, `mlforecast` e `hierarchicalforecast`:
- AutoARIMA + AutoTheta + AutoETS + XGBoost
- Reconciliação hierárquica: BottomUp, MinTrace, TopDown
- Avalia com MAPE hierárquico
- **ATENÇÃO:** Requer um `data.csv` com colunas `data_epi`, `casos`, `uf`, `pais`, `regiao` — não existe no repositório atual

## Dependências Críticas
- `scikit-learn`, `xgboost` — modelos principais
- `statsforecast`, `mlforecast`, `hierarchicalforecast`, `utilsforecast` — para dengue.py
- `requests` — download Open-Meteo
- `pandas`, `numpy`, `matplotlib` — base
