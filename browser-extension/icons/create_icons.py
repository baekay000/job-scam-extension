from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, text, filename):
    # Create a new image with a blue background
    img = Image.new('RGB', (size, size), color='#2563eb')
    draw = ImageDraw.Draw(img)
    
    # Try to use a font, fallback to default
    try:
        # You might need to adjust the font path for your system
        font = ImageFont.truetype("Arial", size-8)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size-8)
        except:
            font = ImageFont.load_default()
    
    # Calculate text position (centered)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    
    # Draw the text
    draw.text((x, y), text, fill='white', font=font)
    
    # Save the image
    img.save(filename)
    print(f"Created {filename}")

# Create all required icons
create_icon(16, "J", "icons/icon16.png")
create_icon(48, "JT", "icons/icon48.png") 
create_icon(128, "JOB", "icons/icon128.png")

print("✅ All icons created successfully!")
