# RFC-002: Proposta de Pipeline de Análise, Limpeza e Modelagem Preditiva de Dengue no DF

- **Driver:** @Antigravity
- **Aprovador:** @Roger (Developer/User)
- **Status:** REVISADO
- **Impacto:** ALTO
- **Tags:** `modelagem`, `dengue`, `notebook`, `limpeza`, `validacao`, `ablation`
- **Criado em:** 2026-05-24
- **Revisado em:** 2026-05-24 (baseado em revisão crítica `revisao-plano-repositorio-2026-05-24.md`)
- **Revisão Recomendada:** 2026-05-31

---

## Changelog desta Revisão

| # | Seção | Mudança |
|---|---|---|
| 1 | §2 Premissas | Adicionada premissa explícita sobre definição do target epidemiológico |
| 2 | §2 Premissas | Adicionada premissa sobre populacao histórica como pré-requisito (não P2 opcional) |
| 3 | §3 Critérios | Adicionado critério de separação explícita entre nowcasting e forecast fechado |
| 4 | §4 Opção A | Adicionadas Fases 0 (target), 4b (ablation) e distinção nowcasting/forecast |
| 5 | §6 Action Items | Adicionados itens para ablation, baseline formal e rolling validation explícita |

---

## 1. Contexto & Definição do Problema

O Distrito Federal enfrenta surtos epidêmicos de dengue periódicos de grande magnitude (com destaque para o pico histórico de 2024, que registrou mais de 325 mil notificações).

Atualmente, o repositório contém scripts de modelagem preditiva pontuais por Região Administrativa (`dengue_radf.py`) e modelos hierárquicos nacionais experimentais (`dengue.py`).

No entanto, o processo carece de uma **fase robusta de análise exploratória, limpeza de dados rigorosa e validação de engenharia de atributos (features)** estruturada em um ambiente interativo (Jupyter Notebook). Sem esse passo, corremos o risco de treinar modelos em dados com ruído demográfico, geolocalizações ausentes ou *data leakage* temporal nos lags.

> [!WARNING]
> A revisão crítica de 2026-05-24 identificou que `dengue_radf.py` calcula `cases_lag_1..4` em toda a série antes do split. No período de teste de 2025/2026, isso permite que o modelo utilize casos reais de semanas futuras como input — caracterizando **data leakage temporal**. Os resultados atuais (R² ≈ 0.70) devem ser considerados **nowcasting rolling**, não forecast fechado de 52 semanas.

---

## 2. Premissas (Assumptions)

1. **Premissa 1 — Fonte de Dados:** A base `info-saude/` é o registro georreferenciado mais fiel das notificações de dengue locais do DF.
   * *Confiança:* Alta.
   * *Gatilho de Invalidação:* Mudança nos padrões de armazenamento ou integridade dos arquivos CSV da Secretaria de Saúde.

2. **Premissa 2 — Clima Centralizado:** Os registros de clima da NASA POWER e a base InfoDengue Fiocruz servem como preditores climáticos válidos para as 35 Regiões Administrativas do DF.
   * *Confiança:* Média-Alta (presume que as anomalias de microclima entre RAs não inviabilizam o uso do clima centralizado de Brasília).

3. **Premissa 3 — Definição de Target (NOVA — P0):** O target epidemiológico é definido como registros simultâneos de `i_class_final == 'Caso Provável'` **E** `i_desc_classificacao == 'Dengue'`. A decisão de incluir ou excluir registros `Inconclusivo`/`Não Informado` deve ser tomada e documentada **antes** de qualquer treinamento, pois impacta diretamente toda a série alvo.
   * *Confiança:* Decisão em aberto — requer validação com o banco de 2024 para quantificar o impacto volumétrico de cada critério.

4. **Premissa 4 — População Histórica como Pré-requisito (NOVA — P1):** A integração de [populacao_historica.csv](file:///c:/arbodf/DocML/populacao_historica.csv) não é uma melhoria incremental, mas um **pré-requisito** para qualquer uso de RA como feature. Sem população histórica por RA/ano, a taxa de incidência carrega viés demográfico estrutural, tornando as features de RA incomparáveis entre períodos.

---

## 3. Critérios de Decisão (Weights)

Antes de avaliar as opções de modelagem e análise, definimos os seguintes critérios de aceitação:

1. **Rigor Científico (Peso: 40%):** Prevenção absoluta de *data leakage* (vazamento de dados temporais) nos conjuntos de treino, teste e validação. Isso inclui a distinção explícita entre **nowcasting rolling** (modelo operacional semana a semana, com lags reais permitidos) e **forecast fechado** (previsão prospectiva sem acesso a dados futuros).
2. **Modularidade e Reprodutibilidade (Peso: 30%):** O pipeline de análise exploratória e modelagem deve ser facilmente executado e compreendido por qualquer colaborador em um Jupyter Notebook.
3. **Precisão Preditiva com Baseline (Peso: 30%):** Qualquer modelo final deve superar de forma estatisticamente significativa o baseline naive `cases_lag_1`. O ganho real das features climáticas/espaciais/populacionais precisa ser demonstrado com **ablation tests**.

---

## 4. Opções Consideradas

### Opção A: Jupyter Notebook Focado na Base `info-saude` com Clima Lags Integrado (Recomendada)

Esta opção consiste em estruturar um Jupyter Notebook (`dengue_analise_modelagem.ipynb`) para executar:

*   **Fase 0 (NOVA — P0): Formalização do Target:** Decisão documentada e explícita sobre os filtros de `i_class_final` e `i_desc_classificacao`. Comparação volumétrica das séries resultantes para cada critério antes de prosseguir.
*   **Fase 1: Seleção e Limpeza do Target:** Isolamento da coluna alvo com os filtros definidos na Fase 0 e mapeamento descritivo da evolução dos casos absolutos agregados por semana (`epi_sunday`) e por RA.
*   **Fase 2: Análise Correlacional e Limpeza:** Integração dos lags climáticos (chuva, temperatura e **umidade relativa**) e análise de correlação (Pearson/Spearman) direta com a taxa de incidência para validar a relevância biológica das defasagens de 2 a 8 semanas.
*   **Fase 3: Alinhamento Demográfico (P1 — pré-requisito):** Cruzamento dinâmico com [populacao_historica.csv](file:///c:/arbodf/DocML/populacao_historica.csv) e criação de um benchmark de **População Absoluta do DF** para validar tendências globais e neutralizar distorções territoriais nas RAs recém-criadas.
*   **Fase 4: Codificação de Variáveis Cíclicas:** Transformação de variáveis temporais/calendário (`week_of_year`, `month`) em projeções trigonométricas de **Seno e Cosseno**.
*   **Fase 4b (NOVA — P1): Ablation Tests:** Treinamento sequencial de 4 modelos com features crescentes para isolar a contribuição de cada grupo:
    1.  `lag-only`: apenas `cases_lag_1..4` como baseline formal.
    2.  `lag + clima`: adiciona precipitação, temperatura e umidade com lags.
    3.  `lag + clima + RA`: adiciona codificação das Regiões Administrativas.
    4.  `lag + clima + RA + população`: adiciona taxa por 100k com populacao histórica.
*   **Fase 5: Divisão com Janela Deslizante (Rolling Forecast) Explícita:** Cálculo de lags auto-regressivos feito **dentro de cada fold** (agrupado por RA, sem vazamento para o período de teste). Distinção documentada entre o modo nowcasting e o modo forecast fechado.
*   **Fase 6: Benchmarking de Modelagem:** Treinamento de Random Forest e XGBoost Regressors com comparação direta com os baselines.

### Opção B: Migrar direto para Modelagem de Séries Temporais Hierárquicas (`dengue.py`)

Focar exclusivamente na reconciliação hierárquica usando Nixtla (`statsforecast`/`mlforecast`), ignorando a geolocalização detalhada por RA do `info-saude` em favor de dados nacionais.
*   *Problema:* Falta de granularidade das RAs locais do DF no modelo hierárquico e dependência de um arquivo `data.csv` ausente no repositório.
*   *Problema adicional (NOVO):* Antes de qualquer reconciliação Brasil→Região→UF→RA, é necessário provar compatibilidade temporal e semântica entre o SINAN nacional (2001-2017) e o `info-saude` local (2017-2026). As diferenças de granularidade, definição de caso e cobertura tornam essa etapa obrigatória, não trivial.

---

## 5. Recomendação e Racional

Recomendamos a **Opção A**. Ela atende a 100% dos critérios estabelecidos, fornecendo o rigor metodológico ideal para a limpeza da base local, controle de vazamento temporal através de divisão rígida e integração dinâmica dos dados climáticos e populacionais.

A sequência de ablation tests (Fase 4b) é essencial para demonstrar que os modelos RF e XGBoost agregam valor real além do baseline naive de lag-1, dado que a revisão crítica identificou que a margem atual (R² 0.703 vs. 0.697) é estatisticamente insignificante.

---

## 6. Plano de Ação (Action Items)

### P0 — Antes de qualquer código de modelagem
- [ ] **Congelar target:** Decidir e documentar os filtros exatos (`i_class_final` e `i_desc_classificacao`). Medir impacto volumétrico de cada opção.
- [ ] **Separar nowcasting de forecast:** Documentar explicitamente qual modo de validação cada célula do notebook implementa.

### P1 — MVP do notebook
- [ ] Criar o notebook interativo `dengue_analise_modelagem.ipynb` na raiz do projeto.
- [ ] Calcular lags auto-regressivos **dentro de cada fold** do rolling validation (agrupados por RA, sem leakage).
- [ ] Integrar [populacao_historica.csv](file:///c:/arbodf/DocML/populacao_historica.csv) como join obrigatório por `RA` + `ano` antes de qualquer feature de RA.
- [ ] Implementar a codificação Seno/Cosseno para sazonalidade.
- [ ] Implementar ablation tests sequenciais (4 configurações de features).
- [ ] Reportar R² do baseline `cases_lag_1` como linha de corte mínima de aceitação.

### P2 — Maturidade e qualidade
- [ ] Adicionar testes de contratos de dados (schema, encoding, nulos, tipos).
- [ ] Adicionar umidade do InfoDengue/NASA após tratamento de nulos.
- [ ] Inicializar repositório Git com `.gitignore` adequado (excluindo CSVs brutos sensíveis).

---

## 7. Decisão Final (Outcome)

O grupo optou pela **Opção A**.

O desenvolvimento será conduzido através do novo Jupyter Notebook `dengue_analise_modelagem.ipynb`. O fluxo incluirá: (0) formalização do target, (1) limpeza da base `info-saude`, (2) integração com dados climáticos (NASA POWER/InfoDengue) e populacionais históricos (IBGE/Codeplan), (3) ablation tests com 4 configurações de features, e (4) rolling validation explícita sem data leakage nos lags.
