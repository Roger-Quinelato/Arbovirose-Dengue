# Pipeline: dengue_radf.py

**Tags:** `pipeline`, `dengue_radf.py`, `features`, `modelos`
**Descoberto em:** 2026-05-24

## Fluxo de Execução

```
info-saude/*.csv  ──┐
                    ├──> carregar_e_limpar_dados()  ──> df_cases (epi_sunday, RA, cases)
populacao.csv   ──┐│
                  ├──> carregar_dados_demograficos() -> df_pop (RA, populacao)
Open-Meteo API ──┐││
dados_clima_cache├──> obter_dados_climaticos()      -> df_weather (semanal, Brasília)
                 │││
                 └┴┴──> criar_grid_e_features()     -> df_dataset
                                                          │
                                                          └──> treinar_e_avaliar()
                                                                    │
                                                                    ├──> RF + XGB em log(1+cases)
                                                                    ├──> métricas MAE/RMSE/R²
                                                                    └──> previsoes_finais_radf.csv
                                                                              │
                                                                         gerar_graficos()
                                                                              │
                                                                    resultados_graficos/
```

## Features do Modelo

### Lags Climáticos (de `df_weather`)
- `precip_lag_2` a `precip_lag_8` — precipitação com 2 a 8 semanas de defasagem
- `temp_mean_lag_2` a `temp_mean_lag_8` — temperatura média defasada
- `temp_min_lag_2` a `temp_min_lag_8` — temperatura mínima defasada
- `temp_max_lag_2` a `temp_max_lag_8` — temperatura máxima defasada

### Lags de Autocorrelação de Casos (por RA)
- `cases_lag_1` a `cases_lag_4` — casos das últimas 1-4 semanas (agrupado por RA!)
- Nota: `incid_lag_*` é criado mas excluído das features no treino

### Variáveis Sazonais
- `week_of_year` — semana do ano (1-53)
- `month` — mês (1-12)

### Codificação Espacial
- One-Hot Encoding das RAs (`RA_CEILÂNDIA`, `RA_SAMAMBAIA`, etc.)

### Target
- `log1p(cases)` — transformação logarítmica para estabilizar variância dos picos

## Divisão Temporal
- **Treino:** 2017 → 2024-12-31
- **Teste (out-of-sample):** 2025-01-01 → atual

## Modelos
| Modelo | Parâmetros-chave |
|---|---|
| `RandomForestRegressor` | n_estimators=100, max_depth=15, n_jobs=-1 |
| `XGBRegressor` | n_estimators=150, lr=0.05, max_depth=6, n_jobs=-1 |

## Gotchas Importantes
1. **Lags de casos devem ser calculados agrupados por RA** (`groupby('RA')['cases'].shift(lag)`) — misturar datas de RAs diferentes gera data leakage
2. **Open-Meteo cache:** se `dados_clima_cache.csv` existe, a API não é chamada. Para atualizar, deletar o cache
3. **Normalização de RAs:** `normalize_ra()` mapeia variações de grafia (sem acento, abreviações) para o padrão do `populacao.csv`
4. **`data.csv` não existe:** `dengue.py` depende de um arquivo `data.csv` que não está no repositório. Esse script está incompleto/experimental
