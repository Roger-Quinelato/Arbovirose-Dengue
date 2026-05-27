from dengue_pipeline.reporting.report_writer import (
    formatar_tabela_markdown,
    analisar_alvo_epidemiologico,
    gerar_visualizacoes_eda,
    gerar_graficos_ablacao,
    gerar_painel_final,
    validar_consistencia_fontes
)

# Aliases para retrocompatibilidade
df_para_markdown = formatar_tabela_markdown
executar_analise_target = analisar_alvo_epidemiologico
gerar_graficos_eda = gerar_visualizacoes_eda
gerar_visualizacoes_finais = gerar_painel_final
validar_sinan_infosaude = validar_consistencia_fontes
