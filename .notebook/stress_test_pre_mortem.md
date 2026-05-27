# Auditoria Técnica DocML — Fase 5: Estresse Preditivo e Pre-Mortem

**Tags:** `auditoria`, `the-fool`, `pre-mortem`, `stress-test`, `extrapolacao`, `conformal`  
**Data:** 2026-05-27  
**Status:** Concluído com Sucesso (Desafio de Premissas)  

---

## 🗺️ 1. Tese Steelmanned (Steelmanned Thesis)

Abaixo está a consolidação das premissas fundamentais do design do pipeline **DocML** em sua versão mais forte possível:

> "Acreditamos que a modelagem de arbovirose (dengue) por Região Administrativa do Distrito Federal é otimizada ao utilizar um ensemble não-linear de árvores (Random Forest e XGBoost) treinado no espaço logarítmico para estabilizar a heterocedasticidade extrema das RAs. Este modelo é validado de forma robusta e livre de leakage temporal através de um `TimeSeriesSplit` com `gap=4` semanas para refletir os atrasos reais do fluxo do SINAN, enquanto a incerteza estatística é calibrada de forma adaptativa out-of-sample via Conformal Prediction Indutivo Dinâmico usando as últimas 26 semanas de treino para capturar a dispersão de erros recente."

---

## 🥊 2. Críticas Severas às Premissas Metodológicas

Como revisores implacáveis, desafiamos as quatro premissas sob o rigor estatístico e a literatura científica epidemiológica:

### 1ª Premissa Desafiada: Validação Temporal com `TimeSeriesSplit(gap=4)`
*   **A Falha:** A escolha de um `gap=4` semanas é estática e ignora a dinâmica operacional real de sistemas de saúde pública em tempos de crise. 
*   **O Estresse:** Durante períodos interepidemias (calmaria), o atraso de inserção de fichas no SINAN/info-saude é de fato de ~3 a 4 semanas. Contudo, em **picos epidêmicos explosivos** (como nos anos de 2024 e 2026 no DF), a infraestrutura hospitalar e de vigilância sanitária colapsa. O atraso na notificação e na digitação dos dados sobe exponencialmente para **8 a 12 semanas**.
*   **O Impacto:** Avaliar o modelo em validação com um gap irreal de 4 semanas gera métricas de R² infladas. Em produção, durante o pior momento do surto, o modelo estará recebendo lags de casos (`cases_lag_1` a `cases_lag_4`) compostos por zeros ou valores severamente subnotificados devido ao represamento, o que fará as predições de nowcasting despencarem justamente quando as autoridades precisam do alerta de pico.

### 2ª Premissa Desafiada: Modelos de Árvore (RF/XGBoost) para Extrapolação Epidêmica
*   **A Falha:** Florestas Aleatórias e XGBoost são algoritmos baseados em árvores de decisão que dividem o espaço de features em hiperretângulos ortogonais. Eles são **incapazes de extrapolar tendências além do limite máximo observado no conjunto de treino**.
*   **O Estresse:** Se o surto de 2026 for 2 vezes maior em volume absoluto do que o pico histórico de 2024 (por exemplo, devido à introdução em massa de um novo sorotipo como o DENV-3), a saída das árvores irá saturar rigidamente no valor máximo do treino ($y_{\text{max}}$). Mesmo que o clima esteja extremamente propício (lags climáticos) e o Rt esteja acelerando exponencialmente, o modelo de árvores preverá um platô achatado.
*   **O Impacto:** O modelo é incapaz de alertar sobre crises humanitárias sem precedentes, agindo como um limitador de gravidade artificial em cenários de catástrofe epidemiológica.

### 3ª Premissa Desafiada: Transformação Logarítmica `np.log1p` e a Desigualdade de Jensen
*   **A Falha:** A aplicação de $\log(y + 1)$ estabiliza a variância para RAs de grande volume (ex: Ceilândia), mas distorce gravemente os gradientes de RAs de baixíssimo volume (ex: SIA, Varjão), onde as contagens semanais oscilam frequentemente entre 0 e 2 casos.
*   **O Estresse:** Mais criticamente, ao treinar no espaço logarítmico e aplicar a transformação inversa direta $\hat{y} = \exp(\hat{z}) - 1$, o pipeline viola a **Desigualdade de Jensen**:
    $$\mathbb{E}[\exp(Z)] > \exp(\mathbb{E}[Z])$$
    A exponencial da média logarítmica subestima sistematicamente o valor esperado real quando a variância do termo de erro é alta.
*   **O Impacto:** O modelo apresenta uma tendência intrínseca e matematicamente garantida de **subestimar gravemente a altura dos picos epidemiológicos** no espaço real de casos, exatamente onde o erro residual e a variância são máximos.

### 4ª Premissa Desafiada: Representatividade da Calibração Conformal de 26 Semanas
*   **A Falha:** Calibrar o quantil crítico de não-conformidade $q_{\text{conf}}$ usando estritamente as últimas 26 semanas (6 meses) do conjunto de treino é um erro grave de amostragem sazonal.
*   **O Estresse:** A dengue em Brasília possui ciclos anuais rígidos ditados pelo clima do Cerrado: alta transmissão no verão úmido (Janeiro a Maio) e seca extrema fria no inverno (Julho a Outubro). Se o conjunto de treino terminar em Novembro, a janela de 26 semanas cobrirá apenas o período seco de baixa transmissão. Os resíduos do modelo nesse período serão extremamente baixos e a variância quase nula, calibrando um $q_{\text{conf}}$ excessivamente estreito.
*   **O Impacto:** Quando o modelo entrar no pico explosivo de 2025, a banda de confiança conformalizada de 90% será **extremamente estreita e otimista**, falhando em fornecer a cobertura estatística de 90% teórica no momento em que os erros do modelo dispararem.

---

## ☠️ 3. Exercício de Pre-Mortem (Árvore de Falhas em Produção)

Abaixo estão os cenários operacionais realistas de como o modelo falhará catastroficamente se implantado sem defesas:

### Cenário A: Colapso por Represamento Sanitário (Greve de Fichas)
*   **Trigger:** Greve de 6 semanas dos servidores da vigilância epidemiológica do DF impede a digitação das fichas do SINAN no info-saude.
*   **Cadeia de Consequências:**
    ```
    Greve na Saúde (Atraso de 6 semanas nas notificações reais)
      → 1º Nível: Lags de casos reais (cases_lag_1 a cases_lag_4) são computados como zero ou valores mínimos
        → 2º Nível: O modelo de ML interpreta a queda abrupta como fim natural da epidemia
          → 3º Nível: O Nowcasting prevê "Zero Casos" para as próximas semanas e desativa alertas
            → 4º Nível: Hospitais de campanha são desmobilizados preventivamente com base no modelo, gerando falta crítica de leitos e mortes evitáveis
    ```
*   **Ponto de Detecção:** Apenas quando os relatórios de internações por sintomas clínicos superarem em 500% as predições do modelo, mas a essa altura a infraestrutura já terá sido desarticulada.

### Cenário B: Saturação por Anomalia Climática Unprecedented
*   **Trigger:** Brasília enfrenta uma onda de calor extremo histórica (El Niño acoplado ao aquecimento global) com temperaturas médias semanais atingindo $+5^\circ\text{C}$ acima de qualquer valor registrado no treino de 2017-2024.
*   **Cadeia de Consequências:**
    ```
    Onda de Calor Extremo (+5°C acima do histórico)
      → 1º Nível: As features de temperatura caem nos nós folha mais externos das árvores de decisão
        → 2º Nível: Random Forest e XGBoost saturam o efeito de temperatura no limite máximo do passado
          → 3º Nível: O modelo falha em capturar o encurtamento do ciclo de reprodução do mosquito (extrapolação falha)
            → 4º Nível: A epidemia explode 3x acima do esperado, mas o alerta do modelo prevê apenas um pico moderado
    ```

---

## 🛡️ 4. Sugestões de "Guardas-Chuva" de Proteção (Defesas de Produção)

Para blindar o pipeline de produção contra esses pontos de falha matemáticos e operacionais, sugerimos a inclusão de quatro mecanismos de defesa:

```
                                  DIRETRIZES DE DEFESA
                                           │
         ┌─────────────────────────────────┼────────────────────────────────┐
         ▼                                 ▼                                ▼
[Fallback de Atraso]             [Hibridização Linear]             [Conformal Sazonal]
Substitui lags reais             Adiciona regressor linear         Calibração de quantis
por previsões se o               ou SIR ao ensemble para           por estações (Seca/Chuva)
atraso SINAN for detectado.      extrapolar novos picos.           garante cobertura real.
```

### Defesa 1: Detector de Atraso e Fallback de Lags (Lag-Safe Fallback)
*   **Mecanismo:** Implementar uma telemetria em tempo real que monitora a taxa de atualização dos dados inseridos nas últimas semanas. Se o desvio padrão ou a quantidade de dias desde a última notificação útil subir além de um limite crítico (ex: >14 dias), o sistema **desativa automaticamente o Nowcasting (que consome lags reais)** e força o **Fallback para o Forecast Recursivo Fechado** (que usa as próprias predições do modelo como lag). Isso impede que a lentidão humana de digitação seja interpretada pelo modelo como "cura" da doença.

### Defesa 2: Hibridização com Modelos de Extrapolação (Linear/SIR Hybrid)
*   **Mecanismo:** Adicionar uma camada de extrapolação ao ensemble. Em vez de confiar puramente em RF/XGBoost, estruturar um modelo híbrido:
    - O ensemble de árvores modela os resíduos e as complexas interações não-lineares sazonais de curto prazo.
    - Um modelo paramétrico robusto (ex: Regressão de Poisson Generalizada com penalização Ridge ou um modelo epidemiológico compartimental dinâmico **SEIR**) modela a tendência macro.
    - Isso garante que, se os inputs climáticos subirem para patamares inéditos, o componente linear/SEIR continuará escalando a previsão exponencialmente de forma biologicamente correta.

### Defesa 3: Calibração Conformal Sazonal Condicional (Grouped Conformal)
*   **Mecanismo:** Em vez de extrair o quantil crítico $q_{\text{conf}}$ de forma global das últimas 26 semanas, agrupar os resíduos históricos do conjunto de calibração em duas janelas sazonais: **"Temporada de Picos"** (Semanas 1 a 26) e **"Temporada de Seca"** (Semanas 27 a 52).
    - Calibrar dois quantis críticos independentes: $q_{\text{conf\_alta}}$ e $q_{\text{conf\_baixa}}$.
    - Aplicar dinamicamente o quantil correspondente à semana epidemiológica corrente da previsão. Isso garante intervalos de confiança largos e seguros durante o surto e estreitos durante a calmaria.

### Defesa 4: Fator de Correção de Smearing para Reversão Logarítmica
*   **Mecanismo:** Para neutralizar a subestimação sistemática da incidência provocada pela reversão direta $\exp(\hat{z}) - 1$ (Desigualdade de Jensen), aplicar o **Fator de Correção de Smearing de Duan**:
    $$\text{Predição Corrigida} = (\exp(\hat{z}) - 1) \times \frac{1}{N} \sum_{i=1}^N \exp(e_i)$$
    Onde $e_i$ são os resíduos de treino no espaço logarítmico. Isso reajusta a média matemática da escala real, impedindo a subestimação artificial dos picos de transmissão.
