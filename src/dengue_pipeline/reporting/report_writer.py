import json
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path
import shutil

# Configurar matplotlib para modo não-interativo antes de carregar pyplot
matplotlib.use("Agg")

from dengue_pipeline.shared_kernel import sanitizar_texto, calcular_semana_epidemiologica
from dengue_pipeline.etl import ingestar_dados_saude_local, mascaras_target
from dengue_pipeline.etl.case_ingestion import FAMILIA_DENGUE
from dengue_pipeline.modeling import calcular_r2_robusto, calcular_erro_quadratico_medio, consolidar_metricas_performance

import logging
logger = logging.getLogger(__name__)
from dengue_pipeline.config import (
    BASE_DIR,
    GRAFICOS_DIR as OUTPUT_DIR,
    NOTEBOOK_DIR,
    ABLATION_CSV,
    ABLATION_RA_CSV,
    ABLATION_PRED_CSV,
)

DADOS_GOV_DIR = BASE_DIR / "dados-gov"
FINAL_REPORT_MD = NOTEBOOK_DIR / "relatorio_final_execucao.md"
SINAN_REPORT_MD = NOTEBOOK_DIR / "validacao_consistencia_fontes.md"

def formatar_tabela_markdown(df: pd.DataFrame) -> str:
    """
    Converte um DataFrame do pandas em uma string formatada como tabela Markdown.
    
    Parâmetros:
        df (pd.DataFrame): DataFrame de entrada.
        
    Retorna:
        str: Representação em Markdown do DataFrame.
    """
    columns = [str(c) for c in df.columns]
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    rows = []
    for _, row in df.iterrows():
        values = []
        for value in row.tolist():
            if isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join([header, separator] + rows)

def analisar_alvo_epidemiologico(run_dir: Path | None = None) -> tuple[pd.DataFrame, dict]:
    """
    Executa a análise de definição do target epidemiológico para a modelagem.
    Avalia a frequência e proporções das classificações e tipos de dengue e plota gráficos comparativos.
    
    Retorna:
        tuple: (df_resumo_anual, dict_resumo_decisao)
    """
    logger.info(">>> P0/P1: formalizando target epidemiologico...")
    df = ingestar_dados_saude_local()
    masks = mascaras_target(df)
    
    class_counts = df["i_class_final"].value_counts(dropna=False).rename_axis("classificacao_final").reset_index(name="casos")
    disease_counts = df["i_desc_classificacao"].value_counts(dropna=False).rename_axis("classificacao_doenca").reset_index(name="casos")
    combo_counts = df.groupby(["i_class_final", "i_desc_classificacao"]).size().reset_index(name="casos").sort_values("casos", ascending=False).head(20)
    
    provavel_counts = {
        "total_provavel": int(masks["simples_caso_provavel"].sum()),
        "dengue_exata": int(masks["duplo_dengue_exata"].sum()),
        "familia_dengue": int(masks["familia_dengue"].sum()),
    }
    
    # 3. Análise Anual comparativa dos filtros
    annual = df.groupby(df["date"].dt.year).agg(
        total_casos=("class_norm", "count"),
        provavel=("class_norm", lambda s: s.eq("CASO PROVAVEL").sum()),
        dengue_exata=("disease_norm", lambda s: (s.eq("DENGUE") & df.loc[s.index, "class_norm"].eq("CASO PROVAVEL")).sum()),
        familia_dengue=("disease_norm", lambda s: (s.isin(FAMILIA_DENGUE) & df.loc[s.index, "class_norm"].eq("CASO PROVAVEL")).sum()),
    ).reset_index().rename(columns={"date": "ano"})
    
    # 4. Plotagem comparativa
    weekly_all = []
    for name, mask in masks.items():
        w = df[mask].groupby("epi_sunday").size().reset_index(name="casos")
        w["target"] = name
        weekly_all.append(w)
    weekly_all = pd.concat(weekly_all, ignore_index=True)
    weekly_all["epi_sunday"] = pd.to_datetime(weekly_all["epi_sunday"])
    
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    simple_w = weekly_all[weekly_all["target"] == "simples_caso_provavel"]
    exact_w = weekly_all[weekly_all["target"] == "duplo_dengue_exata"]
    family_w = weekly_all[weekly_all["target"] == "familia_dengue"]
    
    axes[0].plot(simple_w["epi_sunday"], simple_w["casos"], label="Caso provavel", linewidth=1.8)
    axes[0].plot(exact_w["epi_sunday"], exact_w["casos"], label="Caso provavel + Dengue", linewidth=1.5)
    axes[0].set_title("Filtro simples vs filtro duplo exato")
    axes[0].legend()
    axes[0].grid(alpha=0.25)
    
    axes[1].plot(simple_w["epi_sunday"], simple_w["casos"], label="Caso provavel", linewidth=1.8)
    axes[1].plot(family_w["epi_sunday"], family_w["casos"], label="Familia dengue", linewidth=1.5)
    axes[1].set_title("Filtro simples vs familia dengue")
    axes[1].legend()
    axes[1].grid(alpha=0.25)
    
    for ax in axes:
        ax.set_xlabel("Semana epidemiologica")
        ax.set_ylabel("Casos")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "target_comparativo.png", dpi=220)
    plt.close()
    if run_dir is not None:
        import shutil
        shutil.copy2(OUTPUT_DIR / "target_comparativo.png", run_dir / "target_comparativo.png")

    summary = {
        "class_counts": class_counts.to_dict(orient="records"),
        "disease_counts": disease_counts.to_dict(orient="records"),
        "combo_top20": combo_counts.to_dict(orient="records"),
        "provavel_counts": provavel_counts,
        "target_name": "familia_dengue",
        "target_filter": (
            "i_class_final == 'Caso Provavel' AND i_desc_classificacao in "
            "['Dengue', 'Dengue com sinais de alarme', 'Dengue grave']"
        ),
        "recommendation": (
            "Usar familia_dengue: remove Inconclusivo/Nao Informado, preserva dengue grave "
            "e dengue com sinais de alarme, e fica semanticamente mais perto da familia de codigos "
            "de dengue observada no SINAN."
        ),
    }
    
    class_counts.to_csv(BASE_DIR / "dados_processados" / "target_class_final_counts.csv", index=False)
    disease_counts.to_csv(BASE_DIR / "dados_processados" / "target_desc_classificacao_counts.csv", index=False)
    combo_counts.to_csv(BASE_DIR / "dados_processados" / "target_combinacoes_top20.csv", index=False)
    annual.to_csv(BASE_DIR / "dados_processados" / "target_formalizacao_resumo.csv", index=False)
    
    (NOTEBOOK_DIR / "target-formalizacao.md").write_text(
        "# Target epidemiologico\n\n"
        f"**Filtro escolhido:** `{summary['target_filter']}`\n\n"
        f"**Recomendacao:** {summary['recommendation']}\n\n"
        "## Contagens de caso provavel\n\n"
        + "\n".join(f"- {k}: {v}" for k, v in provavel_counts.items())
        + "\n",
        encoding="utf-8",
    )
    
    if run_dir is not None:
        class_counts.to_csv(run_dir / "target_class_final_counts.csv", index=False)
        disease_counts.to_csv(run_dir / "target_desc_classificacao_counts.csv", index=False)
        combo_counts.to_csv(run_dir / "target_combinacoes_top20.csv", index=False)
        annual.to_csv(run_dir / "target_formalizacao_resumo.csv", index=False)
        shutil.copy2(NOTEBOOK_DIR / "target-formalizacao.md", run_dir / "target-formalizacao.md")
    
    return annual, summary

def gerar_visualizacoes_eda(dataset: pd.DataFrame, run_dir: Path | None = None) -> None:
    """
    Gera gráficos de Análise Exploratória de Dados (EDA) e salva-os em resultados_graficos/.
    Gera curvas comparativas (Ceilândia vs Lago Sul), mapa de calor semanal e barras do Top 10 RAs.
    
    Parâmetros:
        dataset (pd.DataFrame): Dataset processado contendo casos, incidência e lags.
    """
    logger.info(">>> P1: gerando graficos de EDA...")
    OUTPUT_DIR.mkdir(exist_ok=True)
    import shutil
    
    ceilandia = dataset[dataset["RA"].map(sanitizar_texto).eq("CEILANDIA")]
    lago_sul = dataset[dataset["RA"].map(sanitizar_texto).eq("LAGO SUL")]
    
    # 1. Comparativo Ceilândia vs Lago Sul
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    for label, frame in [("Ceilandia", ceilandia), ("Lago Sul", lago_sul)]:
        axes[0].plot(frame["epi_sunday"], frame["cases"], label=label)
        axes[1].plot(frame["epi_sunday"], frame["incidencia_100k"], label=label)
    axes[0].set_title("Casos absolutos: Ceilandia vs Lago Sul")
    axes[1].set_title("Incidencia por 100k: Ceilandia vs Lago Sul")
    for ax in axes:
        ax.legend()
        ax.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "populacao_cases_incidencia.png", dpi=220)
    plt.close()
    if run_dir is not None:
        shutil.copy2(OUTPUT_DIR / "populacao_cases_incidencia.png", run_dir / "populacao_cases_incidencia.png")
 
    # 2. Correlação Spearman Lags Climáticos
    lag_cols = [c for c in dataset.columns if c.startswith(("precip_sum_lag_", "temp_mean_lag_", "umidmed_lag_"))]
    corr = dataset[lag_cols + ["incidencia_100k"]].corr(method="spearman")["incidencia_100k"].drop("incidencia_100k")
    corr_df = corr.rename("spearman").reset_index().rename(columns={"index": "feature"})
    corr_df.to_csv(BASE_DIR / "dados_processados" / "correlacao_lags_clima.csv", index=False)
    if run_dir is not None:
        corr_df.to_csv(run_dir / "correlacao_lags_clima.csv", index=False)
    
    heat = corr_df.assign(
        variable=corr_df["feature"].str.replace(r"_lag_\d+$", "", regex=True),
        lag=corr_df["feature"].str.extract(r"_lag_(\d+)$").astype(int),
    ).pivot(index="variable", columns="lag", values="spearman")
    
    fig, ax = plt.subplots(figsize=(9, 4))
    im = ax.imshow(heat.values, cmap="coolwarm", aspect="auto", vmin=-0.35, vmax=0.35)
    ax.set_xticks(range(len(heat.columns)), labels=heat.columns)
    ax.set_yticks(range(len(heat.index)), labels=heat.index)
    ax.set_title("Spearman: lags climaticos vs incidencia")
    plt.colorbar(im, ax=ax)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "correlacao_lags_clima.png", dpi=220)
    plt.close()
    if run_dir is not None:
        shutil.copy2(OUTPUT_DIR / "correlacao_lags_clima.png", run_dir / "correlacao_lags_clima.png")
 
    # 3. Série Temporal DF Total
    df_total = dataset.groupby("epi_sunday")["cases"].sum().reset_index()
    peak = df_total.loc[df_total["cases"].idxmax()]
    plt.figure(figsize=(13, 5))
    plt.plot(df_total["epi_sunday"], df_total["cases"], color="#263238", linewidth=1.8)
    plt.scatter([peak["epi_sunday"]], [peak["cases"]], color="#c62828", zorder=3)
    plt.annotate(
        f"Pico 2024: {int(peak['cases'])} casos",
        xy=(peak["epi_sunday"], peak["cases"]),
        xytext=(peak["epi_sunday"], peak["cases"] * 0.82),
        arrowprops={"arrowstyle": "->", "color": "#c62828"},
    )
    plt.title("Serie temporal DF total")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "serie_df_total_qualidade.png", dpi=220)
    plt.close()
    if run_dir is not None:
        shutil.copy2(OUTPUT_DIR / "serie_df_total_qualidade.png", run_dir / "serie_df_total_qualidade.png")
 
    # 4. Heatmap RA vs Semana
    pivot = dataset.pivot_table(index="RA", columns="epi_sunday", values="cases", aggfunc="sum").fillna(0)
    norm = pivot.div(pivot.max(axis=1).replace(0, np.nan), axis=0).fillna(0)
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.imshow(norm.values, aspect="auto", cmap="YlOrRd")
    ax.set_yticks(range(len(norm.index)), labels=norm.index, fontsize=7)
    ax.set_xticks([])
    ax.set_title("Heatmap semana x RA (casos normalizados por RA)")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "heatmap_ra_semana.png", dpi=220)
    plt.close()
    if run_dir is not None:
        shutil.copy2(OUTPUT_DIR / "heatmap_ra_semana.png", run_dir / "heatmap_ra_semana.png")
 
    # 5. Top 10 RAs por Volume de Casos
    top10 = dataset.groupby("RA")["cases"].sum().sort_values(ascending=True).tail(10)
    plt.figure(figsize=(10, 6))
    plt.barh(top10.index, top10.values, color="#2e7d32")
    plt.title("Top 10 RAs por volume de casos")
    plt.xlabel("Casos")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "top10_ra_volume.png", dpi=220)
    plt.close()
    if run_dir is not None:
        shutil.copy2(OUTPUT_DIR / "top10_ra_volume.png", run_dir / "top10_ra_volume.png")

def gerar_graficos_ablacao(result: pd.DataFrame, run_dir: Path | None = None) -> None:
    """
    Gera gráficos comparativos para a análise de ablação de features.
    
    Parâmetros:
        result (pd.DataFrame): DataFrame de resultados consolidado dos testes de ablação.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    import shutil
    
    fig, ax = plt.subplots(figsize=(10, 5.5))
    plot_df = result.sort_values(["config", "modelo"]).copy()
    labels = plot_df["config"] + " / " + plot_df["modelo"]
    colors = ["#1565c0" if m == "RF" else "#ef6c00" for m in plot_df["modelo"]]
    
    ax.barh(labels, plot_df["r2_df"], color=colors)
    ax.set_title("Ablation comparativo: R2 DF por config/modelo")
    ax.set_xlabel("R2 DF")
    ax.grid(axis="x", alpha=0.25)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "ablation_comparativo.png", dpi=220)
    plt.close()
    if run_dir is not None:
        shutil.copy2(OUTPUT_DIR / "ablation_comparativo.png", run_dir / "ablation_comparativo.png")
 
    baseline = result[result["config"].eq("lag-only")]["r2_df"].max()
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.barh(labels, plot_df["r2_df"], color=colors)
    ax.axvline(baseline, color="#263238", linestyle="--", label="melhor lag-only")
    ax.axvline(baseline + 0.05, color="#2e7d32", linestyle=":", label="criterio +0.05")
    ax.set_title("Contribuicao dos grupos de features")
    ax.set_xlabel("R2 DF")
    ax.legend()
    ax.grid(axis="x", alpha=0.25)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "ablation_contribuicao.png", dpi=220)
    plt.close()
    if run_dir is not None:
        shutil.copy2(OUTPUT_DIR / "ablation_contribuicao.png", run_dir / "ablation_contribuicao.png")

def gerar_painel_final(df: pd.DataFrame, winner: dict, final_predictions: pd.DataFrame, run_dir: Path | None = None) -> None:
    """
    Gera visualizações finais do pipeline (Real vs Previsto global e por RAs principais)
    e redige o arquivo markdown do relatório final com os resultados.
    
    Parâmetros:
        df (pd.DataFrame): Dataset original processado.
        winner (dict): Dicionário contendo os dados da especificação de features vencedora.
        final_predictions (pd.DataFrame): Previsões finais tunadas dos modelos.
        run_dir (Path, opcional): Subdiretório versionado para salvar resultados desta execução.
    """
    logger.info(">>> P1: gerando visualizacoes finais e relatorio...")
    OUTPUT_DIR.mkdir(exist_ok=True)
    NOTEBOOK_DIR.mkdir(exist_ok=True)
    import shutil
    
    ablation_pred_csv = run_dir / "predicoes_ablation.csv" if run_dir else ABLATION_PRED_CSV
    ablation_csv = run_dir / "resultados_ablacao_nowcasting.csv" if run_dir else ABLATION_CSV
    ablation_ra_csv = run_dir / "resultados_ablation_por_ra.csv" if run_dir else ABLATION_RA_CSV
    
    ablation_pred = pd.read_csv(ablation_pred_csv, parse_dates=["epi_sunday"])
    baseline_model = (
        pd.read_csv(ablation_csv)
        .query("config == 'lag-only'")
        .sort_values("r2_df", ascending=False)
        .iloc[0]["modelo"]
    )
    
    config_winner = winner["config"]
    model_winner = winner["modelo"]
    
    pred_baseline = ablation_pred[
        ablation_pred["config"].eq("lag-only") & ablation_pred["modelo"].eq(baseline_model)
    ]
    pred_winner = ablation_pred[
        ablation_pred["config"].eq(config_winner) & ablation_pred["modelo"].eq(model_winner)
    ]
 
    actual_total = df.groupby("epi_sunday", as_index=False)["cases"].sum()
    base_total = pred_baseline.groupby("epi_sunday", as_index=False)["prediction"].sum()
    win_total = pred_winner.groupby("epi_sunday", as_index=False)["prediction"].sum()
    
    peak = actual_total.loc[actual_total["cases"].idxmax()]
    
    # 1. Gráfico Real vs Previsto Total DF
    plt.figure(figsize=(14, 6))
    plt.plot(actual_total["epi_sunday"], actual_total["cases"], color="#263238", label="Real", linewidth=1.8)
    plt.plot(base_total["epi_sunday"], base_total["prediction"], color="#1565c0", label="Lag-only", linewidth=1.6)
    plt.plot(win_total["epi_sunday"], win_total["prediction"], color="#ef6c00", label="Config vencedora", linewidth=1.6)
    plt.axvspan(pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31"), color="#90caf9", alpha=0.2)
    plt.scatter([peak["epi_sunday"]], [peak["cases"]], color="#b71c1c")
    plt.annotate("Pico 2024", (peak["epi_sunday"], peak["cases"]), xytext=(peak["epi_sunday"], peak["cases"] * 0.82),
                 arrowprops={"arrowstyle": "->", "color": "#b71c1c"})
    plt.title("DF total: real vs previsto")
    plt.legend()
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "serie_df_total.png", dpi=220)
    plt.close()
    if run_dir is not None:
        shutil.copy2(OUTPUT_DIR / "serie_df_total.png", run_dir / "serie_df_total.png")
 
    # 2. Séries dos Top 6 RAs
    top6 = pred_winner.groupby("RA")["cases"].sum().nlargest(6).index.tolist()
    fig, axes = plt.subplots(2, 3, figsize=(16, 9), sharex=True)
    for ax, ra in zip(axes.flatten(), top6):
        g = pred_winner[pred_winner["RA"].eq(ra)].sort_values("epi_sunday")
        score = calcular_r2_robusto(g["cases"], g["prediction"])
        ax.plot(g["epi_sunday"], g["cases"], label="Real", color="#263238")
        ax.plot(g["epi_sunday"], g["prediction"], label="Previsto", color="#ef6c00")
        ax.set_title(f"{ra} | R2={score:.2f}")
        ax.grid(alpha=0.25)
    axes.flatten()[0].legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "series_top6_ra.png", dpi=220)
    plt.close()
    if run_dir is not None:
        shutil.copy2(OUTPUT_DIR / "series_top6_ra.png", run_dir / "series_top6_ra.png")
 
    # 3. Incidência média por RA em 2025
    incidence = (
        df[(df["epi_sunday"] >= "2025-01-01") & (df["epi_sunday"] < "2026-01-01")]
        .groupby("RA", as_index=False)["incidencia_100k"]
        .mean()
        .sort_values("incidencia_100k", ascending=True)
    )
    plt.figure(figsize=(10, 9))
    plt.barh(incidence["RA"], incidence["incidencia_100k"], color="#00897b")
    plt.title("Incidencia media por RA em 2025")
    plt.xlabel("Incidencia por 100k")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "incidencia_por_ra_2025.png", dpi=220)
    plt.close()
    if run_dir is not None:
        shutil.copy2(OUTPUT_DIR / "incidencia_por_ra_2025.png", run_dir / "incidencia_por_ra_2025.png")

    # 4. Compilar relatório de métricas e ablação em formato Markdown
    ablation = pd.read_csv(ablation_csv)
    ra_metrics = pd.read_csv(ablation_ra_csv)
    winner_ra = ra_metrics[
        ra_metrics["config"].eq(config_winner) & ra_metrics["modelo"].eq(model_winner)
    ].sort_values("rmse_ra", ascending=False)
    worst_ra = winner_ra.iloc[0]
    
    final_metrics = []
    for _, group in final_predictions.groupby("modelo"):
        metrics, _ = consolidar_metricas_performance(group)
        final_metrics.append({"modelo": group["modelo"].iloc[0], **metrics})
    final_metrics_df = pd.DataFrame(final_metrics)
    
    metrics_csv_path = run_dir / "metricas_modelos_finais.csv" if run_dir else (BASE_DIR / "resultados_modelagem" / "metricas_modelos_finais.csv")
    final_metrics_df.to_csv(metrics_csv_path, index=False)
    if run_dir:
        final_metrics_df.to_csv(BASE_DIR / "resultados_modelagem" / "metricas_modelos_finais.csv", index=False)

    report = [
        "# Relatorio final - Execucao do Pipeline",
        "",
        "## Decisao de features",
        "",
        f"- Config vencedora conservadora: `{winner['config']}` / `{winner['modelo']}`.",
        f"- Melhor config observada: `{winner['best_observed_config']}` / `{winner['best_observed_modelo']}`.",
        f"- Ganho complexo aceito pelo criterio? `{winner['accepted_complex_gain']}`.",
        f"- Motivo: {winner['reason']}",
        "",
        "## Respostas da Avaliacao de Data Science",
        "",
        "1. A config que agregou valor real demonstravel foi considerada apenas se superou "
        "lag-only por delta R2 > 0.05 ou RMSE melhor in >70% das RAs.",
        f"2. Resultado: {winner['reason']}",
        f"3. RA com maior RMSE na config vencedora: `{worst_ra['RA']}` (RMSE={worst_ra['rmse_ra']:.3f}). "
        "Hipotese: RAs com picos localizados e baixa base semanal sao mais dificeis para modelos globais.",
        "4. O pipeline fica mais defensavel para nowcasting operacional semanal. Para forecast fechado, "
        "use o resultado recursivo como referencia; a incerteza cresce rapidamente sem casos reais recentes.",
        "5. Antes da hierarquia nacional, a compatibilidade SINAN vs info-saude precisa passar pelos criterios "
        "de correlacao e diferenca media documentados em validacao_consistencia_fontes.md.",
        "",
        "## Estudo de Ablacao",
        "",
        formatar_tabela_markdown(ablation),
        "",
        "## Modelos tunados",
        "",
        formatar_tabela_markdown(final_metrics_df),
        "",
    ]
    FINAL_REPORT_MD.write_text("\n".join(report), encoding="utf-8")
    if run_dir is not None:
        shutil.copy2(FINAL_REPORT_MD, run_dir / "relatorio_final_execucao.md")

def normalizar_sg_uf(series: pd.Series) -> pd.Series:
    """
    Normaliza a coluna de UF de residência ou notificação do SINAN.
    Apoia a validação ao classificar '53' numérico ou a string 'DF' como DF (Distrito Federal).
    
    Parâmetros:
        series (pd.Series): Série original.
        
    Retorna:
        pd.Series: Série booleana indicando se pertence ao DF.
    """
    numeric = pd.to_numeric(series, errors="coerce")
    text = series.astype(str).str.upper().str.strip()
    return numeric.eq(53) | text.eq("DF")

def validar_consistencia_fontes(target_name: str = "familia_dengue", run_dir: Path | None = None) -> dict:
    import shutil
    """
    Valida a consistência de contagens entre a base federal do SINAN (DENGBR17) e a distrital do info-saude
    para o ano de 2017. Avalia métricas de correlação e erro percentual para decidir aceitação.
    
    Parâmetros:
        target_name (str): Filtro de máscara para a base info-saude. Default: 'familia_dengue'.
        
    Retorna:
        dict: Estatísticas e resultado de aceitação da validação.
    """
    logger.info(">>> P2: validando SINAN 2017 vs info-saude 2017...")
    sinan_file = DADOS_GOV_DIR / "DENGBR17.csv"
    if not sinan_file.exists():
        logger.warning(f"  [AVISO] Arquivo do SINAN para validação não encontrado em {sinan_file}. Pulando validação.")
        report = [
            "# Validacao Consistencia Fontes - SINAN vs info-saude",
            "",
            "A validação foi pulada porque o arquivo federal do SINAN (`dados-gov/DENGBR17.csv`) não está presente neste ambiente.",
        ]
        SINAN_REPORT_MD.write_text("\n".join(report), encoding="utf-8")
        if run_dir is not None:
            shutil.copy2(SINAN_REPORT_MD, run_dir / "validacao_consistencia_fontes.md")
        return {
            "selected_codes": [],
            "residencia": {"corr": 0.0, "mean_pct": 0.0, "max_pct": 0.0, "accepted": False},
            "notificacao": {"corr": 0.0, "mean_pct": 0.0, "max_pct": 0.0, "accepted": False},
            "accepted": False,
            "status": "skipped_due_to_missing_file",
        }
        
    chunks_res = []
    chunks_not = []
    class_counts = {}
    selected_codes = None
    
    for chunk in pd.read_csv(
        sinan_file,
        encoding="latin-1",
        usecols=lambda c: c in {"SG_UF", "SG_UF_NOT", "CLASSI_FIN", "DT_SIN_PRI"},
        chunksize=100_000,
        low_memory=False,
    ):
        class_fin = pd.to_numeric(chunk["CLASSI_FIN"], errors="coerce")
        mask_res = normalizar_sg_uf(chunk["SG_UF"])
        mask_not = normalizar_sg_uf(chunk["SG_UF_NOT"])
        
        for code, count in class_fin[mask_res | mask_not].value_counts(dropna=False).items():
            key = "NA" if pd.isna(code) else str(int(code))
            class_counts[key] = class_counts.get(key, 0) + int(count)
            
        if selected_codes is None:
            selected_codes = [1, 2, 3]
            
        mask_class = class_fin.isin(selected_codes)
        if not mask_class.any() and class_fin.isin([10, 11, 12]).any():
            selected_codes = [10, 11, 12]
            mask_class = class_fin.isin(selected_codes)
            
        part_res = chunk.loc[mask_res & mask_class, ["DT_SIN_PRI"]].copy()
        part_res["epi_sunday"] = calcular_semana_epidemiologica(part_res["DT_SIN_PRI"])
        chunks_res.append(part_res.dropna(subset=["epi_sunday"]))
        
        part_not = chunk.loc[mask_not & mask_class, ["DT_SIN_PRI"]].copy()
        part_not["epi_sunday"] = calcular_semana_epidemiologica(part_not["DT_SIN_PRI"])
        chunks_not.append(part_not.dropna(subset=["epi_sunday"]))

    def agregar_intervalos_semanais(chunks: list[pd.DataFrame], name: str) -> pd.DataFrame:
        if not chunks:
            return pd.DataFrame(columns=["epi_sunday", name])
        series = pd.concat(chunks, ignore_index=True)
        weekly = series.groupby("epi_sunday").size().reset_index(name=name)
        return weekly[
            (weekly["epi_sunday"] >= "2017-01-01")
            & (weekly["epi_sunday"] < "2018-01-01")
        ]

    sinan_res_weekly = agregar_intervalos_semanais(chunks_res, "sinan_residencia")
    sinan_not_weekly = agregar_intervalos_semanais(chunks_not, "sinan_notificacao")

    info = ingestar_dados_saude_local()
    masks = mascaras_target(info)
    info = info[
        masks[target_name]
        & info["uf_norm"].eq("DF")
        & (info["epi_sunday"] >= pd.Timestamp("2017-01-01"))
        & (info["epi_sunday"] < pd.Timestamp("2018-01-01"))
    ]
    info_weekly = info.groupby("epi_sunday").size().reset_index(name="info_saude")
    
    combined = (
        sinan_res_weekly.merge(sinan_not_weekly, on="epi_sunday", how="outer")
        .merge(info_weekly, on="epi_sunday", how="outer")
        .fillna(0)
        .sort_values("epi_sunday")
    )

    def comparar(col: str) -> dict:
        diff = combined["info_saude"] - combined[col]
        denominator = combined[col].replace(0, np.nan)
        diff_pct_abs = (diff.abs() / denominator * 100).replace([np.inf, -np.inf], np.nan)
        corr = float(combined[[col, "info_saude"]].corr().iloc[0, 1])
        mean_pct = float(diff_pct_abs.mean(skipna=True))
        max_pct = float(diff_pct_abs.max(skipna=True))
        return {
            "corr": corr,
            "mean_pct": mean_pct,
            "max_pct": max_pct,
            "accepted": bool(corr >= 0.90 and mean_pct <= 15.0),
        }

    metrics_res = comparar("sinan_residencia")
    metrics_not = comparar("sinan_notificacao")
    
    combined["diff_residencia"] = combined["info_saude"] - combined["sinan_residencia"]
    combined["diff_pct_abs_residencia"] = (
        combined["diff_residencia"].abs() / combined["sinan_residencia"].replace(0, np.nan) * 100
    )
    combined["diff_notificacao"] = combined["info_saude"] - combined["sinan_notificacao"]
    combined["diff_pct_abs_notificacao"] = (
        combined["diff_notificacao"].abs() / combined["sinan_notificacao"].replace(0, np.nan) * 100
    )
    
    accepted = metrics_res["accepted"]

    combined.to_csv(BASE_DIR / "dados_processados" / "validacao_sinan_infosaude_2017.csv", index=False)
    if run_dir is not None:
        combined.to_csv(run_dir / "validacao_sinan_infosaude_2017.csv", index=False)
    
    # 5. Plotagem do Comparativo SINAN vs info-saude
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    axes[0].plot(combined["epi_sunday"], combined["sinan_residencia"], label="SINAN residencia", linewidth=1.8)
    axes[0].plot(combined["epi_sunday"], combined["sinan_notificacao"], label="SINAN notificacao", linewidth=1.4)
    axes[0].plot(combined["epi_sunday"], combined["info_saude"], label="info-saude 2017", linewidth=1.8)
    axes[0].legend()
    axes[0].set_title("SINAN vs info-saude - DF 2017")
    axes[0].grid(alpha=0.25)
    
    axes[1].plot(combined["epi_sunday"], combined["diff_pct_abs_residencia"], color="#c62828", label="residencia")
    axes[1].plot(combined["epi_sunday"], combined["diff_pct_abs_notificacao"], color="#1565c0", alpha=0.75, label="notificacao")
    axes[1].axhline(15, color="#263238", linestyle="--", label="criterio 15%")
    axes[1].set_title("Diferenca percentual absoluta")
    axes[1].legend()
    axes[1].grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "sinan_infosaude_2017.png", dpi=220)
    plt.close()
    if run_dir is not None:
        import shutil
        shutil.copy2(OUTPUT_DIR / "sinan_infosaude_2017.png", run_dir / "sinan_infosaude_2017.png")

    sinan_counts_df = pd.DataFrame(
        [{"codigo": key, "n_df_res_ou_not": value} for key, value in sorted(class_counts.items())]
    )
    sinan_counts_df.to_csv(BASE_DIR / "dados_processados" / "sinan_class_fin_counts_df_2017.csv", index=False)
    if run_dir is not None:
        sinan_counts_df.to_csv(run_dir / "sinan_class_fin_counts_df_2017.csv", index=False)

    report = [
        "# Validacao Consistencia Fontes - SINAN vs info-saude",
        "",
        f"- Codigos CLASSI_FIN usados: `{selected_codes}`.",
        "- Observacao: o plano citava `[1, 2, 3]`, mas DENGBR17 neste workspace usa outra codificacao; "
        "a familia de dengue aparece nos codigos `[10, 11, 12]`.",
        f"- Residencia (SG_UF == 53) correlacao: {metrics_res['corr']:.4f}",
        f"- Residencia diferenca media percentual absoluta: {metrics_res['mean_pct']:.2f}%",
        f"- Residencia pico maximo de divergencia percentual: {metrics_res['max_pct']:.2f}%",
        f"- Residencia criterio de aceite atingido? `{metrics_res['accepted']}`",
        f"- Notificacao (SG_UF_NOT == 53) correlacao: {metrics_not['corr']:.4f}",
        f"- Notificacao diferenca media percentual absoluta: {metrics_not['mean_pct']:.2f}%",
        f"- Notificacao criterio de aceite atingido? `{metrics_not['accepted']}`",
        "",
        "## Conclusao",
        "",
    ]
    if accepted:
        report.append("As series passam no criterio definido para splicing exploratorio.")
    else:
        report.append(
            "As series nao passam no criterio definido. Nao recomenda-se construir a hierarquia nacional "
            "sem reconciliar definicao de caso, cobertura e atraso de notificacao."
        )
    SINAN_REPORT_MD.write_text("\n".join(report), encoding="utf-8")
    if run_dir is not None:
        shutil.copy2(SINAN_REPORT_MD, run_dir / "validacao_consistencia_fontes.md")
    
    return {
        "selected_codes": selected_codes,
        "residencia": metrics_res,
        "notificacao": metrics_not,
        "accepted": accepted,
    }
