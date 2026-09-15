from PIL import Image

img = Image.open("icon.png")
img.save("logo.ico", sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
print("✓ logo.ico ساخته شد")