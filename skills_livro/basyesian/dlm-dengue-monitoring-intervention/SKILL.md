---
name: dlm-dengue-monitoring-intervention
description: "Guia avançado para aplicação de intervenções subjetivas de saúde pública, alarmes automáticos de surtos de dengue via fatores de Bayes e modelagem multiprócesso de mistura (Classe I e II) em séries temporais. Use when: O usuário precisa injetar conhecimentos epidemiológicos subjetivos (como novo sorotipo), configurar alarmes de detecção precoce de epidemia ou alternar regimes dinâmicos. Do NOT use for: Formulações clássicas básicas de espaço de estados (use dlm-dengue-foundation) ou modelagem direta de sazonalidade e clima (use dlm-dengue-components)."
license: CC-BY-4.0
metadata:
  author: Roger Quinelato
  version: 1.0.0
---

# Intervenção Epidemiológica, Alarmes de Surto e Modelos Multiprócesso

Esta skill apresenta os conceitos de gestão epidemiológica dinâmica através do monitoramento de modelos Bayesianos. Ela aborda como introduzir conhecimento clínico ou biológico externo nos estados de um DLM univariado (intervenções feed-forward), como monitorar a adequabilidade do modelo para detectar o início explosivo de epidemias (surtos de dengue) e como misturar e alternar dinamicamente entre modelos sob diferentes regimes de transmissão (Modelos Multiprócesso de Classe I e II).

## Quando Usar Esta Skill (Use When)

Use esta skill em cenários de vigilância epidemiológica onde seja necessário:
- Realizar intervenções subjetivas para acomodar perturbações externas conhecidas a priori (ex: chegada do sorotipo DENV-3, aumento rápido de criadouros por chuvas atípicas ou mudanças no protocolo de notificação da rede hospitalar).
- Configurar alarmes de surto baseados na análise em tempo real de erros de previsão normalizados usando Fatores de Bayes (*Bayes' Factors*).
- Projetar um modelo que represente a concorrência e mistura estocástica de regimes, como o regime de "Transmissão Basal/Endêmica" e o regime "Epidêmico/Surto", calculando as probabilidades a posteriori de estarmos em epidemia a cada nova semana.

Não use esta skill para (Do NOT use for):
- Montar as equações matemáticas do filtro de Kalman clássico ou da suavização histórica simples (use `dlm-dengue-foundation`).
- Desenvolver decomposições de regressão climática e sazonalidade clássicas sem quebras estruturais ou misturas (use `dlm-dengue-components`).

## Gatilhos de Ativação (Triggers)

### Em Português
- "como injetar conhecimento epidemiológico subjetivo no DLM"
- "alarme de surto de dengue usando fator de Bayes"
- "modelagem multiprócesso classe I e II para dengue"
- "intervenção subjetiva em séries temporais de saúde pública"
- "detectar quebra estrutural na curva epidêmica de dengue"
- "modelo de mistura bayesiana para epidemia e endemia"

### Em Inglês
- "how to inject subjective epidemiological knowledge into DLM"
- "dengue outbreak alarm using Bayes' Factor"
- "multi-process modeling class I and II for dengue"
- "subjective intervention in public health time series"
- "detect structural breaks in dengue epidemic curves"
- "bayesian mixture model for epidemic and endemic regimes"

---

## Métodos Teóricos e Epidemiológicos de Monitoramento

### 1. Intervenções Subjetivas (Expert Priors / Feed-Forward)

A maior vantagem da abordagem Bayesiana de West & Harrison é a capacidade de combinar dados passados com conhecimentos epidemiológicos futuros subjetivos. Se um biólogo avisa que um novo sorotipo viral começou a circular em uma região antes imune, a taxa de transmissão ($\theta_t$) vai explodir de forma que o histórico anterior não consegue prever.

Modelamos isso realizando uma **intervenção no tempo $t$**:
Dada a distribuição a posteriori na semana epidemiológica $t-1$: $(\theta_{t-1} \mid D_{t-1}) \sim N(m_{t-1}, C_{t-1})$.

Em vez de usar a evolução rotineira, o epidemiologista injeta uma **priori modificada**:
- **Alteração do Nível Esperado ($m_{t-1}^*$)**: Se esperamos um aumento imediato na transmissão, ajustamos $m_{t-1}^* = m_{t-1} + \Delta$, onde $\Delta$ é o ganho logarítmico esperado de incidência.
- **Aumento de Incerteza ($C_{t-1}^*$)**: Para permitir que o modelo se adapte instantaneamente a qualquer quebra de tendência, aumentamos a covariância adicionando uma matriz de incerteza subjetiva $H_t$:
  $$C_{t-1}^* = C_{t-1} + H_t$$
  Isso fará com que o ganho adaptativo $A_t$ na semana seguinte fique próximo de 1.0, forçando o modelo a "esquecer" o passado e rastrear os novos dados imediatamente.

### 2. Monitoramento de Alarmes de Surtos via Fatores de Bayes

A detecção de um surto de dengue pode ser formulada como um teste sequencial de hipóteses concorrentes baseadas em densidades preditivas de curto prazo:
- **Hipótese Nula ($H_0$)**: O modelo rotineiro (endêmico/sazonal padrão) é adequado.
- **Hipótese Alternativa ($H_1$)**: Ocorre uma perturbação ou quebra estrutural (surto/epidemia rápida).

Dada a observação de casos reais $y_t$:
O modelo rotineiro fornece a densidade preditiva de $y_t$ dada a história passada $D_{t-1}$:
$$p(y_t \mid H_0, D_{t-1}) = N(y_t \mid f_t, Q_t)$$

Definimos um modelo alternativo $H_1$ onde a incerteza é ampliada (por exemplo, dividindo por um fator de desconto agressivo para prever flutuações rápidas), gerando uma variância preditiva muito maior: $Q_{t,1} \gg Q_t$. A densidade preditiva sob $H_1$ é:
$$p(y_t \mid H_1, D_{t-1}) = N(y_t \mid f_t, Q_{t,1})$$

A cada semana epidemiológica, calculamos o **Fator de Bayes Preditivo ($H_t$)**:
$$H_t = \frac{p(y_t \mid H_0, D_{t-1})}{p(y_t \mid H_1, D_{t-1})}$$
- Se $H_t < 0.1$, a evidência em favor da rotina padrão colapsa, indicando que uma anomalia severa (início de um surto explosivo) está em curso.
- Para evitar alarmes falsos devido a ruídos semanais individuais, monitoramos o **Fator de Bayes Acumulado ($L_t$)**:
  $$L_t = H_t L_{t-1}$$
  Se $L_t$ cruzar um limite inferior crítico (ex: $\tau = 0.01$), um **alarme epidemiológico de surto** é ativado, disparando alertas para a secretaria de saúde. Se o modelo se normalizar, o fator acumulado é resetado para 1.0.

### 3. Modelos Multiprócesso (Classe I e Classe II)

Em vez de usar um único modelo estático, os Modelos Multiprócesso assumem que a realidade é composta por uma coleção de modelos concorrentes $\mathcal{M} = \{M_1, M_2, \dots, M_K\}$.

- **Classe I (Modelos de Parâmetros Dinâmicos Estáticos)**:
  Assume-se que um único modelo $M_j$ é o correto para toda a série, mas não sabemos qual. Útil para identificar se a dinâmica de transmissão de uma cidade é melhor descrita por uma sazonalidade de 1 harmônico ($M_1$) ou de 2 harmônicos ($M_2$).
  As probabilidades a posteriori de cada modelo $p_j(t) = P(M_j \mid D_t)$ são atualizadas recursivamente:
  $$p_j(t) \propto p_j(t-1) p(y_t \mid M_j, D_{t-1})$$

- **Classe II (Modelos de Quebra e Mudança de Regime)**:
  Assume-se que a cada semana $t$, o sistema pode transicionar de regime de transmissão. Por exemplo:
  - $M_1$: Regime Basal (Padrão de transmissão estável/endêmico)
  - $M_2$: Regime de Outbreak (Início de epidemia explosiva)
  - $M_3$: Regime de Transição Pós-Outbreak (Declínio e arrefecimento da transmissão)

  As previsões a cada passo são uma **combinação de misturas gaussianas**. Para evitar o crescimento exponencial da árvore de misturas (um aumento de $K^t$ caminhos possíveis), o algoritmo de aproximação de Harrison-Stevens colapsa as misturas a cada passo de volta para $K$ distribuições normais equivalentes usando médias ponderadas das posteriori.

---

## Implementação Prática em Python

A classe abaixo implementa o monitoramento em tempo real de séries de Dengue com Fator de Bayes e emissão automática de alarmes baseada em resíduos preditivos padronizados:

```python
import numpy as np
import pandas as pd
from scipy.stats import norm

class DengueOutbreakMonitor:
    def __init__(self, threshold_alarm=0.05, sensitivity=2.0):
        self.threshold_alarm = threshold_alarm
        self.sensitivity = sensitivity
        self.L_t = 1.0
        
    def step_monitor(self, y_obs, f_t, Q_t):
        prob_H0 = norm.pdf(y_obs, loc=f_t, scale=np.sqrt(Q_t))
        Q_t_alt = Q_t * self.sensitivity
        prob_H1 = norm.pdf(y_obs, loc=f_t, scale=np.sqrt(Q_t_alt))
        H_t = prob_H0 / (prob_H1 + 1e-12)
        self.L_t = self.L_t * H_t
        is_alarm = False
        if self.L_t < self.threshold_alarm:
            is_alarm = True
            self.L_t = 1.0 
        elif self.L_t > 1.5:
            self.L_t = 1.0
        return {
            'Bayes_Factor_Step': H_t,
            'Bayes_Factor_Cumulative': self.L_t,
            'Outbreak_Alarm': is_alarm,
            'Standardized_Residual': (y_obs - f_t) / np.sqrt(Q_t)
        }

    def process_series(self, y, forecasts, variances):
        T = len(y)
        bf_step = np.zeros(T)
        bf_cum = np.zeros(T)
        alarms = np.zeros(T, dtype=bool)
        residuals = np.zeros(T)
        for t in range(T):
            res = self.step_monitor(y[t], forecasts[t], variances[t])
            bf_step[t] = res['Bayes_Factor_Step']
            bf_cum[t] = res['Bayes_Factor_Cumulative']
            alarms[t] = res['Outbreak_Alarm']
            residuals[t] = res['Standardized_Residual']
        return pd.DataFrame({
            'Real': y,
            'Forecast': forecasts,
            'Residuo_Padronizado': residuals,
            'Fator_Bayes_Semana': bf_step,
            'Fator_Bayes_Acumulado': bf_cum,
            'Alarme_Surtos': alarms
        })
```

---

## Exemplos Práticos de Uso (Example Cases)

### Exemplo 1 (Example 1): Detecção de Surto e Aplicação de Intervenção Externa por Novo Sorotipo

**Usuário (User says)**: "Minha cidade está enfrentando um aumento atípico de casos de dengue que o modelo sazonal básico não previu. Os resíduos de curto prazo estão enormes. Além disso, a vigilância genômica acabou de confirmar que o sorotipo DENV-3 começou a circular amplamente. Como estruturo o alarme automático usando fatores de Bayes e aplico uma intervenção manual para o modelo se recuperar?"

**Agente (Result / Response)**: "Esta é uma situação crítica onde a simbiose entre automação estatística (fatores de Bayes) e julgamento clínico humano (intervenção feed-forward) se torna indispensável. O ciclo do vírus DENV-3 vai expor uma grande parcela de suscetíveis na população, quebrando o padrão sazonal normal.

1. **Passo 1: Detecção do Surto**:
   O monitor de Fatores de Bayes comparará a verossimilhança dos resíduos preditivos. Quando a incidência real $y_t$ sobe muito acima da média sazonal $f_t$, o Fator de Bayes acumulado colapsará e disparará o alarme de quebra estrutural.

2. **Passo 2: Intervenção Epidemiológica**:
   Assim que o alarme dispara ou no momento em que você recebe a confirmação do DENV-3 (semana $t^*$), você deve realizar uma **intervenção manual no vetor de estados** para permitir que o modelo se ajuste imediatamente à nova realidade de contágio.

Faremos isso aumentando substancialmente a covariância de erro do nível $C_{t^*, 0, 0}$ e injetando um crescimento positivo $m_{t^*, 1}$:

```python
# Nossos estados: [Nível, Crescimento, Sazonalidade(2), Regressão Clima]
# 1. Recuperamos a posteriori estimada na semana 12
m_t12 = np.array([4.2, -0.05, 0.5, -0.2, 0.05])
C_t12 = np.eye(5) * 0.05

# 2. Aplicamos a intervenção epidemiológica para a semana 13
m_t12_interv = np.copy(m_t12)
m_t12_interv[1] = 0.35  # Ajuste feed-forward: injetando aceleração epidêmica positiva
C_t12_interv = np.copy(C_t12)
C_t12_interv[0, 0] = 1.5  # Libera o nível para absorver saltos na semana que vem
C_t12_interv[1, 1] = 0.5  # Libera o crescimento

# 3. Continuamos a filtragem de Kalman na semana 13
```

Essa intervenção manual (feed-forward adjustment) impede que o modelo subestime a epidemia, garantindo um resultado (result) com projeções muito mais condizentes com a realidade prática."

---

## Diretrizes de Resolução de Problemas (Troubleshooting)

### Problema 1: Excesso de Alarmes Falsos (O fator de Bayes dispara alarmes frequentes devido a oscilações normais de digitação de exames)
- **Causa**: O ruído de digitação semanal (por exemplo, lotes atrasados digitados todos de uma vez) introduz valores extremos que violam a distribuição normal de curto prazo sem representar uma quebra de regime epidemiológico real.
- **Solução**:
  1. Aumente o limite de sensibilidade do modelo alternativo $H_1$ (ex: defina `sensitivity = 4.0` ou `5.0`). Isso torna o modelo alternativo mais amplo e tolerante a ruídos pontuais.
  2. Ajuste o limite de corte crítico de alarme acumulado para um nível mais rigoroso ($\tau = 0.005$ ou $0.001$), exigindo que a anomalia persista por pelo menos 2 ou 3 semanas seguidas antes de disparar o alerta de vigilância.

### Problema 2: Lentidão no Alarme de Declínio (O alarme avisa que o surto começou, mas demora semanas para indicar que ele terminou)
- **Causa**: O Fator de Bayes acumulado $L_t$ cai a valores extremamente próximos de zero (ex: $10^{-8}$) durante a subida da epidemia. Quando a epidemia atinge o pico e começa a cair, o fator acumulado leva muitas semanas multiplicando por fatores de recuperação maiores que 1.0 para conseguir subir de volta e superar o limite de alarme.
- **Solução**:
  1. Imponha um limite inferior absoluto (*lower floor boundary*) para o Fator de Bayes Acumulado. Nunca permita que $L_t$ caia abaixo de $0.01$. Isso garante que o monitor esteja sempre pronto para se recuperar rapidamente no momento exato em que a curva epidêmica estabilizar ou iniciar o declínio.
