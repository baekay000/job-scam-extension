from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, text, filename):
    # Create a new image with a blue background
    img = Image.new('RGB', (size, size), color='#2563eb')
    draw = ImageDraw.Draw(img)
    
    # Try to use different fonts
    font_size = max(size - 8, 8)  # Ensure font size is at least 8
    
    try:
        # Try Arial first (common on Mac)
        font = ImageFont.truetype("/Library/Fonts/Arial.ttf", font_size)
    except:
        try:
            # Try system font
            font = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", font_size)
        except:
            try:
                # Try Helvetica
                font = ImageFont.truetype("/Library/Fonts/Helvetica.ttf", font_size)
            except:
                # Use default font as last resort
                font = ImageFont.load_default()
    
    # Calculate text position (centered)
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except:
        # Fallback if textbbox fails
        text_width = size // 2
        text_height = size // 2
    
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    
    # Draw the text
    draw.text((x, y), text, fill='white', font=font)
    
    # Save the image
    img.save(filename)
    print(f"✅ Created {filename} ({size}x{size})")

# Make sure icons directory exists
os.makedirs('icons', exist_ok=True)

# Create all required icons
create_icon(16, "J", "icons/icon16.png")
create_icon(48, "JT", "icons/icon48.png") 
create_icon(128, "JOB", "icons/icon128.png")

print("🎉 All icons created successfully!")
print("📁 Icons are in: browser_extension/icons/")
