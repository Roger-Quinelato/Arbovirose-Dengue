# ADR-003: Adoção de Conformal Prediction Dinâmico para Bandas de Incerteza

- **Date**: 2026-05-25
- **Status**: Accepted
- **Deciders**: @Roger, @Antigravity
- **Tags**: `architecture`, `uncertainty-quantification`, `conformal-prediction`, `modeling`

## Context and Problem Statement

O pipeline de previsão de dengue produz estimativas pontuais de casos semanais por Região Administrativa. Em vigilância epidemiológica, intervalos de predição confiáveis são tão importantes quanto as estimativas pontuais: gestores de saúde precisam saber se 50 casos previstos têm incerteza de ±10 ou ±200 casos para planejar recursos adequadamente.

Duas propriedades problemáticas foram identificadas na análise de resíduos dos modelos RF e XGBoost:

1. **Heteroscedasticidade**: O erro absoluto cresce proporcionalmente ao volume do surto — em picos de 300+ casos/semana, o erro é muito maior que em semanas de endemia (5–20 casos). Um intervalo fixo ±σ subestima incerteza durante surtos e superestima em períodos endêmicos.

2. **Colapso de forecast fechado**: Em projeções recursivas (sem casos reais das semanas futuras), a incerteza estimada por métodos de bootstrap clássico tende a colapsar à medida que o horizonte avança, produzindo bandas falsamente estreitas.

## Decision Drivers

- **Calibração empírica**: A cobertura nominal (90%) deve ser atingida empiricamente — i.e., 90% dos valores reais devem cair dentro do intervalo predito.
- **Adaptatividade**: A largura do intervalo deve ser proporcional ao volume previsto (heteroscedasticidade).
- **Eficiência computacional**: O método deve ser aplicável em produção semanal sem re-treinamento completo.
- **Interpretabilidade**: Gestores devem entender que o intervalo representa incerteza real, não um artefato estatístico.

## Considered Options

- **Option A (Bootstrap Paramétrico)**: Gerar múltiplas amostras bootstrap do conjunto de calibração e calcular percentis.
- **Option B (Conformal Prediction Induction — intervalo fixo)**: Calcular os resíduos absolutos de calibração e usar o quantil `q_conf` como margem fixa.
- **Option C (Conformal Prediction Dinâmico — escalonado pela predição)**: Normalizar os resíduos pela predição (`score_i = |y_i − ŷ_i| / (ŷ_i + ε)`) e usar `q_conf × (ŷ + ε) × √k` como margem adaptativa ao volume e ao horizonte.

## Decision Outcome

Chosen option: **"Option C"**, porque é a única abordagem que resolve simultaneamente heteroscedasticidade e colapso de forecast.

A margem de erro dinâmica usa a própria predição do modelo (`ŷ`) como estimador de escala:

```
score_i = |y_i − ŷ_i| / (ŷ_i + ε)       ← calibração
margin  = q_conf × (ŷ + ε) × √k          ← aplicação (k = horizonte em semanas)
```

O fator `√k` cresce com o horizonte de previsão, capturando a incerteza que se acumula em projeções fechadas.

### Positive Consequences

- **Melhoria empírica mensurável**: Winkler Score melhorou de 6,34 → 5,84 (+8%) com cobertura empírica ≥ 90%.
- **Intervalos proporcionais ao risco**: Surtos preditos de 200 casos têm bandas de ~40 casos; períodos endêmicos com 10 casos previstos têm bandas de ~2 casos.
- **Zero re-treinamento**: O modelo conformal é calibrado uma única vez após o treinamento e salvo em JSON para reutilização operacional.

### Negative Consequences

- **Dependência da qualidade da calibração**: Se o conjunto de calibração for muito pequeno ou não representar épocas de surto, `q_conf` será mal estimado. Requer que o período de calibração contenha pelo menos um ciclo epidêmico completo.
- **Pressuposto de estacionariedade relativa**: O método assume que a proporção `erro/predição` é estável entre o período de calibração e o período de aplicação. Mudanças estruturais no padrão de dengue (novo sorotipo DENV, campanhas de vacinação) podem invalidar o quantil calibrado.

## Pros and Cons of the Options

### Option A: Bootstrap Paramétrico

- ✅ Teoricamente bem fundamentado e amplamente usado
- ❌ Computacionalmente caro (N amostras × M previsões por bootstrap)
- ❌ Não resolve heteroscedasticidade naturalmente sem transformações adicionais

### Option B: Conformal Prediction — Intervalo Fixo

- ✅ Simples e com garantias teóricas de cobertura marginal
- ❌ Ignora heteroscedasticidade — largura do intervalo idêntica em surtos e endemia
- ❌ Não cresce com o horizonte de previsão

### Option C: Conformal Prediction Dinâmico ✅ Chosen

- ✅ Resolve heteroscedasticidade via normalização pelo volume predito
- ✅ Resolve colapso de forecast via fator `√k`
- ✅ Leve: calibração em JSON, sem re-treinamento
- ❌ Mais complexo de explicar a stakeholders não-técnicos
- ❌ Sensível à representatividade do conjunto de calibração

## Links

- Implementação: [src/dengue_pipeline/modeling/conformal_prediction.py](file:///c:/arbodf/DocML/src/dengue_pipeline/modeling/conformal_prediction.py)
- Auditoria de Segurança e Leakage: [.notebook/relatorio_seguranca_data_leakage.md](.notebook/relatorio_seguranca_data_leakage.md)
- Supersede: N/A
