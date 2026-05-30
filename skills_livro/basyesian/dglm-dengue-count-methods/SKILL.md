---
name: dglm-dengue-count-methods
description: "Guia teórico-prático para aplicação de Modelos Dinâmicos Generalizados (DGLMs) de Poisson e métodos de simulação estocástica (MCMC/Gibbs) para dados de contagem discreta de casos de Dengue. Use when: O usuário precisa modelar dados semanais de incidência na escala discreta natural sem aproximação gaussiana, utilizar dinâmica de famílias exponenciais ou realizar inferência. Do NOT use for: Modelos lineares gaussianos puros com transformações log/raiz (use dlm-dengue-foundation) ou para decomposição de sazonalidade clássica linear (use dlm-dengue-components)."
license: CC-BY-4.0
metadata:
  author: Roger Quinelato
  version: 1.0.0
---

# Modelos Dinâmicos de Contagem e Métodos de Simulação em Epidemiologia

Esta skill descreve as abordagens de Modelos Dinâmicos Generalizados (DGLMs) de West & Harrison para lidar com a natureza não-gaussiana inerente às séries epidemiológicas de dengue. Ela foca no modelo de contagem de Poisson Dinâmica com atualizações conjugadas e fornece diretrizes para a aplicação de métodos de simulação estocástica de Monte Carlo via Cadeias de Markov (MCMC e Amostragem de Gibbs) para quantificação rigorosa de incertezas.

## Quando Usar Esta Skill (Use When)

Use esta skill em cenários de modelagem epidemiológica onde se deseja:
- Modelar diretamente a contagem discreta de casos de dengue $Y_t \in \{0, 1, 2, \dots\}$ em municípios de baixa densidade populacional, onde muitos zeros inviabilizam a aproximação gaussiana linear clássica.
- Implementar DGLMs da Família Exponencial Dinâmica usando funções de ligação logarítmicas ($\log(\lambda_t)$) e distribuições conjugadas dinâmicas.
- Estimar parâmetros estáticos do modelo de espaço de estados (como taxas autoregressivas e variâncias de evolução estruturais) usando inferência conjunta por Simulação baseada em MCMC e amostragem de Gibbs.

Não use esta skill para (Do NOT use for):
- Modelos que assumem normalidade dos erros observacionais na escala transformada log/raiz (use `dlm-dengue-foundation`).
- Desenvolver alarmes automáticos de quebras sazonais baseados exclusivamente em filtros de Kalman normais (use `dlm-dengue-monitoring-intervention`).

## Gatilhos de Ativação (Triggers)

### Em Português
- "modelo dinâmico generalizado DGLM para dengue"
- "modelar contagem discreta de casos de dengue com Poisson"
- "amostragem de Gibbs para modelo espaço de estados de arboviroses"
- "MCMC aplicado à previsão e dinâmica de transmissão de dengue"
- "atualização conjugada Poisson-Gamma de incidência epidemiológica"
- "função de ligação log em DGLM Bayesiano"

### Em Inglês
- "dynamic generalized linear model DGLM for dengue"
- "model discrete counts of dengue cases with Poisson"
- "Gibbs sampling for state space model of arboviruses"
- "MCMC applied to dengue forecasting and transmission dynamics"
- "Poisson-Gamma conjugate updating of epidemiological incidence"
- "log link function in Bayesian DGLM"

---

## Métodos de Modelagem de Contagem e Simulação Estocástica

### 1. Modelos Dinâmicos Generalizados (DGLMs): O Caso de Poisson

Séries epidemiológicas reais em cidades menores possuem semanas com zero casos notificados, intercaladas com pequenos surtos (ex: 2, 5, 12 casos). A premissa gaussiana do DLM desmorona nesses cenários. O **DGLM de Poisson Dinâmico** resolve isso assumindo:

1. **Distribuição Observacional**:
   $$(Y_t \mid \eta_t) \sim \text{Poisson}(\lambda_t)$$
   Onde $\lambda_t$ é a taxa média esperada de novos casos de dengue na semana $t$.

2. **Função de Ligação**:
   A taxa $\lambda_t$ é mapeada linearmente ao espaço de estado $\theta_t$ através da ligação logarítmica:
   $$\eta_t = \log(\lambda_t) = F_t^T \theta_t$$

3. **Equação de Evolução do Estado**:
   $$\theta_t = G_t \theta_{t-1} + w_t$$

**O Processo de Atualização Conjugada Poisson-Gamma**:
Seguindo West & Harrison, em vez de recorrer a MCMC a cada semana (o que seria computacionalmente inviável em tempo real), aproximamos as distribuições marginais para manter a eficiência analítica:

Dada a informação $D_{t-1}$, o estado a priori é $(\theta_t \mid D_{t-1}) \sim [\text{Média } a_t, \text{ Covariância } R_t]$.
Isso implica que para o parâmetro linear $\eta_t = F_t^T \theta_t$, temos:
$$(\eta_t \mid D_{t-1}) \sim [f_t = F_t^T a_t, \quad Q_t = F_t^T R_t F_t]$$

Para realizar a atualização com a distribuição Poisson de $Y_t$, mapeamos a priori de $\eta_t$ para uma distribuição conjugada Gamma sobre a taxa média $\lambda_t = e^{\eta_t}$:
$$(\lambda_t \mid D_{t-1}) \sim \text{Gamma}(\alpha_t, \beta_t)$$
Onde os parâmetros $\alpha_t, \beta_t$ são calibrados para coincidir com a média e variância a priori projetadas de $\lambda_t$:
- Média preditiva de $\lambda_t$: $E[\lambda_t \mid D_{t-1}] = e^{f_t + Q_t / 2}$
- Variância preditiva de $\lambda_t$: $Var(\lambda_t \mid D_{t-1}) = e^{2f_t + Q_t}(e^{Q_t} - 1)$

Ao observar $Y_t = y_t$, a posteriori exata de $\lambda_t$ pela conjugação Bayesiana é:
$$(\lambda_t \mid D_t) \sim \text{Gamma}(\alpha_t + y_t, \quad \beta_t + 1)$$

Essa distribuição a posteriori de $\lambda_t$ é mapeada de volta para o espaço linear de $\eta_t$ (calculando $E[\eta_t \mid D_t]$ e $Var(\eta_t \mid D_t)$ usando as funções digama e trigama), o que nos permite atualizar o estado $\theta_t$ gerando a posteriori média $m_t$ e covariância $C_t$.

### 2. Simulação Espaço-Estado via Gibbs Sampling (MCMC)

Quando o modelo possui parâmetros estáticos desconhecidos (ex: o coeficiente de persistência autoregressivo da transmissão ou a própria variância observacional do ruído sistemático), a solução analítica falha. Usamos a **Amostragem de Gibbs** para simular a distribuição conjunta a posteriori de todos os estados históricos $\theta_{1:T}$ e parâmetros estáticos $\psi$ condicionados à série completa de dados $D_T$.

O algoritmo de Gibbs alterna recursivamente entre:
1. **Amostragem da Trajetória do Estado (FFBS - Forward Filtering Backward Sampling)**:
   Amostramos o bloco completo de estados históricos $\theta_{1:T}$ condicionado aos parâmetros estáticos atuais $\psi$ e dados $Y_{1:T}$:
   $$\theta_{1:T} \sim p(\theta_{1:T} \mid \psi, Y_{1:T})$$
   Isso é feito executando o filtro de Kalman e, no passo para trás (backward), em vez de apenas calcular as médias suavizadas, extraímos amostras estocásticas da distribuição normal condicionada retroativa.

2. **Amostragem dos Parâmetros $\psi$**:
   Amostramos os parâmetros estáticos condicionados à trajetória de estados simulada $\theta_{1:T}$ e priors correspondentes (ex: distribuições Gamma Inversa para variâncias):
   $$\psi \sim p(\psi \mid \theta_{1:T}, Y_{1:T})$$

---

## Implementação Prática em Python

A classe abaixo descreve a lógica do DGLM de Poisson Dinâmico para uma série semanal de dengue usando aproximação de momentos conjugados:

```python
import numpy as np
import pandas as pd
from scipy.special import digamma, polygamma

class DenguePoissonDGLM:
    def __init__(self, delta=0.98):
        self.delta = delta
        
    def fit_filter(self, y, m0, C0):
        T = len(y)
        m = np.zeros(T)
        C = np.zeros(T)
        lambda_est = np.zeros(T)
        m_prev = m0
        C_prev = C0
        for t in range(T):
            a_t = m_prev
            R_t = C_prev / self.delta
            mu_lambda = np.exp(a_t + R_t / 2.0)
            var_lambda = np.exp(2 * a_t + R_t) * (np.exp(R_t) - 1.0)
            beta_t = mu_lambda / (var_lambda + 1e-9)
            alpha_t = mu_lambda * beta_t
            alpha_post = alpha_t + y[t]
            beta_post = beta_t + 1.0
            m[t] = digamma(alpha_post) - np.log(beta_post)
            C[t] = polygamma(1, alpha_post)
            lambda_est[t] = alpha_post / beta_post
            m_prev = m[t]
            C_prev = C[t]
        return pd.DataFrame({
            'Real_Casos': y,
            'Nivel_LogIncidencia': m,
            'Incidencia_Var': C,
            'Taxa_Esperada_Casos': lambda_est
        })
```

---

## Exemplos Práticos de Uso (Example Cases)

### Exemplo 1 (Example 1): Modelando Pequenos Surtos em Cidades do Interior sem Violação de Normalidade

**Usuário (User says)**: "Estou analisando dados de dengue de um município muito pequeno no semiárido onde há semanas consecutivas com zero casos, seguidas por semanas com 2 ou 3 casos. Aplicar o DLM Gaussiano na série bruta ou até aplicando logaritmo está gerando intervalos de previsão negativos e resíduos péssimos. Como o DGLM de Poisson dinâmico resolve isso no meu pipeline?"

**Agente (Result / Response)**: "Esta é a situação clássica em que os pressupostos de um DLM gaussiano linear padrão se quebram. Quando temos dados de contagem discreta pequenos com forte presença de zeros, o DGLM de Poisson dinâmico é a abordagem Bayesiana estatisticamente correta por dois motivos principais:
1. **Garantia de Não-Negatividade**: O número esperado de casos de dengue ($\lambda_t$) é sempre positivo porque é derivado da ligação exponencial $\lambda_t = e^{\eta_t}$.
2. **Respeito à Natureza Discreta**: A verossimilhança é modelada como uma distribuição de contagem de Poisson, eliminando resíduos de variância fixa sob zeros.

Vamos configurar e executar o modelo dinâmico Poisson univariado para a sua série semanal em Python:

```python
# Série epidemiológica simulada de uma cidade pequena
casos_semanais = np.array([0, 0, 0, 1, 0, 0, 2, 0, 1, 3, 5, 4, 1, 0, 0, 0])

# Priori inicial do nível epidêmico na escala log
m0 = -0.7
C0 = 0.5  # incerteza moderada

# Executa o DGLM de Poisson com fator de desconto de 0.95
modelo = DenguePoissonDGLM(delta=0.95)
resultados = modelo.fit_filter(casos_semanais, m0, C0)

# Calculando intervalos de credibilidade preditivos Bayesianos de 95% para a taxa esperada
resultados['Taxa_Limite_Inferior'] = np.exp(resultados['Nivel_LogIncidencia'] - 1.96 * np.sqrt(resultados['Incidencia_Var']))
resultados['Taxa_Limite_Superior'] = np.exp(resultados['Nivel_LogIncidencia'] + 1.96 * np.sqrt(resultados['Incidencia_Var']))

print(resultados[['Real_Casos', 'Taxa_Esperada_Casos', 'Taxa_Limite_Inferior', 'Taxa_Limite_Superior']])
```

Esse procedimento fornecerá uma estimativa (result) muito mais condizente com as baixas contagens de casos."

---

## Diretrizes de Resolução de Problemas (Troubleshooting)

### Problema 1: Sobredispersão Sistemática (A variância preditiva observada é muito maior do que a média estipulada pela distribuição Poisson)
- **Causa**: A dengue se propaga por surtos agrupados (uma única casa infectada gera múltiplos casos na mesma rua). A distribuição de Poisson assume que a variância é igual à média ($Var(Y) = E[Y]$), o que subestima gravemente a incerteza real durante picos epidêmicos.
- **Solução**:
  1. Mude o DGLM para usar a **Distribuição Binomial Negativa Dinâmica**, que introduz um parâmetro de dispersão adicional $\alpha$ para acomodar flutuações e picos agrupados.
  2. Adicione um componente estocástico de ruído multiplicativo na variância do estado evolutivo para ampliar a incerteza durante a fase de transição epidêmica.

### Problema 2: Instabilidade nas Funções Digama e Trigama para Parâmetros $\alpha$ Próximos de Zero
- **Causa**: Se o modelo projeta uma taxa esperada extremamente próxima de zero, os parâmetros da Gamma $\alpha_t$ e $\beta_t$ assumem valores minúsculos. As funções `digamma` e `polygamma(1)` tornam-se numericamente instáveis ou retornam infinitos quando $\alpha_t \to 0$.
- **Solução**:
  1. Imponha um limite inferior (*floor constraint*) para o parâmetro $\alpha_t$ (por exemplo, $\alpha_{t} = \max(\alpha_{t}, 10^{-4})$) antes de chamar as funções digama e trigama. Isso preserva a estabilidade do processo de atualização computacional sem distorcer o significado epidemiológico.
