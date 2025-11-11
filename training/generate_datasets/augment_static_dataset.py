import os
from PIL import Image, ImageEnhance
import random

AUGMENT_CLASSES = ['2', '6', 'm', 'n', 'p', 'q', 'w']
INPUT_FOLDER = 'training/dataset_multimedia/dataset_static'
OUTPUT_FOLDER = 'training/dataset_multimedia/dataset_static_augmented'
AUGMENTATIONS_PER_IMAGE = 3

for cls in AUGMENT_CLASSES:
    os.makedirs(os.path.join(OUTPUT_FOLDER, cls), exist_ok=True)

def augment_image(img):
    variants = []

    angle = random.uniform(-15, 15)
    variants.append(img.rotate(angle))

    scale = random.uniform(1.0, 1.2)
    w, h = img.size
    resized = img.resize((int(w * scale), int(h * scale)))
    cropped = resized.crop((0, 0, w, h))
    variants.append(cropped)

    enhancer = ImageEnhance.Brightness(img)
    brightness = random.uniform(0.7, 1.3)
    variants.append(enhancer.enhance(brightness))

    return variants

for cls in AUGMENT_CLASSES:
    class_path = os.path.join(INPUT_FOLDER, cls)
    output_class_path = os.path.join(OUTPUT_FOLDER, cls)

    if not os.path.exists(class_path):
        print(f"⚠️ Carpeta no encontrada: {class_path}")
        continue

    for fname in os.listdir(class_path):
        if not fname.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue

        img_path = os.path.join(class_path, fname)
        img = Image.open(img_path).convert("RGB")
        augmented = augment_image(img)

        for idx, aug in enumerate(augmented):
            out_name = f"{os.path.splitext(fname)[0]}_aug{idx}.jpg"
            aug.save(os.path.join(output_class_path, out_name))

print("✅ Augmentación completada.")