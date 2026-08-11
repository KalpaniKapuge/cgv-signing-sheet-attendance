import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

# Add the current and parent directories to Python's module search path.
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config
import _data

# Colours used to represent attendance status.
PRESENT_COLOUR = "#0ca30c"
ABSENT_COLOUR = "#d03b3b"


def make_figure():
    # Load attendance records and convert them into a student-by-date table.
    df = _data.load_attendance()
    pivot = df.pivot(index="name", columns="date", values="present")
    # Keep student row order stable (by index_no) rather than alphabetical.
    order = df.drop_duplicates("name").sort_values("student_id")["name"]
    pivot = pivot.loc[order]

    dates = pivot.columns
    students = pivot.index.tolist()
    grid = pivot.values

    # Create the heatmap using fixed colours for Present and Absent.
    fig, ax = plt.subplots(figsize=(8, 4.8))
    cmap = ListedColormap([ABSENT_COLOUR, PRESENT_COLOUR])
    ax.imshow(grid, cmap=cmap, vmin=0, vmax=1, aspect="auto")

    # Add P/A labels to make each attendance cell easy to identify.
    for r in range(grid.shape[0]):
        for c in range(grid.shape[1]):
            label = "P" if grid[r, c] == 1 else "A"
            ax.text(
                c, r, label,
                ha="center",
                va="center",
                color="white",
                fontsize=11,
                fontweight="bold"
            )

    # Display student names on the y-axis.
    ax.set_yticks(range(len(students)))
    ax.set_yticklabels(students, fontsize=9)

    # Calculate the percentage of students present for each date.
    pct_per_day = (
        (pivot.sum(axis=0) / pivot.shape[0] * 100)
        .round(0)
        .astype(int)
    )

    # Show attendance percentage and date on each x-axis label.
    ax.set_xticks(range(len(dates)))
    ax.set_xticklabels([
        f"{pct}%\n{d.strftime('%d %b')}"
        for d, pct in zip(dates, pct_per_day)
    ])
    ax.tick_params(axis="x", which="major", pad=8)

    # Add white lines between heatmap cells for better readability.
    ax.set_xticks(
        [x - 0.5 for x in range(1, len(dates))],
        minor=True
    )
    ax.set_yticks(
        [y - 0.5 for y in range(1, len(students))],
        minor=True
    )
    ax.grid(which="minor", color="white", linewidth=2)

    # Hide unnecessary tick marks and chart borders.
    ax.tick_params(which="minor", bottom=False, left=False)
    ax.tick_params(which="major", bottom=False, left=False)

    for spine in ax.spines.values():
        spine.set_visible(False)

    # Add a legend explaining the attendance colours.
    handles = [
        plt.Rectangle(
            (0, 0), 1, 1,
            color=PRESENT_COLOUR,
            label="Present"
        ),
        plt.Rectangle(
            (0, 0), 1, 1,
            color=ABSENT_COLOUR,
            label="Absent"
        )
    ]

    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=2,
        frameon=False,
        fontsize=10
    )

    # Set the chart title and adjust the layout.
    ax.set_title(
        "Attendance Heatmap - BSc SE 2016.1 (CGV)",
        fontsize=12,
        weight="bold",
        pad=12
    )

    fig.tight_layout()
    return fig


def main():
    # Save the generated heatmap to the configured output directory.
    out = config.OUTPUT_DIR / "charts" / "m4_heatmap.png"
    out.parent.mkdir(parents=True, exist_ok=True)

    fig = make_figure()
    fig.savefig(out, dpi=130)
    plt.close(fig)

    print(f"[M4] heatmap -> {out}")


# Run the chart generation only when this file is executed directly.
if __name__ == "__main__":
    main()

