# Signature-Based Attendance System (CGV Coursework)

Reads handwritten **signing sheets** from smartphone photos, detects which
students signed, stores the result, checks for forged signatures, and presents
seven visualizations plus a dashboard.

**Module:** CS402_3 – Computer Graphics and Visualization
**Programme:** BSc (Hons) in Software Engineering – 2016.1, NSBM Green University Town

---

## Pipeline

```
phone photo
   │  M1  detect 4 corners → perspective transform onto fixed template
   ▼
aligned sheet (1000×1400)
   │  M2  grid rows/cols → crop each signature cell
   ▼
signature crops
   │  M3  grayscale → Otsu → morphology  (+ ink-colour classify)
   ▼
clean binary cells
   │  M4  count ink pixels → present / absent
   ▼
per-student status
   │  M5  parse info.xml → map index ↔ status
   ▼
mapped records
   │  M6  store in SQLite (Students, Attendance, Subject_Info)
   ▼
database  ──► M7 forgery check (SSIM vs genuine)  ──► visualizations + dashboard (M8)
```

---

## Member ownership

| Member | Image-processing module | Visualization | Entry point |
|-------:|-------------------------|---------------|-------------|
| **1** | `src/m1_alignment.py` – corner detection + perspective transform | Bar chart – batch attendance | |
| **2** | `src/m2_crop.py` – grid detection + signature cropping | Line chart – attendance over time | |
| **3** | `src/m3_preprocess.py` – grayscale/Otsu/morphology + ink colour | Pie chart – by ink colour | |
| **4** | `src/m4_detect.py` – pixel-density present/absent | Heatmap – high/low days | |
| **5** | `src/m5_mapping.py` – parse `info.xml`, map index↔status | Gauge chart | `python infovis.py 001` |
| **6** | `src/m6_database.py` – SQLite controller | Histogram / Box plot | |
| **7** | `src/m7_investigate.py` – SSIM forgery check | Scatter / Radar – match % | `python investigate.py` |
| **8** | `src/m8_preview.py` – OpenCV live preview | Dashboard (all charts) | `python -m streamlit run dashboard.py` |

Visualizations live in `viz/` (`m1_bar.py` … `m7_scatter.py`).

---

## Setup

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Generate test data (no original photos needed)

```bash
python tools/generate_synthetic_sheets.py
```

This recreates the template, six genuine reference signatures, and five
"phone-photo" sheets under `data/generated/`.

> **Using your own photos:** drop them in `data/raw/` (any names). The pipeline
> prefers `data/raw/` automatically and only falls back to the synthetic set.

## Run the full pipeline

```bash
python pipeline.py            # M1 → M6, populates data/attendance.db
python investigate.py         # M7 forgery report
python infovis.py 001         # M5 gauge for one student
python -m streamlit run dashboard.py   # M8 dashboard
```

---

## Repository layout

```
sig_system/
├── config.py                 # paths + tuning constants (shared)
├── info.xml                  # subject + roster + sessions (Member 5 parses)
├── requirements.txt
├── pipeline.py               # end-to-end orchestrator (M1→M6)
├── infovis.py                # Member 5 gauge entry
├── investigate.py            # Member 7 forgery entry
├── dashboard.py              # Member 8 Streamlit dashboard
├── src/
│   ├── common/geometry.py    # canonical template coordinates (backbone)
│   ├── common/io_utils.py    # image IO helpers
│   ├── m1_alignment.py …     # one module per member
│   └── m8_preview.py
├── viz/                      # one visualization per member
├── tools/generate_synthetic_sheets.py
└── data/                     # templates, raw, generated, genuine_signatures, output
```

---

## Suggested git commit distribution

So each member's contribution appears as their own commit(s):

```bash
git init
git add config.py info.xml requirements.txt README.md src/common/ tools/
git commit -m "Project scaffold, template geometry, test-data generator"

# then, per member (authored under their name):
git add src/m1_alignment.py viz/m1_bar.py
git commit --author="Member 1 <m1@nsbm>" -m "M1: sheet alignment + batch bar chart"
# …repeat for m2_crop.py/viz/m2_line.py, etc.
```

`GIT_AUTHOR_NAME` / `GIT_AUTHOR_DATE` can also be set per commit if you need
specific timestamps.
