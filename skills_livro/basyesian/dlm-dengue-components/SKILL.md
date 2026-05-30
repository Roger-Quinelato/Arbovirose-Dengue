---
name: dlm-dengue-components
description: "Guia prático-teórico para modelagem estrutural de tendências de crescimento, sazonalidade epidemiológica baseada em Fourier e regressão dinâmica com fatores climáticos para séries de Dengue com calibração por fatores de desconto. Use when: O usuário precisa montar modelos estruturais dinâmicos (DLM), adicionar termos de sazonalidade de transmissão ou incluir preditores climáticos com parâmetros variantes. Do NOT use for: Dados de contagem não-gaussianos discretos puros (use dglm-dengue-count-methods) ou alarmes e intervenções subjetivas em tempo real (use dlm-dengue-monitoring-intervention)."
license: CC-BY-4.0
metadata:
  author: Roger Quinelato
  version: 1.0.0
---

# Componentes Estruturais em Modelos Dinâmicos: Tendência, Sazonalidade e Covariáveis Climáticas

Esta skill orienta a construção de Modelos Estruturais Dinâmicos de West & Harrison aplicados à Dengue. O objetivo é decompor a série de casos em subcomponentes interpretáveis de tendência física, ciclos sazonais e efeitos de variáveis climáticas externas (precipitação, temperatura e umidade) com coeficientes variantes no tempo, calibrados eficientemente usando Fatores de Desconto (*Discount Factors*).

## Quando Usar Esta Skill (Use When)

Use esta skill quando for necessário projetar e implementar um DLM estrutural para:
- Capturar a aceleração e velocidade da curva epidemiológica usando modelos polinomiais de segunda ordem (crescimento linear local).
- Modelar a sazonalidade anual sistemática da dengue (período de 52 semanas epidemiológicas) usando representações harmônicas de Fourier ou fatores sazonais form-free.
- Incorporar preditores climáticos externos (com defasagens epidemiológicas adequadas) através de uma regressão dinâmica cujas sensibilidades mudam ao longo do ano.
- Calibrar a evolução de incerteza do estado utilizando fatores de desconto componentes, evitando parametrizações complexas de matrizes de evolução $W_t$.

Não use esta skill para (Do NOT use for):
- Formulação básica do modelo de nível constante de primeira ordem ou suavização retrospectiva geral (use `dlm-dengue-filter-smooth` na skill `dlm-dengue-foundation`).
- Detecção e monitoramento de surtos e alarmes via Fatores de Bayes (use `dlm-dengue-monitoring-intervention`).

## Gatilhos de Ativação (Triggers)

### Em Português
- "como modelar sazonalidade da dengue com Fourier"
- "regressão dinâmica com dados de clima e dengue"
- "modelo linear de crescimento local para epidemia"
- "fatores de desconto em modelos dinâmicos lineares"
- "série temporal estrutural de dengue com covariáveis"
- "componente de tendência e sazonalidade em DLM"

### Em Inglês
- "how to model dengue seasonality with Fourier"
- "dynamic regression with climate and dengue data"
- "local linear growth model for epidemics"
- "discount factors in dynamic linear models"
- "dengue structural time series with covariates"
- "trend and seasonal component in DLM"

---

## Formulação e Estruturação de Componentes em DLM

O princípio fundamental de West & Harrison é a **composição de modelos**. Vários blocos independentes (componentes) de espaço de estados podem ser concatenados de forma aditiva em um único modelo unificado.

Sejam as equações gerais do DLM:
$$Y_t = F_t^T \theta_t + v_t, \quad v_t \sim N(0, V_t)$$
$$\theta_t = G_t \theta_{t-1} + w_t, \quad w_t \sim N(0, W_t)$$

Ao combinarmos $K$ componentes independentes (ex: tendência $T$, sazonalidade $S$ e regressão climática $R$), o vetor de design $F_t$, a matriz de transição $G_t$ e o vetor de estado $\theta_t$ são blocos empilhados:
$$\theta_t = \begin{bmatrix} \theta_{t,T} \\ \theta_{t,S} \\ \theta_{t,R} \end{bmatrix}, \quad F_t = \begin{bmatrix} F_{t,T} \\ F_{t,S} \\ F_{t,R} \end{bmatrix}, \quad G_t = \begin{bmatrix} G_{t,T} & 0 & 0 \\ 0 & G_{t,S} & 0 \\ 0 & 0 & G_{t,R} \end{bmatrix}$$

### 1. Componente de Tendência: Crescimento Linear Local (2ª Ordem)

Representa o nível da epidemia e sua taxa de variação (velocidade de propagação do contágio):
$$\theta_{t,T} = \begin{bmatrix} \mu_t \\ \beta_t \end{bmatrix} \begin{array}{l} \text{(Nível local)} \\ \text{(Taxa de crescimento/Declínio)} \end{array}$$
$$F_{t,T} = \begin{bmatrix} 1 \\ 0 \end{bmatrix}, \quad G_{t,T} = \begin{bmatrix} 1 & 1 \\ 0 & 1 \end{bmatrix}$$
Isso implica que:
- Nível: $\mu_t = \mu_{t-1} + \beta_{t-1} + w_{t,\mu}$
- Tendência: $\beta_t = \beta_{t-1} + w_{t,\beta}$

### 2. Componente de Sazonalidade: Forma Harmônica de Fourier

Modelar sazonalidade com fatores qualitativos consome muitos graus de liberdade (51 parâmetros para semanas epidemiológicas). A alternativa Bayesiana eficiente é a sazonalidade de Fourier. Para um ciclo anual com período $P=52$ semanas, a sazonalidade é representada pela soma de harmônicos (geralmente $r=1$ ou $r=2$ harmônicos dominantes são suficientes):

Para cada harmônico $j$ ($j = 1, \dots, r$):
$$\theta_{t,S_j} = \begin{bmatrix} s_{1,t} \\ s_{2,t} \end{bmatrix}, \quad F_{t,S_j} = \begin{bmatrix} 1 \\ 0 \end{bmatrix}, \quad G_{t,S_j} = \begin{bmatrix} \cos(\omega_j) & \sin(\omega_j) \\ -\sin(\omega_j) & \cos(\omega_j) \end{bmatrix}$$
Onde a frequência angular é $\omega_j = 2\pi j / 52$.

### 3. Componente de Regressão Dinâmica (Clima)

Integra o efeito de fatores climáticos externos, como a precipitação acumulada de 2 a 4 semanas atrás (período de eclosão de ovos do mosquito). Os coeficientes de regressão são dinâmicos e adaptam-se ao longo da série:
$$\theta_{t,R} = \beta_{t,clima} \quad \text{(Coeficiente de sensibilidade ao clima)}$$
$$F_{t,R} = [X_t] \quad \text{(Variável climática observada na semana t, ex: temperatura media)}$$
$$G_{t,R} = [1]$$

### 4. Fatores de Desconto (Discount Factors)

Em vez de estimar cada entrada da matriz de variância de evolução $W_t$, West & Harrison propõem o uso de Fatores de Desconto Componentes. Para cada componente $i$ do modelo, define-se um fator de desconto $\delta_i \in [0.9, 1.0]$.
A variância a priori a partir da covariância a posteriori filtrada $C_{t-1}$ é projetada como:
$$R_t = G_t C_{t-1} G_t^T + W_t$$
Em termos de desconto, definimos individualmente para cada bloco:
$$R_{t,i} = \frac{1}{\delta_i} G_{t,i} C_{t-1,i} G_{t,i}^T$$
O que implicitamente define a variância de evolução do bloco como:
$$W_{t,i} = \frac{1-\delta_i}{\delta_i} G_{t,i} C_{t-1,i} G_{t,i}^T$$
- **Fatores típicos para Dengue**:
  - Tendência ($\delta_{tend}$): $0.90 - 0.95$ (Permite adaptação rápida no início explosivo da curva epidêmica).
  - Sazonalidade ($\delta_{saz}$): $0.99 - 0.999$ (Sazonalidade é um ciclo físico estável, muda muito devagar).
  - Regressão Climática ($\delta_{clim}$): $0.95 - 0.98$ (A influência do clima varia de acordo com a abundância do vetor).

---

## Implementação Prática em Python

A classe a seguir monta e executa um DLM Estrutural Completo (Tendência Polinomial + Sazonalidade de Fourier de 1 Harmônico + Regressão Climática Dinâmica) usando Fatores de Desconto:

```python
import numpy as np
import pandas as pd

class DengueStructuralDLM:
    def __init__(self, delta_trend=0.95, delta_seas=0.995, delta_reg=0.98):
        self.delta_trend = delta_trend
        self.delta_seas = delta_seas
        self.delta_reg = delta_reg
        self.F_t = [1.0, 0.0]
        self.G_t = [[1.0, 1.0], [0.0, 1.0]]
        self.idx_trend = [0, 1]
        omega = 2.0 * np.pi * 1.0 / 52.0
        self.F_s = [1.0, 0.0]
        self.G_s = [[np.cos(omega), np.sin(omega)], [-np.sin(omega), np.cos(omega)]]
        self.idx_seas = [2, 3]
        self.idx_reg = [4]
        self.G = np.zeros((5, 5))
        self.G[0:2, 0:2] = self.G_t
        self.G[2:4, 2:4] = self.G_s
        self.G[4, 4] = 1.0
        
    def run_model(self, y, X_climate, m0, C0, V):
        T = len(y)
        d = len(m0)
        m = np.zeros((T, d))
        C = np.zeros((T, d, d))
        f = np.zeros(T)
        Q = np.zeros(T)
        m_prev = np.copy(m0)
        C_prev = np.copy(C0)
        for t in range(T):
            F = np.array([1.0, 0.0, 1.0, 0.0, X_climate[t]])
            a = self.G @ m_prev
            R = self.G @ C_prev @ self.G.T
            R[0:2, 0:2] /= self.delta_trend
            R[2:4, 2:4] /= self.delta_seas
            R[4, 4] /= self.delta_reg
            f[t] = F @ a
            Q[t] = F @ R @ F.T + V
            e_t = y[t] - f[t]
            A_t = (R @ F) / Q[t]
            m[t] = a + A_t * e_t
            C[t] = R - np.outer(A_t, A_t) * Q[t]
            m_prev = m[t]
            C_prev = C[t]
        return pd.DataFrame({
            'Real': y,
            'Forecast': f,
            'Forecast_Var': Q,
            'Nivel_Estimado': m[:, 0],
            'Crescimento_Estimado': m[:, 1],
            'Sazonalidade_Fourier': m[:, 2],
            'Efeito_Clima': m[:, 4]
        })
```

---

## Exemplos Práticos de Uso (Example Cases)

### Exemplo 1 (Example 1): Decompondo Casos de Dengue sob Efeito de Temperatura Média com Lags

**Usuário (User says)**: "Estou estudando a dinâmica de dengue em Brasília e quero construir um modelo que decomponha a série semanal usando tendência linear, um ciclo sazonal harmônico e adicione a Temperatura Média defasada de 3 semanas como covariável com coeficientes dinâmicos no tempo. Como posso usar fatores de desconto componentes para calibrar isso?"

**Agente (Result / Response)**: "Essa é uma aplicação clássica de Modelos Estruturais Dinâmicos Bayesianos. A escolha da temperatura média com defasagem de 3 semanas é biologicamente consistente, pois cobre o ciclo de incubação extrínseca do vírus no vetor mais o tempo de desenvolvimento das larvas.

1. **Configuração da Estrutura**:
   Nosso vetor de estado $\theta_t$ terá 5 dimensões:
   - $\theta_{t, 0}$: Nível local da epidemia.
   - $\theta_{t, 1}$: Velocidade de crescimento semanal.
   - $\theta_{t, 2}$ e $\theta_{t, 3}$: Componentes senoidais do ciclo harmônico de Fourier de 52 semanas.
   - $\theta_{t, 4}$: Coeficiente dinâmico de sensibilidade à Temperatura Média ($X_{t-3}$).

2. **Ajuste de Fatores de Desconto**:
   - Para a **Tendência**, escolhemos $\delta_{tend} = 0.95$, permitindo que o modelo responda rápido quando uma curva epidêmica entra em fase de subida geométrica.
   - Para a **Sazonalidade**, fixamos $\delta_{saz} = 0.999$, porque o padrão sazonal geográfico muda muito sutilmente de um ano para o outro.
   - Para o **Efeito Climático**, definimos $\delta_{reg} = 0.98$, pois a influência da temperatura sobre a incidência de casos pode arrefecer ou aumentar dependendo da abundância absoluta do vetor ou da imunidade populacional no ano epidemiológico.

Veja como preparar e rodar esse modelo dinâmico em Python:

```python
# Série epidemiológica (y) transformada (log-casos) e vetor climatológico correspondente
df = pd.DataFrame({
    'semana_epidemiologica': range(1, 105),
    'casos_notificados': [10, 12, 15, 22, 30, 45, 75, 110, 180, 240, 310, 280, 190, 100, 50, ...]
})
# Criando a covariável climática defasada (3 semanas de lag)
df['temp_media'] = [22.4, 23.1, 23.5, 24.0, 24.2, 23.8, 22.9, 21.8, ...]
df['temp_defasada'] = df['temp_media'].shift(3).fillna(22.0) # preenchendo lag inicial

# Preparando entradas para o modelo
y = np.log1p(df['casos_notificados'].values)
X_climate = df['temp_defasada'].values

# Priori inicial para vetor de 5 estados
m0 = np.array([3.0, 0.0, 0.0, 0.0, 0.1])
C0 = np.eye(5) * 0.5  # incerteza moderada

# Executando o modelo dinâmico
modelo = DengueStructuralDLM(delta_trend=0.95, delta_seas=0.999, delta_reg=0.98)
resultado = modelo.run_model(y, X_climate, m0, C0, V=0.16)

# Visualizando a decomposição dinâmica
print(resultado[['Real', 'Forecast', 'Nivel_Estimado', 'Crescimento_Estimado', 'Sazonalidade_Fourier', 'Efeito_Clima']].tail(10))
```

Esse modelo ajustará semana a semana o peso do efeito da temperatura sobre os novos casos reportados."

---

## Diretrizes de Resolução de Problemas (Troubleshooting)

### Problema 1: Superposição Epidemiológica de Componentes (O efeito do clima está "vazando" para a sazonalidade e vice-versa)
- **Causa**: Temperatura e sazonalidade pura andam juntas (altamente correlacionadas no tempo). Se ambos os componentes tiverem descontos muito flexíveis, eles competirão para explicar a mesma variação cíclica, gerando colinearidade dinâmica e variâncias inflacionadas.
- **Solução**:
  1. Torne o componente sazonal extremamente rígido escolhendo $\delta_{seas} = 1.0$ (sem evolução de variância para sazonalidade harmônica) ou $0.999$.
  2. Ajuste a covariável climática removendo sua média sazonal de longo prazo (anomalia de temperatura/precipitação) antes de inseri-la como regressor. Isso garante que a regressão capture apenas variações anômalas climáticas e a sazonalidade capte o ciclo fixo anual do vetor.

### Problema 2: Explosão na Covariância de Previsão $Q_t$
- **Causa**: Fatores de desconto acumulados durante longas séries temporais sem observações de atualização (devido a falhas de comunicação ou ausência de dados reportados) podem inflacionar exponencialmente a covariância do estado $R_t$.
- **Solução**:
  1. Durante semanas sem dados reais ($y_t$ ausente), execute apenas a evolução temporal ($a_t = G_t m_{t-1}$) mas **não aplique o fator de desconto** (mantenha $R_t = G_t C_{t-1} G_t^T$ sem divisão por $\delta$). Isso impede que a incerteza se propague ao infinito na ausência prolongada de informação epidemiológica.
