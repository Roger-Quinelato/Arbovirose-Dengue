import requests
import sys

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

response = requests.get(url, params=params)

if response.status_code == 200:
    from pathlib import Path
    BASE_DIR = Path(__file__).resolve().parents[1]
    filename = str(BASE_DIR / "dados_clima_nasa" / "POWER_Point_Daily_20060101_20260524_015d79S_047d88W_LST.csv")
    with open(filename, "wb") as f:
        f.write(response.content)
    print(f"Data successfully saved to {filename}")
else:
    print(f"Failed to fetch data: {response.status_code}")
    print(response.text)
    sys.exit(1)
