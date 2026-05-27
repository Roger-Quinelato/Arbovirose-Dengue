# Relatorio final - Plano Prompts Opus

## Decisao de features

- Config vencedora conservadora: `lag-only` / `RF`.
- Melhor config observada: `lag-only` / `RF`.
- Ganho complexo aceito pelo criterio? `False`.
- Motivo: Nenhuma config complexa superou o baseline; lag-only vence por conservadorismo.

## Respostas do Prompt 6

1. A config que agregou valor real demonstravel foi considerada apenas se superou lag-only por delta R2 > 0.05 ou RMSE melhor em >70% das RAs.
2. Resultado: Nenhuma config complexa superou o baseline; lag-only vence por conservadorismo.
3. RA com maior RMSE na config vencedora: `SANTA MARIA` (RMSE=3.680). Hipotese: RAs com picos localizados e baixa base semanal sao mais dificeis para modelos globais.
4. O pipeline fica mais defensavel para nowcasting operacional semanal. Para forecast fechado, use o resultado recursivo como referencia; a incerteza cresce rapidamente sem casos reais recentes.
5. Antes da hierarquia nacional, a compatibilidade SINAN vs info-saude precisa passar pelos criterios de correlacao e diferenca media documentados em validacao-sinan-infosaude.md.

## Ablation

| config | modelo | n_features | r2_df | mae_df | rmse_df | r2_media_ras | mae_media_ras | rmse_media_ras | delta_r2_df_vs_prev | rmse_improved_pct_vs_prev | passes_acceptance_vs_prev |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lag-only | RF | 4 | 0.6555 | 10.4689 | 13.8331 | -0.1112 | 0.9196 | 1.2096 | nan | nan | False |
| lag-only | XGB | 4 | 0.6090 | 11.5799 | 14.7357 | 0.0651 | 0.8396 | 1.1090 | nan | nan | False |
| lag+clima | RF | 29 | 0.6483 | 11.0477 | 13.9757 | -0.0071 | 0.8682 | 1.1490 | -0.0071 | 0.4286 | False |
| lag+clima | XGB | 29 | 0.6007 | 11.5353 | 14.8920 | 0.0316 | 0.8664 | 1.1410 | -0.0083 | 0.1714 | False |
| lag+clima+RA | RF | 64 | 0.6562 | 11.0395 | 13.8190 | -0.0027 | 0.8663 | 1.1343 | 0.0078 | 0.7429 | True |
| lag+clima+RA | XGB | 64 | 0.5742 | 11.8457 | 15.3786 | 0.0278 | 0.8713 | 1.1518 | -0.0265 | 0.6857 | False |
| lag+clima+RA+incid-target | RF | 65 | 0.5724 | 12.1370 | 15.4111 | 0.0312 | 0.8811 | 1.1310 | -0.0838 | 0.6000 | False |
| lag+clima+RA+incid-target | XGB | 65 | 0.5540 | 11.6172 | 15.7385 | 0.0325 | 0.8893 | 1.1546 | -0.0202 | 0.4857 | False |

## Modelos tunados

| modelo | r2_df | mae_df | rmse_df | mape_df | smape_df | hit_rate_picos | r2_media_ras | mae_media_ras | rmse_media_ras |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RF_tunado | 0.6554 | 10.6490 | 13.8342 | 32.2710 | 22.3958 | 0.5714 | -0.1567 | 0.9385 | 1.2438 |
| XGB_tunado | 0.6117 | 11.6264 | 14.6851 | 32.9890 | 24.4066 | 0.5714 | 0.0555 | 0.8457 | 1.1192 |
