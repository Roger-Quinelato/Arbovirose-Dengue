import pandas as pd
# pyrefly: ignore [missing-import]
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

def main():
    print(">>> Iniciando a geração da base histórica de população por RA (2017-2026)...")
    
    # 1. Carregar a base de população de 2024 (PDAD-A)
    pop_2024_file = BASE_DIR / 'dados_processados' / 'populacao.csv'
    try:
        df_base = pd.read_csv(pop_2024_file)
    except FileNotFoundError:
        print(f"[ERRO] Arquivo {pop_2024_file} não encontrado no diretório atual.")
        return
        
    # Padronizar nomes de RAs para consistência
    df_base = df_base.rename(columns={'label': 'RA', 'value': 'populacao_2024'})
    
    # 2. Definir taxas de crescimento anual oficial da Codeplan (conforme o PDF)
    # Taxas: 1.20% ao ano para >= 2020 | 1.39% ao ano para < 2020
    growth_rate_ge_2020 = 0.0120
    growth_rate_lt_2020 = 0.0139
    
    records = []
    
    # 3. Calcular a população de cada RA para cada ano entre 2017 e 2026
    for idx, row in df_base.iterrows():
        ra = row['RA']
        p_2024 = row['populacao_2024']
        
        # Dicionário temporário para guardar as populações calculadas por ano
        pop_by_year = {}
        pop_by_year[2024] = p_2024
        
        # Retro-projeção de 2023 até 2020 (taxa de 1.20% ao ano)
        for year in [2023, 2022, 2021, 2020]:
            pop_by_year[year] = pop_by_year[year + 1] / (1 + growth_rate_ge_2020)
            
        # Retro-projeção de 2019 até 2017 (taxa de 1.39% ao ano)
        for year in [2019, 2018, 2017]:
            pop_by_year[year] = pop_by_year[year + 1] / (1 + growth_rate_lt_2020)
            
        # Projeção de 2025 até 2026 (taxa de 1.20% ao ano)
        for year in [2025, 2026]:
            pop_by_year[year] = pop_by_year[year - 1] * (1 + growth_rate_ge_2020)
            
        # Salvar os registros formatados com arredondamento para inteiros
        for year, pop_val in pop_by_year.items():
            records.append({
                'RA': ra,
                'ano': year,
                'populacao': int(round(pop_val))
            })
            
    # 4. Criar o Dataframe resultante
    df_hist = pd.DataFrame(records)
    
    # Ordenar por RA e por ano para legibilidade
    df_hist = df_hist.sort_values(by=['RA', 'ano']).reset_index(drop=True)
    
    # 5. Salvar em populacao_historica.csv
    output_file = BASE_DIR / 'dados_processados' / 'populacao_historica.csv'
    df_hist.to_csv(output_file, index=False)
    print(f"\n>>> Sucesso! Nova base de dados criada: {output_file}")
    
    # 6. Exibir resumo consolidado por ano para verificação demográfica
    print("\n=== Resumo Consolidado do DF por Ano ===")
    resumo = df_hist.groupby('ano')['populacao'].sum().reset_index()
    resumo['crescimento_anual_%'] = resumo['populacao'].pct_change() * 100
    
    for idx, r in resumo.iterrows():
        cresc_str = f" ({r['crescimento_anual_%']:.2f}%)" if idx > 0 else ""
        print(f"  Ano {int(r['ano'])}: {int(r['populacao']):,} habitantes{cresc_str}")

if __name__ == '__main__':
    main()
