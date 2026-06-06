import numpy as np
from matplotlib import pyplot as plt
import preprocess as pp
#for when the image has been preprocessed, ie. we have a 2d image of the sudoku
DEBUG = True
def split(img:np.array, n:int, k:int):
    #image is known to be square because of preprocessing
    side_length=img.shape[0]
    slice_size=(int)(side_length/(n*k))
    border_size=(int)(slice_size/8)
    curr_x=0
    curr_y=0
    cells=[]
    for i in range(n*k):
        for j in range(n*k):
            cells.append(img[curr_x+border_size:curr_x+slice_size-border_size, curr_y+border_size:curr_y+slice_size-border_size])
            curr_y+=slice_size
        curr_x+=slice_size
        curr_y=0
    return cells

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

if __name__ == "__main__":
    n,k=3,3
    img=pp.load_image("test_images/test2.png")
    if img is not None:
        flat_img=pp.do_preprocess(img)
        cells=split(flat_img,n,k)
        show_split(cells)
