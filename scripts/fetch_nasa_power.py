import requests
import sys
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

url = "https://power.larc.nasa.gov/api/temporal/daily/point"

params = {
    "parameters": "PRECTOTCORR,T2M,T2M_MAX,T2M_MIN,RH2M",
    "community": "AG",
    "longitude": -47.8825,
    "latitude": -15.7942,
    "start": "20060101",
    "end": "20260524",
    "format": "CSV"
}

# Configura tentativas de reenvio automáticas (Retries) resilientes
session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504],
    raise_on_status=False
)
session.mount("https://", HTTPAdapter(max_retries=retries))

try:
    print(">>> Ingestando dados climáticos da NASA POWER API...")
    # Timeout explícito de 15 segundos para evitar travamentos infinitos
    response = session.get(url, params=params, timeout=15)
    
    if response.status_code == 200:
        BASE_DIR = Path(__file__).resolve().parents[1]
        filename = str(BASE_DIR / "dados_clima_nasa" / "POWER_Point_Daily_20060101_20260524_015d79S_047d88W_LST.csv")
        with open(filename, "wb") as f:
            f.write(response.content)
        print(f"✓ Dados climáticos salvos com sucesso em: {filename}")
    else:
        print(f"[ERRO] Falha ao consultar a API. Código HTTP: {response.status_code}")
        print(response.text)
        sys.exit(1)
except requests.exceptions.Timeout:
    print("[ERRO CRÍTICO] Tempo limite de conexão esgotado (Timeout de 15s). A API da NASA POWER não respondeu.")
    sys.exit(1)
except requests.exceptions.RequestException as e:
    print(f"[ERRO CRÍTICO] Falha de conexão ou rede na API da NASA POWER: {e}")
    sys.exit(1)
