from PIL import Image, ImageTk
from math import gcd

def getZoomFromFraction(fraction:str = "1/1") -> tuple[int, int]:
        zs_str = fraction.split("/")
        len_zs = len(zs_str)

        # Convert str to tuple(int, int)
        if len_zs > 1:
            zoom, subsample = max(1, int(zs_str[0])), max(1, int(zs_str[1]))
        else: zoom, subsample = max(1, int(zs_str[0])), 1

        if zoom != subsample:
            # Reduce the fraction if possible.
            greatest_common_factor = gcd(zoom, subsample)
            if greatest_common_factor > 1:
                zoom = int(zoom / greatest_common_factor)
                subsample = int(subsample / greatest_common_factor)
        else: zoom, subsample = 1, 1

        return (zoom, subsample)


class UImage():
    def __init__(self, **kwargs):
        if 'file' not in kwargs:
            self._path = kwargs.pop('source') if 'source' in kwargs else None
            size = (kwargs['width'], kwargs['height']) if 'width' in kwargs and 'height' in kwargs else (1, 1)
            self._pil = Image.new('RGBA', size)
        else:
            self._path = kwargs['file']
            self._pil = Image.open(self._path)

        self._photo = None
        self._res = None
        self._opaque, self._data, self._key = None, None, None
        self._width, self._height = None, None

    @classmethod
    def fromPIL(cls, pil_image: Image.Image) -> 'UImage':
        ui_image = cls(width=pil_image.width, height=pil_image.height)
        ui_image._pil = pil_image
        return ui_image

    def toPhotoImage(self):
        #if self._photo is None:
        self._photo = ImageTk.PhotoImage(self._pil)
        return self._photo

    @property
    def resolution(self) -> tuple[int,int]:
        if self._res is None: self._res = self._pil.size
        return self._res
    @property
    def width(self) -> int: return self.resolution[0]
    @property
    def height(self) -> int: return self.resolution[1]

    @property
    def path(self): return self._path

    def isOpaque(self) -> bool:     # TODO: It would be better to know TRUE opacity, not just hint-opacity.
        if self._opaque is None: self._opaque = not self._pil.has_transparency_data
        return self._opaque

    def clone(self): UImage.fromPIL(self._pil)

    def crop(self, x:int = 0, y:int = 0, width:int = None, height:int = None) -> 'UImage':
        x1 = x + width if width is not None else self.width
        y1 = y + height if height is not None else self.height
        return UImage.fromPIL(self._pil.crop((x, y, x1, y1)))

    def cropTo(self, recipient:'UImage', x:int = 0, y:int = 0, width:int = None, height:int = None,
                                                                                        dest_x:int = 0, dest_y:int = 0):
        cropped = self.crop(x, y, width, height)
        x1 = x + width if width is not None else self.width
        y1 = y + height if height is not None else self.height
        box = (x, y, x1, y1)

        if not self.isOpaque() and not recipient.isOpaque():
            fg_img_trans = Image.new("RGBA", recipient.resolution)
            fg_img_trans.paste(cropped._pil, box, cropped._pil)
            recipient._pil = Image.alpha_composite(recipient._pil, fg_img_trans)
        else: recipient._pil.paste(cropped._pil, (dest_x, dest_y))

    def rotate(self, clockwise:bool = True) -> 'UImage':
        if clockwise:
            return UImage.fromPIL(self._pil.transpose(Image.Transpose.ROTATE_90))
        else: return UImage.fromPIL(self._pil.transpose(Image.Transpose.ROTATE_270))

    def flip(self, flip_x:bool = False, flip_y:bool = False) -> 'UImage':
        out = self._pil.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if flip_x else self
        if flip_y: out = self._pil.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        return UImage.fromPIL(out) if isinstance(out, Image.Image) else out

    # PhotoImage's built-in scaling methods - zoom and subsample - combine to offer non-lossy integer scaling.
    def scale(self, scale_fraction:str = "1/2", scale_y_fraction:str = None) -> 'UImage':
        wn, wd = getZoomFromFraction(scale_fraction)
        frac = wn/wd
        w = round(self.width * frac)
        if scale_y_fraction is not None:
            hn, hd = getZoomFromFraction(scale_y_fraction)
            h = round(self.height * (hn/hd))
        else: h = round(self.height * frac)
        return UImage.fromPIL(self._pil.resize((w, h), 0))

    # Bilinear scaling provides float/non-integer scaling, but at the cost of partial-transparency.
    def scaleHQ(self, scale:float, scale_y:float = None) -> 'UImage':
        sx = max(0.0, min(1.0, scale))
        sy = max(0.0, min(1.0, scale_y)) if scale_y is not None else sx
        return UImage.fromPIL(self._pil.resize((round(self.width*sx), round(self.height*sy)),
                                               Image.Resampling.BICUBIC))

    def flood(self, color:str): self._pil = Image.new("RGB", (self.width, self.height), color)

    def tileTo(self, recipient: 'UImage', bbox: tuple[int, int, int, int]):
        x1, y1, x2, y2 = bbox
        box_w, box_h = x2 - x1, y2 - y1
        brush = self._pil
        bw, bh = brush.size

        # Create a tile pattern that fully covers the bbox
        cols = (box_w + bw - 1) // bw
        rows = (box_h + bh - 1) // bh

        pattern = Image.new("RGBA", (cols * bw, rows * bh))
        for y in range(0, rows * bh, bh):
            for x in range(0, cols * bw, bw):
                pattern.paste(brush, (x, y))

        cropped_pattern = pattern.crop((0, 0, box_w, box_h))
        recipient._pil.paste(cropped_pattern, (x1, y1))
