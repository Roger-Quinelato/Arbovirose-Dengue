# Base de Dados InfoDengue (Fiocruz/FGV)

**Tags:** `dados`, `infodengue`, `fiocruz`, `clima`, `alertas`, `Rt`
**Descoberto em:** 2026-05-24

## Visão Geral do Dataset

O diretório `InfoDengue/` contém dados epidemiológicos e climáticos semanais obtidos diretamente do portal **InfoDengue** (Fiocruz/FGV) para o município de Brasília (Distrito Federal, ID: `5300108`). 

Esses dados representam uma fonte extremamente rica de inteligência epidemiológica oficial pré-processada, cobrindo o período de **2006 a 2026**.

### Arquivos no Diretório
*   [InfoDengue_2006-2025.csv](file:///c:/arbodf/DocML/InfoDengue/InfoDengue_2006-2025.csv): Série histórica longa de 2006 a 2025.
*   [InfoDengue_2016-2026.csv](file:///c:/arbodf/DocML/InfoDengue/InfoDengue_2016-2026.csv): Série focada nos últimos 10 anos, cobrindo até maio de 2026.
*   [InfoDengue_2026(Jan-Mai).csv](file:///c:/arbodf/DocML/InfoDengue/InfoDengue_2026(Jan-Mai).csv): Dados parciais recentes de 2026.
*   [DicionarioBase.txt](file:///c:/arbodf/DocML/InfoDengue/DicionarioBase.txt): Dicionário de colunas explicativo.

---

## Estrutura e Colunas Principais

A base do InfoDengue possui **31 colunas** que integram vigilância epidemiológica, dados climáticos locais, estimativas de Rt e até menções em redes sociais:

### 1. Dados Epidemiológicos e Vigilância
*   `data_iniSE`: Data do primeiro dia da semana epidemiológica (Domingo) — chave perfeita para agrupamento temporal.
*   `SE`: Código da semana epidemiológica (`AAAASS`).
*   `casos`: Número de casos reais de dengue notificados na semana.
*   `casos_est`: Casos estimados via modelo de *nowcasting* (corrige o atraso de notificação retrospectivamente).
*   `casos_est_min` e `casos_est_max`: Intervalo de credibilidade de 95% do *nowcasting*.
*   `p_inc100k`: Taxa de incidência estimada por 100 mil habitantes.
*   `nivel`: Nível de alerta oficial da semana:
    *   `1` = Verde (Semana não-epidêmica, controle)
    *   `2` = Amarelo (Atenção, transmissão ativa)
    *   `3` = Laranja (Alerta, risco de surto)
    *   `4` = Vermelho (Epidemia instalada)

### 2. Indicadores Biológicos e Transmissão
*   `Rt`: Estimativa do número de reprodução efetivo (média de pessoas infectadas por cada caso ativo).
*   `p_rt1`: Probabilidade do $R_t > 1$. Um critério para emitir o alerta laranja é `p_rt1 > 0.95` por 3 ou mais semanas consecutivas.
*   `receptivo`: Receptividade climática para capacidade vetorial do mosquito:
    *   `0` = Desfavorável
    *   `1` = Favorável
    *   `2` = Favorável nesta semana e na passada
    *   `3` = Favorável por $\geq 3$ semanas (suficiente para o ciclo completo do mosquito e incubação).
*   `transmissao`: Evidência de transmissão ativa sustentada (`0` = Nenhuma, `1` = Possível, `2` = Provável, `3` = Altamente Provável).
*   `nivel_inc`: Incidência em relação aos limiares (`0` = abaixo do limiar pré-epidemia, `1` = acima do limiar pré-epidemia mas abaixo do epidêmico, `2` = acima do limiar epidêmico).

### 3. Climatologia Integrada (Dados Locais Ricos)
Diferente da cache Open-Meteo do projeto (que possui apenas precipitação e temperatura), o InfoDengue traz **dados de umidade relativa**, cruciais para a sobrevida do mosquito adulto:
*   `tempmin`, `tempmed`, `tempmax`: Média das temperaturas mínimas, médias e máximas diárias na semana.
*   `umidmin`, `umidmed`, `umidmax`: Média da umidade relativa mínima, média e máxima diária na semana.

### 4. Inteligência Digital
*   `tweet`: Número de tweets relacionados à dengue na região (usado como termômetro social de surto em tempo real).

---

## Oportunidades para o Projeto DocML

O dataset InfoDengue abre excelentes caminhos de modelagem no Distrito Federal:

1.  **Baseline de Comparação:** As predições de nossos modelos baseados em Regiões Administrativas (`dengue_radf.py`) podem ser agregadas para o nível DF e comparadas diretamente com a curva de `casos_est` (nowcasting) e o nível de alerta (`nivel`) do InfoDengue.
2.  **Enriquecimento Metereológico:** Podemos utilizar a série histórica de umidade relativa (`umidmed`, `umidmin`) como novas features de lag no nosso modelo principal. A literatura destaca que a umidade relativa elevada é um dos maiores impulsionadores da transmissão devido ao prolongamento da vida útil do *Aedes aegypti*.
3.  **Modelagem de Alerta Preditivo:** Podemos treinar um classificador para prever se a próxima semana atingirá o alerta laranja (`nivel >= 3`) ou vermelho (`nivel == 4`) com 4 a 8 semanas de antecedência, usando os lags climáticos e a probabilidade `p_rt1`.

### Exemplo de Carregamento Rápido em Python
```python
import pandas as pd

# Carregar base focada
df_infodengue = pd.read_csv('InfoDengue/InfoDengue_2016-2026.csv')
df_infodengue['ds'] = pd.to_datetime(df_infodengue['data_iniSE'])

# Filtrar apenas colunas úteis para modelagem
cols_ml = ['ds', 'casos', 'casos_est', 'Rt', 'tempmed', 'umidmed', 'nivel']
df_filtered = df_infodengue[cols_ml].sort_values('ds')
```
