# ADR-004: Versionamento de Execuções do Pipeline via Timestamp (`run_id`)

- **Date**: 2026-05-27
- **Status**: Accepted
- **Deciders**: @Roger, @Antigravity
- **Tags**: `architecture`, `reproducibility`, `pipeline`, `data-management`

## Context and Problem Statement

Cada execução do pipeline produzia artefatos (CSVs de métricas, gráficos, modelos `.joblib`) com nomes de arquivo fixos em diretórios fixos (`resultados_modelagem/`, `resultados_graficos/`). Isso tornava impossível:

1. **Comparar resultados entre execuções**: A execução seguinte sobrescrevia os artefatos da anterior sem histórico.
2. **Rastrear o estado dos dados na execução**: Não havia forma de saber com quais dados de entrada (quais semanas, quais RAs) determinados resultados foram gerados.
3. **Reprodução científica**: Compartilhar resultados com outros pesquisadores exigia guardar os arquivos manualmente fora do diretório padrão.

## Decision Drivers

- **Reprodutibilidade**: Qualquer execução passada deve poder ser identificada e reproduzida por seu `run_id`.
- **Non-destructive**: Execuções novas não devem sobrescrever resultados anteriores.
- **Compatibilidade com leitura padrão**: Código que lê `resultados_modelagem/` não deve quebrar — deve continuar apontando para o resultado mais recente.
- **Leveza no Git**: Artefatos pesados (`.joblib`) não devem ser rastreados pelo Git; apenas métricas leves (CSVs, JSONs) devem ser versionadas.

## Considered Options

- **Option A (Do nothing)**: Manter nomes fixos e instruir o usuário a copiar manualmente antes de re-executar.
- **Option B (Sufixo de data no arquivo)**: Adicionar data ao nome de cada arquivo: `resultados_ablation_20260527.csv`.
- **Option C (Subdiretório por `run_id` + symlink `latest/`)**: Criar `resultados_modelagem/<YYYYMMDD_HHMM>/` por execução e manter um symlink/cópia em `resultados_modelagem/latest/` para leitura padrão.

## Decision Outcome

Chosen option: **"Option C"**, porque mantém o princípio de non-destructive write e preserva a compatibilidade de leitura via `latest/`.

A implementação:
1. Em `__main__.py`, ao iniciar `main()`: `run_id = datetime.now().strftime("%Y%m%d_%H%M")`
2. O `run_dir` é criado em `resultados_modelagem/<run_id>/`
3. Cada módulo de saída (`train_tuning`, `report_writer`) recebe `run_dir` como parâmetro opcional
4. Ao final de cada execução, os artefatos são copiados para `resultados_modelagem/latest/`
5. O `.gitignore` ignora `.joblib` mas rastreia CSVs e JSONs dentro de `resultados_modelagem/`

### Positive Consequences

- Cada execução tem um diretório próprio identificável por data/hora.
- A leitura via `latest/` garante que código de análise e notebooks continuem funcionando sem ajuste.
- O histórico de métricas (CSVs, JSONs) fica preservado no Git; apenas binários pesados são ignorados.

### Negative Consequences

- O diretório `resultados_modelagem/` pode crescer rapidamente em disco com muitas execuções. Requer política de limpeza manual periódica (ou script de purge de runs > N dias).
- Em Windows, symlinks requerem privilégios elevados. A solução usa `shutil.copytree()` ao invés de `os.symlink()` para garantir compatibilidade cross-platform.

## Pros and Cons of the Options

### Option A: Nomes Fixos (Status Quo)

- ✅ Zero mudança de código necessária
- ❌ Sobrescreve resultados anteriores silenciosamente
- ❌ Impossível comparar duas execuções sem procedimento manual

### Option B: Sufixo de Data no Nome do Arquivo

- ✅ Simples de implementar
- ❌ Proliferação de arquivos no mesmo diretório (difícil de navegar)
- ❌ Código que lê por nome fixo quebra

### Option C: Subdiretório `run_id/` + `latest/` ✅ Chosen

- ✅ Cada execução é atômica e isolada
- ✅ Compatibilidade via `latest/` sem mudança de código nos leitores
- ✅ Histórico de métricas leves no Git
- ❌ Crescimento de disco requer política de purge

## Links

- Ponto de Entrada: [src/dengue_pipeline/__main__.py](file:///c:/arbodf/DocML/src/dengue_pipeline/__main__.py)
- Módulo de Tuning: [src/dengue_pipeline/modeling/train_tuning.py](file:///c:/arbodf/DocML/src/dengue_pipeline/modeling/train_tuning.py)
- Módulo de Relatório: [src/dengue_pipeline/reporting/report_writer.py](file:///c:/arbodf/DocML/src/dengue_pipeline/reporting/report_writer.py)
- Supersede: N/A
