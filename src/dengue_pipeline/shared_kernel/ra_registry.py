import unicodedata
from pathlib import Path
import pandas as pd

# Caminho base para acessar arquivos de dados
BASE_DIR = Path(__file__).resolve().parents[3]

def remover_acentos_maiusculo(valor) -> str | None:
    """
    Remove acentos e converte para maiúsculo, removendo espaços nas bordas.
    
    Parâmetros:
        valor: Valor de entrada (esperado string).
        
    Retorna:
        String normalizada ou None caso não seja string.
    """
    if not isinstance(valor, str):
        return None
    valor = "".join(
        c for c in unicodedata.normalize("NFD", valor)
        if unicodedata.category(c) != "Mn"
    )
    return valor.upper().strip()

def carregar_historico_populacao() -> pd.DataFrame:
    """
    Carrega o histórico populacional do arquivo dados_processados/populacao_historica.csv.
    
    Retorna:
        DataFrame com o histórico de populações por RA e ano.
    """
    caminho_csv = BASE_DIR / "dados_processados" / "populacao_historica.csv"
    if not caminho_csv.exists():
        raise FileNotFoundError(f"Arquivo dados_processados/populacao_historica.csv não encontrado em {caminho_csv}")
    pop = pd.read_csv(caminho_csv)
    pop["RA"] = pop["RA"].astype(str)
    pop["ra_key"] = pop["RA"].map(remover_acentos_maiusculo)
    return pop

def busca_ra_canonica() -> dict[str, str]:
    """
    Monta um mapeamento das chaves normalizadas (sem acentos) para os nomes canônicos das RAs.
    Implementa um fallback estático robusto caso o arquivo CSV esteja indisponível.
    
    Retorna:
        Dicionário com o mapeamento chave_normalizada -> nome_canonico.
    """
    lookup = {}
    try:
        pop = carregar_historico_populacao()
        lookup = dict(zip(pop["ra_key"], pop["RA"]))
    except Exception as e:
        import warnings
        warnings.warn(
            f"Falha ao carregar populacao_historica.csv em busca_ra_canonica: {e}. Usando fallback estatico.",
            UserWarning
        )
        # Fallback estático com nomes normalizados sem acento
        static_ras = [
            "AGUA QUENTE", "ARAPOANGA", "ARNIQUEIRA", "BRAZLANDIA", "CANDANGOLANDIA",
            "CEILANDIA", "CRUZEIRO", "FERCAL", "GAMA", "GUARA", "ITAPOA",
            "JARDIM BOTANICO", "LAGO NORTE", "LAGO SUL", "NUCLEO BANDEIRANTE",
            "PARANOA", "PARK WAY", "PLANALTINA", "PLANO PILOTO", "RECANTO DAS EMAS",
            "RIACHO FUNDO", "RIACHO FUNDO II", "SAMAMBAIA", "SANTA MARIA", "SCIA",
            "SIA", "SOBRADINHO", "SOBRADINHO II", "SOL NASCENTE E POR DO SOL",
            "SUDOESTE/OCTOGONAL", "SAO SEBASTIAO", "TAGUATINGA", "VARJAO",
            "VICENTE PIRES", "AGUAS CLARAS"
        ]
        lookup = {ra: ra for ra in static_ras}
    
    # Aliases comuns de normalização
    aliases = {
        "SCIA (ESTRUTURAL)": "SCIA",
        "SOL NASCENTE/POR DO SOL": "SOL NASCENTE E POR DO SOL",
        "SOL NASCENTE/POR DO SOL RES": "SOL NASCENTE E POR DO SOL",
        "SAO SEBASTIAO": "SAO SEBASTIAO",
        "CEILANDIA": "CEILANDIA",
        "BRAZLANDIA": "BRAZLANDIA",
        "GUARA": "GUARA",
        "PARANOA": "PARANOA",
        "ITAPOA": "ITAPOA",
        "AGUAS CLARAS": "AGUAS CLARAS",
        "JARDIM BOTANICO": "JARDIM BOTANICO",
        "NUCLEO BANDEIRANTE": "NUCLEO BANDEIRANTE",
        "CANDANGOLANDIA": "CANDANGOLANDIA",
    }
    
    # Garantir que todos os aliases apontem para as chaves normalizadas no lookup
    for alias, canonical_key in aliases.items():
        key_alias = remover_acentos_maiusculo(alias)
        key_canonical = remover_acentos_maiusculo(canonical_key)
        if key_canonical in lookup:
            lookup[key_alias] = lookup[key_canonical]
        else:
            lookup[key_alias] = key_canonical
            
    return lookup

def normalizar_ra(valor, lookup: dict[str, str] | None = None) -> str | None:
    """
    Padroniza os nomes das Regiões Administrativas para maiúsculo e sem acento.
    Mapeia aliases e resolve variações de digitação ou acentuação.
    
    Parâmetros:
        valor: String contendo o nome da RA.
        lookup: Dicionário opcional pré-carregado de RAs canônicas.
        
    Retorna:
        Nome da RA padronizado ou None caso seja inválido ou "NAO INFORMADO".
    """
    chave = remover_acentos_maiusculo(valor)
    if chave is None or chave == "NAO INFORMADO":
        return None
    lookup = lookup or busca_ra_canonica()
    
    res = lookup.get(chave, chave)
    return remover_acentos_maiusculo(res) if res else None
