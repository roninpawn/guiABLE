from tkinter import PhotoImage


class UImage: pass      # Forward declaration for parameter typing.


class UImage(PhotoImage):
    TRANSPARENCY_KEY = (255, 0, 205)
    def __init__(self, **kwargs):
        if 'file' not in kwargs:
            self._path = kwargs.pop('source') if 'source' in kwargs else None
        else: self._path = kwargs['file']

        super().__init__(**kwargs)

        self._res = None
        self._opaque, self._data, self._key = None, None, None
        self._width, self._height = None, None

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

    def crop(self, x:int = 0, y:int = 0, width:int = None, height:int = None) -> UImage:
        if width is None: width = self.width()
        if height is None: height = self.height()

        out = UImage(width=width, height=height, source=f"Cropped from {self} at {x}, {y}")
        self._blit(out, x, y, width, height)
        return out

    def cropTo(self, recipient:UImage, x:int = 0, y:int = 0, width:int = None, height:int = None,
                                                                                        dest_x:int = 0, dest_y:int = 0):
        if width is None: width = self.width()
        if height is None: height = self.height()
        self._blit(recipient, x, y, width, height, dest_x, dest_y)

    def rotate(self, clockwise:bool = True) -> UImage:
        w, h = self.resolution
        out = UImage(width=h, height=w)
        for y in range(h):
            yy = h-1-y if clockwise else y
            for x in range(w): out.copy_replace(self, from_coords=(x, y, x + 1, y + 1), to=(yy, x))
        return out

    def flip(self, flip_x:bool = False, flip_y:bool = False) -> UImage:
        if not flip_x and not flip_y: return self
        w, h = self.resolution
        flipped = UImage(width=w, height=h)
        if flip_x and flip_y:
            tmp = UImage(width=w, height=h)
            [tmp.copy_replace(self, from_coords=(col, 0, col + 1, h), to=(w-1-col, 0)) for col in range(w)]
            [flipped.copy_replace(tmp, from_coords=(0, row, w, row + 1), to=(0, h-1-row)) for row in range(h)]

        elif flip_x: [flipped.copy_replace(self, from_coords=(col, 0, col + 1, h), to=(w-1-col, 0)) for col in range(w)]
        elif flip_y: [flipped.copy_replace(self, from_coords=(0, row, w, row + 1), to=(0, h-1-row)) for row in range(h)]

        return flipped

    def flood(self, color:str): self.put(color, to=(0, 0, *self.resolution))

    def tileTo(self, recipient:UImage, bbox:tuple[int,int,int,int]):
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

    def pixelMap(self) -> list[tuple[int,int,int]]:
        if not self._data or self._key != self.TRANSPARENCY_KEY:
            self._key = self.TRANSPARENCY_KEY       # Stores key used as background in self._data.

            # Fetch image's raw binary RGB data as 'PPM' using a key color to represent transparency.
            self._data = []
            data = self.data(format="PPM", background=f'#{self._key[0]:02x}{self._key[1]:02x}{self._key[2]:02x}')
            if isinstance(data, str): data = data.encode("latin1")      # Tk <= 8.6.12 returns a str()

            # Split header from pixel payload and re-populate resolution from header data.
            header, raw = data.split(b'\n255\n', 1)
            wh_parts = header.split()       # Fetch width/height from header. (b'P6\n128 192' means w=128, h=192)
            w, h = int(wh_parts[1]), int(wh_parts[2])
            self._res = (w, h)
            if w == 0 or h == 0: return []

            # This is the single fastest method for populating an internal pixel map without using an external library.
            row_stride = w * 3
            for y in range(h):
                offset = y * row_stride
                for x in range(w):
                    i = offset + x*3
                    self._data.append((raw[i], raw[i+1], raw[i+2]))

        return self._data

    def _blit(self, dest:UImage, crop_x:int, crop_y:int, crop_w:int, crop_h:int, dest_x:int = 0, dest_y:int = 0):
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
        if self.transparency_get(0, 0): return False        # Cheapest path if first pixel is transparent.

        data = self.pixelMap()
        w, h = self._res

        for y in range(h):
            offset = y * w
            for x in range(w):
                if data[offset + x] == self._key: return False
        return True