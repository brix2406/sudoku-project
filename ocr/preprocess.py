import cv2 as cv
import numpy as np
from matplotlib import pyplot as plt

DEBUG=True

def load_image(image_path):
    img = cv.imread(image_path)
    if img is None:
        print(f"Error loading image: {image_path}")
        return
    return img

def image_prep(img):
    # Convert image to grayscale
    img_gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

    # Apply gaussian blur to avoid small irregularities causing incorrect detection
    img_blur = cv.GaussianBlur(img_gray, (9, 9), 0)

    # Standard adaptive threshold
    thresh = cv.adaptiveThreshold(
            img_blur, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv.THRESH_BINARY_INV, 11, 2)
    return img_blur,thresh

def find_sudoku_grid(img,thresh,DEBUG=False):
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
            if DEBUG: draw_with_contours(img,sudoku_corners,thresh)
            return sudoku_corners
    return None


# Show original image with contours next to thresh
def draw_with_contours(img, sudoku_corners, thresh):
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
    return sudoku_corners

def flatten_img (img, sudoku_corners):

    # Reshape and order corners: top-left, top-right, bottom-right, bottom-left
    pts = sudoku_corners.reshape(4, 2)
    rect = np.zeros((4, 2), dtype="float32")
    
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    
    # Define the destination points for a flat 450x450 image
    dst = np.array([
        [0, 0],
        [449, 0],
        [449, 449],
        [0, 449]
    ], dtype="float32")
    
    # Calculate the perspective transform matrix and apply it
    matrix = cv.getPerspectiveTransform(rect, dst)
    flattened = cv.warpPerspective(img, matrix, (450, 450))
    return flattened

def show_flattened(image: np.ndarray, title: str = "OpenCV DEBUG") -> None:
    # Initialize a properly sized plot
    plt.figure(figsize=(8, 8))
    plt.title(title)
    
    # Determine if the image is color (3 dimensions) or grayscale (2 dimensions)
    if len(image.shape) == 3:
        # Convert OpenCV's default BGR format to Matplotlib's RGB format
        display_img = cv.cvtColor(image, cv.COLOR_BGR2RGB)
        plt.imshow(display_img)
    else:
        # Display grayscale image with the correct colormap
        plt.imshow(image, cmap="gray")
        
    # Hide the X and Y axes for a cleaner look at the geometry
    plt.axis("off")
    
    # Render the plot to the screen
    plt.show()

def do_preprocess(img, DEBUG=False):
    img_ready,thresh = image_prep(img)
    sudoku_corners=find_sudoku_grid(img_ready,thresh,DEBUG=DEBUG)
    if sudoku_corners is not None:
        flat_img=flatten_img(img, sudoku_corners)
        if DEBUG: show_flattened(flat_img)
    return flat_img

if __name__ == "__main__":
    img=load_image("test_images/test2.png")
    if img is not None:
        do_preprocess(img)
