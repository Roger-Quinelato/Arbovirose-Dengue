import pandas as pd

def domingo_epidemiologico(series: pd.Series) -> pd.Series:
    """
    Calcula o domingo da semana epidemiológica correspondente para uma série de datas.
    
    Parâmetros:
        series: Pandas Series contendo as datas de sintomas ou registros.
        
    Retorna:
        Pandas Series com os domingos correspondentes normalizados e sem timezone.
        
    Premissas críticas:
        Assume que as datas de entrada podem ser convertidas pelo pd.to_datetime.
        A semana epidemiológica inicia no domingo.
    """
    dates = pd.to_datetime(series, errors="coerce", utc=True)
    sundays = dates - pd.to_timedelta((dates.dt.weekday + 1) % 7, unit="D")
    return sundays.dt.tz_localize(None).dt.normalize()
