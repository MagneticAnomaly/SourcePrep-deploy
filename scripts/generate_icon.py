from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(path):
    size = (1024, 1024)
    color = (0, 122, 255) # System Blue
    img = Image.new('RGBA', size, color)
    draw = ImageDraw.Draw(img)
    
    # Draw simple text or shape
    # Just a white circle
    margin = 100
    draw.ellipse([margin, margin, size[0]-margin, size[1]-margin], fill=(255, 255, 255))
    
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    print(f"Created square icon at {path}")

if __name__ == "__main__":
    create_icon("src/codrag/dashboard/src-tauri/icons/icon.png")
