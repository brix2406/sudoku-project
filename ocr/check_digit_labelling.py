"""
check_digit_labelling.py — Interactive UI to verify digit classifications.

Processes test images (test1–test8), runs grid detection + digit classification,
and presents each cell one-by-one for manual verification.

Controls:
    [Next]       — advance to the next cell
    [Extract]    — save the current cell as a standalone PNG (for finetuning)
    q / Esc      — quit
"""

import sys
from pathlib import Path

import cv2 as cv
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.widgets import Button, TextBox
from PIL import Image

from split_image import extract_numbered_cells
from split_image_labelling import label_cells
# ---------------------------------------------------------------------------
# Image discovery — maps logical test number -> actual file path
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_IMAGE_DIR = _HERE / "test_images"
_OUT_DIR = _HERE / "failing_cells"

# Flexible resolution: test3 is .jpg, test5 has variants, test6 lives in a subdir
IMAGE_MAP: dict[int, Path] = {}

for n in range(1, 9):
    candidates: list[Path] = []
    # direct
    for ext in (".png", ".jpg", ".jpeg"):
        p = _IMAGE_DIR / f"test{n}{ext}"
        if p.exists():
            candidates.append(p)
    # outrageous_images subdir
    p_sub = _IMAGE_DIR / "outrageous_images" / f"test{n}.png"
    if p_sub.exists():
        candidates.append(p_sub)
    # test5 variants
    if n == 5:
        for variant in ("test5full.png", "test5easy.png"):
            p = _IMAGE_DIR / variant
            if p.exists():
                candidates.append(p)

    if candidates:
        IMAGE_MAP[n] = candidates[0]

# ---------------------------------------------------------------------------
# Data: one record per cell across all images
# ---------------------------------------------------------------------------
class CellRecord:
    """Holds one cell's image, its predicted label, and source metadata."""
    __slots__ = ("image", "label", "confidence", "src_name", "row", "col")

    def __init__(self, image: np.ndarray, label: int, confidence: float,
                 src_name: str, row: int, col: int):
        self.image = image
        self.label = label
        self.confidence = confidence
        self.src_name = src_name
        self.row = row
        self.col = col


def process_all_images(image_map=None):
    """Run the pipeline on every image in *image_map* using label_cells."""
    records: list[CellRecord] = []
    n, k = 3, 3
    if image_map is None:
        image_map = IMAGE_MAP

    total = len(image_map)
    for idx, num in enumerate(sorted(image_map), 1):
        path = image_map[num]
        print(f"[{idx}/{total}] Processing {path.name} …", end=" ", flush=True)
        cells = extract_numbered_cells(str(path), n, k)
        if not cells:
            print("no grid found")
            continue
        labeled = label_cells(cells)

        for entry in labeled:
            records.append(CellRecord(
                image=entry['cell'],
                label=entry['label'],
                confidence=entry['confidence'],
                src_name=path.name,
                row=entry['row'],
                col=entry['col'],
            ))
        print(f"done ({len(labeled)} cells)")

    return records

# ---------------------------------------------------------------------------
# Interactive UI
# ---------------------------------------------------------------------------
class VerificationUI:
    """Matplotlib-based cell-by-cell verification tool."""

    def __init__(self, records: list[CellRecord]):
        self.records = records
        self.idx = 0
        self.total = len(records)

        self.fig, (self.ax_img, self.ax_info) = plt.subplots(
            1, 2, figsize=(8, 5),
            gridspec_kw={"width_ratios": [1, 1.2]},
        )
        self.fig.canvas.manager.set_window_title("Digit Classification Verification")

        # ---- Image axis ----
        self.ax_img.set_aspect("equal")
        self.ax_img.axis("off")
        self.img_display = self.ax_img.imshow(np.zeros((50, 50, 3), dtype=np.uint8))

        # ---- Info axis ----
        self.ax_info.axis("off")
        self.info_text = self.ax_info.text(
            0.05, 0.9, "", transform=self.ax_info.transAxes,
            fontsize=12, fontfamily="monospace", verticalalignment="top",
        )
        # ---- Buttons ----
        btn_ax_prev = self.fig.add_axes([0.38, 0.02, 0.15, 0.06])
        btn_ax_next = self.fig.add_axes([0.55, 0.02, 0.15, 0.06])
        btn_ax_extract = self.fig.add_axes([0.72, 0.02, 0.20, 0.06])

        self.btn_prev = Button(btn_ax_prev, "Back", hovercolor="0.9")
        self.btn_next = Button(btn_ax_next, "Next", hovercolor="0.9")
        self.btn_extract = Button(btn_ax_extract, "Extract failing", hovercolor="0.9")

        self.btn_prev.on_clicked(self._on_prev)
        self.btn_next.on_clicked(self._on_next)
        self.btn_extract.on_clicked(self._on_extract)

        # ---- Text box for entering the correct label ----
        tb_ax = self.fig.add_axes([0.62, 0.10, 0.10, 0.05])
        self.correct_label_box = TextBox(tb_ax, "Correct label: ", initial="0")
        self.correct_label_box.on_submit(self._on_label_submitted)

        # ---- Keyboard shortcuts ----
        self.fig.canvas.mpl_connect("key_press_event", self._on_key)

        self._show_cell()
        plt.show()

    def _show_cell(self):
        """Update the display for the current cell."""
        rec = self.records[self.idx]

        # Show cell image (BGR -> RGB for matplotlib)
        img_rgb = cv.cvtColor(rec.image, cv.COLOR_BGR2RGB)
        self.img_display.set_data(img_rgb)
        self.ax_img.set_title(
            f"Cell {self.idx + 1} / {self.total}",
            fontsize=10,
        )
        # Sync the correct-label text box (silently -- set_val fires on_submit)
        self._suppress_save = True
        self.correct_label_box.set_val(str(rec.label))
        self._suppress_save = False

        # Info panel
        pct = rec.confidence * 100
        info = (
            f"Source : {rec.src_name}\n"
            f"Row    : {rec.row}\n"
            f"Col    : {rec.col}\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"Label  : {rec.label}"
        )
        if rec.label != 0:
            info += f"\nConf   : {pct:.1f}%"

        self.info_text.set_text(info)

        # Color the info text based on confidence
        color = "black"
        if rec.label != 0 and rec.confidence < 0.5:
            color = "red"
        elif rec.label == 0:
            color = "gray"
        self.info_text.set_color(color)

        # Also set figure title to make it more obvious from taskbar
        self.fig.canvas.manager.set_window_title(
            f"Verifying {rec.src_name} -- cell ({rec.row},{rec.col}) "
            f"\u2192 {rec.label}"
        )

        self.fig.canvas.draw_idle()

    def _on_next(self, _event=None):
        if self.idx < self.total - 1:
            self.idx += 1
            self._show_cell()
        else:
            print("\u2713 All cells verified. You can close the window.")
            plt.close(self.fig)

    def _on_prev(self, _event=None):
        if self.idx > 0:
            self.idx -= 1
            self._show_cell()

    def _on_extract(self, _event=None):
        """Save the cell with the label currently in the text box, then advance."""
        self._on_label_submitted(self.correct_label_box.text)
        self._on_next()

    def _on_label_submitted(self, text):
        """Save the cell with the user-supplied correct label."""
        if getattr(self, "_suppress_save", False):
            return

        rec = self.records[self.idx]
        _OUT_DIR.mkdir(exist_ok=True)

        try:
            correct = int(text.strip())
        except ValueError:
            correct = rec.label

        stem = Path(rec.src_name).stem
        fname = f"{stem}_r{rec.row}_c{rec.col}_pred{rec.label}_correct{correct}"
        if rec.confidence > 0:
            fname += f"_conf{rec.confidence:.3f}"
        fname += ".png"

        out_path = _OUT_DIR / fname
        # Model expects RGBA; convert BGR -> RGB -> RGBA
        rgb = cv.cvtColor(rec.image, cv.COLOR_BGR2RGB)
        alpha = np.full(rgb.shape[:2], 255, dtype=np.uint8)
        rgba = np.dstack((rgb, alpha))
        Image.fromarray(rgba, mode="RGBA").save(out_path)
        print(f"  Saved \u2192 {out_path.name}  (corrected: {correct})")


    def _on_key(self, event):

        if event.key in ("q", "escape"):
            plt.close(self.fig)
        elif event.key in ("right", "n", "space"):
            self._on_next()
        elif event.key in ("left", "b", "p"):
            self._on_prev()
        elif event.key in ("e", "x"):
            self._on_extract()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Optional CLI: pass a test number to process only that image
    # e.g. python3 check_digit_labelling.py 7
    if len(sys.argv) > 1:
        try:
            num = int(sys.argv[1])
            if num in IMAGE_MAP:
                selected = {num: IMAGE_MAP[num]}
                print(f"Running on: {IMAGE_MAP[num].name}")
            else:
                print(f"Test {num} not found in IMAGE_MAP. Available: {sorted(IMAGE_MAP)}")
                sys.exit(1)
        except ValueError:
            print(f"Usage: {sys.argv[0]} [test_number]")
            sys.exit(1)
    else:
        selected = IMAGE_MAP
        print(f"Found {len(IMAGE_MAP)} test images: {', '.join(p.name for p in IMAGE_MAP.values())}")
    print()
    print("  [Back] / [\u2190/b/p]        \u2014 previous cell")
    print("  [Next] / [\u2192/n/Space]    \u2014 next cell")
    print("  [Extract] / [e/x]       \u2014 save cell as PNG")
    records = process_all_images(selected)
    
    # Only keep cells the model thinks contain a digit
    populated = [r for r in records if r.label != 0]
    skipped = len(records) - len(populated)
    print(f"\nTotal cells: {len(records)}  \u2014  empty/skipped: {skipped}  \u2014  populated: {len(populated)}")
    if not populated:
        print("No populated cells to verify. Exiting.")
        sys.exit(0)
    
    print("  [q/Esc]              \u2014 quit\n")
    VerificationUI(populated)
