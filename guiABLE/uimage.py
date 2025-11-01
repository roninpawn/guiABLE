from tkinter import PhotoImage
from math import gcd


# Because PhotoImage only provides integer-based scaling, to achieve a scale of 2/3rds we must .zoom(2) and then
# .subsample(3). This function accepts "2/3" as a string and returns the appropriate zoom/subsample integers.
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


class UImage(PhotoImage):
    TRANSPARENCY_KEY = (255, 0, 205)    # Color in (R, G, B) format
    def __init__(self, **kwargs):
        if 'file' not in kwargs:
            self._path = kwargs.pop('source') if 'source' in kwargs else None
        else: self._path = kwargs['file']

        super().__init__(**kwargs)

        self._res = None
        self._opaque, self._data, self._key = None, None, None
        self._width, self._height = None, None

    @classmethod
    def fromPhotoImage(cls, photo:PhotoImage, source:str = "Passed internally.") -> 'UImage':
        w, h = photo.width(), photo.height()
        ui_image = UImage(width=w, height=h, source=source)
        ui_image.copy_replace(photo, from_coords=(0, 0, w, h))
        return ui_image
    @classmethod
    def fromPixelMap(cls, pixel_map: list[list[tuple[int,int,int]]], rgb_key=None, source:str = "") -> 'UImage':
        w, h = len(pixel_map[0]), len(pixel_map)
        img = UImage(width=w, height=h, source=source)
        for x in range(w):
            col = [None] * h
            for y in range(h):
                rgb = pixel_map[y][x]
                col[y] = f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'
            img.put(col, to=(x, 0))

        if rgb_key is not None:
            for x in range(w):
                for y in range(h):
                    if pixel_map[y][x] == rgb_key: img.transparency_set(x, y, True)

        return img

    @property
    def resolution(self) -> tuple[int,int]:
        if self._res is None: self._res = (super().width(), super().height())
        return self._res
    def width(self) -> int: return self.resolution[0]
    def height(self) -> int: return self.resolution[1]

    @property
    def path(self): return self._path

    def isOpaque(self) -> bool:
        if self._opaque is None: self._opaque = self._isOpaque()
        return self._opaque

    def clone(self): return UImage.fromPhotoImage(self, f"Copied from {self}")

    def crop(self, x:int = 0, y:int = 0, width:int = None, height:int = None) -> 'UImage':
        if width is None: width = self.width()
        if height is None: height = self.height()

        out = UImage(width=width, height=height, source=f"Cropped from {self} at {x},{y}")
        self._blit(out, x, y, width, height)
        return out

    def cropTo(self, recipient:'UImage', x:int = 0, y:int = 0, width:int = None, height:int = None,
                                                                                        dest_x:int = 0, dest_y:int = 0):
        if width is None: width = self.width()
        if height is None: height = self.height()
        self._blit(recipient, x, y, width, height, dest_x, dest_y)

    def rotate(self, clockwise:bool = True) -> 'UImage':
        w, h = self.resolution
        out = UImage(width=h, height=w, source =f"Rotation of {self}")
        for y in range(h):
            yy = h-1-y if clockwise else y
            for x in range(w): out.copy_replace(self, from_coords=(x, y, x + 1, y + 1), to=(yy, x))
        return out

    def flip(self, flip_x:bool = False, flip_y:bool = False) -> 'UImage':
        if not flip_x and not flip_y: return self
        w, h = self.resolution
        out = UImage(width=w, height=h, source=f"Flipped {self} on {'x' if flip_x else ''}{'y' if flip_y else ''}")
        if flip_x and flip_y:
            tmp = UImage(width=w, height=h)
            [tmp.copy_replace(self, from_coords=(col, 0, col + 1, h), to=(w-1-col, 0)) for col in range(w)]
            [out.copy_replace(tmp, from_coords=(0, row, w, row + 1), to=(0, h-1-row)) for row in range(h)]

        elif flip_x: [out.copy_replace(self, from_coords=(col, 0, col + 1, h), to=(w-1-col, 0)) for col in range(w)]
        elif flip_y: [out.copy_replace(self, from_coords=(0, row, w, row + 1), to=(0, h-1-row)) for row in range(h)]

        return out

    # PhotoImage's built-in scaling methods - zoom and subsample - combine to offer non-lossy integer scaling.
    def scale(self, scale_fraction:str = "1/2", scale_y_fraction:str = None) -> 'UImage':
        z1, s1 = getZoomFromFraction(scale_fraction)
        if scale_y_fraction is not None:
            z2, s2 = getZoomFromFraction(scale_y_fraction)
            if z1 != s1 or z2 != s2:
                out = self.zoom(z1, z2) if z1 > 1 or z2 > 1 else self
                out = out.subsample(s1, s2) if s1 > 1 or s2 > 1 else out
            print(z1, z2, s1, s2)
        elif z1 != s1:
            out = self.zoom(z1) if z1 > 1 else self
            out = out.subsample(s1) if s1 > 1 else out
            print(z1, s1)
        else: out = self
        return UImage.fromPhotoImage(out, f"Scaled from {self}")

    # Bilinear scaling provides float/non-integer scaling, but at the complete loss of partial-transparency.
    def scaleBilinear(self, scale:float, scale_y:float = None, alpha_tolerance_per:float = .02) -> 'UImage':
        a_t = max(0, min(255, round(255 * alpha_tolerance_per)))
        return self.fromPixelMap(self._scale_bilinear(scale, scale_y, a_t), self._key, f"Scaled from {self}")

    def flood(self, color:str): self.put(color, to=(0, 0, *self.resolution))

    def tileTo(self, recipient:'UImage', bbox:tuple[int,int,int,int]):
        x1, y1, x2, y2 = bbox
        box_w, box_h = x2 - x1, y2 - y1
        bw, bh = min(self.width(), box_w), min(self.height(), box_h)

        # TODO: Do the largest blit from brush possible. Do 4 operations instead of 400.
        if bw and bh:
            for y in range(y1, y2, bh):
                h = min(bh, y2-y)
                for x in range(x1, x2, bw):
                    w = min(bw, x2-x)
                    if w >= 0 and h >= 0:
                        recipient.copy_replace(self, from_coords=(0, 0, w, h), to=(x, y))

    def getSprites(self, width_per_sprite:int, rows:int = 1, margins:tuple = (0, 0)) -> list['UImage']:
        # Ensure row sanity and collect geometry.
        if rows < 1: rows = 1
        height = self.height() // rows
        cols = (self.width() + margins[0]) // (width_per_sprite + margins[0])

        # Populate self._images with the sprites from the sheet.
        sprites = []
        for row in range(rows):
            for col in range(cols):
                x1, y1 = col * width_per_sprite + margins[0], row * height + margins[1]
                sprite = self.crop(x1, y1, width_per_sprite, height)

                sprites.append(sprite)
        return sprites

    def pixelMap(self) -> list[list[tuple[int,int,int]]]:
        if not self._data or self._key != self.TRANSPARENCY_KEY:
            self._key = self.TRANSPARENCY_KEY       # Stores key used as background in self._data.

            # Fetch image's raw binary RGB data as 'PPM' using a key color to represent transparency.
            self._data = []
            data = self.data(format="PPM", background=f'#{self._key[0]:02x}{self._key[1]:02x}{self._key[2]:02x}')
            if isinstance(data, str): data = data.encode("latin1")      # Tk <= 8.6.12 returns a str(), so convert.

            # Split header from pixel payload and re-populate resolution from header data.
            header, raw = data.split(b'\n255\n', 1)
            wh_parts = header.split()       # Fetch width/height from header. (b'P6\n128 192' means w=128, h=192)
            w, h = int(wh_parts[1]), int(wh_parts[2])
            self._res = (w, h)
            if w == 0 or h == 0: return []

            # This is the single fastest method for writing and reading an internal pixel map sans an external library.
            row_stride = w * 3
            self._data = [None] * h
            for y in range(h):
                offset = y * row_stride
                row = [None] * w
                for x in range(w):
                    i = offset + x*3
                    row[x] = ((raw[i], raw[i+1], raw[i+2]))
                self._data[y] = row

        return self._data

    def _blit(self, dest:'UImage', crop_x:int, crop_y:int, crop_w:int, crop_h:int, dest_x:int = 0, dest_y:int = 0):
        def clamp_positive(p0, size, dest):
            if p0 < 0:
                size += p0  # shrink size by the overflow
                dest -= p0  # shift dest to compensate
                p0 = 0
            return p0, size, dest

        # Clamp destination coordinates to non-negative
        crop_x, crop_w, dest_x = clamp_positive(crop_x, crop_w, dest_x)
        crop_y, crop_h, dest_y = clamp_positive(crop_y, crop_h, dest_y)
        dest_x, crop_w, crop_x = clamp_positive(dest_x, crop_w, crop_x)
        dest_y, crop_h, crop_y = clamp_positive(dest_y, crop_h, crop_y)

        # Clamp width/height to fit both source and dest
        crop_w = min(crop_w, self.width() - crop_x, dest.width() - dest_x)
        crop_h = min(crop_h, self.height() - crop_y, dest.height() - dest_y)

        # Bail out if the region is invalid
        if crop_w <= 0 or crop_h <= 0: return

        w, h = self._res
        crop_x = min(w, crop_x)
        crop_y = min(h, crop_y)
        src_x2 = min(w, crop_x + crop_w)
        src_y2 = min(h, crop_y + crop_h)

        if src_x2 - crop_x <= 0 or src_y2 - crop_y <= 0: return

        # Perform the blit
        dest.copy_replace(self, from_coords=(crop_x, crop_y, src_x2, src_y2), to=(dest_x, dest_y))

    def _isOpaque(self):
        if self.width() == 0 or self.height() == 0: return False
        if self.transparency_get(0, 0): return False        # Cheapest path if first pixel is transparent.

        data = self.pixelMap()
        w, h = self._res

        for y in range(h):
            for x in range(w):
                if data[y][x] == self._key: return False
        return True

    def _rgb_is_transparent(self, rgb_color:tuple[int,int,int], alpha_tolerance:int):
        return (abs(rgb_color[0]-self._key[0]) < alpha_tolerance and
                abs(rgb_color[1]-self._key[1]) < alpha_tolerance and
                abs(rgb_color[2]-self._key[2]) < alpha_tolerance)

    def _scale_bilinear(self, scale:float, scale_y:float = None, alpha_tolerance:int = 5) -> list[list[tuple[int,int,int]]]:
        sw, sh = scale, scale_y or scale
        src = self.pixelMap()
        h, w = len(src), len(src[0])
        new_w, new_h = round(w * sw), round(h * sh)
        x_ratio, y_ratio = (w - 1) / new_w, (h - 1) / new_h

        scaled = [[]] * new_h
        for j in range(new_h):
            y = j * y_ratio
            y0 = int(y)
            y_lerp = y - y0
            y1 = min(y0 + 1, h - 1)

            row = [None] * new_w
            for i in range(new_w):
                x = i * x_ratio
                x0 = int(x)
                x_lerp = x - x0
                x1 = min(x0 + 1, w - 1)

                # Fetch 4 samples
                c00 = src[y0][x0]
                c10 = src[y0][x1]
                c01 = src[y1][x0]
                c11 = src[y1][x1]

                # Handle transparency
                if any(self._rgb_is_transparent(c, alpha_tolerance) for c in (c00, c10, c01, c11)):
                    row[i] = self._key
                    continue

                # Interpolate
                r = (c00[0]*(1-x_lerp)*(1-y_lerp) + c10[0]*x_lerp*(1-y_lerp)
                     + c01[0]*(1-x_lerp)*y_lerp + c11[0]*x_lerp*y_lerp)
                g = (c00[1]*(1-x_lerp)*(1-y_lerp) + c10[1]*x_lerp*(1-y_lerp)
                     + c01[1]*(1-x_lerp)*y_lerp + c11[1]*x_lerp*y_lerp)
                b = (c00[2]*(1-x_lerp)*(1-y_lerp) + c10[2]*x_lerp*(1-y_lerp)
                     + c01[2]*(1-x_lerp)*y_lerp + c11[2]*x_lerp*y_lerp)

                row[i] = (int(r), int(g), int(b))
            scaled[j] = row
        return scaled
