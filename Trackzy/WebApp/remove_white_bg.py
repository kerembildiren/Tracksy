"""Remove white background from PNGs and save to static/img for hub."""
import os

try:
    from PIL import Image
except ImportError:
    print("Installing Pillow...")
    import subprocess
    subprocess.check_call(["pip", "install", "Pillow", "-q"])
    from PIL import Image

# Paths to attached images (Cursor assets - files are directly in assets folder)
ASSETS = os.path.join(
    os.path.expanduser("~"),
    ".cursor", "projects", "c-Users-4-Desktop-Cursor-Projects", "assets"
)
BASKETBALL_SRC = os.path.join(ASSETS, "c__Users_4_AppData_Roaming_Cursor_User_workspaceStorage_89a8e28bf13bf3f9ff0a9db49fc53b23_images_Orange_Ball_Icon_Basketball_Logo-2025e9ed-1b30-48ee-986b-aadd8b501612.png")
MIC_SRC = os.path.join(ASSETS, "c__Users_4_AppData_Roaming_Cursor_User_workspaceStorage_89a8e28bf13bf3f9ff0a9db49fc53b23_images_1-7780c530-2b66-4d84-b229-4eb04ea0a52c.png")

OUT_DIR = os.path.join(os.path.dirname(__file__), "static", "img")
BASKETBALL_DST = os.path.join(OUT_DIR, "hub-basketball.png")
MIC_DST = os.path.join(OUT_DIR, "hub-mic.png")

def make_white_transparent(img, threshold=248):
    """Set white/near-white pixels to transparent. threshold: 0-255, higher = more aggressive."""
    img = img.convert("RGBA")
    data = img.getdata()
    new_data = []
    for item in data:
        r, g, b, a = item
        if r >= threshold and g >= threshold and b >= threshold:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)
    img.putdata(new_data)
    return img

def process(src_path, dst_path, name):
    if not os.path.isfile(src_path):
        print(f"Not found: {src_path}")
        return False
    img = Image.open(src_path)
    img = make_white_transparent(img)
    os.makedirs(OUT_DIR, exist_ok=True)
    img.save(dst_path, "PNG")
    print(f"Saved: {name} -> {dst_path}")
    return True

if __name__ == "__main__":
    process(BASKETBALL_SRC, BASKETBALL_DST, "basketball")
    process(MIC_SRC, MIC_DST, "mic")
