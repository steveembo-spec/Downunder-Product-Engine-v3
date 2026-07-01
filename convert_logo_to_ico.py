#!/usr/bin/env python3
"""
Convert PNG logo to Windows ICO format for PyInstaller.

Usage:
    python convert_logo_to_ico.py

Output:
    assets/logo.ico
"""

from pathlib import Path
from PIL import Image

def convert_logo_to_ico():
    """Convert assets/logo.png to assets/logo.ico"""
    
    project_root = Path(__file__).resolve().parent
    png_path = project_root / "assets" / "logo.png"
    ico_path = project_root / "assets" / "logo.ico"
    
    if not png_path.exists():
        print(f"ERROR: {png_path} not found")
        return False
    
    try:
        # Open the PNG image
        img = Image.open(png_path)
        
        # Convert to RGB if necessary (ICO doesn't support RGBA for all formats)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        
        # Resize to 256x256 (standard for Windows icons)
        img = img.resize((256, 256), Image.Resampling.LANCZOS)
        
        # Save as ICO
        img.save(ico_path, format='ICO')
        
        print(f"✓ Successfully converted {png_path.name} to {ico_path.name}")
        print(f"✓ Icon size: 256x256 pixels")
        print(f"✓ Output: {ico_path}")
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to convert logo: {e}")
        return False

if __name__ == "__main__":
    convert_logo_to_ico()
