"""
tools/generate_synthetic_sheets.py
===================================
Reproduces the NSBM signing-sheet template and produces test data so the whole
pipeline is runnable without the original phone photos.

It writes:
  data/templates/sheet_template.png        the blank template (Member 1 target)
  data/genuine_signatures/<indexNo>.png    one clean reference sig per student
  data/generated/_aligned/<name>.png       axis-aligned filled sheets (ground truth)
  data/generated/<name>.png                "phone photo" versions: the aligned
                                           sheet placed on a desk background and
                                           perspective-warped + noised, matching
                                           the <session image="..."> names in info.xml

Run:
    python tools/generate_synthetic_sheets.py
    python tools/generate_synthetic_sheets.py --no-warp     # skip photo simulation

Design notes
------------
* Attendance per session is fixed (PRESENT) to roughly mirror the real sheets,
  giving varied data that makes every visualization meaningful.
* Each student has a deterministic signature "style" (seeded by index number).
  Genuine references reuse that seed with no jitter; on-sheet signatures reuse it
  with small jitter -> high SSIM (Member 7 sees them as genuine).
* One deliberate forgery is injected (FORGERY) using a different seed so Member 7
  has a positive test case.
"""

import argparse
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# --- make config + geometry importable regardless of cwd --------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src", "common"))

import config          # noqa: E402
import geometry        # noqa: E402

try:
    import cv2         # noqa: E402
    HAVE_CV2 = True
except Exception:
    HAVE_CV2 = False


# --------------------------------------------------------------------------- #
# Fixed scenario data (best-effort mirror of the five real sheets)
# --------------------------------------------------------------------------- #
# rows present on each date (row numbers 1..6)
PRESENT = {
    "2019-05-31": [1, 2, 3, 4, 5, 6],
    "2019-06-21": [1, 2, 3, 4, 5],          # row 6 marked absent on the real sheet
    "2019-06-28": [1, 4, 5, 6],             # rows 2,3 blank
    "2019-07-05": [1, 3, 5, 6],             # rows 2,4 blank
    "2019-07-12": [1, 2, 3, 4, 5, 6],
}
# ink colour per (date,row) is derived deterministically; palette below (RGB)
INK_RGB = {"Blue": (25, 45, 165), "Black": (20, 20, 20), "Green": (20, 110, 45)}
INK_CYCLE = ["Blue", "Blue", "Black", "Blue", "Green", "Black"]  # by row -> varied pie

# inject one forgery: (date, row) drawn with a different signature seed
FORGERY = ("2019-07-12", 3)


# --------------------------------------------------------------------------- #
# Fonts
# --------------------------------------------------------------------------- #
def _font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-"
        + ("Bold" if bold else "Regular") + ".ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


# --------------------------------------------------------------------------- #
# info.xml loading
# --------------------------------------------------------------------------- #
def load_info():
    root = ET.parse(config.INFO_XML).getroot()
    subj = {c.tag: (c.text or "").strip() for c in root.find("subject")}
    students = [dict(s.attrib) for s in root.find("students")]
    sessions = [dict(s.attrib) for s in root.find("sessions")]
    return subj, students, sessions


# --------------------------------------------------------------------------- #
# Drawing helpers
# --------------------------------------------------------------------------- #
def _text_in(draw, rect, text, font, align="left", pad=8, fill=(0, 0, 0)):
    x0, y0, x1, y1 = rect
    tb = draw.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    ty = y0 + (y1 - y0 - th) / 2 - tb[1]
    tx = x0 + pad if align == "left" else x0 + (x1 - x0 - tw) / 2
    draw.text((tx, ty), text, font=font, fill=fill)


def _grid(draw, cells, width=2):
    for cell in cells:
        draw.rectangle(cell.rect, outline=(0, 0, 0), width=width)


def draw_template(subj, students):
    """Build and save the blank template; return it as a PIL image."""
    W, H = config.TEMPLATE_W, config.TEMPLATE_H
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    # --- header text block ---
    hx = geometry.HEADER_LEFT_FX * W
    hy = geometry.HEADER_TOP_FY * H
    d.text((hx, hy), "Signing Sheet", font=_font(40, bold=True), fill=(0, 0, 0))
    d.text((hx, hy + 52), subj["university"], font=_font(20), fill=(0, 0, 0))
    d.text((hx, hy + 80), subj["faculty"], font=_font(20), fill=(0, 0, 0))
    d.text((hx, hy + 108), subj["programme"], font=_font(22, bold=True), fill=(0, 0, 0))
    d.text((hx, hy + 150), "CGV", font=_font(26), fill=(20, 40, 160))

    # --- info table ---
    info = geometry.info_table_cells()
    for r in info.values():
        d.rectangle(r, outline=(0, 0, 0), width=2)
    fh = _font(18, bold=True)
    _text_in(d, info["Date_head"], "Date", fh, align="center")
    _text_in(d, info["Time_head"], "", fh, align="center")
    _text_in(d, info["Lecturer_head"], "Lecture's Name", fh, align="center")
    _text_in(d, info["LecSig_head"], "Signatue", fh, align="center")

    # --- main table grid + headers + fixed student columns ---
    cells = geometry.all_main_cells()
    _grid(d, cells)
    header_font = _font(18, bold=True)
    body_font = _font(17)
    by_row = {}
    for cell in cells:
        by_row.setdefault(cell.row, {})[cell.col] = cell.rect

    for c, name in enumerate(geometry.COL_NAMES):
        _text_in(d, by_row[0][c], name, header_font, align="center")

    for stu in students:
        row = int(stu["row"])
        _text_in(d, by_row[row][0], str(row), body_font, align="center")
        _text_in(d, by_row[row][1], stu["indexNo"], body_font, align="left")
        _text_in(d, by_row[row][2], stu["title"], body_font, align="center")
        _text_in(d, by_row[row][3], stu["name"], body_font, align="left")

    config.TEMPLATE_IMAGE.parent.mkdir(parents=True, exist_ok=True)
    img.save(config.TEMPLATE_IMAGE)
    print(f"[template] {config.TEMPLATE_IMAGE}")
    return img


# --------------------------------------------------------------------------- #
# Signature synthesis
# --------------------------------------------------------------------------- #
def _sig_points(rect, seed, jitter=0.0, n=7):
    rng = np.random.default_rng(seed)
    x0, y0, x1, y1 = rect
    px, py = (x1 - x0) * 0.12, (y1 - y0) * 0.25
    ax0, ay0, ax1, ay1 = x0 + px, y0 + py, x1 - px, y1 - py
    base_y = rng.uniform(0.25, 0.75, size=n)
    pts = []
    for i in range(n):
        fx = i / (n - 1)
        X = ax0 + fx * (ax1 - ax0)
        Y = ay0 + base_y[i] * (ay1 - ay0)
        if jitter:
            X += rng.uniform(-jitter, jitter) * (ax1 - ax0)
            Y += rng.uniform(-jitter, jitter) * (ay1 - ay0)
        pts.append((float(X), float(Y)))
    return pts


def draw_signature(draw, rect, seed, colour_rgb, jitter=0.0):
    pts = _sig_points(rect, seed, jitter=jitter)
    draw.line(pts, fill=colour_rgb, width=3, joint="curve")
    # a second flourish stroke for realism
    pts2 = _sig_points(rect, seed + 999, jitter=jitter, n=4)
    draw.line(pts2, fill=colour_rgb, width=2, joint="curve")


def render_genuine_signatures(students):
    """One clean reference signature per student (Member 7 baseline)."""
    sig_cells = geometry.signature_cells()
    for stu in students:
        row = int(stu["row"])
        x0, y0, x1, y1 = sig_cells[row]
        w, h = x1 - x0, y1 - y0
        img = Image.new("RGB", (w, h), "white")
        d = ImageDraw.Draw(img)
        draw_signature(d, (0, 0, w, h), seed=int(stu["indexNo"]),
                       colour_rgb=INK_RGB["Blue"], jitter=0.0)
        out = config.GENUINE_SIG_DIR / f"{stu['indexNo']}.png"
        img.save(out)
    print(f"[genuine] {len(students)} reference signatures -> {config.GENUINE_SIG_DIR}")


# --------------------------------------------------------------------------- #
# Phone-photo simulation
# --------------------------------------------------------------------------- #
def warp_like_photo(pil_img, seed):
    """Place the sheet on a desk background and apply a mild perspective warp."""
    if not HAVE_CV2:
        return pil_img
    rng = np.random.default_rng(seed)
    sheet = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    h, w = sheet.shape[:2]

    # canvas (desk) larger than the sheet, warm off-white like the real photos
    M = int(0.18 * w)
    bg = np.full((h + 2 * M, w + 2 * M, 3), (208, 214, 220), np.uint8)
    bg[M:M + h, M:M + w] = sheet
    H, Wd = bg.shape[:2]

    src = np.float32([[M, M], [M + w, M], [M + w, M + h], [M, M + h]])
    j = 0.06
    dst = src + rng.uniform(-j, j, src.shape) * np.float32([Wd, H])
    tf = cv2.getPerspectiveTransform(src, dst.astype(np.float32))
    warped = cv2.warpPerspective(bg, tf, (Wd, H),
                                 borderValue=(208, 214, 220))
    # lighting + sensor noise
    warped = np.clip(warped.astype(np.float32) * rng.uniform(0.9, 1.0)
                     + rng.normal(0, 4, warped.shape), 0, 255).astype(np.uint8)
    return Image.fromarray(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB))


# --------------------------------------------------------------------------- #
# Sheet generation
# --------------------------------------------------------------------------- #
def generate_sheets(template, students, sessions, do_warp=True):
    sig_cells = geometry.signature_cells()
    aligned_dir = config.GENERATED_DIR / "_aligned"
    aligned_dir.mkdir(parents=True, exist_ok=True)

    idx_by_row = {int(s["row"]): s for s in students}

    for sess in sessions:
        date = sess["date"]
        present = PRESENT.get(date, [])
        sheet = template.copy()
        d = ImageDraw.Draw(sheet)

        # info-table values
        info = geometry.info_table_cells()
        _text_in(d, info["Date_val"], ".".join(reversed(date.split("-"))),
                 _font(20), align="left", fill=(15, 40, 150))
        _text_in(d, info["Time_val"], f"{sess['start']}-{sess['end']}",
                 _font(15), align="center", fill=(15, 40, 150))
        _text_in(d, info["Lecturer_val"], "Dr. Rasika",
                 _font(20), align="left", fill=(15, 40, 150))
        draw_signature(d, geometry.lecturer_signature_cell(),
                       seed=777, colour_rgb=INK_RGB["Blue"])

        # student signatures
        for row in present:
            stu = idx_by_row[row]
            colour = INK_CYCLE[(row - 1) % len(INK_CYCLE)]
            seed = int(stu["indexNo"])
            if (date, row) == FORGERY:
                seed += 500000            # different hand -> low SSIM
            draw_signature(d, sig_cells[row], seed=seed,
                           colour_rgb=INK_RGB[colour], jitter=0.05)

        name = sess["image"]
        sheet.save(aligned_dir / name)
        final = warp_like_photo(sheet, seed=hash(date) & 0xFFFF) if do_warp else sheet
        final.save(config.GENERATED_DIR / name)
        print(f"[sheet] {date}  present={present}  -> {name}"
              + ("  (+forgery)" if date == FORGERY[0] else ""))

    print(f"[done] aligned ground-truth in {aligned_dir}")
    print(f"[done] phone-photo inputs in {config.GENERATED_DIR}")


def write_ground_truth_csv(students, sessions):
    """
    Emit data/output/attendance.csv describing the *true* attendance we drew.
    Visualizations read this until Member 6's real database exists, so every
    chart is testable today. Columns:
        date, student_id, index_no, name, present, ink_colour, forged
    """
    idx_by_row = {int(s["row"]): s for s in students}
    rows = []
    for sess in sessions:
        date = sess["date"]
        present = PRESENT.get(date, [])
        for row in range(1, geometry.N_STUDENTS + 1):
            stu = idx_by_row[row]
            is_present = row in present
            colour = INK_CYCLE[(row - 1) % len(INK_CYCLE)] if is_present else ""
            forged = 1 if (date, row) == FORGERY else 0
            rows.append({
                "date": date,
                "student_id": stu["id"],
                "index_no": stu["indexNo"],
                "name": stu["name"],
                "present": int(is_present),
                "ink_colour": colour,
                "forged": forged,
            })
    out = config.OUTPUT_DIR / "attendance.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    header = "date,student_id,index_no,name,present,ink_colour,forged"
    lines = [header] + [
        f'{r["date"]},{r["student_id"]},{r["index_no"]},"{r["name"]}",'
        f'{r["present"]},{r["ink_colour"]},{r["forged"]}'
        for r in rows
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[csv] ground-truth attendance -> {out}")


def main():
    ap = argparse.ArgumentParser(description="Generate synthetic signing sheets")
    ap.add_argument("--no-warp", action="store_true",
                    help="skip phone-photo perspective simulation")
    args = ap.parse_args()

    subj, students, sessions = load_info()
    template = draw_template(subj, students)
    render_genuine_signatures(students)
    generate_sheets(template, students, sessions, do_warp=not args.no_warp)
    write_ground_truth_csv(students, sessions)
    if not HAVE_CV2 and not args.no_warp:
        print("[warn] OpenCV not available -> phone-photo warp skipped.")


if __name__ == "__main__":
    main()
