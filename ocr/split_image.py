import numpy as np
from matplotlib import pyplot as plt
import cv2 as cv
import preprocess as pp
import os
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
        if len(cell.shape) == 3:
            display_cell = cv.cvtColor(cell, cv.COLOR_BGR2RGB)
            axes[i].imshow(display_cell)
        else:
            axes[i].imshow(cell, cmap='gray')
        axes[i].axis('off')
        
    for i in range(len(cells), len(axes)):
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
            cv.THRESH_BINARY_INV, 11, 10)
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

def extract_numbered_cells(img_input, n: int = 3, k: int = 3):
    """Load, preprocess, split a sudoku image and return every cell.

    Each cell is marked with whether it likely contains a digit.

    Args:
        img_input: Raw image (numpy array from cv.imread) or file path (str).
        n: Number of blocks per row/column (3 for standard sudoku).
        k: Block size in cells (3 for standard sudoku).

    Returns:
        List of dicts with keys 'row', 'col', 'cell', 'has_digit'.
        Returns empty list if grid isolation fails.
    """
    if isinstance(img_input, str):
        img = pp.load_image(img_input)
        if img is None:
            return []
    else:
        img = img_input

    grid_img = pp.do_preprocess(img)
    if grid_img is None:
        return []

    cells = split(grid_img, n, k)
    grid_size = n * k

    all_cells = []
    numbered_set = {id(c) for c in determine_cells_with_numbers(cells)}

    for idx, cell in enumerate(cells):
        all_cells.append({
            'row': idx // grid_size,
            'col': idx % grid_size,
            'cell': cell,
            'has_digit': id(cell) in numbered_set,
        })
    return all_cells

if __name__ == "__main__":
    n, k = 3, 3
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    img_path = os.path.join(script_dir, "test_images", "test1.png")
    
    cells = extract_numbered_cells(img_path, n, k)
    if cells:
        digit_cells = [c for c in cells if c['has_digit']]
        print(f"Grid: {len(cells)} total cells, {len(digit_cells)} with detected digits")
        for entry in cells:
            flag = 'D' if entry['has_digit'] else '.'
            print(f"  [{flag}] row={entry['row']}, col={entry['col']}")
        show_split([entry['cell'] for entry in cells])
    else:
        print("Grid isolation failed.")
    
    ## Old inline code:
    # img = pp.load_image(img_path)
    # if img is not None:
    #     flat_img = pp.do_preprocess(img)
    #     cells = split(flat_img, n, k)
    #     show_split(thresh(cells))
    #     number_cells = determine_cells_with_numbers(cells)
    #     show_split(number_cells)