# ADR-001: Adoção de Arquitetura Modular em Pacote Python (`src/dengue_pipeline`)

- **Date**: 2026-05-24
- **Status**: Accepted
- **Deciders**: @Roger, @Antigravity
- **Tags**: `architecture`, `modularization`, `refactoring`, `pipeline`

## Context and Problem Statement

O pipeline preditivo de arboviroses do DF foi inicialmente construído como um único script monolítico (`dengue_radf.py` / `pipeline_modelagem_dengue.py`) de ~400 linhas. Toda a lógica — ETL, engenharia de features, treinamento, avaliação e geração de relatórios — estava acoplada em um único arquivo sem interfaces claras entre domínios.

Esse modelo de crescimento funcionou para experimentação rápida, mas criou barreiras concretas à evolução do projeto: duplicação de lógica de normalização de Regiões Administrativas, impossibilidade de testar funções isoladas, hardcoding de datas e paths, e impossibilidade de reutilizar componentes (ex: o calendário epidemiológico) sem copiar código.

## Decision Drivers

- **Testabilidade**: Funções críticas como `normalizar_ra()`, `calibrar_conformal()` e `agregar_metricas()` precisam ser testáveis isoladamente.
- **Reutilização**: O `shared_kernel` (calendário epidemiológico, registro de RAs) deve ser acessível por qualquer módulo sem duplicação.
- **Manutenibilidade**: Mudanças no ETL não devem exigir alterações no código de modelagem.
- **Onboarding científico**: Novos colaboradores devem conseguir navegar no pipeline por domínio, sem ler 400 linhas sequenciais.
- **Auditoria reproduzível**: Cada saída do pipeline deve ser rastreável a uma execução específica com timestamp.

## Considered Options

- **Option A (Do nothing)**: Manter o script monolítico e organizar melhor internamente com comentários e seções.
- **Option B (Módulos Python soltos em `/scripts`)**: Separar funções em arquivos `.py` independentes na pasta `scripts/`.
- **Option C (Pacote Python modular `src/dengue_pipeline/`)**: Criar um pacote Python estruturado por domínio funcional, instalável via `pip install -e .`, com subpacotes `etl/`, `modeling/`, `reporting/`, `shared_kernel/`.

## Decision Outcome

Chosen option: **"Option C"**, porque é a única abordagem que impõe contratos claros de interface entre domínios, permite `import` estruturado (sem manipulação de `sys.path`), e cria fundação para testes unitários e CI.

### Positive Consequences

- Cada domínio funcional tem um único responsável: `etl/` para ingestão, `modeling/` para treinamento/avaliação, `reporting/` para saídas, `shared_kernel/` para código compartilhado.
- O `shared_kernel/ra_registry.py` eliminou a duplicação de normalização de RAs presente no script legado.
- O script monolítico foi movido para `legacy/` como referência histórica, sem ser deletado (preserva rastreabilidade científica).
- O pacote é executado via `python -m dengue_pipeline`, suportando futura paralelização por RA.

### Negative Consequences

- Aumenta a complexidade de entrada: novos colaboradores precisam entender a estrutura de pacote Python (`src/`, `__init__.py`, imports relativos) antes de contribuir.
- O import circular latente entre `evaluation.py` e `train_tuning.py` (resolvido com imports tardios) é um sinal de que a separação de responsabilidades entre os módulos de avaliação e treinamento ainda não está completa.

## Pros and Cons of the Options

### Option A: Monolítico (Status Quo)

- ✅ Simples para executar e entender superficialmente
- ❌ Impossível testar funções isoladas sem executar o pipeline inteiro
- ❌ Duplicação de lógica inevitável conforme o projeto cresce
- ❌ Hardcoding de paths e datas se multiplica sem controle

### Option B: Módulos Soltos em `/scripts`

- ✅ Simples de implementar; não exige conhecimento de empacotamento Python
- ❌ Imports via `sys.path.append` são frágeis e não escaláveis
- ❌ Não impõe fronteiras de domínio — qualquer módulo pode importar qualquer outro

### Option C: Pacote Python `src/dengue_pipeline/` ✅ Chosen

- ✅ Interfaces de domínio claras via subpacotes
- ✅ Importável sem manipulação de `sys.path`
- ✅ Compatível com `pytest`, `mypy`, `ruff` e ferramentas de CI
- ❌ Curva de aprendizado inicial para colaboradores sem experiência em estrutura de pacotes Python

## Links

- Script Legado Preservado: [legacy/pipeline_modelagem_dengue.py](file:///c:/arbodf/DocML/legacy/pipeline_modelagem_dengue.py)
- Ponto de Entrada Atual: [src/dengue_pipeline/__main__.py](file:///c:/arbodf/DocML/src/dengue_pipeline/__main__.py)
- Auditoria de Estrutura: [.notebook/auditoria-fases2-3-estrutura-qualidade.md](.notebook/auditoria-fases2-3-estrutura-qualidade.md)
- Supersedido por: N/A
