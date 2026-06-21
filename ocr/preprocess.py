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

def image_prep(img):
    img_gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    blur_k = getattr(image_prep, '_tune_blur', None) or 9
    img_blur = cv.GaussianBlur(img_gray, (blur_k, blur_k), 0)
    block = getattr(image_prep, '_tune_block', None)
    block = block if block is not None else 11
    c = getattr(image_prep, '_tune_c', None)
    c = c if c is not None else 2
    thresh = cv.adaptiveThreshold(
            img_blur, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv.THRESH_BINARY_INV, block, c)
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
    dilate_iters = getattr(find_sudoku_grid, '_tune_dilate', None)
    dilate_iters = dilate_iters if dilate_iters is not None else 1
    thresh_dilated = cv.dilate(thresh, kernel, iterations=dilate_iters)


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

                # Reject clusters that don't span a full 9x9 — peripheral cells
                # (e.g. coloured border cells in Unknown.png) sometimes fail to
                # threshold as separate contours, shrinking the box. A complete
                # grid spans ~9 median cells per side; require >= 8 (tolerates one
                # clipped edge) so incomplete clusters fall through to ATTEMPT 2.
                _, _, cl_w, cl_h = cv.boundingRect(all_pts)
                med_w = np.median([d['w'] for d in main_grid_cells])
                med_h = np.median([d['h'] for d in main_grid_cells])
                if cl_w < 8.0 * med_w or cl_h < 8.0 * med_h:
                    if DEBUG:
                        print(f"ATTEMPT 1 cluster incomplete ({cl_w/med_w:.1f}x{cl_h/med_h:.1f} cells); skipping")
                    continue
                
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

    # ====================================================================
    # ATTEMPT 3: Edge-to-edge digital grid (fills the frame, no outer border).
    # Handles screenshots like failing2.png. Last resort: only fires when a
    # dense cluster of cell-sized blobs covers most of a roughly-square frame,
    # so genuine no-grid images still return None (-> worker saves the failure).
    # ====================================================================
    if sudoku_corners is None:
        h, w = img.shape[:2]
        if 0.8 < (w / h) < 1.25:
            blob_data = []
            for c in contours_fallback:
                a = cv.contourArea(c)
                if 0.0005 * img_area < a < 0.05 * img_area:
                    x, y, bw, bh = cv.boundingRect(c)
                    blob_data.append({'cx': x + bw / 2.0, 'cy': y + bh / 2.0,
                                      'w': bw, 'h': bh, 'contour': c})
            if len(blob_data) >= 40:
                cluster = get_largest_cell_cluster(blob_data)
                if len(cluster) >= 40:
                    pts = np.vstack([d['contour'] for d in cluster]).reshape(-1, 2)
                    _, _, cbw, cbh = cv.boundingRect(pts)
                    if (cbw * cbh) / img_area >= 0.5:
                        sudoku_corners = np.array(
                            [[[0, 0]], [[w - 1, 0]], [[w - 1, h - 1]], [[0, h - 1]]],
                            dtype=np.int32)
                        if DEBUG:
                            print("Found grid using ATTEMPT 3: Full-frame fallback")

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
    img_ready, thresh = image_prep(img)
    
    sudoku_corners = find_sudoku_grid(img, thresh, DEBUG=DEBUG)
    
    if sudoku_corners is not None:
        flat_img = flatten_img(img, sudoku_corners)
        
        if DEBUG: 
            show_flattened(flat_img, "Flattened Sudoku Grid")
            
        return flat_img, sudoku_corners
    else:
        print("Warning: Could not isolate Sudoku grid. Returning None.")
        return None, None

if __name__ == "__main__":
    img = load_image("test_images/test1.png")
    if img is not None:
        do_preprocess(img, DEBUG=DEBUG)