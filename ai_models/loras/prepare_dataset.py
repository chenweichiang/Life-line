import os
from PIL import Image

SOURCE_DIR = "../../source images"
TARGET_DIR = "dataset/img/1_lifeline"

CAPTION = "lifeline_art_style, watercolor and ink on textured paper, organic flowing lines, rhythmic dashed brushstrokes, earthy tones, ochre, olive green, rust red, abstract biological, fluid motion"

os.makedirs(TARGET_DIR, exist_ok=True)

def pad_and_resize(img, target_size=1024):
    """將圖片補白為正方形並縮放至 1024x1024，保留紙張邊界"""
    w, h = img.size
    max_dim = max(w, h)
    
    # 使用白色或稍微米黃色的紙張底色來填充
    new_img = Image.new("RGB", (max_dim, max_dim), (250, 250, 245))
    
    # 將原圖貼在正中央
    offset = ((max_dim - w) // 2, (max_dim - h) // 2)
    new_img.paste(img, offset)
    
    # 縮放至 1024x1024
    return new_img.resize((target_size, target_size), Image.Resampling.LANCZOS)

def main():
    if not os.path.exists(SOURCE_DIR):
        print(f"Error: 找不到來源資料夾 {SOURCE_DIR}")
        return

    count = 0
    for file in os.listdir(SOURCE_DIR):
        if not file.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue

        source_path = os.path.join(SOURCE_DIR, file)
        target_name = os.path.splitext(file)[0]
        
        # 1. 影像預處理
        try:
            with Image.open(source_path) as img:
                img = img.convert("RGB")
                processed_img = pad_and_resize(img)
                target_img_path = os.path.join(TARGET_DIR, f"{target_name}.jpg")
                processed_img.save(target_img_path, quality=95)
        except Exception as e:
            print(f"處理圖片失敗 {file}: {e}")
            continue
            
        # 2. 建立標註檔 (.txt)
        target_txt_path = os.path.join(TARGET_DIR, f"{target_name}.txt")
        with open(target_txt_path, "w", encoding="utf-8") as f:
            f.write(CAPTION)
            
        print(f"✓ 已處理: {file}")
        count += 1
        
    print(f"\n完成！共處理 {count} 張圖片及標註檔，存放至 {TARGET_DIR}")

if __name__ == "__main__":
    main()
