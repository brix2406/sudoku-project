import os
import requests
import sys

# Change this to match wherever your Flask app is running
API_URL = "http://localhost:5000/solve-image"

def print_boards_side_by_side(original, solved):
    print("\n   Original Board          Solved Board")
    print(" -------------------     -------------------")
    
    for r in range(9):
        # Format the rows nicely, replacing "." with a dim dash for readability
        orig_row = " ".join(original[r]).replace(".", "-")
        sol_row = " ".join(solved[r])
        
        # Add the vertical dividers for that classic Sudoku look
        orig_fmt = f"{orig_row[:5]}|{orig_row[6:11]}|{orig_row[12:]}"
        sol_fmt = f"{sol_row[:5]}|{sol_row[6:11]}|{sol_row[12:]}"
        
        print(f"  {orig_fmt}   ==>   {sol_fmt}")
        
        # Add horizontal dividers
        if r == 2 or r == 5:
            print(" -------+-----+-------   -------+-----+-------")
    print("\n")

if __name__ == "__main__":
    # Point this to one of your real test images!
    current_dir = os.path.dirname(os.path.abspath(__file__))
    image_path = os.path.abspath(os.path.join(current_dir, "../../ocr/test_images/test2.png"))
    
    if not os.path.exists(image_path):
        print(f" Error: Could not find image at {image_path}")
        sys.exit(1)

    print(f"🚀 Sending '{os.path.basename(image_path)}' to {API_URL}...")
    
    try:
        # Open the image as raw bytes and POST it to Flask
        with open(image_path, "rb") as f:
            files = {"image": f}
            response = requests.post(API_URL, files=files)
            
        if response.status_code == 200:
            data = response.json()
            print(" Success! Pipeline returned a solution.")
            print_boards_side_by_side(data["original_board"], data["solved_board"])
        else:
            print(f" API Error ({response.status_code}):")
            print(response.json())
            
    except requests.exceptions.ConnectionError:
        print(" Error: Could not connect to the API. Is your Flask server running?")