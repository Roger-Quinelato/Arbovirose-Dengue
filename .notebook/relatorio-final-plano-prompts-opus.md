# Relatorio final - Plano Prompts Opus

## Decisao de features

- Config vencedora conservadora: `lag-only` / `RF`.
- Melhor config observada: `lag+clima` / `RF`.
- Ganho complexo aceito pelo criterio? `False`.
- Motivo: Nenhuma config complexa superou o baseline; lag-only vence por conservadorismo.

## Respostas do Prompt 6

1. A config que agregou valor real demonstravel foi considerada apenas se superou lag-only por delta R2 > 0.05 ou RMSE melhor em >70% das RAs.
2. Resultado: Nenhuma config complexa superou o baseline; lag-only vence por conservadorismo.
3. RA com maior RMSE na config vencedora: `SANTA MARIA` (RMSE=3.806). Hipotese: RAs com picos localizados e baixa base semanal sao mais dificeis para modelos globais.
4. O pipeline fica mais defensavel para nowcasting operacional semanal. Para forecast fechado, use o resultado recursivo como referencia; a incerteza cresce rapidamente sem casos reais recentes.
5. Antes da hierarquia nacional, a compatibilidade SINAN vs info-saude precisa passar pelos criterios de correlacao e diferenca media documentados em validacao-sinan-infosaude.md.

## Ablation

| config | modelo | n_features | r2_df | mae_df | rmse_df | mape_df | smape_df | hit_rate_picos | r2_media_ras | mae_media_ras | rmse_media_ras | delta_r2_df_vs_prev | rmse_improved_pct_vs_prev | passes_acceptance_vs_prev |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lag-only | RF | 7 | 0.6627 | 10.4334 | 13.6869 | 32.1803 | 22.0727 | 0.6429 | -0.1034 | 0.9128 | 1.2100 | nan | nan | False |
| lag-only | XGB | 7 | 0.6190 | 11.4685 | 14.5459 | 32.7363 | 23.9522 | 0.5000 | 0.0608 | 0.8370 | 1.1096 | nan | nan | False |
| lag+clima | RF | 32 | 0.6642 | 10.7729 | 13.6574 | 37.0168 | 23.6144 | 0.6429 | -0.0317 | 0.8681 | 1.1499 | 0.0015 | 0.4571 | False |
| lag+clima | XGB | 32 | 0.5848 | 11.6937 | 15.1851 | 42.0364 | 25.5945 | 0.6429 | 0.0231 | 0.8655 | 1.1404 | -0.0342 | 0.2000 | False |
| lag+clima+RA | RF | 67 | 0.6618 | 10.6831 | 13.7048 | 37.0747 | 23.1917 | 0.8571 | -0.0004 | 0.8696 | 1.1412 | -0.0023 | 0.7429 | True |
| lag+clima+RA | XGB | 67 | 0.5824 | 11.6931 | 15.2289 | 43.8547 | 25.2981 | 0.6429 | 0.0295 | 0.8711 | 1.1463 | -0.0024 | 0.3143 | False |
| lag+clima+RA+incid-target | RF | 68 | 0.5343 | 12.4594 | 16.0825 | 44.8828 | 23.9714 | 0.9286 | 0.0080 | 0.8943 | 1.1497 | -0.1275 | 0.5714 | False |
| lag+clima+RA+incid-target | XGB | 68 | 0.5106 | 11.8393 | 16.4865 | 45.6122 | 23.6116 | 0.7143 | 0.0318 | 0.8828 | 1.1519 | -0.0718 | 0.4857 | False |

## Modelos tunados

| modelo | r2_df | mae_df | rmse_df | mape_df | smape_df | hit_rate_picos | r2_media_ras | mae_media_ras | rmse_media_ras |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RF_tunado | 0.6554 | 10.6490 | 13.8342 | 32.2710 | 22.3958 | 0.5714 | -0.1567 | 0.9385 | 1.2438 |
| XGB_tunado | 0.6117 | 11.6264 | 14.6851 | 32.9890 | 24.4066 | 0.5714 | 0.0555 | 0.8457 | 1.1192 |
