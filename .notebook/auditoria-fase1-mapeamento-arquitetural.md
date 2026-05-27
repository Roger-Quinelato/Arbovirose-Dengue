# Auditoria Fase 1 — Mapeamento Arquitetural

**Tags:** `auditoria`, `arquitetura`, `leakage`, `duplicação`, `pontos-criticos`
**Data:** 2026-05-27

---

## Fluxo de Dados Principal (src/dengue_pipeline/)

```
info-saude/*.csv  ──► etl/case_ingestion.py:ler_info_saude()
                           │ (filtro familia_dengue, normaliza RA, epi_sunday)
                           ▼
dados_processados/        ──► shared_kernel/ra_registry.py:carregar_historico_populacao()
populacao_historica.csv        │
                               ▼
dados_processados/        ──► etl/weather_ingestion.py:carregar_clima()
dados_clima_cache.csv +        │ (merge Open-Meteo + InfoDengue umidade)
InfoDengue/InfoDengue_         │
2016-2026.csv                  ▼
                       modeling/feature_engineering.py:construir_dataset_processado()
                           │ (grid RA×semana, lags casos 1-4, lags clima 2-8,
                           │  delta/growth_rate, sin/cos sazonais, incidência)
                           ▼ → salva dataset_processado.parquet (raiz do projeto)
                       modeling/evaluation.py:executar_testes_ablacao()
                           │ (4 configs × 2 modelos — ajustar_prever_config)
                           ▼
                       modeling/train_tuning.py:tunar_modelos()
                           │ (GridSearch + TimeSeriesSplit gap=4)
                           ▼ → salva scripts/modelo_rf_tunado.joblib
                                             scripts/modelo_xgb_tunado.joblib
                       modeling/train_tuning.py:executar_validacao_rolling()
                           │ (nowcasting k=1 vs forecast fechado recursivo)
                           │ + conformal_prediction.py (bandas dinâmicas 90%)
                           ▼ → predicoes_rolling_nowcasting.csv
                               predicoes_forecast_fechado.csv
                       reporting/report_writer.py:gerar_visualizacoes_finais()
                           ▼ → resultados_graficos/ + .notebook/relatorio-final.md
```

---

## Pontos Críticos Identificados

### 🔴 CRÍTICO: Artefatos LEAKY presentes no root
- `predicoes_modelos_finais_LEAKY.csv` (root)
- `resultados_ablation_LEAKY.csv` (root)
- `resultados_ablation_winner_LEAKY.json` (root)
- `resultados_tuning_LEAKY.csv` (root)
- `scripts/modelo_rf_tunado_LEAKY.joblib` (181 MB!)
- `scripts/modelo_xgb_tunado_LEAKY.joblib`
→ **Risco:** Esses arquivos existem paralelamente aos "limpos" sem separação clara de ambiente/branch. Modelos LEAKY ainda executáveis localmente; risco de confusão operacional e uso inadvertido.

### 🔴 CRÍTICO: Modelos e artefatos de saída salvos em `scripts/`
- `scripts/modelo_rf_tunado.joblib` (181 MB)
- `scripts/modelo_xgb_tunado.joblib`
→ Pasta `scripts/` é destinada a utilitários e coleta de dados. Artefatos pesados de modelagem deveriam ir para `resultados_modelagem/` (caminho correto definido em `train_tuning.py:BASE_DIR`). O path de saída está hardcoded como `SCRIPTS_DIR` em `tunar_modelos()` — divergência entre design e implementação.

### 🟡 MÉDIO: `dataset_processado.parquet` gravado na raiz do projeto
- `feature_engineering.py:L93` salva em `BASE_DIR / "dataset_processado.parquet"` (root)
- `.gitignore` ignora `*.parquet` mas o arquivo existe fisicamente no root (318 KB rastreado em commits anteriores)
→ Deveria ser salvo em `dados_processados/`.

### 🟡 MÉDIO: Duplicação entre `dengue_radf.py` e `src/dengue_pipeline/`
- `dengue_radf.py` implementa inteiramente: carregamento, limpeza, feature engineering, treinamento (RF+XGB), métricas e gráficos.
- `src/dengue_pipeline/` replica toda essa lógica de forma modular, com melhorias substanciais.
- Os dois caminhos coexistem sem documentação de deprecação.
- `dengue_radf.py` usa `normalize_ra()` embutida; `src/` usa `shared_kernel/ra_registry.py:normalizar_ra()` — duas implementações do mesmo mapeamento de RAs.

### 🟡 MÉDIO: Ausência de `__main__.py` ou entrypoint documentado no pacote modular
- `src/dengue_pipeline/__init__.py` está vazio.
- O README menciona `python -m dengue_pipeline` mas não existe `__main__.py`.
- Não há como executar o pipeline modular sem saber a ordem de chamada das funções internas.

### 🟡 MÉDIO: Lags climáticos calculados por RA em `feature_engineering.py:L80`
```python
dataset[f"{col}_lag_{lag}"] = dataset.groupby("RA")[col].shift(lag)
```
→ Clima é uma variável **única para o DF** (não por RA). Fazer `groupby("RA").shift()` é semanticamente incorreto — não há variação de clima por RA, o que pode introduzir pequenas distorções de borda (NaN nos primeiros lags de cada RA ao invés de usar a série contínua do DF). Em `dengue_radf.py` o lag climático é calculado corretamente sobre a tabela de clima antes do merge.

### 🟢 OBSERVAÇÃO: `gerar_populacao_historica.py` usa `iterrows()`
- `scripts/gerar_populacao_historica.py:L30`: `for idx, row in df_base.iterrows()`
- Não é crítico para este script (n=33 RAs), mas é padrão anti-performático.

### 🟢 OBSERVAÇÃO: `report_writer.py` usa `iterrows()` em `df_para_markdown()`
- `report_writer.py:L40`: `for _, row in df.iterrows()` — aceitável para formatação de tabelas pequenas.

### 🟢 OBSERVAÇÃO: Arquivo `plano_prompts_opus.md` (22 KB) no root
- Documento de planejamento interno, não faz parte do código nem dos dados.
- Deveria estar em `.notebook/` ou ser ignorado.

---

## Estrutura de Módulos (src/dengue_pipeline/)

| Módulo | Responsabilidade |
|---|---|
| `etl/case_ingestion.py` | Leitura e filtragem dos CSVs info-saude |
| `etl/weather_ingestion.py` | Cache climático + merge umidade InfoDengue |
| `modeling/feature_engineering.py` | Grid RA×semana, lags, sazonais, parquet |
| `modeling/train_tuning.py` | Fábrica de modelos, ablação, tuning, rolling |
| `modeling/evaluation.py` | Métricas globais e por RA, ablação sistemática |
| `modeling/conformal_prediction.py` | Bandas de incerteza dinâmicas (Inductive CP) |
| `reporting/report_writer.py` | Gráficos EDA, ablação, finais, relatórios MD |
| `shared_kernel/ra_registry.py` | Normalização de RAs, histórico demográfico |
| `shared_kernel/epi_calendar.py` | Calendário epidemiológico (SE → domingo) |

---

## Referências de Código Chave

- Lag climático por RA (bug semântico): `feature_engineering.py` L77-80
- Modelos salvos em local errado: `train_tuning.py:tunar_modelos()` L223
- Dataset parquet no root: `feature_engineering.py` L93
- Duplicação normalize_ra: `dengue_radf.py` L17-43 vs `shared_kernel/ra_registry.py` L95-113
