# RFC-09: Estratégia de Forecast Multi-Step (Exposure Bias / Error Propagation) e Integração Arquitetural

| Campo            | Valor                                                                |
|------------------|----------------------------------------------------------------------|
| **Impacto**      | HIGH — viés estrutural na previsão de surtos de múltiplas semanas e adaptação à nova arquitetura baseada em Pipelines |
| **Status**       | APPROVED                                                             |
| **Driver**       | @roger-quinelato                                                     |
| **Aprovador**    | @roger-quinelato                                                     |
| **Contribuidores** | Orientador (se aplicável)                                        |
| **Informados**   | —                                                                    |
| **Prazo**        | TBD (antes de publicar resultados de forecast fechado)              |
| **Criado em**    | 2026-05-27                                                           |
| **Atualizado**   | 2026-05-27                                                           |

---

## Background

**Estado Atual:**
Em `train_tuning.py`, `executar_validacao_temporal` implementa previsão autoregressiva recursiva, onde as predições de um passo são usadas como entrada para o próximo passo.

**Problema — Exposure Bias:**
O modelo é **treinado** com valores reais históricos, mas em **inferência recursiva** os lags passam a ser as próprias predições do modelo. Erros se acumulam exponencialmente. Em dinâmicas epidemiológicas, este erro se amplifica rapidamente.

**Contexto Arquitetural Atualizado:**
Com a aprovação das RFCs recentes, o sistema está migrando para:
- **RFC-01/02:** `sklearn.pipeline.Pipeline` para garantir encapsulamento e prevenir vazamento de dados, aliado à biblioteca MAPIE para intervalos Conformal.
- **RFC-03:** Desacoplamento do fluxo via um arquivo central `orchestration.py`.
- **RFC-04:** Contratos rigorosos de interface utilizando tipagem clara com `NamedTuple` (ex: `PredictionResult`).
- **RFC-05:** Centralização de caminhos de configuração em `config.py` baseada em `PIPELINE_ROOT`.

A estratégia de previsão recursiva é incompatível com o encapsulamento limpo do `sklearn.Pipeline` e dificulta severamente a extração de intervalos de confiança multi-horizon consistentes usando a biblioteca MAPIE, forçando complexas manobras em runtime.

---

## Assumptions

| # | Pressuposto | Confiança | Invalidado se |
|---|-------------|-----------|---------------|
| 1 | O horizonte máximo de projeção do modelo é ≤ 8 semanas (dentro da janela do surto) | Médio | O projeto exigir previsões contínuas de longo prazo (>12 semanas) |
| 2 | Direct Multi-Horizon Forecasting é viável computacionalmente iterando múltiplos `sklearn.Pipeline` | Alto | Memória ou recursos computacionais (CPU) não suportarem o treinamento de $K$ pipelines paralelos |
| 3 | Múltiplos pipelines independentes podem ser envelopados limpidamente via `NamedTuples` | Alto | Um único objeto for estritamente exigido para o inferenciador por ferramentas downstream |

---

## Critérios de Decisão

| Prioridade | Critério | Peso |
|------------|----------|------|
| 1 | Eliminar o exposure bias no forecast multi-step integrando organicamente com `sklearn.Pipeline` | Must-have |
| 2 | Respeitar contratos `NamedTuple` e gerenciamento unificado de artefatos (RFC-04, RFC-05) | Must-have |
| 3 | Manter compatibilidade impecável com a API do MAPIE (RFC-01/02) para os intervalos de previsão | Alto |
| 4 | Custo computacional, de treinamento e de armazenamento controlados | Médio |

---

## Opções Consideradas

### Opção 1: Direct Multi-Horizon com Conjunto de Pipelines Independentes ⭐ (Recomendada)

**Descrição:**
Treinar um `sklearn.Pipeline` totalmente isolado (possuindo seu próprio pré-processamento, target transformer e regressor empacotado no MAPIE) para cada horizonte `k`. A orquestração (via `orchestration.py`) coordena a criação das defasagens e o treinamento simultâneo para todos os $K$ horizontes e persiste os artefatos individualmente conforme definido no `config.py`.

```python
# Contrato guiado pela RFC-04
class MultiHorizonForecastResult(NamedTuple):
    horizon: int
    pipeline: Pipeline
    metrics: Dict[str, float]

# Caminhos unificados guiados pela RFC-05
model_path = PIPELINE_ROOT / "models" / f"direct_mh_pipeline_k{k}.pkl"
```

**Prós:**
- Elimina completamente o *exposure bias* do forecasting.
- O MAPIE lida nativamente com cada horizonte gerando calibração condicional correta de incertezas, seguindo a essência da RFC-01 e RFC-02.
- Pipelines estáticos durante a inferência facilitam uso das `NamedTuples`.

**Contras:**
- Retenção de $K$ modelos em disco, multiplicando o esforço de treinamento (necessidade de iterar sobre `k`).

---

### Opção 2: Multi-Output Regression Pipeline (Saída Vetorizada)

**Descrição:**
Alterar o estimador final inserido no `sklearn.Pipeline` para englobar `MultiOutputRegressor`, convertendo a variável resposta $y$ em um vetor tamanho $K$ representando $(y_{t+1}, \dots, y_{t+K})$.

**Prós:**
- Um único modelo gravado em disco e menos complexidade de repetição do processo de treino.

**Contras:**
- Complexidade ou até quebra da API para integrar `MAPIE` perfeitamente em estimadores multi-output sem comprometer a confiança dos intervalos de predição.
- Não há flexibilidade para escolher transformações diferentes por horizonte, se for o caso.

---

## Comparativo

| Critério | Opção 1 (Direct Pipelines) | Opção 2 (Multi-Output) |
|---|---|---|
| Elimina Exposure Bias | ✅ | ✅ |
| Compatibilidade c/ `sklearn.Pipeline` | ✅ (Trivial e isolado) | ⚠️ (Requer wrappers avançados) |
| Compatibilidade nativa MAPIE | ✅ | ❌ |
| Aderência `NamedTuple` & Configs | ✅ | ✅ |

---

## Decisão

**Decisão:** Opção 1: Direct Multi-Horizon com Conjunto de Pipelines Independentes ⭐

**Data:** 2026-05-27

**Rationale:** 
Face à recente adoção do encapsulamento restrito com `sklearn.Pipeline` (RFC-02) e a implementação de validação estatística de intervalos com MAPIE (RFC-01), treinar um pipeline distinto para cada horizonte é a solução técnica de maior robustez metodológica. Evita-se as incertezas operacionais da compatibilidade entre MAPIE e estimadores `MultiOutputRegressor`. A estruturação de saída será encapsulada na tipagem forte via `NamedTuple` (RFC-04), com os $K$ arquivos resultantes perfeitamente descritos no `config.py` (RFC-05).

---

## Action Items

| Ação | Responsável | Prazo | Status |
|------|-------------|-------|--------|
| Ajustar lógicas em `orchestration.py` para instanciar pipelines isolados variando o target deslocado ($y_{t+k}$) | @roger | TBD | NOT STARTED |
| Instituir a nova tipagem `MultiHorizonForecastResult(NamedTuple)` abrangendo os modelos iterados | @roger | TBD | NOT STARTED |
| Mapear e atualizar centralizadamente diretórios para armazenamento de artefatos segmentados por `k` em `config.py` | @roger | TBD | NOT STARTED |

---

## Outcome

**Follow-up:**
- [ ] Validar o custo/tempo agregado de treinamento da estratégia Direct MH.
- [ ] Se o custo por *fold* se mostrar intensivo (devido à reexecução), viabilizar o uso do `joblib` para treinamentos paralelos gerenciados pelo orquestrador.
