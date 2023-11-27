import math
import os
import sys
import argparse
import configparser
import colorsys
from PIL import Image, ImageColor, ImageDraw, ImageFont

IMAGE_UPSCALE = 40
GRID_COLOR = ImageColor.getrgb("black")

class BeadColor():
    def __init__(self, name: str, rgb: tuple[int, int, int]):
        self.name = name
        self.rgb = rgb
        self.yuv = None
        self.hsv = None

    def __rgb2yuv(self, rgb: tuple[int, int, int]):
        r, g, b = rgb
        y = 0.299 * r + 0.587 * g + 0.114 * b
        u = 0.492 * (b - y)
        v = 0.877 * (r - y)
        return [y, u, v]

    def __rgb2hsv(self, rgb: tuple[int, int, int]):
        r, g, b = rgb
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        return [h*360, s, v]

    def __distance_rgb(self, rgb: tuple[int, int, int]) -> float:
        r1, g1, b1 = self.rgb
        r2, g2, b2 = rgb
        rmean = r1 + r2 / 2
        dr, dg, db = (r1-r2)**2, (g1-g2)**2, (b1-b2)**2
        return math.sqrt(((2 + rmean/256) * dr) + (4 * dg) + ((2 + (255-rmean) / 256) * db))

    def __distance_yuv(self, rgb: tuple[int, int, int]) -> float:
        if self.yuv is None:
            self.yuv = self.__rgb2yuv(self.rgb)
        y1, u1, v1 = self.yuv
        y2, u2, v2 = self.__rgb2yuv(rgb)
        return math.sqrt((y1 - y2) ** 2 + (u1 - u2) ** 2 + (v1 - v2) ** 2)

    def __distance_hsv(self, rgb: tuple[int, int, int]) -> float:
        if self.hsv is None:
            self.hsv = self.__rgb2hsv(self.rgb)
        h1, s1, v1 = self.hsv
        h2, s2, v2 = self.__rgb2hsv(rgb)
        dh = min(abs(h2-h1), 360-abs(h2-h1)) / 180.0
        ds = abs(s2 - s1)
        dv = abs(v2 - v1)
        return math.sqrt(dh*dh + ds*ds + dv*dv)

    def get_distance(self, color_space: str, rgb: tuple[int, int, int]) -> float:
        match color_space.upper():
            case "RGB":
                return self.__distance_rgb(rgb)
            case "YUV":
                return self.__distance_yuv(rgb)
            case "HSV":
                return self.__distance_hsv(rgb)
            case _:
                raise ValueError

    def get_textcolor(self) -> tuple[int, int, int]:
        if sum(self.rgb) > (128*3):
            return ImageColor.getrgb("black")
        else:
            return ImageColor.getrgb("white")

class BeadPalette():
    def __init__(self):
        self.palette = list()

    def add(self, color: BeadColor):
        self.palette.append(color)

    def get_closest(self, color_space: str, rgb: tuple[int, int, int]) -> BeadColor:
        min_distance = float('inf')
        best_color = None
        for color in self.palette:
            distance = color.get_distance(color_space, rgb)
            if (distance < min_distance):
                min_distance = distance
                best_color = color
        return best_color


def load_color_palette(filename) -> BeadPalette:
    config = configparser.ConfigParser()
    config.read(filename)
    palette = BeadPalette()
    for key in config['Palette']:
        rgb = tuple(int(x) for x in config['Palette'][key].split('#')[0].rstrip().split(','))
        palette.add(BeadColor(key, rgb))

    return palette

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Image to convert into bead image")
    parser.add_argument("-p" , "--palette", help="INI file defining the bead color palette")
    parser.add_argument("-c" , "--color", default="rgb", type=str, help="Color space to compute distance: rgb, yuv, hsv")
    args = parser.parse_args()

    # Load palette
    palette = None
    if args.palette is not None:
        palette = load_color_palette(args.palette)

    # Load image
    im_in = Image.open(args.image).convert('RGBA')

    # Create output image
    im_out = Image.new('RGBA', tuple(x*IMAGE_UPSCALE for x in im_in.size))

    # Draw output image
    draw = ImageDraw.Draw(im_out)
    draw.font = ImageFont.truetype("arial.ttf", 12)
    for y in range(im_in.height):
        for x in range(im_in.width):
            in_color = im_in.getpixel((x, y))

            # Skip if pixel is transparent
            if in_color[3] == 0:
                continue

            # Extract only RGB
            in_color = in_color[0:3]

            if palette is not None:
                out_color = palette.get_closest(args.color, in_color)
            else:
                out_color = BeadColor("", in_color)

            draw.rectangle([(x*IMAGE_UPSCALE, y*IMAGE_UPSCALE), (x*IMAGE_UPSCALE+IMAGE_UPSCALE, y*IMAGE_UPSCALE+IMAGE_UPSCALE)], fill=out_color.rgb, outline=GRID_COLOR)
            draw.text((x*IMAGE_UPSCALE+IMAGE_UPSCALE/2, y*IMAGE_UPSCALE+IMAGE_UPSCALE/2), out_color.name, fill=out_color.get_textcolor(), anchor='mm')

    # Save output file
    if palette is None:
        suffix = "big"
    else:
        suffix = "bead"

    output_filename = "{0}_{2}_{3}{1}".format(*os.path.splitext(args.image), suffix, args.color.lower())
    im_out.save(output_filename)

if __name__ == "__main__":
    sys.exit(main())
