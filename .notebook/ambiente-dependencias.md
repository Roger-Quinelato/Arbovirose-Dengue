# Ambiente Virtual e Dependências

**Tags:** `venv`, `requirements`, `setup`
**Descoberto em:** 2026-05-24

## Ambiente Virtual

- **Localização:** `c:\arbodf\DocML\.venv\`
- **Python:** 3.10.11
- **Criado com:** `python -m venv .venv`

### Ativar o ambiente

```powershell
# PowerShell (Windows)
.venv\Scripts\Activate.ps1

# CMD (Windows)
.venv\Scripts\activate.bat
```

### Instalar dependências

```powershell
.venv\Scripts\pip install -r requirements.txt
```

## Dependências (requirements.txt)

### Grupos Principais

| Grupo | Pacotes | Para qual script |
|---|---|---|
| Manipulação de dados | `pandas`, `numpy` | ambos |
| ML principal | `scikit-learn`, `xgboost` | `dengue_radf.py` |
| Séries hierárquicas | `statsforecast`, `mlforecast`, `hierarchicalforecast`, `utilsforecast` | `dengue.py` |
| Deep Learning | `tensorflow` (ou `torch`) | LSTM futuro |
| Visualização | `matplotlib`, `seaborn` | ambos |
| API/HTTP | `requests` | `dengue_radf.py` (Open-Meteo) |
| Jupyter | `jupyter`, `ipykernel` | `dengue.ipynb` |

## Gotchas de Instalação

- `tensorflow` é pesado (~500 MB). Se não for usar LSTM imediatamente, pode omitir.
- `hierarchicalforecast` e `statsforecast` dependem de `utilsforecast` — instalar na ordem do `requirements.txt`
- Em Windows, `xgboost` pode precisar de Microsoft Visual C++ Redistributable

## Observação sobre `dengue.py`

O script `dengue.py` precisa de um arquivo `data.csv` com colunas `data_epi`, `casos`, `uf`, `pais`, `regiao` que **não existe no repositório**. Este script está em modo experimental/referência. O pipeline de produção é o `dengue_radf.py`.
