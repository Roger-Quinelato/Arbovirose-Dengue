---
name: dlm-dengue-foundation
description: "Guia teórico-prático para modelagem de curvas epidêmicas de Dengue com DLM univariado. Use when: O usuário precisa estruturar equações de Kalman sequenciais, previsões preditivas ou suavização retrospectiva de arboviroses. Do NOT use for: Dados de contagem não-gaussianos discretos (use dglm-dengue-count-methods) ou inclusão de sazonalidade harmônica complexa e dados de clima (use dlm-dengue-components)."
license: CC-BY-4.0
metadata:
  author: Roger Quinelato
  version: 1.0.0
---

# Fundações de Modelos Dinâmicos Lineares em Epidemiologia (Dengue)

Esta skill fornece diretrizes matemáticas e práticas para formular Modelos Dinâmicos Lineares (DLMs) aplicados a séries temporais de casos de dengue, cobrindo a formulação de espaço de estados, o processo de atualização sequencial Bayesiana e a análise retrospectiva (suavização) para retificar séries históricas de saúde pública.

## Quando Usar Esta Skill (Use When)

Use esta skill em cenários de modelagem de séries temporais de arboviroses onde se deseja:
- Estruturar o espaço de estados de uma curva epidêmica (equações de observação e evolução).
- Aplicar o processo sequencial de inferência Bayesiana (atualização passo a passo a cada semana epidemiológica).
- Calcular distribuições preditivas de curto prazo (*forecast* de 1 a 4 semanas à frente).
- Realizar análise retrospectiva (filtragem e suavização de Kalman) para avaliar o verdadeiro comportamento histórico de um surto e retificar atrasos de digitação ou notificação de casos.

Não use esta skill para (Do NOT use for):
- Modelar sazonalidade anual complexa ou incluir regressões de clima variáveis no tempo (use `dlm-dengue-components`).
- Tratar dados puros de contagem discreta (como Poisson ou Binomial Negativa) sem aproximação gaussiana (use `dglm-dengue-count-methods`).

## Gatilhos de Ativação (Triggers)

### Em Português
- "como estruturar um DLM para dengue"
- "equações de atualização sequencial de casos de dengue"
- "filtro de Kalman bayesiano para séries de epidemiologia"
- "suavização retrospectiva de surto de dengue"
- "modelo constante steady model para dengue"
- "equações de espaço de estados para arboviroses"

### Em Inglês
- "how to structure a dlm for dengue"
- "sequential updating equations for dengue cases"
- "bayesian kalman filter for epidemiology time series"
- "retrospective smoothing of dengue outbreak"
- "steady model for dengue forecasting"
- "state-space equations for arboviruses"

---

## Instruções de Modelagem e Formulação Matemática

### Passo 1: Formulação Espaço-Estado para Curva Epidemiológica (Modelo Estacionário/Steady)

O modelo dinâmico linear univariado básico para a incidência de dengue in uma determinada semana epidemiológica $t$ é especificado por um par de equações lineares gaussianas:

1. **Equação de Observação**:
   $$Y_t = \theta_t + v_t, \quad v_t \sim N(0, V_t)$$
   Onde $Y_t$ é o número transformado de casos de dengue na semana $t$ (por exemplo, aplicando $\log(Casos + 1)$ ou $\sqrt{Casos}$ para estabilização de variância), $\theta_t$ representa o nível verdadeiro da epidemia no tempo $t$, e $v_t$ é o ruído observacional com variância $V_t$.

2. **Equação de Evolução do Estado**:
   $$\theta_t = \theta_{t-1} + w_t, \quad w_t \sim N(0, W_t)$$
   Onde $w_t$ representa a perturbação estocástica do nível epidêmico de uma semana para outra, com variância de evolução $W_t$.

### Passo 2: Atualização Sequencial Bayesiana (Equações de Atualização)

A informação acumulada até a semana $t-1$ é resumida na distribuição a posteriori do estado:
$$(\theta_{t-1} \mid D_{t-1}) \sim N(m_{t-1}, C_{t-1})$$

Para avançar para a semana $t$, seguimos as três etapas fundamentais do filtro sequencial Bayesiano:

1. **Distribuição a Priori do Estado em $t$**:
   $$(\theta_t \mid D_{t-1}) \sim N(a_t, R_t)$$
   Onde:
   $$a_t = m_{t-1}$$
   $$R_t = C_{t-1} + W_t$$

2. **Distribuição Preditiva Unipasso (Forecast)**:
   $$(Y_t \mid D_{t-1}) \sim N(f_t, Q_t)$$
   Onde:
   $$f_t = a_t$$
   $$Q_t = R_t + V_t$$

3. **Distribuição a Posteriori do Estado em $t$**:
   Após observar o valor real de casos $Y_t = y_t$, calculamos a posteriori:
   $$(\theta_t \mid D_t) \sim N(m_t, C_t)$$
   Onde:
   $$m_t = a_t + A_t e_t$$
   $$C_t = R_t - A_t^2 Q_t$$
   E as quantidades auxiliares são:
   - Erro de previsão: $e_t = y_t - f_t$
   - Ganho adaptativo (Ganho de Kalman): $A_t = R_t / Q_t$

### Passo 3: Análise Retrospectiva (Suavização / Smoothing)

Em saúde pública, os dados mais recentes de dengue sofrem com atrasos de notificação (as fichas de notificação física demoram semanas para serem digitadas no Sinan). Análise retrospectiva permite reconstruir a curva histórica real de casos no tempo $t$ usando toda a informação disponível até o presente $T$ ($t < T$).

Dada a posteriori suavizada no tempo $t+1$: $(\theta_{t+1} \mid D_T) \sim N(a_{t+1}(T), R_{t+1}(T))$, a posteriori suavizada no tempo $t$ é obtida recursivamente de trás para frente (de $T-1$ até $1$):
$$(\theta_t \mid D_T) \sim N(a_t(T), R_t(T))$$
Onde:
$$a_t(T) = m_t + B_t (a_{t+1}(T) - a_{t+1})$$
$$R_t(T) = C_t - B_t^2 (R_{t+1} - R_{t+1}(T))$$
E o ganho de suavização é:
$$B_t = C_t / R_{t+1}$$

---

## Implementação Prática em Python

Abaixo está o algoritmo de filtragem e suavização sequencial para o modelo constante de nível local aplicado a uma série de dengue simulada:

```python
import numpy as np
import pandas as pd

def dlm_dengue_filter_smooth(y, m0, C0, V, W):
    """
    y: array-like - Série temporal transformada de casos de dengue
    m0, C0: float - Priori inicial do nível epidêmico
    V: float - Variância observacional
    W: float - Variância de evolução
    """
    T = len(y)
    m = np.zeros(T)
    C = np.zeros(T)
    a = np.zeros(T)
    R = np.zeros(T)
    f = np.zeros(T)
    Q = np.zeros(T)
    m_prev = m0
    C_prev = C0
    for t in range(T):
        a[t] = m_prev
        R[t] = C_prev + W
        f[t] = a[t]
        Q[t] = R[t] + V
        e_t = y[t] - f[t]
        A_t = R[t] / Q[t]
        m[t] = a[t] + A_t * e_t
        C[t] = R[t] - (A_t**2) * Q[t]
        m_prev = m[t]
        C_prev = C[t]
    a_smooth = np.zeros(T)
    R_smooth = np.zeros(T)
    a_smooth[-1] = m[-1]
    R_smooth[-1] = C[-1]
    for t in range(T - 2, -1, -1):
        R_next = R[t+1]
        a_next = a[t+1]
        B_t = C[t] / R_next
        a_smooth[t] = m[t] + B_t * (a_smooth[t+1] - a_next)
        R_smooth[t] = C[t] + (B_t**2) * (R_smooth[t+1] - R_next)
    return pd.DataFrame({
        'Obs': y,
        'Filtrado_Mean': m,
        'Filtrado_Var': C,
        'Suavizado_Mean': a_smooth,
        'Suavizado_Var': R_smooth,
        'Forecast_Mean': f,
        'Forecast_Var': Q
    })
```

---

## Exemplos Práticos de Uso (Example Cases)

### Exemplo 1 (Example 1): Reconstrução Histórica de um Surto de Dengue com Notificação Tardia

**Usuário (User says)**: "Tenho uma série semanal de casos de dengue que está muito poluída com atrasos de notificação nas últimas semanas. Quero rodar um filtro e suavização dinâmicos para entender qual é a verdadeira tendência estabilizada das últimas 10 semanas usando o modelo dinâmico constante de West & Harrison. Como defino a priori e inicializo as equações?"

**Agente (Result / Response)**: "Excelente escolha. Séries epidemiológicas de dengue com atrasos sistemáticos de notificação de fato se beneficiam muito da suavização retrospectiva do espaço de estados, pois ela redistribui o peso da informação futura para estimar o nível epidemiológico real do passado.

Vamos modelar utilizando o **Modelo Constante Dinâmico** (Steady Model) sobre a escala de logaritmo estabilizada: $y_t = \log(\text{casos}_t + 1)$.

1. **Definição da Priori Inicial**: Se antes de analisar a série você sabe que a média histórica é de aproximadamente 150 casos por semana no período basal, temos $\log(150 + 1) \approx 5.0$. Podemos definir a priori inicial do nível como:
   $$\theta_0 \sim N(m_0 = 5.0, C_0 = 1.0)$$
   (Uma variância $C_0 = 1.0$ representa bastante incerteza na escala logarítmica).

2. **Parametrização das Variâncias de Ruído**:
   - **Variância Observacional $V$**: Reflete o ruído de notificação. Definimos como $V = 0.25$ (desvio padrão de 0.5 na escala log).
   - **Variância de Evolução $W$**: Reflete a velocidade com que a taxa de transmissão muda. Um valor de $W = 0.04$ permite que o nível mude suavemente semana a semana.

Aqui está o código completo para rodar a reconstrução e extrair o nível epidêmico real suavizado na escala original:

```python
# Massa de dados semanal simulada log-casos
casos_dengue = [120, 135, 140, 190, 250, 310, 420, 390, 350, 280, 200, 150, 110]
y = np.log1p(casos_dengue)

# Executando o modelo
resultados = dlm_dengue_filter_smooth(y, m0=5.0, C0=1.0, V=0.25, W=0.04)

# Convertendo o nível real suavizado de volta para a escala de contagem de casos
resultados['Casos_Suavizados'] = np.expm1(resultados['Suavizado_Mean'])
resultados['Casos_Limite_Superior'] = np.expm1(resultados['Suavizado_Mean'] + 1.96 * np.sqrt(resultados['Suavizado_Var']))
resultados['Casos_Limite_Inferior'] = np.expm1(resultados['Suavizado_Mean'] - 1.96 * np.sqrt(resultados['Suavizado_Var']))

print(resultados[['Obs', 'Casos_Suavizados', 'Casos_Limite_Inferior', 'Casos_Limite_Superior']])
```

Esse procedimento removerá os ruídos de digitação pontuais e fornecerá a curva real estabilizada, com intervalos de credibilidade Bayesianos de 95% para cada semana epidemiológica."

---

## Diretrizes de Resolução de Problemas (Troubleshooting)

### Problema 1: Inércia Excessiva do Nível Estimado (O modelo não acompanha a subida rápida de uma epidemia de dengue)
- **Causa**: A variância de evolução $W$ está muito pequena em relação à variância observacional $V$. O ganho de Kalman $A_t$ fica muito baixo, fazendo com que o modelo trate a explosão de novos casos como ruído temporário ($v_t$) em vez de uma mudança estrutural no nível verdadeiro da transmissão ($\theta_t$).
- **Solução**:
  1. Aumente temporariamente a volatilidade de evolução $W$ (ex: multiplique por 2 ou 3) para permitir que a taxa de transmissão se adapte rapidamente.
  2. Implemente fatores de desconto (*discount factors*) para atualizar $R_t = C_{t-1} / \delta$ (com $\delta \in [0.9, 0.98]$) em vez de um $W$ estático. Isso é detalhado na skill `dlm-dengue-components`.

### Problema 2: Instabilidade Matemática ao Lidar com Baixas Contagens de Casos (Períodos Interepidêmicos)
- **Causa**: Durante o inverno, a contagem de casos de dengue cai para zero ou valores próximos de zero. Aplicar transformações como $\log(Y_t)$ em séries com muitos zeros introduz forte assimetria e violação da hipótese de normalidade dos resíduos.
- **Solução**:
  1. Se a aproximação gaussiana for estritamente necessária, utilize a transformação raiz quadrada $\sqrt{Y_t + 3/8}$ (transformação de Anscombe), que estabiliza melhor a variância de contagens pequenas.
  2. Para modelar adequadamente períodos com muitos zeros sem perder a coerência probabilística, mude para modelos Bayesianos de contagem Poisson Dinâmica usando a skill `dglm-dengue-count-methods`.
