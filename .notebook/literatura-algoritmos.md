# Literatura Científica: Algoritmos e Variáveis Preditoras

**Tags:** `artigos`, `algoritmos`, `variáveis`, `literatura`
**Descoberto em:** 2026-05-24
**Referência completa:** `sintese_dengue_df.md` (arquivo completo com mermaid e detalhamento)

## Artigos na pasta `artigos/`

| Arquivo | Tema Principal |
|---|---|
| `informatics-12-00015.pdf` | Revisão sistemática: ML para diagnóstico clínico de dengue (Andrade Girón et al., 2025) |
| `MLeDengueCeará.pdf` | Tese Sobral-CE: RF vs LSTM para previsão de casos com dados climáticos |
| `MLeDengueNaAmericaLatina.pdf` | Revisão: ML para séries temporais de dengue na América Latina (Cabrera et al., 2022) |
| `Sisamob Barbosa et al 2023.pdf` | SISAMOB: vigilância de arboviroses no DF com dados de mobilidade |
| `Artificial Intelligence In Medicine.pdf` | CNN/GRU/GNN para surtos respiratórios (referência metodológica, não específico de dengue) |

---

## Melhores Algoritmos por Cenário

### A. Diagnóstico Clínico (classificar se o paciente TEM dengue)
1. **PCA-SVM (poly-5):** 99,52% acurácia — melhor resultado da literatura (25% dos estudos)
2. **Random Forest:** 85-90% acurácia — segundo mais utilizado (15,6% dos estudos)

### B. Previsão Epidemiológica (prever quantidade de casos futuros)
1. **Random Forest + Engenharia de Features:** R²=0,80 (Sobral-CE) — **mas SOMENTE com lags e médias móveis**
   - Sem feature engineering: R²=-0,27 (péssimo!)
2. **LSTM:** Captura melhor picos abruptos e sazonalidade; correlação 0,87-0,92 em Natal/BR com 3-6 semanas de antecedência
3. **Ensemble RF+LSTM:** Arriscado — se LSTM tiver R²<0, puxa o ensemble para baixo (R²=0,13 no Sobral)

---

## Variáveis Mais Importantes (por categoria)

### 1. Climatológicas (mais críticas — usar com LAG!)
- **Temperatura** (média, máx, mín): acelera larvas e reduz incubação extrínseca do vírus
- **Umidade relativa:** aumenta longevidade do mosquito
- **Precipitação:** cria criadouros (mas chuva forte pode lavar larvas — efeito não-linear)
- **ENSO/Niño 3.4:** anomalias multi-anuais que causam surtos históricos

### 2. Vetoriais/Biológicas (mais diretas)
- **Índice de Densidade de Ovos (ovitrampas):** preditor biológico direto mais relevante
- **NDVI:** identifica corpos d'água e abrigo de mosquitos via satélite

### 3. Demográficas/Sociais
- **Mobilidade/Commuting:** principal disseminador espacial do vírus
- **Saneamento e armazenamento de água:** proxy para criação de criadouros
- **Altitude:** correlação negativa com transmissão

### 4. Clínicas (para triagem hospitalar)
- **Plaquetas (PLAQ_MENOR)** e **hematócrito (HEMA_MAIOR):** preditores de gravidade
- **IgM, NS1, PCR:** confirmação laboratorial do sorotipo

---

## Gotchas da Literatura
- Lags de 2-8 semanas climáticos são **obrigatórios** — dengue hoje reflete o clima de semanas atrás
- Médias móveis de 2-3 meses suavizam ruído sazonal
- Chuva torrencial pode ter efeito paradoxal (lava larvas) — modelar como feature não-linear
- Seca pode AUMENTAR casos (armazenamento doméstico de água)
