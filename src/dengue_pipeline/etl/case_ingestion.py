import pandas as pd
from pathlib import Path
from dengue_pipeline.shared_kernel import sanitizar_texto, calcular_semana_epidemiologica

BASE_DIR = Path(__file__).resolve().parents[3]
DIRETORIO_INFO_SAUDE = BASE_DIR / "info-saude"

COLUNAS_INFO_SAUDE = [
    "i_class_final",
    "i_desc_classificacao",
    "i_desc_uf_res",
    "i_desc_radf_res",
    "i_data_prim_sintomas",
]

FAMILIA_DENGUE = {
    "DENGUE",
    "DENGUE COM SINAIS DE ALARME",
    "DENGUE GRAVE",
}

def ingestar_dados_saude_local() -> pd.DataFrame:
    """
    Lê os arquivos CSV do diretório de vigilância de saúde, consolidando-os.
    Aplica normalização de strings e calcula o domingo epidemiológico para cada caso.
    
    Retorna:
        pd.DataFrame: DataFrame contendo todos os casos e colunas auxiliares de data e RA normalizadas.
        
    Premissas críticas:
        Os arquivos no diretório info-saude devem ser separados por ';' e ter codificação UTF-8.
    """
    if not DIRETORIO_INFO_SAUDE.exists():
        raise FileNotFoundError(f"Diretório de dados info-saude não encontrado: {DIRETORIO_INFO_SAUDE}")
        
    frames = []
    for file in sorted(DIRETORIO_INFO_SAUDE.glob("*.csv")):
        try:
            df = pd.read_csv(file, sep=";", encoding="utf-8", usecols=COLUNAS_INFO_SAUDE)
        except UnicodeDecodeError:
            print(f"  [AVISO] Encoding UTF-8 falhou em {file.name}. Tentando latin-1...")
            df = pd.read_csv(file, sep=";", encoding="latin-1", usecols=COLUNAS_INFO_SAUDE)
        df["source_file"] = file.name
        frames.append(df)
        
    if not frames:
        raise FileNotFoundError(f"Nenhum arquivo CSV encontrado em {DIRETORIO_INFO_SAUDE}")
        
    df_all = pd.concat(frames, ignore_index=True)
    df_all["class_norm"] = df_all["i_class_final"].map(sanitizar_texto)
    df_all["disease_norm"] = df_all["i_desc_classificacao"].map(sanitizar_texto)
    df_all["uf_norm"] = df_all["i_desc_uf_res"].map(sanitizar_texto)
    df_all["ra_norm_raw"] = df_all["i_desc_radf_res"].map(sanitizar_texto)
    df_all["date"] = pd.to_datetime(df_all["i_data_prim_sintomas"], errors="coerce", utc=True)
    df_all["ano"] = df_all["date"].dt.year
    df_all["epi_sunday"] = calcular_semana_epidemiologica(df_all["i_data_prim_sintomas"])
    return df_all

def mascaras_target(df: pd.DataFrame) -> dict[str, pd.Series]:
    """
    Gera máscaras booleanas para diferentes definições de filtragem epidemiológica do target.
    
    Parâmetros:
        df (pd.DataFrame): DataFrame contendo os casos de dengue.
        
    Retorna:
        dict[str, pd.Series]: Dicionário indexado pelos nomes das configurações contendo a série booleana correspondente.
    """
    simples = df["class_norm"].eq("CASO PROVAVEL")
    dengue_exata = simples & df["disease_norm"].eq("DENGUE")
    familia_dengue = simples & df["disease_norm"].isin(FAMILIA_DENGUE)
    return {
        "simples_caso_provavel": simples,
        "duplo_dengue_exata": dengue_exata,
        "familia_dengue": familia_dengue,
    }
