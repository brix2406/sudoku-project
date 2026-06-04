import cv2 as cv
import numpy as np
from matplotlib import pyplot as plt

def find_sudoku_grid(image_path):
    img = cv.imread(image_path)
    if img is None:
        print(f"Error loading image: {image_path}")
        return

    img_gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    img_blur = cv.GaussianBlur(img_gray, (9, 9), 0)

    # Standard adaptive threshold
    thresh = cv.adaptiveThreshold(
            img_blur, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv.THRESH_BINARY_INV, 11, 2
    )

    # Optional but highly recommended: 
    # Dilate slightly to connect broken lines in the thresholded grid
    kernel = cv.getStructuringElement(cv.MORPH_RECT, (3, 3))
    thresh_dilated = cv.dilate(thresh, kernel, iterations=1)

    # --- NEW PHASE: Top-Down Largest Polygon Search ---
    
    # Find all contours (RETR_LIST ensures we don't just grab a black page border)
    contours, _ = cv.findContours(thresh_dilated, cv.RETR_LIST, cv.CHAIN_APPROX_SIMPLE)

    # Sort contours by area in descending order (largest first)
    contours = sorted(contours, key=cv.contourArea, reverse=True)

    sudoku_corners = None

    # Look for the largest contour that has exactly 4 corners
    for c in contours:
        area = cv.contourArea(c)
        
        # Ignore tiny contours that are obviously just text or noise
        if area < (img.shape[0] * img.shape[1] * 0.05):
            continue

        # Approximate the contour shape to a simpler polygon
        perimeter = cv.arcLength(c, True)
        
        # 0.02 is a standard tuning parameter for how strictly to approximate corners
        approx = cv.approxPolyDP(c, 0.02 * perimeter, True)

        # If the approximated contour has exactly 4 points, it's our Sudoku board!
        if len(approx) == 4:
            sudoku_corners = approx
            break

    # --- Drawing and Plotting ---
    img_with_contours = img.copy()

    if sudoku_corners is not None:
        # Draw the final outer bounding box in GREEN
        cv.polylines(img_with_contours, [sudoku_corners], isClosed=True, color=(0, 255, 0), thickness=5)
    else:
        print("Could not find a 4-sided Sudoku grid.")

    # Show the results!
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))
    
    ax1.imshow(thresh, cmap="gray")
    ax1.set_title("Standard Threshold")
    
    ax2.imshow(cv.cvtColor(img_with_contours, cv.COLOR_BGR2RGB))
    ax2.set_title("Final 9x9 Bounding Box")
    
    plt.show()

if __name__ == "__main__":
    find_sudoku_grid("test_images/test2.png")