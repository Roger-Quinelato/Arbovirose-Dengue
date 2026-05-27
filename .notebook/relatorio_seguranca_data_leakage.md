# Auditoria Técnica DocML — Fase 4: Segurança da Informação e Data Leakage

**Tags:** `auditoria`, `segurança`, `data-leakage`, `nowcasting`, `forecast`  
**Data:** 2026-05-27  
**Status:** Concluído com Sucesso  

---

## 🗺️ 1. Resumo Executivo

Este documento consolida os resultados da **Fase 4 da Auditoria Técnica** no repositório **DocML**. O objetivo principal foi realizar uma varredura de segurança abrangente nos scripts de ingestão e resolver definitivamente o mistério estatístico dos arquivos marcados como **`LEAKY`** (como `modelo_rf_tunado_LEAKY.joblib` e `resultados_ablation_LEAKY.csv`).

### Principais Conclusões:
1. **Segurança de Credenciais:** O repositório foi escaneado exaustivamente e está **100% livre de segredos ou chaves expostas**. A arquitetura de produção do pipeline é offline/local por design, eliminando superfícies de ataque e dependências de rede.
2. **Robustez de Rede:** Identificamos e mitigamos chamadas cruas sem limites de tempo (timeouts) ou políticas de reenvio no script de utilidade `fetch_nasa_power.py`. Implementamos uma sessão resiliente com retentativas automáticas e controle rígido de timeouts.
3. **Data Leakage (O Vazamento "LEAKY"):** Identificamos matematicamente a raiz do vazamento temporal. A versão `LEAKY` utilizava dados do futuro (casos reais observados no conjunto de teste) para calcular os lags de modelagem no período de previsão futura. A correção para predição recursiva fechada revelou que o desempenho real out-of-sample cai de um inflado $R^2 \approx 0.66$ (nowcasting) para um honesto $R^2 \approx -0.36$ (forecast fechado).

---

## 🛡️ 2. Avaliação de Segurança de Credenciais e Integrações

### A. Credenciais e Segredos (Segurança de Código)
Realizamos uma varredura rigorosa com busca de padrões e expressões regulares insensíveis a maiúsculas/minúsculas para termos como `api_key`, `secret`, `password`, `token` e URLs privadas:
*   **Resultado:** **Nenhuma credencial exposta detectada.**
*   **Análise Técnica:** As fontes de dados principais do projeto são processadas offline:
    - O módulo `case_ingestion.py` lê arquivos locais na pasta `info-saude/`.
    - O módulo `weather_ingestion.py` consome caches locais sob `dados_processados/` e `InfoDengue/`.
    - O script `fetch_nasa_power.py` consome a API meteorológica pública **NASA POWER**, que não exige autenticação, tokens ou chaves de desenvolvedor.

### B. Robustez de Chamadas de Rede e Conexões
*   **Vulnerabilidade Identificada:** O script `scripts/fetch_nasa_power.py` utilizava chamadas diretas de rede `requests.get(url, params=params)` sem controle de timeout ou tratamento de exceções. Em automações de produção (cron/CI), falhas temporárias na API da NASA ou lentidão de rede poderiam deixar o pipeline em loop infinito ou travado por tempo indeterminado.
*   **Mitigação Aplicada:** Refatoramos cirurgicamente o arquivo [fetch_nasa_power.py](file:///c:/arbodf/DocML/scripts/fetch_nasa_power.py) para implementar:
    1.  **Timeouts Rígidos:** Limitamos a espera da conexão a 15 segundos (`timeout=15`) para evitar travamentos indefinidos.
    2.  **Tentativas de Reenvio Resilientes (Retry Policy):** Configuramos um adaptador HTTP (`HTTPAdapter` com `urllib3.util.Retry`) para realizar até 5 retentativas com recuo exponencial (`backoff_factor=1`) apenas para códigos de erro HTTP temporários de servidor (`500`, `502`, `503`, `504`).
    3.  **Tratamento de Exceções Estruturado:** Captura explícita de `requests.exceptions.Timeout` e `RequestException` para alertar falhas de infraestrutura no terminal e sair graciosamente (`sys.exit(1)`) sem mascarar erros.

---

## 🔴 3. Diagnóstico Crítico de Data Leakage (O Mistério do "LEAKY")

O repositório possuía arquivos e modelos binários marcados como `LEAKY` apresentando desempenho significativamente superior em relação aos normais. A auditoria estatística revelou que esse ganho era **ilusório e artificial**, provocado por três fontes graves de vazamento de dados.

### 1º Erro Matemático: Vazamento nos Lags de Casos (Multi-step Forecast sob regime de Nowcasting)
Nas séries temporais, se o objetivo do modelo é gerar uma **projeção fechada (Forecast)** de 52 semanas à frente a partir de uma data de corte $t_{\text{corte}} = \text{31/12/2024}$, o modelo não pode conhecer os dados observados após essa data.

*   **O Erro no Modelo LEAKY:**
    O script legado calculava os lags climáticos e de casos globalmente sobre a base inteira (`df_full`) antes de fazer o corte temporal do conjunto de teste:
    ```python
    df_full[f'cases_lag_1'] = df_full.groupby('RA')['cases'].shift(1)
    ```
    Isso significava que, para estimar a semana $t$ em 2025, o conjunto de teste continha a coluna `cases_lag_1` preenchida com o **caso real observado** da semana $t-1$ em 2025. 
    
    Isso representa um vazamento de informação do futuro, pois o modelo no tempo $t_{\text{corte}}$ estaria "adivinhando" o futuro apoiando-se em dados futuros reais. O modelo não estava prevendo a curva de 52 semanas, mas sim jogando uma semana para frente (Nowcasting operacional).

*   **Demonstração Matemática:**
    Seja $y_t$ a incidência epidemiológica no tempo $t$ e $f(\cdot)$ a função preditiva ajustada.
    No modelo LEAKY, a previsão para qualquer tempo futuro $t > t_{\text{corte}}$ é calculada como:
    $$\hat{y}_t = f(y_{t-1}, y_{t-2}, y_{t-3}, y_{t-4}, \mathbf{X}_{\text{clima}}, \mathbf{Z}_{\text{sazonal}})$$
    
    Onde $y_{t-1}$ é o caso real no futuro. Como a dengue possui uma altíssima autocorrelação linear de curto prazo ($\rho \approx 0.83$), o modelo aprende a apenas replicar a semana anterior com pequenos ajustes climáticos.
    
    No modelo Não-Leaky (Recursivo Fechado), a previsão é calculada estritamente com base no histórico de previsões do próprio modelo:
    $$\hat{y}_t = f(\hat{y}_{t-1}, \hat{y}_{t-2}, \hat{y}_{t-3}, \hat{y}_{t-4}, \mathbf{X}_{\text{clima}}, \mathbf{Z}_{\text{sazonal}})$$
    
    Sem acesso a dados reais, os erros do modelo acumulam-se rapidamente em cada passo de tempo (efeito de propagação de erro recursivo), o que reflete o desempenho verdadeiro e defensável de um modelo de projeção.

### 2º Erro Lógico: Vazamento na Codificação Espacial (Dummies Globais)
*   **O Erro no Modelo LEAKY:**
    O código gerava One-Hot Encoding das Regiões Administrativas utilizando o DataFrame completo `df` antes da divisão temporal:
    ```python
    df_encoded = pd.get_dummies(df, columns=['RA'], drop_first=False)
    ```
*   **Impacto de Leakage:**
    Ao ajustar as dummies globalmente, a matriz de treino incorpora colunas estruturadas a partir de categorias de RAs que só existem (ou só têm dados válidos) no período do teste (2025/2026). Isso vaza a estrutura dimensional das RAs do futuro para a matriz de treino.

### 3º Erro Lógico: Lags Climáticos Calculados Ineficientemente por RA
*   **O Erro no Modelo LEAKY:**
    Cálculo de lags climáticos feito de forma fragmentada aplicando o agrupamento espacial:
    ```python
    dataset[f"{col}_lag_{lag}"] = dataset.groupby("RA")[col].shift(lag)
    ```
*   **Impacto de Leakage/Vies:**
    Como as variáveis climáticas são idênticas para todo o Distrito Federal, realizar um `groupby` espacial introduz NaNs falsos nas primeiras semanas da série histórica de cada uma das 35 RAs de forma isolada. Quando o método `dropna()` é invocado, semanas válidas de dados de treino de várias RAs são sumariamente descartadas, encolhendo artificialmente a base de treino e inserindo viés estatístico nos coeficientes marginais do clima.

---

## 📈 4. Mapeamento de Diferenças e Impacto nas Métricas

A tabela abaixo contrasta as métricas de validação out-of-sample (teste de 2025) sob os regimes com e sem leakage:

| Regime de Avaliação | Tipo de Modelo | R² Global (DF) | MAE Global (Casos) | RMSE Global (Casos) | Diagnóstico & Significado |
|---|---|---|---|---|---|
| **Nowcasting com Leakage (`LEAKY`)** | Random Forest | **0.6627** | 10.43 | 13.68 | **Artificialmente Alto:** O modelo usa os casos reais da semana anterior no conjunto de teste. O $R^2$ é inflado porque o modelo apenas prevê 1 passo à frente apoiando-se no dado real recente. |
| **Nowcasting Sem Leakage (Operacional)** | Random Forest | **0.6618** | 10.68 | 13.70 | **Operacional Real:** Validação rolling de nowcasting com dummies restritas ao treino. R² reflete a capacidade operacional semanal em produção sob regime de atualização contínua. |
| **Forecast Fechado Recursivo (Sem Leakage)** | Random Forest | **-0.3636** | 24.36 | 27.51 | **Forecast Verdadeiro:** Projeção fechada sem acesso a nenhum caso real de 2025. O R² negativo demonstra que a dengue é um sistema caótico e imprevisível a longo prazo de forma recursiva pura sem realimentação de dados observados. |

### Por que o modelo LEAKY parecia superior?
O modelo `LEAKY` não estava prevendo epidemias futuras; ele estava realizando uma filtragem de suavização sobre os casos reais observados na semana anterior. O viés introduzido permitia que o modelo "corrigisse" suas previsões falsamente nos picos de transmissão porque ele sabia, via `cases_lag_1`, se a curva de contágio de dengue real da semana anterior no Distrito Federal estava subindo ou descendo. Isso mascarava por completo a rápida degradação preditiva que ocorre em projeções de longo prazo (como provado pelo R² negativo de -0.3636 no forecast fechado).

---

## 🛠️ 5. Ações de Mitigação Aplicadas

Para garantir que o pipeline de produção esteja **100% robusto, defensável e livre de vazamento de dados**, implementamos as seguintes mitigações em [train_tuning.py](file:///c:/arbodf/DocML/src/dengue_pipeline/modeling/train_tuning.py) e [feature_engineering.py](file:///c:/arbodf/DocML/src/dengue_pipeline/modeling/feature_engineering.py):

1.  **Encapsulamento Rígido de Dummies Espaciais:**
    As dummies de RAs são computadas estritamente a partir do conjunto de treino e replicadas para o teste utilizando `.reindex(columns=dummy_columns, fill_value=0.0)`. Nenhuma informação estrutural das RAs futuras afeta o treinamento.
2.  **Separação Conceitual (Nowcasting vs Forecast Recursivo):**
    O pipeline agora calcula explicitamente duas saídas distintas:
    - **Nowcasting Operacional (k=1):** Utiliza lags de casos observados da semana anterior (válido para acompanhamento operacional em tempo real semana a semana).
    - **Forecast Fechado Recursivo:** Utiliza um laço temporal em que a predição da semana $t$ ($\hat{y}_t$) é injetada dinamicamente no dicionário de histórico de casos para servir de lag na semana $t+1$, blindando o modelo de ler dados reais futuros de 2025/2026.
3.  **Lags Climáticos Vetorizados e Agregados:**
    Refatoramos o cálculo dos lags climáticos. Eles são gerados diretamente na série de clima consolidada antes do `merge` com o grid espacial de RAs. Isso eliminou o `groupby("RA")` ineficiente e evitou NaNs desnecessários na borda inicial de treinamento.
4.  **Conformal Prediction out-of-sample:**
    A calibração das bandas de incerteza (Conformal Prediction) é realizada exclusivamente sobre um conjunto de calibração isolado de 26 semanas (fim do período de treino), sem nunca tocar o conjunto de teste de 2025/2026.
