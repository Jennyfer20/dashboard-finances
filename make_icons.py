from PIL import Image, ImageDraw

sizes = [72, 96, 128, 144, 152, 192, 384, 512]

for s in sizes:
    img = Image.new("RGB", (s, s), "#3b82f6")
    d = ImageDraw.Draw(img)
    d.text((int(s * 0.18), int(s * 0.22)), "BL", fill="white", font_size=int(s * 0.4))
    img.save(f"static/icon-{s}x{s}.png")
    print(f"icon-{s}x{s}.png cree !")

print("Toutes les icones sont creees !")