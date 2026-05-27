# -*- coding: utf-8 -*-
"""
[DEPRECADO] Este arquivo é parte do pipeline legado e monolítico de dengue.
Foi movido para a pasta legacy/ para despoluição da raiz do projeto.
Utilize o novo pipeline modular e robusto rodando:
    python -m dengue_pipeline
"""

import warnings
warnings.warn(
    "Este script é legado, monolítico e está deprecado. Use o pipeline modular em src/dengue_pipeline.",
    DeprecationWarning,
    stacklevel=1
)

import os
import glob
import unicodedata
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Configuração de visualização de gráficos
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 11

def normalize_ra(ra_name):
    """Padroniza os nomes das Regiões Administrativas (RAs) para alinhar com o censo populacional."""
    if not isinstance(ra_name, str):
        return None
    
    # Remover acentos e converter para maiúsculo
    ra_clean = ''.join(c for c in unicodedata.normalize('NFD', ra_name) if unicodedata.category(c) != 'Mn').upper().strip()
    
    # Mapeamento para ajustar variações específicas do dataset info-saude
    mapping = {
        'SCIA (ESTRUTURAL)': 'SCIA',
        'SOL NASCENTE/POR DO SOL': 'SOL NASCENTE E POR DO SOL',
        'SOL NASCENTE/POR DO SOL RES': 'SOL NASCENTE E POR DO SOL',
        'SAO SEBASTIAO': 'SÃO SEBASTIÃO',
        'CEILANDIA': 'CEILÂNDIA',
        'BRAZLANDIA': 'BRAZLÂNDIA',
        'GUARA': 'GUARÁ',
        'PARANOA': 'PARANOÁ',
        'ITAPOA': 'ITAPOÃ',
        'AGUAS CLARAS': 'ÁGUAS CLARAS',
        'JARDIM BOTANICO': 'JARDIM BOTÂNICO',
        'NUCLEO BANDEIRANTE': 'NÚCLEO BANDEIRANTE',
        'CANDANGOLANDIA': 'CANDANGOLÂNDIA',
        'AGUA QUENTE': 'AGUA QUENTE'
    }
    
    return mapping.get(ra_clean, ra_clean)

def carregar_e_limpar_dados(info_saude_dir):
    """Lê, limpa, padroniza e agrupa todos os casos de dengue do info-saude."""
    print(">>> Iniciando carregamento e agregação dos dados de casos...")
    csv_files = glob.glob(os.path.join(info_saude_dir, "*.csv"))
    
    if not csv_files:
        raise FileNotFoundError(f"Nenhum arquivo CSV encontrado em: {info_saude_dir}")
        
    dfs = []
    for file in csv_files:
        print(f"  Carregando {os.path.basename(file)}...")
        df = pd.read_csv(file, sep=';', usecols=['i_class_final', 'i_data_prim_sintomas', 'i_desc_radf_res'])
        
        # Filtra apenas prováveis casos de dengue
        df = df[df['i_class_final'] == 'Caso Provável'].copy()
        dfs.append(df)
        
    df_all = pd.concat(dfs, ignore_index=True)
    print(f"  Total de casos prováveis carregados: {len(df_all)}")
    
    # Tratamento de datas
    df_all['date'] = pd.to_datetime(df_all['i_data_prim_sintomas'], errors='coerce')
    df_all = df_all.dropna(subset=['date']).copy()
    
    # Calcular o epi_sunday (domingo da semana epidemiológica correspondente)
    # df_all['date'].dt.weekday: Monday=0, Sunday=6
    # O domingo da semana é: date - ((weekday + 1) % 7) dias
    df_all['epi_sunday'] = df_all['date'] - pd.to_timedelta((df_all['date'].dt.weekday + 1) % 7, unit='D')
    # Normalizar hora para data pura e remover fuso horário
    df_all['epi_sunday'] = df_all['epi_sunday'].dt.normalize().dt.tz_localize(None)
    
    # Normalização das RAs
    df_all['RA'] = df_all['i_desc_radf_res'].apply(normalize_ra)
    
    # Filtrar 'Não Informado' e valores nulos nas RAs
    df_all = df_all[df_all['RA'].notna() & (df_all['RA'] != 'NAO INFORMADO')].copy()
    
    # Agrupar semanalmente por RA
    df_grouped = df_all.groupby(['epi_sunday', 'RA']).size().reset_index(name='cases')
    
    return df_grouped

def carregar_dados_demograficos(populacao_file):
    """Carrega dados populacionais das RAs para padronização."""
    print(">>> Carregando dados demográficos...")
    df_pop = pd.read_csv(populacao_file)
    df_pop['RA'] = df_pop['label'].apply(normalize_ra)
    return df_pop[['RA', 'value']].rename(columns={'value': 'populacao'})

def obter_dados_climaticos(cache_file='dados_clima_cache.csv'):
    """Obtém dados climáticos históricos do DF via Open-Meteo API ou lê do cache local."""
    if os.path.exists(cache_file):
        print(f">>> Carregando dados climáticos do cache: {cache_file}")
        df_weather = pd.read_csv(cache_file)
        df_weather['epi_sunday'] = pd.to_datetime(df_weather['epi_sunday']).dt.normalize().dt.tz_localize(None)
        return df_weather
        
    print(">>> Cache climático não encontrado. Baixando dados meteorológicos do Open-Meteo...")
    # Coordenadas do centro geográfico de Brasília (DF)
    lat, lon = -15.7801, -47.9292
    url = "https://archive-api.open-meteo.com/v1/archive"
    
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": "2016-10-01",  # Começar antes de 2017 para poder calcular lags climáticos de até 8 semanas
        "end_date": "2026-05-24",
        "daily": ["temperature_2m_max", "temperature_2m_min", "temperature_2m_mean", "precipitation_sum"],
        "timezone": "America/Sao_Paulo"
    }
    
    try:
        response = requests.get(url, params=params).json()
        daily = response['daily']
        
        df_daily = pd.DataFrame({
            'date': pd.to_datetime(daily['time']),
            'temp_max': daily['temperature_2m_max'],
            'temp_min': daily['temperature_2m_min'],
            'temp_mean': daily['temperature_2m_mean'],
            'precip_sum': daily['precipitation_sum']
        })
        
        # Agrupar os dados diários por semana epidemiológica (epi_sunday)
        df_daily['epi_sunday'] = df_daily['date'] - pd.to_timedelta((df_daily['date'].dt.weekday + 1) % 7, unit='D')
        df_daily['epi_sunday'] = df_daily['epi_sunday'].dt.normalize().dt.tz_localize(None)
        
        # Agregações semanais
        df_weekly = df_daily.groupby('epi_sunday').agg({
            'temp_max': 'mean',      # Média das temperaturas máximas da semana
            'temp_min': 'mean',      # Média das temperaturas mínimas da semana
            'temp_mean': 'mean',     # Média da temperatura média da semana
            'precip_sum': 'sum'      # Precipitação acumulada na semana
        }).reset_index()
        
        df_weekly.to_csv(cache_file, index=False)
        print(f"  Dados meteorológicos salvos com sucesso em {cache_file}!")
        return df_weekly
        
    except Exception as e:
        print(f"  [ERRO] Falha ao baixar dados de clima: {e}")
        raise e

def criar_grid_e_features(df_cases, df_weather, df_pop):
    """Une casos, clima e cria as features defasadas temporalmente (lags)."""
    print(">>> Combinando bases e criando engenharia de lags temporais...")
    
    # 1. Obter todas as datas e RAs únicas para fazer o grid completo (MultiIndex)
    all_sundays = pd.date_range(start=df_cases['epi_sunday'].min(), 
                                 end=df_cases['epi_sunday'].max(), 
                                 freq='W-SUN').normalize().tz_localize(None)
    
    # Filtrar apenas as RAs válidas presentes na tabela de população
    valid_ras = df_pop['RA'].unique()
    print(f"  Número de RAs válidas no Distrito Federal: {len(valid_ras)}")
    
    grid = pd.MultiIndex.from_product([all_sundays, valid_ras], names=['epi_sunday', 'RA']).to_frame().reset_index(drop=True)
    
    # 2. Mesclar os casos na grade completa e preencher valores ausentes com 0
    df_grid = pd.merge(grid, df_cases, on=['epi_sunday', 'RA'], how='left')
    df_grid['cases'] = df_grid['cases'].fillna(0).astype(int)
    
    # 3. Adicionar dados populacionais
    df_grid = pd.merge(df_grid, df_pop, on='RA', how='inner')
    
    # Calcular a taxa de incidência por 100 mil habitantes (excelente métrica adicional)
    df_grid['incidencia_100k'] = (df_grid['cases'] / df_grid['populacao']) * 100000
    
    # 4. Criar Lags Climáticos na tabela de clima antes do merge (otimização de velocidade)
    df_weather_features = df_weather.copy().sort_values('epi_sunday')
    
    # Engenharia de Lags Climáticos (Lags de 2 a 8 semanas)
    for lag in range(2, 9):
        df_weather_features[f'precip_lag_{lag}'] = df_weather_features['precip_sum'].shift(lag)
        df_weather_features[f'temp_mean_lag_{lag}'] = df_weather_features['temp_mean'].shift(lag)
        df_weather_features[f'temp_min_lag_{lag}'] = df_weather_features['temp_min'].shift(lag)
        df_weather_features[f'temp_max_lag_{lag}'] = df_weather_features['temp_max'].shift(lag)
        
    # 5. Mesclar o clima com lags no dataset principal
    df_full = pd.merge(df_grid, df_weather_features, on='epi_sunday', how='inner')
    
    # 6. Criar Lags de Casos (Autocorrelação) - Agrupado por RA para não cruzar dados!
    df_full = df_full.sort_values(['RA', 'epi_sunday'])
    
    # Engenharia de Lags de Casos (1 a 4 semanas)
    for lag in [1, 2, 3, 4]:
        df_full[f'cases_lag_{lag}'] = df_full.groupby('RA')['cases'].shift(lag)
        df_full[f'incid_lag_{lag}'] = df_full.groupby('RA')['incidencia_100k'].shift(lag)
        
    # 7. Adicionar variáveis sazonais/calendário
    df_full['week_of_year'] = df_full['epi_sunday'].dt.isocalendar().week.astype(int)
    df_full['month'] = df_full['epi_sunday'].dt.month.astype(int)
    
    # 8. Remover linhas com NaNs que surgiram da criação dos lags
    df_full = df_full.dropna().copy()
    
    return df_full

def treinar_e_avaliar(df):
    """Divide os dados temporalmente, treina Random Forest e XGBoost, e avalia o desempenho."""
    print(">>> Treinando e avaliando modelos Random Forest e XGBoost...")
    
    # Definir colunas de features
    # Excluímos as colunas de identificação e o target direto
    exclude_cols = ['epi_sunday', 'RA', 'cases', 'incidencia_100k', 'populacao', 'temp_max', 'temp_min', 'temp_mean', 'precip_sum']
    feature_cols = [c for c in df.columns if c not in exclude_cols and not c.startswith('incid_lag_')] # Usando apenas lags de casos reais
    
    # Converter a coluna RA em One-Hot Encoding para os modelos
    df_encoded = pd.get_dummies(df, columns=['RA'], drop_first=False)
    encoded_ra_cols = [c for c in df_encoded.columns if c.startswith('RA_')]
    
    # Atualizar lista de features para incluir as RAs codificadas
    feature_cols_all = feature_cols + encoded_ra_cols
    
    # Aplicar transformação logarítmica no target (casos) para estabilizar variância
    df_encoded['target_log'] = np.log1p(df_encoded['cases'])
    
    # Divisão temporal treino e teste
    # Treino: 2017 a 2024
    # Teste: 2025 a 2026 (out-of-sample)
    train_mask = df_encoded['epi_sunday'] < '2025-01-01'
    test_mask = df_encoded['epi_sunday'] >= '2025-01-01'
    
    X_train = df_encoded.loc[train_mask, feature_cols_all]
    y_train_log = df_encoded.loc[train_mask, 'target_log']
    y_train_real = df_encoded.loc[train_mask, 'cases']
    
    X_test = df_encoded.loc[test_mask, feature_cols_all]
    y_test_log = df_encoded.loc[test_mask, 'target_log']
    y_test_real = df_encoded.loc[test_mask, 'cases']
    
    print(f"  Registros no Treino (< 2025): {X_train.shape[0]}")
    print(f"  Registros no Teste (>= 2025): {X_test.shape[0]}")
    print(f"  Número total de features: {len(feature_cols_all)}")
    
    # 1. Random Forest Regressor
    print("  Treinando Random Forest...")
    rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1, max_depth=15)
    rf.fit(X_train, y_train_log)
    
    # Predições no log, convertidas de volta ao real
    rf_pred_log = rf.predict(X_test)
    rf_pred_real = np.expm1(rf_pred_log)
    rf_pred_real = np.clip(rf_pred_real, 0, None) # Evita previsões negativas
    
    # 2. XGBoost Regressor
    print("  Treinando XGBoost...")
    xgb = XGBRegressor(n_estimators=150, learning_rate=0.05, max_depth=6, random_state=42, n_jobs=-1)
    xgb.fit(X_train, y_train_log)
    
    xgb_pred_log = xgb.predict(X_test)
    xgb_pred_real = np.expm1(xgb_pred_log)
    xgb_pred_real = np.clip(xgb_pred_real, 0, None)
    
    # 3. Métricas Globais
    metrics = {}
    for name, pred in [('Random Forest', rf_pred_real), ('XGBoost', xgb_pred_real)]:
        mae = mean_absolute_error(y_test_real, pred)
        rmse = np.sqrt(mean_squared_error(y_test_real, pred))
        r2 = r2_score(y_test_real, pred)
        
        metrics[name] = {'MAE': mae, 'RMSE': rmse, 'R2': r2}
        print(f"\n  === Métricas Globais do {name} no Conjunto de Teste ===")
        print(f"    MAE  (Erro Médio Absoluto): {mae:.2f} casos")
        print(f"    RMSE (Erro Quadrático Médio): {rmse:.2f} casos")
        print(f"    R²   (Coeficiente de Det.): {r2:.4f}")
        
    # Anexar as previsões de volta no dataframe de teste original
    df_test_res = df.loc[test_mask].copy()
    df_test_res['pred_RF'] = rf_pred_real
    df_test_res['pred_XGB'] = xgb_pred_real
    
    return rf, xgb, df_test_res, feature_cols_all, metrics

def gerar_graficos(df_test_res, rf_model, xgb_model, feature_cols, top_ras=None):
    """Gera visualizações dos resultados reais contra previstos e importância das features."""
    print(">>> Gerando gráficos e análises visuais...")
    os.makedirs('resultados_graficos', exist_ok=True)
    
    # 1. Gráficos de Série Temporal de Previsão por RA
    if top_ras is None:
        # Pega as RAs com maior volume de casos no teste
        top_ras = df_test_res.groupby('RA')['cases'].sum().nlargest(4).index.tolist()
        
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    axes = axes.flatten()
    
    for i, ra in enumerate(top_ras):
        df_ra = df_test_res[df_test_res['RA'] == ra].sort_values('epi_sunday')
        ax = axes[i]
        
        ax.plot(df_ra['epi_sunday'], df_ra['cases'], label='Observado (Real)', color='#2c3e50', linewidth=2.5)
        ax.plot(df_ra['epi_sunday'], df_ra['pred_RF'], label='Previsão Random Forest', color='#e67e22', linestyle='--', linewidth=2)
        ax.plot(df_ra['epi_sunday'], df_ra['pred_XGB'], label='Previsão XGBoost', color='#27ae60', linestyle=':', linewidth=2.5)
        
        ax.set_title(f"Série Temporal de Dengue em 2025/2026: {ra}", fontsize=12, fontweight='bold')
        ax.set_xlabel("Semana Epidemiológica")
        ax.set_ylabel("Casos de Dengue")
        ax.legend(frameon=True, facecolor='white')
        ax.grid(True, alpha=0.3)
        
    plt.tight_layout()
    plt.savefig('resultados_graficos/comparativo_series_temporais.png', dpi=300)
    plt.close()
    print("  Salvo: resultados_graficos/comparativo_series_temporais.png")
    
    # 2. Importância das Features (Top 15 mais importantes no XGBoost)
    importances = xgb_model.feature_importances_
    # Filtrar apenas as features principais (remover One-Hot das RAs para ver o impacto real das variáveis)
    main_features_indices = [i for i, f in enumerate(feature_cols) if not f.startswith('RA_')]
    main_features = [feature_cols[i] for i in main_features_indices]
    main_importances = importances[main_features_indices]
    # Re-normalizar importâncias
    main_importances = main_importances / main_importances.sum()
    
    df_imp = pd.DataFrame({
        'Feature': main_features,
        'Importance': main_importances
    }).sort_values('Importance', ascending=True).tail(15)
    
    plt.figure(figsize=(10, 6.5))
    colors = plt.cm.viridis(np.linspace(0.4, 0.8, len(df_imp)))
    plt.barh(df_imp['Feature'], df_imp['Importance'], color=colors, edgecolor='gray', height=0.6)
    plt.title('Importância das Variáveis no Modelo Preditivo (XGBoost)', fontsize=12, fontweight='bold')
    plt.xlabel('Importância Relativa')
    plt.grid(True, axis='x', alpha=0.3)
    plt.tight_layout()
    plt.savefig('resultados_graficos/importancia_features_xgb.png', dpi=300)
    plt.close()
    print("  Salvo: resultados_graficos/importancia_features_xgb.png")
    
    # 3. Gráfico comparativo de dispersão (Scatter Plot) Real vs. Predito
    plt.figure(figsize=(7, 6.5))
    plt.scatter(df_test_res['cases'], df_test_res['pred_XGB'], alpha=0.4, color='#2980b9', edgecolors='none', label='XGBoost')
    plt.scatter(df_test_res['cases'], df_test_res['pred_RF'], alpha=0.3, color='#e67e22', edgecolors='none', label='Random Forest')
    
    max_val = max(df_test_res['cases'].max(), df_test_res['pred_XGB'].max())
    plt.plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='Previsão Perfeita (y = x)')
    
    plt.title('Comparativo de Dispersão: Observado vs Previsto', fontsize=12, fontweight='bold')
    plt.xlabel('Casos Reais')
    plt.ylabel('Casos Previstos')
    plt.xlim(0, max_val)
    plt.ylim(0, max_val)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('resultados_graficos/dispersao_predicao.png', dpi=300)
    plt.close()
    print("  Salvo: resultados_graficos/dispersao_predicao.png")

if __name__ == '__main__':
    # Diretórios e caminhos
    info_saude_dir = 'info-saude'
    populacao_file = 'populacao.csv'
    
    # 1. Carregar casos do info-saude
    df_cases = carregar_e_limpar_dados(info_saude_dir)
    
    # 2. Carregar dados populacionais
    df_pop = carregar_dados_demograficos(populacao_file)
    
    # 3. Obter dados de clima (Open-Meteo)
    df_weather = obter_dados_climaticos()
    
    # 4. Criar grid completo e lags
    df_dataset = criar_grid_e_features(df_cases, df_weather, df_pop)
    
    # 5. Treinar modelos e avaliar
    rf_model, xgb_model, df_test_res, feature_cols, metrics = treinar_e_avaliar(df_dataset)
    
    # 6. Salvar previsões agregadas por RA para análise posterior
    df_test_res.to_csv('previsoes_finais_radf.csv', index=False)
    print(">>> Salvo arquivo de previsões finais: previsoes_finais_radf.csv")
    
    # 7. Gerar gráficos e análises visuais
    # Foco nas RAs mais populosas/afetadas
    top_ras = ['CEILÂNDIA', 'SAMAMBAIA', 'PLANALTINA', 'PLANO PILOTO']
    gerar_graficos(df_test_res, rf_model, xgb_model, feature_cols, top_ras)
    
    print("\n>>> PIPELINE EXECUTADO COM SUCESSO! Modelagem concluída de forma robusta.")
