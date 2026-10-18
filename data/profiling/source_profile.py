"""Course Session 1 ydata-profiling, adapted to four prepared USDA tables."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from ydata_profiling import ProfileReport

OUT_DIR = Path(__file__).resolve().parents[2] / "build/profiling"


def quality_summary(df: pd.DataFrame) -> pd.DataFrame:
    """One row per column: dtype, how many distinct values, and percent
    missing. Sorted worst-missingness first, this is what a live room
    scans to pick candidates before opening the full profile.
    """
    return pd.DataFrame(
        {
            "dtype": df.dtypes.astype(str),
            "n_unique": df.nunique(),
            "pct_missing": (df.isna().mean() * 100).round(1),
        }
    ).sort_values("pct_missing", ascending=False)


def plot_missingness(summary: pd.DataFrame, title: str, top_n: int = 15):
    """Horizontal bar chart of the worst top_n columns by percent
    missing. Skips the plot entirely if nothing is missing, an empty
    chart is not a finding.
    """
    worst = summary[summary["pct_missing"] > 0].head(top_n)
    if worst.empty:
        print(f"{title}: no missing values in any column.")
        return
    fig, ax = plt.subplots(figsize=(7, max(2, 0.35 * len(worst))))
    ax.barh(worst.index[::-1], worst["pct_missing"][::-1])
    ax.set_xlabel("% missing")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(OUT_DIR / (title.replace(" ", "_") + ".png"))
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("foods", "measurements", "nutrients", "categories"):
        path = Path(__file__).resolve().parents[2] / "data" / f"{name}.csv"
        df = pd.read_csv(path)
        summary = quality_summary(df)
        summary.to_csv(OUT_DIR / f"quality_{name}.csv")
        plot_missingness(summary, f"{name}_missingness")
        report = ProfileReport(df, title=f"FoodScope - {name}", minimal=True)
        report.to_file(OUT_DIR / f"profiling_report_{name}.html")
        print(f"Profiled {name}: {df.shape[0]} rows, {df.shape[1]} columns")


if __name__ == "__main__":
    main()
