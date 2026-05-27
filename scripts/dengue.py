# %%
# ! pip install statsforecast hierarchicalforecast mlforecast utilsforecast

# %%
import pandas as pd
from matplotlib import pyplot as plt

# %% [markdown]
# # Carrega e prepara o dataset

# %% [markdown]
# ## Carrega os dados

# %%
data = pd.read_csv('data.csv')
data['ds'] = pd.to_datetime(data['data_epi'])
data = data[data.ds < '2026-01-01']
data

# %% [markdown]
# ## Visualiza o dataset

# %%
df_data = data[data.uf == 'DF']
fig = plt.figure(figsize=(12, 6.75))
df_data.set_index('ds')['casos'].plot(linewidth=2)
plt.grid()
plt.title('Casos de Dengue no DF')
plt.xlabel('Semana Epidemiológica')
plt.ylabel('Casos')
plt.show()

# %% [markdown]
# ## Organiza dataset como séries hierárquicas

# %%
from hierarchicalforecast.utils import aggregate

data = data.rename(columns={"casos": "y"})

hiers = [
    ['pais'],
    ['pais', 'regiao'],
    # ['pais', 'regiao', 'uf']
]

hier_df, S_df, tags_df = aggregate(data, hiers)

hier_df

# %%
print("Níveis hierárquicos disponíveis:")
for uid in hier_df.unique_id.unique():
    print(f"  {uid}")

# %%
groups = [
    'Brasil', 'Brasil/Centro-Oeste', 'Brasil/Nordeste', 'Brasil/Norte', 'Brasil/Sudeste', 'Brasil/Sul'
]

fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(16, 9))
axes = axes.flatten()

for i, group in enumerate(groups):
    df_group = hier_df[hier_df.unique_id == group]
    ax = axes[i]
    ax.plot(df_group["ds"], df_group["y"], label="Observado")
    ax.set_title(group)

plt.tight_layout()
plt.show()

# %% [markdown]
# # Previsão das séries hierárquicas

# %% [markdown]
# ### Split Treino e Teste

# %%
FORECAST_HORIZON = 52  # semanas

test_df  = hier_df.groupby("unique_id", as_index=False).tail(FORECAST_HORIZON)
train_df = hier_df.drop(test_df.index).reset_index(drop=True)
test_df  = test_df.reset_index(drop=True)

print(f"\nTreino: {train_df.ds.min().date()} → {train_df.ds.max().date()}")
print(f"Teste : {test_df.ds.min().date()} → {test_df.ds.max().date()}")
print(f"Horizonte: {FORECAST_HORIZON} semanas")

# %% [markdown]
# ## Previsão

# %% [markdown]
# ### StatsForecast - AutoARIMA + AutoTheta + AutoETS (juntos)

# %%
from statsforecast.core import StatsForecast
from statsforecast.models import AutoARIMA, AutoTheta, AutoETS

sf = StatsForecast(
    models=[
        AutoARIMA(),
        AutoTheta(),
        AutoETS(),
    ],
    freq="W-SUN",
    # n_jobs=-1,       # paraleliza por série
    verbose=True,
)

sf.fit(train_df)

sf_fcst_df = sf.forecast(
    df=train_df,
    h=FORECAST_HORIZON,
    fitted=True,          # necessário para forecast_fitted_values()
)
sf_insample_df = sf.forecast_fitted_values()

# Junta valores reais do teste
sf_fcst_df = pd.merge(sf_fcst_df, test_df[["unique_id", "ds", "y"]], on=["unique_id", "ds"])

print("\nPrevisões StatsForecast:")
print(sf_fcst_df.head())

# %% [markdown]
# ### MLForecast - XGBoost
# 

# %%
from mlforecast import MLForecast
from xgboost import XGBRegressor

ml = MLForecast(
    models={"XGBoost": XGBRegressor(n_estimators=200, learning_rate=0.05, random_state=42)},
    freq='W-SUN',
    lags=[1, 4, 8, 13, 26, 52],
    date_features=["week", "month"],
)

ml.fit(train_df, fitted=True)

ml_fcst_df = ml.predict(FORECAST_HORIZON)
ml_insample_df = ml.forecast_fitted_values()

# Garante colunas compatíveis com StatsForecast
ml_fcst_df = pd.merge(ml_fcst_df, test_df[["unique_id", "ds", "y"]], on=["unique_id", "ds"])

print("\nPrevisões MLForecast:")
print(ml_fcst_df.head())

# %% [markdown]
# # Reconciliação

# %%
# Merge de todas as previsões base numa tabela só
all_fcst_df = sf_fcst_df.merge(
    ml_fcst_df[["unique_id", "ds", "XGBoost"]],
    on=["unique_id", "ds"],
    how="left",
)
 
# Insample: une StatsForecast + MLForecast
all_insample_df = sf_insample_df.merge(
    ml_insample_df[["unique_id", "ds", "XGBoost"]],
    on=["unique_id", "ds"],
    how="left",
).dropna()
 
print("Colunas de previsão base:", [c for c in all_fcst_df.columns if c not in ("unique_id", "ds", "y")])

# %%
from hierarchicalforecast.core import HierarchicalReconciliation
from hierarchicalforecast.methods import BottomUp, MinTrace, TopDown

# definir modelos de reconciliação
# Reconciliação
reconcilers = [
    BottomUp(),
    MinTrace(method="mint_shrink"),
    TopDown(method="forecast_proportions"),
]
hrec = HierarchicalReconciliation(reconcilers)

rec_df = hrec.reconcile(
    Y_hat_df=all_fcst_df,
    Y_df=all_insample_df,
    S_df=S_df,
    tags=tags_df,
)
 
print("\nDataframe reconciliado – colunas:")
print([c for c in rec_df.columns if c not in ("unique_id", "ds")])

# %% [markdown]
# # Avaliação

# %%
from hierarchicalforecast.evaluation import evaluate as hevaluate
from utilsforecast.losses import rmse, mape

eval = hevaluate(
    df = rec_df,
    tags=tags_df,
    metrics=[mape],
)
eval.T

# %%
groups = [
    'Brasil',
    'Brasil/Norte',
    'Brasil/Nordeste',
    'Brasil/Centro-Oeste',
    'Brasil/Sudeste',
    'Brasil/Sul',
]

fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(16, 9))
axes = axes.flatten()

for i, group in enumerate(groups):
    df_group = rec_df[rec_df.unique_id == group]
    ax = axes[i]
    ax.plot(df_group['ds'], df_group['y'], label='Observado')
    ax.plot(df_group['ds'], df_group['XGBoost'], label='XGBoost')
    ax.plot(df_group['ds'], df_group['XGBoost/BottomUp'], label='XGBoost/BottomUp')
    ax.set_title(group)
    if i == 0:
        ax.legend()
plt.show()


