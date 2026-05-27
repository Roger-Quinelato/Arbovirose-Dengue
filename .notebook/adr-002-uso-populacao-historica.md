# ADR-002: Uso de Denominadores Populacionais Dinâmicos via `populacao_historica.csv`

- **Date**: 2026-05-24
- **Status**: Accepted
- **Deciders**: @Roger, @Antigravity
- **Tags**: `architecture`, `database`, `metrics`, `demografia`

## Context and Problem Statement

No pipeline de modelagem preditiva de dengue por Região Administrativa (`dengue_radf.py`), a taxa de incidência de casos por 100 mil habitantes (`incidencia_100k`) é calculada dividindo o volume de casos semanais pela população da RA.

Anteriormente, o sistema utilizava uma base estática e fixa (`populacao.csv`), contendo a população de **2024** ($2.861.057$ habitantes). 
Isso introduzia um viés metodológico nas séries temporais de 2017 a 2023: ao utilizar a população inflada de 2024 como denominador para anos anteriores, o modelo **subestimava a taxa de incidência histórica real** (quando o DF tinha menos habitantes). 

Além disso, novas RAs (como Sol Nascente/Pôr do Sol em 2019 e Arapoanga/Água Quente em 2022) não estavam georreferenciadas ou projetadas adequadamente para os anos passados.

## Decision Drivers

- **Precisão Científica:** A taxa de incidência real em cada ano deve refletir as proporções demográficas fiéis do DF naquele momento.
- **Prevenção de Ruído:** Evitar distorções nas séries de treino que possam induzir os modelos a aprender relações espaciais errôneas.
- **Modularidade:** A solução deve ser facilmente incorporável no script do pipeline (`dengue_radf.py`) e em futuros notebooks sem quebrar a simetria da grade de dados.

## Considered Options

- **Option A (Do nothing):** Manter o denominador fixo de 2024 para todos os anos históricas.
- **Option B (Reconciliação Geográfica Histórica):** Atribuir população 0 para novas RAs antes de suas criações políticas, somando suas populações de volta às RAs "mãe".
- **Option C (Projeção Histórica Calibrada de 35 RAs):** Gerar um banco de dados dinâmico (`populacao_historica.csv`) retroprojetando a população de todas as 35 RAs usando as curvas oficiais da Codeplan/IBGE ($1,20\%$ e $1,39\%$ ao ano), mantendo a grade simétrica.

## Decision Outcome

Option **"Option C"** foi a escolhida. 
Ela foi implementada gerando a base [populacao_historica.csv](file:///c:/arbodf/DocML/populacao_historica.csv) e documentada em [.notebook/bases-de-dados.md](file:///c:/arbodf/DocML/.notebook/bases-de-dados.md).

Esta opção foi escolhida porque mantém a simetria perfeita exigida pela grade de treinamento de Machine Learning (35 RAs x todas as semanas) e, ao mesmo tempo, corrige o viés temporal demográfico de forma extremamente fiel à realidade física do DF.

### Positive Consequences

- A feature `incidencia_100k` agora é computada com denominadores dinâmicos, elevando o realismo dos dados históricos de treino.
- Melhora o alinhamento de anos de picos anteriores (como 2019) no treinamento do Random Forest e XGBoost.
- Mantém a integridade do código sem necessidade de tratamentos complexos de `NaN` ou `0` em séries de RAs desmembradas.

### Negative Consequences

- Pressupõe que a distribuição interna das RAs seguiu a taxa global de crescimento do DF, o que pode ocultar micro-padrões de crescimento demográfico acelerado em algumas RAs específicas (ex: expansões habitacionais no Sol Nascente).

## Pros and Cons of the Options

### Option A: Do Nothing
*   ❌ **Contra:** Subestima a incidência real de anos passados e cria inconsistência demográfica na série temporal.
*   ✅ **Pró:** Simplicidade de código (não requer merges adicionais).

### Option B: Reconciliação Geográfica Histórica
*   ✅ **Pró:** 100% fiel à história geopolítica do Distrito Federal.
*   ❌ **Contra:** Cria degraus estatísticos abruptos que degradam a performance de preditores de boosting (XGBoost/RF) e complicam o merge de dados.

### Option C: Projeção Histórica Calibrada ✅ Chosen
*   ✅ **Pró:** Combina o rigor matemático das taxas de crescimento com a estabilidade de grade de dados de ML.
*   ❌ **Contra:** Pressupõe taxas de crescimento homogêneas entre RAs.

## Links

- RFC Principal: [RFC-002: Proposta de Pipeline de Análise, Limpeza e Modelagem Preditiva](rfc-002-pipeline-dados-modelagem.md)
- Script de Geração: [gerar_populacao_historica.py](file:///c:/arbodf/DocML/gerar_populacao_historica.py)
- Base de Dados Gerada: [populacao_historica.csv](file:///c:/arbodf/DocML/populacao_historica.csv)
