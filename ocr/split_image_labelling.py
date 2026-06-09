import numpy as np
from matplotlib import pyplot as plt
import cv2 as cv
import preprocess as pp
import os
from pathlib import Path
from PIL import Image
from digit_recog.digit_api import classify_digit
#for when the image has been preprocessed, ie. we have a 2d image of the sudoku
DEBUG = True
def split(img:np.array, n:int, k:int):
    #image is known to be square because of preprocessing
    side_length=img.shape[0]
    slice_size=(int)(side_length/(n*k))
    border_size=(int)(slice_size/10)
    curr_x=0
    curr_y=0
    cells=[]
    for i in range(n*k):
        for j in range(n*k):
            cells.append(img[max(0,curr_x-border_size):min(side_length,curr_x+slice_size+border_size), max(0,curr_y-border_size):min(side_length,curr_y+slice_size+border_size)])
            curr_y+=slice_size
        curr_x+=slice_size
        curr_y=0
    return cells

# only used for testing, can be deleted
def show_split(cells: list):
    n = int(np.ceil(np.sqrt(len(cells))))
    fig, axes = plt.subplots(n, n, figsize=(8, 8))
    axes = axes.flatten()
    
    for i, cell in enumerate(cells):
        axes[i].imshow(cell, cmap='gray')
        axes[i].axis('off')
        
    for i in range(len(cells), len(axes)):
        axes[i].axis('off')
        
    plt.tight_layout()
    plt.show()

def show_labeled(labeled: list):
    """Display cells in a grid with their predicted labels overlaid.
    
    Args:
        labeled: list of (cell, label, confidence) tuples from label_cells().
    """
    n = int(np.ceil(np.sqrt(len(labeled))))
    fig, axes = plt.subplots(n, n, figsize=(8, 8))
    axes = axes.flatten()
    
    for i, (cell, label, conf) in enumerate(labeled):
        axes[i].imshow(cell, cmap='gray')
        axes[i].axis('off')
        # Overlay the predicted digit, centered, with a contrasting style
        text = str(label) if label != 0 else ""
        axes[i].text(0.5, 0.5, text, fontsize=14, ha='center', va='center',
                     transform=axes[i].transAxes,
                     color='red', fontweight='bold')
        
    for i in range(len(labeled), len(axes)):
        axes[i].axis('off')
        
    plt.tight_layout()
    plt.show()

# only used for testing, can be deleted
def thresh(cells:list):
    theshed=[]
    for cell in cells:
        # Convert to grayscale for thresholding
        gray_cell = cv.cvtColor(cell, cv.COLOR_BGR2GRAY)
        # Threshhold to avoid shadows messing with number detection
        thresh_cell = cv.adaptiveThreshold(
            gray_cell, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv.THRESH_BINARY_INV, 9, 10)
        theshed.append(thresh_cell)
    return theshed
        
        
def determine_cells_with_numbers(cells):
    cell_length=cells[0].shape[0]
    cells_with_numbers=[]
    artificial_border=int(cell_length*0.3)
    allowed_miscolor=int((cell_length-2*artificial_border)**2*0.05)
    for cell in cells:
        # Convert to grayscale for thresholding
        gray_cell = cv.cvtColor(cell, cv.COLOR_BGR2GRAY)
        # Threshhold to avoid shadows messing with number detection
        thresh_cell = cv.adaptiveThreshold(
            gray_cell, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv.THRESH_BINARY_INV, 9, 10)
        cell_total=0
        added=False
        for row in range(artificial_border,cell_length-artificial_border):
            for pixel in range(artificial_border,cell_length-artificial_border):
                if thresh_cell[row][pixel] > 0:
                    cell_total += 1
                    if cell_total > allowed_miscolor:
                        cells_with_numbers.append(cell)
                        added=True
                        break # exits pixel
            if added: break # exits row
    return cells_with_numbers

def _cell_has_digit(cell):
    """Quick heuristic: does this cell likely contain a digit?"""
    cell_length = cell.shape[0]
    gray = cv.cvtColor(cell, cv.COLOR_BGR2GRAY)
    thresh = cv.adaptiveThreshold(
        gray, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv.THRESH_BINARY_INV, 9, 10)
    border = int(cell_length * 0.2)
    allowed = int((cell_length - 2 * border) ** 2 * 0.05)
    count = 0
    for row in range(border, cell_length - border):
        for px in range(border, cell_length - border):
            if thresh[row, px] > 0:
                count += 1
                if count > allowed:
                    return True
    return False

def label_cells(cells, confidence_threshold=0.5):
    """Classify each cell using the digit recognition model.

    Only cells that appear to contain a digit (via threshold heuristic)
    are forwarded to the model; blank cells are labelled 0 directly.

    Args:
        cells: list of numpy arrays (BGR cell images from split()).
        confidence_threshold: minimum top-1 confidence to accept a digit.
                              Below this threshold, label is set to 0 (blank).

    Returns:
        list of (cell, label, confidence) tuples, one per input cell, in order.
        label 0 means blank / undetected.
    """
    # Phase 1 — identify cells that actually contain a digit
    has_digit = [_cell_has_digit(c) for c in cells]
    digit_indices = [i for i, v in enumerate(has_digit) if v]

    # Phase 2 — convert digit cells to PIL Images for the digit API
    cells_pil = []
    for i in digit_indices:
        cell = cells[i]
        if cell.ndim == 2:
            cells_pil.append(Image.fromarray(cell, mode='L'))
        elif cell.ndim == 3 and cell.shape[2] == 3:
            gray = cv.cvtColor(cell, cv.COLOR_BGR2GRAY)
            cells_pil.append(Image.fromarray(gray, mode='L'))
        else:
            raise ValueError(f"Unsupported cell shape: {cell.shape}")

    # Phase 3 — classify only digit cells
    predictions = classify_digit(cells_pil) if cells_pil else []

    # Phase 4 — assemble results
    results = [(cells[i], 0, 0.0) for i in range(len(cells))]
    for idx_in, idx_out in enumerate(digit_indices):
        top = predictions[idx_in][0]
        label = top["digit"] if top["confidence"] >= confidence_threshold else 0
        results[idx_out] = (cells[idx_out], label, top["confidence"])

    return results

if __name__ == "__main__":
    n, k = 3, 3
    
    # Get the directory where this script is located (sudokudo/ocr)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Construct the path to the image relative to the script's directory
    img_path = os.path.join(script_dir, "test_images/outrageous_images", "testTP.png")
    
    img = pp.load_image(img_path)
    if img is not None:
        flat_img = pp.do_preprocess(img)
        cells = split(flat_img, n, k)
        labeled = label_cells(cells)
        
        # Export all cells that failed the confidence threshold (heuristic said
        # there's a digit but the model wasn't sure) for manual inspection.
        out_dir = Path(script_dir) / "failing_cells"
        out_dir.mkdir(exist_ok=True)
        for idx, (cell, label, conf) in enumerate(labeled):
            row, col = divmod(idx, n * k)
            if label == 0 and _cell_has_digit(cell):
                gray = cv.cvtColor(cell, cv.COLOR_BGR2GRAY)
                Image.fromarray(gray, mode='L').save(
                    out_dir / f"fail_r{row}_c{col}_conf{conf:.3f}.png"
                )
        
        # Figure 1 — thresholded cells (original view)
        show_split(thresh(cells))
        
        # Figure 2 — cells with predicted labels overlaid in red
        show_labeled(labeled)
        
        # Also print the grid to terminal
        print("Sudoku grid (0 = blank):")
        for i in range(n * k):
            row_digits = []
            for j in range(n * k):
                _, label, conf = labeled[i * (n * k) + j]
                row_digits.append(str(label))
            print(" ".join(row_digits))