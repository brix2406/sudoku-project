import cv2 as cv
import numpy as np
from matplotlib import pyplot as plt

# Global debug flag
DEBUG = True

def load_image(image_path):
    img = cv.imread(image_path)
    if img is None:
        print(f"Error loading image: {image_path}")
        return None
    return img

def is_darkmode(img, threshold: float = 110.0) -> bool:
    """True if the image has a dark background (light-on-dark / dark mode).

    Uses the median grayscale value: the background dominates the pixel
    count, so the median tracks background brightness and is robust to the
    minority of light digit/grid pixels. Measured medians: dark-mode
    screenshot ~23, light-mode sudokus 185-255 — 110 separates with wide margin.
    """
    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return float(np.median(gray)) < threshold

def image_prep(img):
    img_gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    img_blur = cv.GaussianBlur(img_gray, (9, 9), 0)
    thresh = cv.adaptiveThreshold(
            img_blur, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv.THRESH_BINARY_INV, 11, 2)
    return img_blur, thresh

# --- Grid Clustering Logic (For Complex/Adjacent Images) ---
def get_largest_cell_cluster(cell_data):
    if not cell_data: return []

    centers = np.array([[d['cx'], d['cy']] for d in cell_data])
    widths = np.array([d['w'] for d in cell_data])
    heights = np.array([d['h'] for d in cell_data])
    
    n = len(cell_data)
    adj_matrix = np.zeros((n, n), dtype=bool)
    
    for i in range(n):
        dx = np.abs(centers[:, 0] - centers[i, 0])
        dy = np.abs(centers[:, 1] - centers[i, 1])
        
        avg_w = (widths[i] + widths) / 2.0
        avg_h = (heights[i] + heights) / 2.0
        
        is_horiz_neighbor = (dx < 1.3 * avg_w) & (dy < 0.6 * avg_h)
        is_vert_neighbor  = (dx < 0.6 * avg_w) & (dy < 1.3 * avg_h)
        
        adj_matrix[i] = is_horiz_neighbor | is_vert_neighbor
        
    visited = np.zeros(n, dtype=bool)
    components = []
    
    for i in range(n):
        if not visited[i]:
            comp = []
            queue = [i]
            visited[i] = True
            while queue:
                curr = queue.pop(0)
                comp.append(curr)
                neighbors = np.where(adj_matrix[curr])[0]
                for neighbor in neighbors:
                    if not visited[neighbor]:
                        visited[neighbor] = True
                        queue.append(neighbor)
            components.append(comp)
            
    largest_comp = max(components, key=len)
    return [cell_data[i] for i in largest_comp]



def find_sudoku_grid(img, thresh, DEBUG=False):
    kernel = cv.getStructuringElement(cv.MORPH_RECT, (3, 3))
    thresh_dilated = cv.dilate(thresh, kernel, iterations=1)

    img_area = img.shape[0] * img.shape[1]
    sudoku_corners = None

    # ====================================================================
    # ATTEMPT 1: Advanced Topological Grid Clustering (Handles test1, test2)
    # ====================================================================
    contours, hierarchy = cv.findContours(thresh_dilated, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE)

    if hierarchy is not None:
        hierarchy = hierarchy[0] 
        cnts_with_info = []

        for i, c in enumerate(contours):
            area = cv.contourArea(c)
            if 0.05 * img_area < area < 0.95 * img_area:
                cnts_with_info.append((area, c, i))

        cnts_with_info = sorted(cnts_with_info, key=lambda x: x[0], reverse=True)

        for area, c, i in cnts_with_info:
            child_idx = hierarchy[i][2] 
            valid_cell_contours = []
            
            while child_idx != -1:
                child_c = contours[child_idx]
                child_area = cv.contourArea(child_c)
                
                if (area / 400) < child_area < (area / 10):
                    valid_cell_contours.append(child_c)
                    
                child_idx = hierarchy[child_idx][0] 

            if len(valid_cell_contours) < 40:
                continue 

            cell_data = []
            for cc in valid_cell_contours:
                x, y, w, h = cv.boundingRect(cc)
                cx, cy = x + w/2.0, y + h/2.0
                cell_data.append({'cx': cx, 'cy': cy, 'w': w, 'h': h, 'contour': cc})

            main_grid_cells = get_largest_cell_cluster(cell_data)

            if len(main_grid_cells) >= 40:
                filtered_contours = [d['contour'] for d in main_grid_cells]
                all_pts = np.vstack(filtered_contours).reshape(-1, 2)
                
                s = all_pts.sum(axis=1)
                diff = np.diff(all_pts, axis=1)

                top_left = all_pts[np.argmin(s)]
                bottom_right = all_pts[np.argmax(s)]
                top_right = all_pts[np.argmin(diff)]
                bottom_left = all_pts[np.argmax(diff)]
                
                sudoku_corners = np.array([[top_left], [top_right], [bottom_right], [bottom_left]], dtype=np.int32)
                if DEBUG: print("Found grid using ATTEMPT 1: Topological Clustering")
                break

    # ====================================================================
    # ATTEMPT 2: Classic Polygon Search Fallback (Handles test3)
    # ====================================================================
    if sudoku_corners is None:
        if DEBUG: print("Attempt 1 failed. Falling back to ATTEMPT 2: Classic Polygon Search")
        
        contours_fallback, _ = cv.findContours(thresh_dilated, cv.RETR_LIST, cv.CHAIN_APPROX_SIMPLE)
        contours_fallback = sorted(contours_fallback, key=cv.contourArea, reverse=True)

        for c in contours_fallback:
            area = cv.contourArea(c)
            
            if area < (img_area * 0.05):
                continue

            perimeter = cv.arcLength(c, True)
            approx = cv.approxPolyDP(c, 0.02 * perimeter, True)

            if len(approx) == 4:
                sudoku_corners = approx
                break

    # Drawing 
    if DEBUG: 
        draw_with_contours(img, sudoku_corners, thresh)

    return sudoku_corners


def draw_with_contours(img, sudoku_corners, thresh):
    img_with_contours = img.copy()

    if sudoku_corners is not None:
        cv.polylines(img_with_contours, [sudoku_corners], isClosed=True, color=(40, 190, 244), thickness=10)
    else:
        print("Could not find a 4-sided Sudoku grid.")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))
    ax1.imshow(thresh, cmap="gray")
    ax1.set_title("Standard Threshold")
    ax2.imshow(cv.cvtColor(img_with_contours, cv.COLOR_BGR2RGB))
    ax2.set_title("Final 9x9 Bounding Box")
    plt.show()

def flatten_img(img, sudoku_corners):
    pts = sudoku_corners.reshape(4, 2)
    rect = np.zeros((4, 2), dtype="float32")
    
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    
    dst = np.array([[0, 0], [449, 0], [449, 449], [0, 449]], dtype="float32")
    
    matrix = cv.getPerspectiveTransform(rect, dst)
    flattened = cv.warpPerspective(img, matrix, (450, 450))
    return flattened

def show_flattened(image: np.ndarray, title: str = "OpenCV DEBUG") -> None:
    plt.figure(figsize=(8, 8))
    plt.title(title)
    if len(image.shape) == 3:
        display_img = cv.cvtColor(image, cv.COLOR_BGR2RGB)
        plt.imshow(display_img)
    else:
        plt.imshow(image, cmap="gray")
    plt.axis("off")
    plt.show()

def do_preprocess(img, DEBUG=False):
    if is_darkmode(img):
        if DEBUG:
            print("Dark mode detected — inverting image")
        img = cv.bitwise_not(img)
    img_ready, thresh = image_prep(img)
    
    sudoku_corners = find_sudoku_grid(img, thresh, DEBUG=DEBUG)
    
    if sudoku_corners is not None:
        flat_img = flatten_img(img, sudoku_corners)
        
        if DEBUG: 
            show_flattened(flat_img, "Flattened Sudoku Grid")
            
        return flat_img
    else:
        print("Warning: Could not isolate Sudoku grid. Returning None.")
        return None

if __name__ == "__main__":
    img = load_image("test_images/test1.png")
    if img is not None:
        do_preprocess(img, DEBUG=DEBUG)