import tkinter as tk

from guiABLE.utilities import (warnPrint, resolvePath, cropImage, loadImage, getGeometry, fastComposite,
                               fastFlood, fastTile, flipImage, rotateImage)


""" Receivable is a base class that lets widgets register with it, and provides methods for updating those recipients. """
class Receivable:
    def __init__(self): self._recipients = []

    def bindWidget(self, widget):   # FilterSkins kept first so they update BEFORE the widgets that might use them.
        self._recipients.insert(0, widget) if isinstance(widget, FilterSkin) else self._recipients.append(widget)
    def unbindWidget(self, widget):
        if widget in self._recipients: self._recipients.remove(widget)

    def dirtyRecipients(self):
        for recipient in self._recipients: recipient.dirty = True
    def redrawRecipients(self):
        for recipient in self._recipients: recipient.redraw()
    def updateRecipients(self):
        for recipient in self._recipients:
            recipient.dirty = True
            recipient.redraw()


""" CoreSkin establishes the core contents and operations of a Skin. It is a base class. Not for standalone use."""
class CoreSkin(Receivable):
    def __init__(self):
        super().__init__()
        self._paths, self._images, self._resolutions = [], [], []
        self._empty_image = tk.PhotoImage()
        self._default_colors = ['gray42', 'gray51', 'gray78', 'gray27']
        self._bg_colors = self._default_colors
        self._use_bg_colors = True
        self._filter = None     # Internal FilterSkin for compositing to background colors.

    # Core access methods
    @property
    def paths(self) -> list[str]: return self._paths
    def path(self, index:int) -> str | None:
        if len(self._paths): return self._paths[index % len(self._paths)]
        return None

    @property
    def images(self) -> list[tk.PhotoImage]: return self._images
    def image(self, index: int = 0) -> tk.PhotoImage:
        if self._images:
            # If bg_colors in use, use FilterSkin to composite, cache, and return without corrupting held images.
            if self._use_bg_colors:
                if self._filter is None: self._filter = FilterSkin(self)
                return self._filter.image(index)
            return self._images[index % len(self._images)]
        return self._empty_image

    @property
    def resolutions(self): return self._resolutions
    def resolution(self, image_index: int = 0) -> tuple[int, int]:
        if any(self._resolutions):
            image_index %= len(self._resolutions)
            return self._resolutions[image_index]
        return 0, 0

    @property
    def bg_colors(self) -> list[str]: return self._bg_colors
    def bgColor(self, index: int = 0) -> str | None:
        if self._use_bg_colors and len(self._bg_colors): return self._bg_colors[index % len(self._bg_colors)]
        return None     # Represents alpha

    def reset(self):
        self._paths, self._images, self._resolutions = [], [], []
        self._bg_colors = self._default_colors
        self.updateRecipients()

    # Informational methods
    def hasImages(self): return any(self._images)
    def usesBgColors(self, use:bool = None) -> bool:
        if use:
            self._use_bg_colors = use
            if not use: self._filter = None     # Unload internal FilterSkin if no longer in use.
            self.updateRecipients()
        return self._use_bg_colors

    def numStates(self): return max(len(self._images), len(self._bg_colors))

    def _imageByPath(self, path:str) -> tk.PhotoImage|None:
        try:
            out = tk.PhotoImage(file=path)
            return out
        except tk.TclError:
            warnPrint(f"Image not found: {path}")
            return None

    def _saveImage(self, image:tk.PhotoImage, index:int, path:str = None, resolution:tuple[int, int] = None):
        self._images[index] = image
        if not resolution:
            self._resolutions[index] = (image.width(), image.height()) if isinstance(image, tk.PhotoImage) else (0,0)
        else: self._resolutions[index] = resolution
        self._paths[index] = path

    @staticmethod
    def _fillList(in_list:list) -> list:
        fallback = next(l for l in in_list if l)     # Find first non-Falsy entry

        for i, l in enumerate(in_list):      # Fill in any gaps by propagating the most recent valid data forward.
            if l: fallback = l
            else: in_list[i] = fallback

        return in_list

    def _expand(self, size:int):       # Expands path and image lists to new length.
        for n in range(size):
            if len(self._paths) < size:         self._paths.append(None)
            if len(self._images) < size:        self._images.append(None)
            if len(self._resolutions) < size:   self._resolutions.append((0,0))


""" SingleSkin is a minimal skin container for holding one image. Used with static images and backgrounds. """
class SingleSkin (CoreSkin):
    def __init__(self, path:str = None):
        super().__init__()
        self._default_colors = ['gray23']
        self._bg_colors = self._default_colors
        self._expand(1)

        self._paths = [resolvePath(path)]
        if path: self._saveImage(self._imageByPath(self._paths[0]), 0, self._paths[0])

    @classmethod
    def fromImage(cls, image:tk.PhotoImage):
        ss = cls()
        if isinstance(image, tk.PhotoImage): ss.setImage(image)
        return ss
    @classmethod
    def fromPath(cls, path:str): return cls(path)
    @classmethod
    def fromColor(cls, color:str):
        ss = cls()
        ss.setColor(color)
        return ss

    def setImage(self, image:tk.PhotoImage, index:int = 0): self._saveImage(image, 0, "passed internally")
    def setPath(self, path:str, index:int = 0):
        self._paths = [resolvePath(path)]
        if path: self._saveImage(self._imageByPath(self._paths[0]), 0, self._paths[0])
    def setColor(self, color:str, index:int = 0): self._bg_colors = [color]


"""
    ColorSkin adds methods for creating/manipulating multiple background colors.
    ex: new_skin = ColorSkin.fromColors('yellow', 'blue', 'orange', 'gray15')
"""
class ColorSkin(CoreSkin):
    @classmethod
    def fromColors(cls, *colors):
        sk = cls()
        sk.setBGColors(*colors)
        return sk
    def setBGColors(self, *colors: str):
        if colors and any(colors):  self._bg_colors = self._fillList([*colors])
        else: warnPrint(f"Skinnable passed list of empty BG colors\n{colors}\nExisting colors retained.")
        self.updateRecipients()
    def setBGColor(self, color:str, index:int = 0):
        # If index is out of range, extend bg_color list with itself until index is valid
        if color:
            while index < -len(self._bg_colors) or index >= len(self._bg_colors): self._bg_colors.extend(self._bg_colors)
            self._bg_colors[index] = color
        else: warnPrint(f"Skinnable passed empty BG color '{color}' for index {index}; Existing color retained.")
        self.updateRecipients()
    def appendBGColors(self, *colors: str):
        if colors and any(colors):  self._bg_colors.extend(self._fillList([*colors]))
        else: warnPrint(f"Skinnable passed list of empty BG colors\n{colors}\nExisting colors retained.")
        self.updateRecipients()


"""
    Skin() provides many different pathways for populating/modifying the image/background colors within the Skin.
    .fromColors()       - new_skin = Skin.fromColors('yellow', 'blue', 'orange', 'gray15')
    .fromPaths()        - new_skin = Skin.fromPaths("skins/skin1/checkbox.png","skins/skin1/checkbox_hover.png", ...)
    .fromImages()       - new_skin = Skin.fromImages(img1, img2, img3, img4) 
    .fromSpriteSheet()  - new_skin = Skin.fromSpriteSheet("/skins/skin1/checkbox.png", width=32, rows=2, margins=(4,4))
    
    The default creation method provides a list of resource paths as strings with an optional orientation value.
    ex: Skin("images/button_norm.png", "images/button_mo.png", "images/button_active.png", orientation="w")
    
    Orientation is expressed in cardinal directions: North, East, South, West as "n", "e," "s", "w", and is used in
    certain rotation/mirror operations, like for Scrollbar generation.
    
    While Skin() supports storing any number of images in any order, the guiABLE's standard order of states is:
    (normal, moused_over, active, disabled) 
"""
class Skin(ColorSkin):
    def __init__(self, *paths:str, orientation:str = None):
        super().__init__()

        if any(paths):
            self._expand(len(paths))
            self._byPaths(paths)
        self._orientation = orientation.lower()[0] if orientation else None

    """ By resource paths. ex: Skin("skins/my_skin/checkbox_enabled.png","skins/my_skin/checkbox_hover.png", ...) """
    @classmethod
    def fromPaths(cls, *paths:str, orientation:str = None):
        sk = cls()
        if any(paths):
            sk._expand(len(paths))
            sk._byPaths(paths)
        sk._orientation = orientation.lower()[0] if orientation else None
        return sk
    def setPaths(self, *paths:str):        # Supports insert-updating by list. ex: ["path", None, None, "path"]
        if len(paths) > len(self._paths): self._expand(len(paths))
        self._byPaths(paths, True)
        self.updateRecipients()
    def setPath(self, path:str, index:int = 0):
        if index >= len(self._images): self._expand(index + 1)
        self._byPaths((path, ), index_offset=index)
        self.updateRecipients()

    """
    By PhotoImage references. ex: Skin.fromImages(checkbox0, checkbox1, checkbox2, ...)
    ⚠️ WARNING: PhotoImage objects must be referenced in Python, or they will be garbage collected. Skinnable() stores
    the image by ref, so you're safe here. But avoid passing PhotoImage(file=...) directly into native Tkinter.
    """
    @classmethod
    def fromImages(cls, *photoimages:tk.PhotoImage, orientation:str = None):
        sk = cls()
        if any(photoimages):
            sk._expand(len(photoimages))
            sk._byPhotoImages(photoimages)
        sk._orientation = orientation.lower()[0] if orientation else None
        return sk
    def setImages(self, *photoimages:tk.PhotoImage):
        if len(photoimages) > len(self._images): self._expand(len(photoimages))
        self._byPhotoImages(photoimages, True)
        self.updateRecipients()
    def setImage(self, photoimage:tk.PhotoImage, index:int = 0):
        if index >= len(self._images): self._expand(index + 1)
        self._byPhotoImages((photoimage, ), index_offset=index)
        self.updateRecipients()

    """
    By Spritesheet -- A single image that contains all variants of a widget's state.
    width:      Per-sprite width
    rows:       How many rows of sprites in the sheet (default = 1)
    margins:    x,y margins. The gap, on each axis, BETWEEN each sprite. There should be NO margin at the image's edges.  
    Example:    Skin.fromSpriteSheet("/skins/default/checkbox.png", width=32, rows=2, margins=(4,4))
    """
    @classmethod
    def fromSpriteSheet(cls, path_or_image:str|tk.PhotoImage, width:int, rows:int = 1, margins:tuple = (0,0),
                        orientation:str = None):
        sk = cls()
        sheet, path = loadImage(path_or_image)
        if sheet is not None:
            sk._bySprite(sheet, path, width, rows, margins)
        sk._orientation = orientation.lower()[0] if orientation else None
        return sk
    def setSprites(self, path_or_image:str|tk.PhotoImage, width:int, rows:int = 1, margins:tuple = (0,0)):
        sheet, path = loadImage(path_or_image)
        if sheet is not None:
            self._paths, self._images = [], []
            self._bySprite(sheet, path, width, rows, margins)
        self.updateRecipients()

    @property
    def orientation(self): return self._orientation

    """ Private Functions """
    def _byPaths(self, paths:tuple[str, ...], skip_falsy:bool = False, index_offset:int = 0):
        for i, path in enumerate(paths):
            i += index_offset       # index_offset is used by .updateByPath() to insert a single change at one location.
            if not path and skip_falsy: continue        # Preserves existing values, allowing insert-changes by list.
            r_path = resolvePath(path)

            # If this path has already been successfully resolved to an image, store same image reference.
            if e := self._existsAt(r_path): self._saveImage(self._images[e], i, self._paths[e])

            # Otherwise store resolved path and try to load the image. If fail, store reference to empty image.
            else:
                self._paths[i] = r_path
                try:
                    self._saveImage(tk.PhotoImage(file=r_path), i, r_path)
                except tk.TclError:
                    warnPrint(f"Image not found: {r_path}")

        self._fillImages()

    def _byPhotoImages(self, images:tuple[tk.PhotoImage, ...], skip_falsy=False, index_offset:int = 0):
        for i, img in enumerate(images):
            if not img and skip_falsy: continue

            i += index_offset
            if img:
                self._saveImage(img, i, "image passed internally")
            else:
                self._images[i] = None
                self._paths[i] = None

        self._fillImages()

    def _bySprite(self, sheet:tk.PhotoImage, source:str, width:int, rows:int = 1, margins:tuple = (0, 0)):
        # Ensure row sanity and collect geometry.
        if rows < 1: rows = 1
        height = sheet.height() // rows
        cols = (sheet.width() + margins[0]) // (width + margins[0])

        # Populate self._images with the sprites from the sheet.
        for row in range(rows):
            for col in range(cols):
                x1, y1 = col * width + margins[0], row * height + margins[1]
                sprite = cropImage(sheet, x1, y1, width, height)

                self._images.append(sprite)
                self._paths.append(f"{x1},{y1},{width},{height} from {source}")
                self._resolutions.append((sprite.width(), sprite.height()))

        self._fillImages()

    def _existsAt(self, path:str) -> int|None:
        for i in range(len(self._images)):
            if self._images[i] and self._paths[i] == path: return i
        return None

    def _fillImages(self):
        fallback = next((i for i in self._images if i is not None), None)       # Find first real image.
        if fallback is None: return

        self._use_bg_colors = False     # If images were loaded, default to transparency.
        for i in range(len(self._images)):      # Fill in any gaps by propagating the most recent valid image forward.
            if self._images[i] is None:
                self._images[i] = fallback
                self._resolutions[i] = (fallback.width(), fallback.height())
            else:
                fallback = self._images[i]
                self._resolutions[i] = (self._images[i].width(), self._images[i].height())


""" DirtySkin is a mix-in that adds per-image dirtiness tracking to a CoreSkin descendant. """
class DirtySkin:
    def __init__(self):
        self.dirty = True
        self._img_dirty = []

    def image(self, image_index: int = 0, *args) -> tk.PhotoImage:
        if self.dirty: self._cleanSkin()
        if self.hasImages():
            image_index = self._cleanIndex(image_index, *args)
            if self._images[image_index]: return self._images[image_index]      # Return the image requested.
        return self._empty_image

    def resolution(self, image_index: int = 0) -> tuple[int, int]:
        if self.dirty: self._cleanSkin()
        if self._resolutions:
            image_index = self._cleanIndex(image_index)
            if self._resolutions[image_index]: return self._resolutions[image_index]
        return 0, 0

    # Define redraw() because widget-recipients of skin changes are asked to redraw.
    def redraw(self): pass

    # _cleanIndex redraws/recalculates dirty images/resolutions and returns an in-range index value.
    def _cleanIndex(self, index:int, *args) -> int:
        if index >= len(self._img_dirty): index = index % len(self._img_dirty)
        if self._img_dirty[index]:
            self._draw(index, *args)
            self._img_dirty[index] = False
        return index

    # Propagate dirty state to each individual image.
    def _cleanSkin(self):
        for i in range(len(self._img_dirty)): self._img_dirty[i] = True
        while len(self._img_dirty) < len(self._images): self._img_dirty.append(True)
        self.dirty = False

    # _draw is a method intended to be fully overridden by the child class.
    def _draw(self, index:int, *args): pass


"""
    FilterSkin provides a cached and ready view of another skin, as mirrored/rotated/flood-filled in place.
    Changes to the original skin will be reflected in the FilterSkin as well. 
"""
class FilterSkin(DirtySkin, CoreSkin):
    def __init__(self, linked_skin:CoreSkin, rotate:bool = False, mirror_x:bool = False, mirror_y:bool = False):
        DirtySkin.__init__(self)
        CoreSkin.__init__(self)

        # If the source skin is -itself- a FilterSkin, link directly to that skin's source, and sum with its transforms.
        if isinstance(linked_skin, FilterSkin):
            rotate, mirror_x, mirror_y = self._state_sum(
                (linked_skin.rotate, linked_skin.mirror_x, linked_skin.mirror_y), (rotate, mirror_x, mirror_y)
            )
            self._linked_skin = linked_skin.linked_skin
        else: self._linked_skin = linked_skin

        self.mirror_x = mirror_x
        self.mirror_y = mirror_y
        self.rotate = rotate

        try:
            self._orientation = self._linked_skin.orientation
            if self._orientation:
                self._transformOrientation()
        except: self._orientation = None

        self._linked_skin.bindWidget(self)
        self._cleanSkin()

    @property
    def linked_skin(self): return self._linked_skin

    def bindWidget(self, widget): self._linked_skin.bindWidget(widget)
    def unbindWidget(self, widget): self._linked_skin.unbindWidget(widget)

    def _cleanSkin(self):
        # Take on all qualities of the linked skin.
        self._paths = self._linked_skin.paths
        self._bg_colors = self._linked_skin.bg_colors
        self._images = list(self._linked_skin.images)
        self._resolutions = self._linked_skin.resolutions

        try:
            self._orientation = self._linked_skin.orientation
            self._transformOrientation()
        except: self._orientation = None

        # Propagate dirty state to individual image states. len(bg_colors) ensures needed length if usesBGColors().
        if self._linked_skin.usesBgColors():
            for i in range(len(self._img_dirty)): self._img_dirty[i] = True
            while len(self._img_dirty) < len(self._bg_colors): self._img_dirty.append(True)
            self.dirty = False
        else: super()._cleanSkin()

    def _draw(self, index:int):
        image_index = index % len(self._images)
        img = self._linked_skin.images[image_index]     # Acquire the original, unmodified image from linked_skin.

        w, h = self._linked_skin.resolution(image_index)
        if self.rotate:                                 # Rotate image as requested.
            img = rotateImage(img, False)
            w, h = h, w
        img = flipImage(img, self.mirror_x, self.mirror_y)      # Mirror/flip image as requested.

        if self._linked_skin.usesBgColors():            # Composite background color, if the linked image uses one.
            flood_img = tk.PhotoImage(width=w, height=h)
            fastFlood(flood_img, w, h, self._bg_colors[index])
            fastComposite(flood_img, w, h, img, 0, 0, w, h)
            img = flood_img

        while len(self._images) <= index: self._images.append(self._empty_image)
        while len(self._resolutions) <= index: self._resolutions.append((0,0))
        self._images[index] = img
        self._resolutions[index] = w, h

    # Update orientation by applying transforms.
    def _transformOrientation(self) -> str|None:
        _directions = {"n":0, "e":1, "s":2, "w":3}
        if self._orientation and self._orientation in _directions:
            o = _directions[self._orientation]
            if self.rotate: o = (o - 1) % 4      # CCW rotation
            if self.mirror_x: o = (4 - o) % 4    # flip E/W
            if self.mirror_y: o = (2 - o) % 4    # flip N/S
            self._orientation = list(_directions.keys())[o]
        else: self._orientation = None

    @staticmethod
    def _state_sum(set_1, set_2) -> tuple[bool, bool, bool]:
        """
        Each state is a tuple (r, x, y) of booleans:
          r: rotate 90° CCW
          x: mirror X
          y: mirror Y

        This formula (dihedral group of the square? -ish?) accounts for rotation-first semantics by flipping set_1's
        horizontal and vertical mirrors if set_2 contains a rotation. After that it simply sums the states by XORs
        while reducing any 2 rotations into an x/y flip, as both r*2 and x/y produce the same '180 degree turn.'
        """
        r1,x1,y1 = set_1
        r2,x2,y2 = set_2

        if r2: x1, y1 = y1, x1      # If S2 rotates, swap the meaning of S1’s mirror operations

        x, y, = x1 ^ x2, y1 ^ y2    # Flip mirrors by XOR

        # 2x rotations (i.e., 180°) equal 1x X and 1x Y
        if r1 and r2:      # trade 180° for flip-both
            x ^= 1
            y ^= 1

        r = r1 ^ r2     # rotation cancellation on 2x rotations happens implicitly

        return bool(r), bool(x), bool(y)


"""
    BarSkin accepts 2-3 skins which function as the end-caps and trough of a variable-length image. On request, BarSkin
    composes, stores, and returns the image of a bar, of the last length specified. Length is extended by repeating the
    trough until the area is filled. (the term 'breadth' is used as the opposite of 'length', throughout the code)
    
    If no second cap_skin is provided, or the .fromTwo() method is used directly, BarSkin will duplicate the first
    cap_skin given, flipping it's images on the appropriate axis (mirror), to generate a cap2_skin.     
    
    ex: BarSkin(cap1, trough, vertical=True)    # When no cap2 is given, cap1 is mirrored to fill the need.
"""
class BarSkin(DirtySkin, ColorSkin):
    def __init__(self, cap_skin: Skin|FilterSkin|None = None, trough_skin: Skin|FilterSkin|None = None,
                 cap2_skin: Skin|FilterSkin|None = None, vertical:bool = False, length:int = 0, breadth:int = 0):
        DirtySkin.__init__(self)
        ColorSkin.__init__(self)

        # Generate or store the skins passed.
        self.trough = trough_skin or Skin()
        if cap_skin is not None:
            self.cap1 = cap_skin
            self.cap2 = cap2_skin or FilterSkin(self.cap1, mirror_x=not vertical, mirror_y=vertical)
        else:
            self.cap1, self.cap2 = Skin(), Skin()

        # Register as a recipient of each skin for dirtiness tracking.
        self.trough.bindWidget(self)
        self.cap1.bindWidget(self)
        self.cap2.bindWidget(self)

        # Store vertical, length and breadth -- populating breadth automatically if it is undeclared.
        self._vertical = vertical
        if breadth < 1:
            self.breadth = max(self.cap1.resolution()[not vertical], self.trough.resolution()[not vertical],
                               self.cap2.resolution()[not vertical], 1)
        else: self.breadth = breadth
        self.length = self.breadth * 3 if length < 1 else length

        # Expand to fit the maximum drawable states.
        self._expand( min(self.cap1.numStates(), self.trough.numStates(), self.cap2.numStates()) )

        # If BarSkin has enough image-containing skins to render a bar at instantiation, bg_colors default to off.
        if self.cap1.hasImages() and self.trough.hasImages(): self._use_bg_colors = False

    # fromTwo takes a trough and only 1 cap, flipping that cap to create the other end of the bar.
    @classmethod
    def fromTwo(cls, cap_skin:Skin|FilterSkin, trough_skin:Skin|FilterSkin, vertical:bool = False, breadth:int = 0):
        return cls(cap_skin, trough_skin, vertical=vertical, breadth=breadth)

    def image(self, index:int = 0, length:int = None) -> tk.PhotoImage:
        if length and length != self.length and length > 2: self.length = length
        return super().image(index)

    # _cleanIndex redraws/recalculates dirty images/resolutions and returns an in-range index value.
    def _cleanIndex(self, index:int) -> int:
        if self._img_dirty:
            if index >= len(self._img_dirty): index = index % len(self._img_dirty)
            w, h = (self.breadth, self.length) if self._vertical else (self.length, self.breadth)
            if self._img_dirty[index] or ((w, h) != self._resolutions[index]):
                self._draw(index, w, h)
                self._img_dirty[index] = False
        return index % len(self._images)

    def _draw(self, index:int = 0, w:int = 0, h:int = 0):
        c1w, c1h = self.cap1.resolution(index)
        c2w, c2h = self.cap2.resolution(index)

        if w >= c2w and h >= c2h:
            new_img = tk.PhotoImage(width=w, height=h)
            # If the bar itself uses bg_colors, flood fill the whole new image.
            if self._use_bg_colors: fastFlood(new_img, w, h, self._bg_colors[index])

            # Calculate values
            if self._vertical:
                c2y = h-c2h                                 # Cap-2's y (height - height of cap)
                bbox = (0, c1h, w, c2y)                     # Trough fill-area as (x,y,w,h)
                cx, cy = int((w*0.5) - c1w*0.5), 0          # Cap-1 Center-x/y
                cx2, cy2 = int((w * 0.5) - c2w*0.5), c2y    # Cap-2 Center-x/y
            else:
                c2x = w-c2w
                bbox = (c1w, 0, c2x, h)
                cx, cy = 0, int((h*0.5) - c1h*0.5)
                cx2, cy2 = c2x, int((h * 0.5) - c1h*0.5)

            # Composite the trough
            fastTile(self.trough.image(index), *self.trough.resolution(index), new_img, w, h, bbox)
            # Composite the first cap
            fastComposite(new_img, w, h, self.cap1.image(index), cx, cy, *self.cap1.resolution(index))
            # Composite the second cap
            fastComposite(new_img, w, h, self.cap2.image(index), cx2, cy2, c2w, c2h)

            self._saveImage(new_img, index, "generated by BarSkin", (w,h))

    def _expand(self, size:int):       # Expands path and image lists to new length.
        for n in range(size):
            if len(self._paths) < size:         self._paths.append(None)
            if len(self._images) < size:        self._images.append(True)       # True appears as though hasImages()
            if len(self._resolutions) < size:   self._resolutions.append((0,0))

"""
    ButtonSkin accepts a single image, and a declaration of that image's facing/pointing direction as its orientation.
    From that image, it rotates and mirrors, to generate all other cardinal directions, preserving the "outside" edge.
    The bottom and the right are considered the "outside" edge, and so an east-facing image will be rotated clockwise
    to generate its south-facing sibling. And then the north-facing image is mirrored from the south-facing one. 
"""
class CardinalSkin(CoreSkin):
    def __init__(self, image:tk.PhotoImage, orientation:str = "n"):
        super().__init__()
        self._orientation = self._get_orientation(orientation)

        self._expand(4)
        self._saveAllImages(image)
        self._use_bg_colors = False

    def _saveAllImages(self, image: tk.PhotoImage):
        o = self._orientation   # Original orientation. [n,e,s,w as 0,1,2,3]
        r = (o + 1) % 4         # Rotated neighbor
        s = (o + 2) % 4         # Opposite of original
        t = (r + 2) % 4         # Opposite of rotated

        self._saveImage(image, o, "passed internally")
        if o in (0, 2):     # North/South → vertical axis
            self._transformImage(o, s, flip_y=True)                     # O → S
            self._transformImage(o, r, rotate=True, clockwise=True)     # O → R
            self._transformImage(r, t, flip_x=True)                     # R → T

        else:               # East/West → horizontal axis
            self._transformImage(o, s, flip_x=True)
            self._transformImage(o, r, rotate=True, clockwise=False)
            self._transformImage(r, t, flip_y=True)

    def _transformImage(self, source_index:int, dest_index:int, rotate:bool=False, clockwise:bool=False,
                        flip_x:bool=False, flip_y:bool=False):
        img = self._images[source_index]
        if rotate: img = rotateImage(img, clockwise)
        if flip_x or flip_y: img = flipImage(img, flip_x, flip_y)
        self._saveImage(img, dest_index, "generated by CardinalSkin")

    @staticmethod
    def _get_orientation(orientation:str) -> int:
        _directions = {"n":0, "e":1, "s":2, "w":3}
        if orientation:
            orientation = orientation.lower()[0]
            if orientation in _directions:
                return _directions[orientation]
        return 0


""" SkinPack is a container class for holding multiple skins, that exists only to be extended by its children. """
class SkinPack:
    def __init__(self, *skins):
        self._skins = list(skins)

    def skin(self, index:int = 0): return self._skins[index % len(self._skins)]

    def setSkin(self, skin:CoreSkin, index:int = 0):
        if index < len(self._skins): self._skins[index] = skin
        else: warnPrint(f"SkinPack.setSkin() was passed an out-of-range index: {index} ")
    def insertSkin(self, skin:CoreSkin, index:int = 0):
        if index < len(self._skins): self._skins.insert(index, skin)
        else: warnPrint(f"SkinPack.insertSkin() was passed an out-of-range index: {index} ")
    def appendSkin(self, skin:CoreSkin): self._skins.append(skin)
    def popSkin(self, index:int = 0): return self._skins.pop(index)


class ButtonPack(SkinPack):
    _cardinals = {"n":0, "e":1, "s":2, "w":3}
    def __init__(self, button_north:CoreSkin, button_east:CoreSkin, button_south:CoreSkin, button_west:CoreSkin):
        super().__init__(button_north or None, button_east or None, button_south or None, button_west or None)
        self._use_bg_colors = False

    @property
    def north(self): return Skin() if self._skins[0] is None else self._skins[0]
    @property
    def east(self): return Skin() if self._skins[1] is None else self._skins[1]
    @property
    def south(self): return Skin() if self._skins[2] is None else self._skins[2]
    @property
    def west(self): return Skin() if self._skins[3] is None else self._skins[3]

    @property
    def skins(self): return self._skins

    def usesBgColors(self, use:bool = None):
        if use:
            [skin.usesBgColors(use) for skin in self._skins]
            self._use_bg_colors = use
        return self._use_bg_colors

    @classmethod
    def fromOne(cls, button_skin:CoreSkin, orientation:str = "n"):
        if orientation := orientation.lower()[0]:
            if orientation in cls._cardinals and button_skin is not None:
                o = cls._cardinals[orientation]     # Original orientation. [n,e,s,w as 0,1,2,3]
                r = (o + 1) % 4                     # Rotated neighbor
                s = (o + 2) % 4                     # Opposite of original
                t = (r + 2) % 4                     # Opposite of rotated

                skins = [None, None, None, None]

                # The pattern below preserves inner/outer relationships, where south and east are the outer directions.
                skins[o] = button_skin
                if o in (0, 2):     # North/South → vertical axis
                    skins[s] = FilterSkin(skins[o], mirror_y=True)                                  # O → S
                    skins[r] = FilterSkin(skins[o], rotate=True, mirror_x=True)                     # O → R
                    skins[t] = FilterSkin(skins[r], mirror_x=True)                                  # R → T
                else:               # East/West → horizontal axis
                    skins[s] = FilterSkin(skins[o], mirror_x=True)                                  # O → S
                    skins[r] = FilterSkin(skins[o], rotate=True)                                    # O → R
                    skins[t] = FilterSkin(skins[r], mirror_y=True)                                  # R → T

                return cls(*skins)
        return cls(Skin(), Skin(), Skin(), Skin())


"""
    ScrollSkin stores two BarSkins for use in rendering the vertical and horizontal ScrollBars of a Scrollable.
    It provides a .fromSkins() method that enables creation by as little as 2 skins.
    .fromSkins()        - scroll1 = ScrollSkin.fromSkins(cap1, trough, vertical = True)
    When .fromSkins() is given only the first cap and a trough, it generates the 2nd cap by mirroring the first, and
    generates both the vertical and horizontal BarSkin by rotating whichever one was given. 
"""
class ScrollSkin(SkinPack):
    def __init__(self, vertical_bar:BarSkin, horizontal_bar:BarSkin, button_pack:ButtonPack = None):
        super().__init__(vertical_bar or None, horizontal_bar or None, button_pack)

    @classmethod
    def fromSkins(cls, cap_skin:Skin, trough_skin:Skin, cap_skin2:Skin|None = None, vertical:bool = True,
                  button_skin:Skin|None = None, button_orientation:str = "n"):
        buttons = ButtonPack.fromOne(button_skin, button_orientation) if button_skin is not None else None
        return cls(*cls._barsFromSkins(cap_skin, trough_skin, cap_skin2, vertical), buttons)

    @property
    def vertical(self) -> BarSkin: return BarSkin() if self._skins[0] is None else self._skins[0]
    @property
    def horizontal(self) -> BarSkin: return BarSkin() if self._skins[1] is None else self._skins[1]
    @property
    def button(self) -> ButtonPack: return self._skins[2]

    def setBars(self, vertical:BarSkin = None, horizontal:BarSkin = None):
        if vertical: self._skins[0] = vertical
        if horizontal: self._skins[1] = horizontal

    def setBySkins(self, cap_skin:Skin, trough_skin:Skin, cap_skin2:Skin|None = None, vertical:bool = True,
                   button_skin:Skin|None = None, button_orientation:str = "n"):
        self._skins[0], self._skins[1] = self._barsFromSkins(cap_skin, trough_skin, cap_skin2, vertical)
        if button_skin is not None: self._skins[2] = ButtonPack.fromOne(button_skin, button_orientation)

    @classmethod
    def _barsFromSkins(cls, cap_skin:Skin, trough_skin:Skin, cap_skin2:Skin|None = None,
                       vertical:bool = True) -> tuple[BarSkin, BarSkin]:
        bar1 = BarSkin(cap_skin, trough_skin, cap_skin2, vertical)
        new_cap = FilterSkin(bar1.cap1, rotate=True, mirror_x = not vertical, mirror_y=not vertical)
        new_trough = FilterSkin(bar1.trough, rotate=True, mirror_x = not vertical, mirror_y=not vertical)
        new_cap2 = FilterSkin(bar1.cap2, rotate=True, mirror_x = not vertical, mirror_y=not vertical)
        bar2 = BarSkin(new_cap, new_trough, new_cap2, not vertical)
        bar2.setBGColors(*bar1.bg_colors)
        return (bar1, bar2) if vertical else (bar2, bar1)


"""
    Skinnable is a mixin that provides core Skin() functionality to guiABLE widgets. It requires a sibling class that
    can make use of after_idle(), for its update() method.
"""
class Skinnable:
    def __init__(self, skin:Skin|BarSkin|FilterSkin = None):
        # Register widget as a user of skin, in case skin updates later and needs to issue a redraw of all users.
        if skin is None:
            try: self._skin = self._default_skin
            except: self._skin = Skin()
        else: self._skin = skin

        self._skin.bindWidget(self)

        self._scratch = None
        self._children = []
        self._geometry = (0, 0, 0, 0)

    @property
    def skin(self) -> CoreSkin: return self._skin

    # Skin registration methods
    def setSkin(self, skin:CoreSkin):
        if self._skin:
            self._skin.unbindWidget(self)
        self._skin = skin
        self._skin.bindWidget(self)

    def dropSkin(self):
        if self._skin: self._skin.unbindWidget(self)
        self._skin = Skin()

    # Speed enhancing methods.
    @property       # Geometry is tracked, providing much faster access than winfo_ gives.
    def geometry(self) -> tuple[int,int,int,int]: return self._geometry
    @property
    def size(self): return self._geometry[2:]
    @property
    def location(self): return self._geometry[:2]
    @property
    def x(self): return self._geometry[0]
    @property
    def y(self): return self._geometry[1]
    @property
    def width(self): return self._geometry[2]
    @property
    def height(self): return self._geometry[3]

    # Persistent PhotoImage provides an INSTANT redraw canvas in compositing.
    def scratchImage(self): return self._scratch

    # Public callable update event that waits until idletasks are complete. (scheduled changes have been applied)
    def refresh(self, event=None): self._refresh(event)

    # Parents that host child widgets track their children and provide a list of those children's z-order.
    def getChildren(self): return self._children
    def registerChild(self, child):
        if child not in self._children: self._children.append(child)
    def dropChild(self, child):
        if child in self._children: self._children.remove(child)

    # Methods for maintaining child z_order on lift/lower configurations.
    def _raiseChildIndex(self, child, above):
        self.dropChild(child)
        if above and above in self._children:
            index = self._children.index(above) + 1
            self._children.insert(index, child)
        else:
            self._children.append(child)

    def _lowerChildIndex(self, child, below):
        self.dropChild(child)
        if below and below in self._children:
            index = self._children.index(below)
            self._children.insert(index, child)
        else:
            self._children.insert(0, child)

    # _update runs On instantiation, and when any tracked change takes place thereafter.
    def _refresh(self, event=None):
        last_geometry = self._geometry
        self._geometry = getGeometry(self)
        if last_geometry[2:] != self._geometry[2:]:
            self._scratch = tk.PhotoImage(width=self._geometry[2], height=self._geometry[3])
        if last_geometry[:2] != self._geometry[:2]:
            self.redraw()

        # If skin provides no image, generate a Skin, utilizing the FilterSkin override for skins that useBgColors().
        if not self._skin.hasImages():
            self._skin._paths, self._skin._images, self._skin._resolutions = [], [], []
            self._skin._expand(1)       # Sneaking in via private methods to preserve _use_bg_colors.
            self._skin._saveImage(tk.PhotoImage(width=self._geometry[2], height=self._geometry[3]), 0, "no image")
            self._skin.updateRecipients()
