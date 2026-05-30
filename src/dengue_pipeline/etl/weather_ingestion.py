import pandas as pd
from pathlib import Path

from dengue_pipeline.config import BASE_DIR

def carregar_cache_climatico() -> pd.DataFrame:
    """
    Carrega dados meteorológicos consolidados cruzando cache local do Open-Meteo com dados históricos da InfoDengue.
    Realiza interpolação linear para colunas de umidade faltantes.
    
    Retorna:
        pd.DataFrame: DataFrame de clima semanal indexado por epi_sunday.
        
    Premissas críticas:
        Espera a existência de dados_processados/dados_clima_cache.csv no projeto
        e InfoDengue_2016-2026.csv na subpasta InfoDengue/.
    """
    caminho_clima_cache = BASE_DIR / "dados_processados" / "dados_clima_cache.csv"
    if not caminho_clima_cache.exists():
        raise FileNotFoundError(f"Arquivo de cache climático não encontrado em {caminho_clima_cache}")
        
    weather = pd.read_csv(caminho_clima_cache)
    weather["epi_sunday"] = pd.to_datetime(weather["epi_sunday"]).dt.normalize()

    info_file = BASE_DIR / "InfoDengue" / "InfoDengue_2016-2026.csv"
    if not info_file.exists():
        raise FileNotFoundError(f"Arquivo InfoDengue não encontrado em {info_file}")
        
    infod = pd.read_csv(info_file)
    infod["epi_sunday"] = pd.to_datetime(infod["data_iniSE"]).dt.normalize()
    humidity_cols = ["epi_sunday", "umidmed", "umidmin", "umidmax"]
    infod = infod[humidity_cols].drop_duplicates("epi_sunday").sort_values("epi_sunday")
    
    climate = weather.merge(infod, on="epi_sunday", how="left").sort_values("epi_sunday")
    for col in ["umidmed", "umidmin", "umidmax"]:
        # Interpolação apenas para frente (forward): nunca usa dados futuros
        # para preencher lacunas do passado — evita data leakage temporal.
        climate[col] = climate[col].interpolate(method="linear", limit_direction="forward")
        # Borda inicial: se as primeiras semanas tiverem NaN, preenche com
        # o primeiro valor válido disponível (backward fill limitado a 4 semanas).
        climate[col] = climate[col].bfill(limit=4)
        
    # Validação de cobertura: não deve haver semanas sem temperatura principal
    colunas_obrigatorias = ["temp_mean", "precip_sum"]
    for col in colunas_obrigatorias:
        if col in climate.columns:
            n_nulos = climate[col].isna().sum()
            if n_nulos > 0:
                semanas = climate.loc[climate[col].isna(), "epi_sunday"].tolist()
                raise ValueError(
                    f"ETL: coluna '{col}' tem {n_nulos} semana(s) sem cobertura climática "
                    f"após interpolação. Primeiras afetadas: {semanas[:5]}. "
                    "Execute fetch_nasa_power.py para atualizar o cache climático."
                )
                
    return climate
