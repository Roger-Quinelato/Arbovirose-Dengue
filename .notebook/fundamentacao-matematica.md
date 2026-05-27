# Fundamentação Matemática e Modelagem Estatística — DocML

Este documento detalha o arcabouço matemático e estatístico do pipeline **DocML**, fornecendo as justificativas científicas para a seleção de transformações, validações, quantificações de incerteza e métricas adotadas no monitoramento preditivo e nowcasting de dengue no Distrito Federal (DF).

---

## 1. Transformação do Alvo (Target) e Suavização de Variância

Os dados epidemiológicos de contagem de casos apresentam distribuição altamente assimétrica à direita, com caudas longas (overdispersion) e picos de magnitude exponencial durante surtos epidêmicos, além de períodos interepidérmicos de transmissão quase nula (zero-inflated).

### 1.1 Transformação Logarítmica `log1p`
Para treinar algoritmos baseados em árvores (Random Forest e XGBoost), que dividem recursivamente o espaço de features para minimizar o erro quadrático, o alvo $y$ (casos absolutos ou incidência) é transformado em escala logarítmica:

$$z = \log(y + 1)$$

#### Raciocínio Matemático e Justificativa:
1. **Estabilização da Variância (Homocedasticidade Relativa):** Em séries temporais ecológicas e epidemiológicas, a variância dos resíduos tende a crescer proporcionalmente ao valor absoluto esperado (heterocedasticidade). O logaritmo estabiliza a escala das flutuações, impedindo que os erros nos anos de pico dominem completamente a função de perda ($MSE$) em detrimento de uma calibração equilibrada em anos normais.
2. **Prevenção de Predições Negativas:** Na escala linear, o espaço de busca dos regressores não é restrito. É comum que algoritmos predigam valores negativos em períodos de seca, o que é fisicamente impossível para contagens humanas. Como a imagem da função inversa $\exp(z)$ é estritamente não-negativa para qualquer $z \in \mathbb{R}$:

$$\hat{y} = \text{expm1}(\hat{z}) = e^{\hat{z}} - 1$$

Ao aplicar o limite inferior através de um clip pós-transformação:

$$\hat{y}_{\text{final}} = \max\left(0, e^{\hat{z}} - 1\right)$$

Garantimos de forma matematicamente elegante que as previsões pertençam estritamente ao espaço admissível $\mathbb{R}^+_{0}$.

---

## 2. Correlação de Spearman para Lags Climáticos

Dengue é uma doença de dinâmica ecológica indireta. O aumento de chuvas não causa o pico epidemiológico no dia seguinte, mas sim após uma cadeia causal complexa (acúmulo de criadouros $\to$ eclosão de larvas $\to$ desenvolvimento do vetor $\to$ picada infectante $\to$ período de incubação intrínseco no hospedeiro).

Para medir e triar esse atraso cronológico (lags de 2 a 8 semanas), adotamos o coeficiente de **Correlação de Postos de Spearman** ($\rho$) ao invés do tradicional Pearson ($r$):

$$\rho = 1 - \frac{6 \sum d_i^2}{n(n^2 - 1)}$$

Onde $d_i = \text{rg}(X_i) - \text{rg}(Y_i)$ é a diferença entre os postos das observações pareadas de clima defasado e incidência epidemiológica.

```
 Pearson (r)  ───> Exige relações lineares estritas e resíduos normais (FALHA em dados de chuva e surtos)
 Spearman (ρ) ───> Avalia relações monótonas não-lineares arbitrárias (ROBUSTO para lags ecológicos)
```

#### Raciocínio Matemático e Justificativa:
- **Não-Linearidade Monótona:** A biologia da transmissão não responde linearmente. Um acréscimo de chuva de 10mm para 50mm acelera a criação de vetores de forma muito diferente de um acréscimo de 200mm para 240mm (que pode inclusive causar o "lavamento" das larvas). A correlação de Spearman detecta se a relação é consistentemente crescente ou decrescente (monótona) sem impor a rigidez de uma reta linear.
- **Robustez a Outliers:** Surtos exponenciais agem como severos outliers geométricos para o coeficiente de Pearson, distorcendo artificialmente a correlação climática. Spearman, operando na escala ordinal de postos, é robusto a extremos geométricos.

---

## 3. Divisão Temporal e Validação Cruzada Sem Vazamento (Anti-Leakage)

A validação em séries temporais exige rigor estrito para evitar o fenômeno de **Data Leakage** (vazamento de dados), onde informações futuras ou autocorrelações próximas enviesam as métricas de treino.

Adotamos a **Validação Cruzada em Janela Móvel** (`TimeSeriesSplit`) adaptada com um **gap temporal paramétrico**:

```
Treinamento (Folds Passados):
[ Semana 1 ───> Semana t ]
                        \
                         \  Gap Epidemiológico (4 Semanas de Exclusão)
                          \───> [ Semana t + 4 ───> Semana t + 4 + V ]
                                Validação (Futuro Isolado)
```

#### Raciocínio Matemático e Justificativa:
- **O Fenômeno da Autocorrelação Autoregressiva:** Nosso design de features inclui os lags epidemiológicos de casos recentes ($cases\_lag\_1$ a $cases\_lag\_4$). Se validarmos o modelo na semana $t+1$ imediatamente posterior à última semana de treino $t$:
  - A feature $cases\_lag\_1$ na semana de validação é exatamente o alvo real $cases$ da semana $t$ do treino.
  - Isso cria um vazamento imediato de sinal de contágio. Em condições operacionais reais (nowcasting), no momento em que estamos prevendo, as últimas semanas frequentemente possuem atrasos severos de notificação ou estão ausentes.
- **Matematização do Gap:** Ao impor um **$gap = 4$ semanas**, removemos as observações de transição da fronteira. Isso garante que o modelo seja treinado para operar sob o cenário operacional mais estressado (nowcasting simulado, onde as predições dependem apenas de sinais estáveis gerados semanas atrás), gerando métricas reais de RMSE e $R^2$ imunes ao leakage de autoregressão.

---

## 4. Quantificação de Incerteza via Conformal Prediction Dinâmico

Intervalos de incerteza estáticos baseados em pressupostos normais ($\pm 1.96\sigma$) violam a realidade física das séries epidemiológicas devido à **heterocedasticidade massiva**:

$$\text{Variância}(\text{Erro}_t) \propto f(\hat{y}_t)$$

O erro absoluto cometido pelo modelo é proporcional à magnitude da predição $\hat{y}_t$. Durante surtos de centenas de casos, erros absolutos de $\pm 50$ casos são aceitáveis; na seca, um erro de $+50$ casos representa uma catástrofe diagnóstica.

### 4.1 Cálculo do Score de Não-Conformidade Dinâmico
Utilizamos uma abordagem de **Split Conformal Prediction** com normalização dinâmica adaptativa local. Em um conjunto de calibração independente $\mathcal{D}_{\text{cal}}$ composto pelas últimas 26 semanas de treino, calculamos o score para cada amostra $i$:

$$s_i = \frac{|y_i - \hat{y}_i|}{\hat{y}_i + \epsilon}$$

Onde $\epsilon = 0.01$ é o fator de regularização e estabilidade numérica para prevenir divisões por zero em períodos interepidérmicos.

### 4.2 Calibração do Quantil Crítico
Dado um nível de significância de cauda $\alpha = 0.10$ (para garantia de cobertura nominal de $90\%$), o quantil empírico crítico $q_{\text{conf}}$ é extraído aplicando-se a correção finita de Papadopoulos:

$$q_{\text{conf}} = \text{Quantile}\left(\{s_i\}_{i \in \mathcal{D}_{\text{cal}}}, \frac{\lceil(N_{\text{cal}} + 1)(1 - \alpha)\rceil}{N_{\text{cal}}}\right)$$

Onde $N_{\text{cal}} = 26 \times 35_{\text{RAs}} = 910$ observações espaciais-temporais.

### 4.3 Aplicação e Expansão Temporal de Forecast (Horizonte $k$)
Para qualquer predição operacional futura no instante $t$, o intervalo conformal dinâmico $\text{CI}_t = [L_t, U_t]$ é derivado de forma 100% vetorizada:

$$\text{margin}_t = q_{\text{conf}} \times (\hat{y}_t + \epsilon) \times \sqrt{k}$$

$$L_t = \max\left(0, \hat{y}_t - \text{margin}_t\right)$$

$$U_t = \hat{y}_t + \text{margin}_t$$

#### Justificativa da Expansão por Raiz Quadrada $\sqrt{k}$:
No forecast fechado recursivo (onde as previsões $\hat{y}_{t+j}$ do próprio modelo substituem os lags autoregressivos ausentes de $cases$ à medida que o horizonte temporal avança), a variância do erro de previsão cresce de forma acumulada e multiplicativa. O fator multiplicador $\sqrt{k}$ (onde $k$ representa o número de passos à frente) expande deterministicamente a largura da banda, representando matematicamente a incerteza que se propaga pela cadeia de realimentação de erros do forecast closed-loop.

---

## 5. Métricas de Avaliação Robusta

### 5.1 $R^2$ Robusto (Coeficiente de Determinação Seguro)
$$R^2 = 1 - \frac{\sum_{i=1}^n (y_i - \hat{y}_i)^2}{\sum_{i=1}^n (y_i - \bar{y})^2}$$

#### Justificativa:
Algumas Regiões Administrativas periféricas de baixíssima densidade demográfica ou de criação recente apresentam zero variação histórica ($\text{Var}(y) \approx 0$). O cálculo padrão do $R^2$ nessas condições causa divisões por zero ($\frac{0}{0}$) que quebram a orquestração do pipeline. Nossa implementação detecta a variância nula do vetor real e retorna `nan` de forma controlada, garantindo robustez algébrica.

### 5.2 Winkler Score (Métrica de Intervalo)
Para avaliar a calibração e a parcimônia das bandas de Conformal Prediction a um nível de confiança $(1 - \alpha)$, adota-se o Winkler Score:

$$\text{Winkler}(L_t, U_t, y_t) = (U_t - L_t) + \frac{2}{\alpha} (L_t - y_t) \mathbb{I}(y_t < L_t) + \frac{2}{\alpha} (y_t - U_t) \mathbb{I}(y_t > U_t)$$

#### Justificativa:
Avaliar bandas apenas pela porcentagem de cobertura é ineficiente (um intervalo infinito $[-\infty, +\infty]$ possui $100\%$ de cobertura, mas utilidade zero). O Winkler Score penaliza intervalos excessivamente largos através do termo linear $(U_t - L_t)$ e penaliza pesadamente, de forma simétrica e proporcional por $\frac{2}{\alpha}$, qualquer ocorrência de observação real que escape das bandas definidas (out-of-bounds). Valores menores indicam modelos com bandas estreitas e alta cobertura empírica.

### 5.3 sMAPE (Symmetric Mean Absolute Percentage Error)
$$\text{sMAPE} = \frac{100\%}{n} \sum_{i=1}^n \frac{2|y_i - \hat{y}_i|}{|y_i| + |\hat{y}_i| + \epsilon}$$

#### Justificativa:
O MAPE clássico dividia o erro pelo valor real $y_i$. Em séries epidemiológicas secas onde $y_i = 0$ ou $y_i = 1$, o MAPE explode para o infinito ou se torna altamente assimétrico. O sMAPE adota um denominador simétrico baseado na média das magnitudes reais e preditas, fornecendo estabilidade limitante para análises ecológicas.

### 5.4 Hit Rate de Picos Epidemiológicos
Uma semana $t$ é classificada como "pico real" ou "pico predito" se pertencer ao quartil superior de contaminações ($q \ge 0.75$). O Hit Rate é a precisão dessa categorização:

$$\text{Hit Rate} = \frac{\sum \left(\mathbb{I}(y_t \ge y_{q75}) \land \mathbb{I}(\hat{y}_t \ge \hat{y}_{q75})\right)}{\sum \mathbb{I}(y_t \ge y_{q75})}$$

#### Justificativa:
Para os tomadores de decisão em saúde pública (Secretaria de Saúde do DF), a precisão numérica média em termos de unidades de casos é secundária ao planejamento estratégico de infraestrutura: eles necessitam prever a **semana exata de colapso de leitos** para deslocar equipes móveis e pulverizar inseticidas (Fumacê). O Hit Rate de picos calcula matematicamente a sensibilidade dos modelos na detecção desses gatilhos críticos.
