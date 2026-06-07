from digit_recog.digit_api import classify_digit
from PIL import Image

img = Image.open("ocr/test_images/test1.png")

print(classify_digit(img))
