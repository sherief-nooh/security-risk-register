"""
Security Risk Register - analysis script

Reads the raw register (data/risk_register.csv), scores every risk on a
5x5 likelihood x impact matrix, and produces:

  outputs/heatmap_inherent_vs_residual.png   two heat maps side by side
  outputs/score_by_category.png              average score before and after mitigation
  outputs/summary.md                         plain-text summary for management

Usage:
    python analysis/risk_analysis.py
    python analysis/risk_analysis.py --as-of 2026-10-01

All data in this project is synthetic. It describes a fictional site.
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "risk_register.csv"
OUT = ROOT / "outputs"

# Rating bands on the 1-25 score scale
BANDS = [(1, 4, "Low"), (5, 9, "Medium"), (10, 14, "High"), (15, 25, "Critical")]
BAND_FILL = {"Low": "#CFE8D5", "Medium": "#F6E3A1", "High": "#F2B27A", "Critical": "#E58C7E"}
INK, MUTED, GRID = "#15202A", "#55636F", "#E3E7EA"
INHERENT_COLOR, RESIDUAL_COLOR = "#C9771A", "#1F6FB2"


def rating(score: int) -> str:
    for low, high, name in BANDS:
        if low <= score <= high:
            return name
    raise ValueError(f"Score out of range: {score}")


def load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["due_date"])
    for col in ["inherent_likelihood", "inherent_impact", "residual_likelihood", "residual_impact"]:
        if not df[col].between(1, 5).all():
            raise ValueError(f"{col} must be between 1 and 5")
    df["inherent_score"] = df.inherent_likelihood * df.inherent_impact
    df["residual_score"] = df.residual_likelihood * df.residual_impact
    df["inherent_rating"] = df.inherent_score.map(rating)
    df["residual_rating"] = df.residual_score.map(rating)
    df["reduction_pct"] = 1 - df.residual_score / df.inherent_score
    return df


def draw_matrix(ax, df, stage, title):
    counts = df.groupby([f"{stage}_likelihood", f"{stage}_impact"]).size()
    for lik in range(1, 6):
        for imp in range(1, 6):
            band = rating(lik * imp)
            ax.add_patch(plt.Rectangle((imp - 0.5, lik - 0.5), 1, 1,
                                       facecolor=BAND_FILL[band], edgecolor="white", linewidth=3))
            n = counts.get((lik, imp), 0)
            if n:
                ax.text(imp, lik, str(n), ha="center", va="center",
                        fontsize=17, fontweight="bold", color=INK)
    ax.set_xlim(0.5, 5.5)
    ax.set_ylim(0.5, 5.5)
    ax.set_xticks(range(1, 6))
    ax.set_yticks(range(1, 6))
    ax.set_xlabel("Impact", color=MUTED)
    ax.set_ylabel("Likelihood", color=MUTED)
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=INK, pad=10)
    ax.tick_params(colors=MUTED, length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    ax.set_aspect("equal")


def heatmaps(df):
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.6))
    draw_matrix(axes[0], df, "inherent", "Inherent risk (before controls)")
    draw_matrix(axes[1], df, "residual", "Residual risk (after mitigation)")
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=BAND_FILL[name]) for _, _, name in BANDS]
    labels = [f"{name} ({lo}-{hi})" for lo, hi, name in BANDS]
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False, fontsize=10)
    fig.suptitle("Number of risks in each cell, 20 risks in total", x=0.06, ha="left",
                 fontsize=10, color=MUTED, y=0.97)
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(OUT / "heatmap_inherent_vs_residual.png", dpi=160, facecolor="white")
    plt.close(fig)


def category_chart(df):
    g = (df.groupby("category")[["inherent_score", "residual_score"]].mean()
           .sort_values("inherent_score"))
    fig, ax = plt.subplots(figsize=(10, 5))
    y = range(len(g))
    for i, (cat, row) in enumerate(g.iterrows()):
        ax.plot([row.residual_score, row.inherent_score], [i, i], color=GRID, linewidth=4, zorder=1)
    ax.scatter(g.inherent_score, y, s=110, color=INHERENT_COLOR, edgecolor="white",
               linewidth=2, zorder=3, label="Inherent")
    ax.scatter(g.residual_score, y, s=110, color=RESIDUAL_COLOR, edgecolor="white",
               linewidth=2, zorder=3, label="Residual")
    for i, (cat, row) in enumerate(g.iterrows()):
        ax.text(row.inherent_score + 0.5, i, f"{row.inherent_score:.1f}", va="center",
                fontsize=9, color=INK)
        ax.text(row.residual_score - 0.5, i, f"{row.residual_score:.1f}", va="center",
                ha="right", fontsize=9, color=INK)
    ax.set_yticks(list(y))
    ax.set_yticklabels(g.index, color=INK)
    ax.set_xlim(0, 20)
    ax.set_xticks([0, 5, 10, 15, 20])
    ax.set_xlabel("Average risk score (likelihood x impact)", color=MUTED)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    ax.legend(loc="lower right", frameon=False)
    ax.set_title("Average score by category, before and after mitigation", loc="left",
                 fontsize=13, fontweight="bold", color=INK, pad=10)
    fig.tight_layout()
    fig.savefig(OUT / "score_by_category.png", dpi=160, facecolor="white")
    plt.close(fig)


def summary(df, as_of):
    order = [name for _, _, name in BANDS]
    by_rating = pd.DataFrame({
        "Inherent": df.inherent_rating.value_counts().reindex(order, fill_value=0),
        "Residual": df.residual_rating.value_counts().reindex(order, fill_value=0),
    })
    overdue = df[(df.due_date < as_of) & (df.status != "Done")]
    top = df.sort_values(["residual_score", "inherent_score"], ascending=False).head(5)

    lines = [
        "# Risk register summary",
        "",
        f"As-of date: {as_of:%d %b %Y}  ",
        f"Risks assessed: {len(df)}  ",
        f"Average score: {df.inherent_score.mean():.1f} inherent, "
        f"{df.residual_score.mean():.1f} residual "
        f"({1 - df.residual_score.sum() / df.inherent_score.sum():.0%} lower overall)",
        "",
        "## Risks by rating",
        "",
        "| Rating | Inherent | Residual |",
        "|---|---:|---:|",
        *[f"| {r} | {by_rating.loc[r, 'Inherent']} | {by_rating.loc[r, 'Residual']} |" for r in order],
        "",
        "## Mitigation status",
        "",
        "| Status | Count |",
        "|---|---:|",
        *[f"| {s} | {n} |" for s, n in df.status.value_counts().items()],
        "",
        f"## Overdue actions ({len(overdue)})",
        "",
        "| ID | Risk | Owner | Due |",
        "|---|---|---|---|",
        *[f"| {r.risk_id} | {r.risk} | {r.owner} | {r.due_date:%d %b %Y} |" for r in overdue.itertuples()],
        "",
        "## Highest residual risks",
        "",
        "| ID | Risk | Residual score | Rating |",
        "|---|---|---:|---|",
        *[f"| {r.risk_id} | {r.risk} | {r.residual_score} | {r.residual_rating} |" for r in top.itertuples()],
        "",
    ]
    text = "\n".join(lines)
    (OUT / "summary.md").write_text(text, encoding="utf-8")
    return text


def main():
    parser = argparse.ArgumentParser(description="Analyse the security risk register.")
    parser.add_argument("--as-of", default="2026-10-01", help="Review date, YYYY-MM-DD")
    args = parser.parse_args()
    as_of = pd.Timestamp(args.as_of)

    OUT.mkdir(exist_ok=True)
    df = load(DATA)
    heatmaps(df)
    category_chart(df)
    print(summary(df, as_of))


if __name__ == "__main__":
    main()
