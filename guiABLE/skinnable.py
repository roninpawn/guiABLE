import tkinter as tk

from guiABLE.utilities import warnPrint, resolvePath, loadImage, getGeometry
from guiABLE.uimage import UImage


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
        self._images = []
        self._empty_image = UImage()
        self._default_colors = ['#6B6B6B', '#828282', '#C7C7C7', '#454545']
        self._bg_colors = self._default_colors
        self._use_bg_colors = True
        self._filter = None     # Internal FilterSkin for compositing to background colors.
        self._skin_res = (0, 0)

    # Core access methods
    @property
    def images(self) -> list[UImage]: return self._images
    def image(self, index:int = 0) -> UImage:
        if self._images:
            # If bg_colors in use, use FilterSkin to composite, cache, and return without corrupting held images.
            if self._use_bg_colors:
                if self._filter is None: self._filter = FilterSkin(self)
                return self._filter.image(index)
            return self._images[index % len(self._images)]
        return self._empty_image

    def resolution(self, image_index: int = None) -> tuple[int, int]:
        if any(self._images):
            if image_index is None: return self._skin_res
            else: return self._images[image_index % len(self._images)].resolution
        return (0, 0)

    def isOpaque(self, image_index: int=0) -> bool:
        if any(self._images):
            image_index %= len(self._images)
            return self._images[image_index].isOpaque()
        return True

    @property
    def bg_colors(self) -> list[str]: return self._bg_colors
    def bgColor(self, index: int = 0) -> str | None:
        if self._use_bg_colors and len(self._bg_colors): return self._bg_colors[index % len(self._bg_colors)]
        return None     # Represents alpha

    def reset(self):
        self._images = []
        self._skin_res = (0, 0)
        self._bg_colors = self._default_colors
        self.updateRecipients()

    # Informational methods
    def hasImages(self): return any(self._images)
    def usesBgColors(self, use:bool = None) -> bool:
        if use is not None:
            self._use_bg_colors = use
            if not use: self._filter = None     # Unload internal FilterSkin if no longer in use.
            self.updateRecipients()
        return self._use_bg_colors

    def numStates(self):
        return max(len(self._images), len(self._bg_colors)) if self._use_bg_colors else len(self._images)

    def _saveImage(self, image:UImage, index:int):
        self._images[index] = image

        # Expand skin dimensions to contain every image, on every axis.
        new_res = list(self._skin_res)
        if image.width() > new_res[0]: new_res[0] = image.width()
        if image.height() > new_res[1]: new_res[1] = image.height()
        self._skin_res = tuple(new_res)

    @staticmethod
    def _fillList(in_list:list) -> list:
        fallback = next(l for l in in_list if l)     # Find first non-Falsy entry

        for i, l in enumerate(in_list):      # Fill in any gaps by propagating the most recent valid data forward.
            if l: fallback = l
            else: in_list[i] = fallback

        return in_list

    def _expand(self, size:int):       # Expands path and image lists to new length.
        while len(self._images) < size: self._images.append(None)


"""
    ColorSkin adds methods for creating/manipulating multiple background colors.
    ex: new_skin = ColorSkin.fromColors('yellow', 'blue', 'orange', 'gray15')
"""
class ColorSkin(CoreSkin):
    @classmethod
    def fromColors(cls, width:int, height:int, *colors:str):
        images = []

        for color in colors:
            img = UImage(width=width, height=height)
            if color: img.flood(color)
            images.append(img)

        return cls(*images)

    @classmethod
    def Transparent(cls, width:int, height:int): return cls.fromColors(width, height, "")

    def setBGColors(self, *colors:str):
        if colors:
            self._bg_colors = list(colors)
            self.updateRecipients()

    def setBGColor(self, color:str, index:int=0):
        while index < -len(self._bg_colors) or index >= len(self._bg_colors):
            self._bg_colors.extend(self._bg_colors)

        self._bg_colors[index] = color
        self.updateRecipients()

    def appendBGColors(self, *colors:str):
        if colors:
            self._bg_colors.extend(colors)
            self.updateRecipients()


class NoSkin(ColorSkin):
    """ Per-widget fallback Skin whose blank source always matches its widget's geometry. """
    def __init__(self, width:int=0, height:int=0):
        super().__init__()
        self.resize(width, height, notify=False)

    def resize(self, width:int, height:int, notify:bool=True):
        width, height = max(0, width), max(0, height)
        if (width, height) == self._skin_res and self._images: return

        self._images = []
        self._skin_res = (0, 0)

        if width and height:
            self._expand(1)
            self._saveImage(UImage(width=width, height=height), 0)

        # CoreSkin.image() may already have created the internal FilterSkin.
        if self._filter is not None: self._filter.dirty = True
        if notify: self.updateRecipients()


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
    def __init__(self, *paths_or_images:str|UImage, orientation:str = None):
        super().__init__()

        if any(paths_or_images):
            self._expand(len(paths_or_images))
            self._byAny(paths_or_images)
        self._orientation = orientation.lower()[0] if orientation else None

    """
    fromSpriteSheet -- A single image that contains all variants of a widget's state.
    width_per_sprite:      The number of pixels, across, that each sprite should have. 
    rows:       How many rows of sprites in the sheet (default=1)
    margins:    The gap, on each axis, BETWEEN sprites. Assumes NO margin at the image's edges. (default=(0,0))  
    Example:    Skin.fromSpriteSheet("/skins/default/checkbox.png", width=32, rows=2, margins=(4,4))
    """
    @classmethod
    def fromSpriteSheet(cls, path_or_image:str|UImage, width_per_sprite:int, rows:int = 1, margins:tuple = (0, 0),
                        orientation:str = None):
        sheet, path = loadImage(path_or_image)
        if sheet is not None: return cls(*sheet.getSprites(width_per_sprite, rows, margins),
                                                                                            orientation=orientation)
        return cls()
    def setSprites(self, path_or_image:str|UImage, width_per_sprite:int, rows:int = 1, margins:tuple = (0,0)):
        sheet, path = loadImage(path_or_image)
        if sheet is not None:
            self._images = []
            self._skin_res = (0, 0)
            self._byAny(sheet.getSprites(width_per_sprite, rows, margins))
        self.updateRecipients()

    def set(self, *paths_or_images:str|UImage, index:int = 0, skip_falsy:bool = True):
        upper = index + len(paths_or_images)
        if upper > len(self._images): self._expand(upper)
        self._byAny(paths_or_images, skip_falsy=skip_falsy, index_offset=index)
        self.updateRecipients()

    @property
    def orientation(self): return self._orientation
    @orientation.setter
    def orientation(self, orientation:str):
        self._orientation = orientation.lower()[0] if orientation else None

    """ Private Functions """
    def _byAny(self, collection:tuple|list, skip_falsy:bool = False, index_offset:int = 0) :
        for i, entry in enumerate(collection):
            i += index_offset
            if not entry:       # If None or Falsy...
                if skip_falsy: continue
                self._images[i] = None
            elif isinstance(entry, str):        # If str, representing a file path...
                r_path = resolvePath(entry)
                if e := self._existsAt(r_path): self._saveImage(self._images[e], i)
                else:
                    try:
                        self._saveImage(UImage(file=r_path), i)
                    except tk.TclError:
                        warnPrint(f"Image not found: {r_path}")
            elif isinstance(entry, UImage):     # If a pre-loaded UImage...
                self._saveImage(entry, i)

        self._fillImages()

    def _existsAt(self, path:str) -> int|None:
        for i in range(len(self._images)):
            if self._images[i] and self._images[i].path == path: return i
        return None

    def _fillImages(self):
        fallback = next((i for i in self._images if i is not None), None)       # Find first real image.
        if fallback is None: return

        self._use_bg_colors = False     # If images were loaded, default to transparency.
        for i in range(len(self._images)):      # Fill in any gaps by propagating the most recent valid image forward.
            if self._images[i] is None:
                self._images[i] = fallback
            else: fallback = self._images[i]


""" DirtySkin is a mix-in that adds per-image dirtiness tracking to a CoreSkin descendant. """
class DirtySkin:
    def __init__(self):
        self.dirty = True
        self._img_dirty = []

    def image(self, image_index: int = 0, *args) -> UImage:
        if self.dirty: self._cleanSkin()
        if self.hasImages():
            image_index = self._cleanIndex(image_index, *args)
            if self._images[image_index]: return self._images[image_index]      # Return the image requested.
        return self._empty_image

    def resolution(self, image_index: int = 0) -> tuple[int, int]:
        if self.dirty: self._cleanSkin()
        return self._images[self._cleanIndex(image_index)].resolution

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
    def _draw(self, index:int): pass


"""
    FilterSkin provides a cached and ready view of another skin, as mirrored/rotated/flood-filled in place.
    Changes to the original skin will be reflected in the FilterSkin as well. 
"""
class FilterSkin(DirtySkin, CoreSkin):
    def __init__(self, linked_skin:CoreSkin, crop:tuple[int,int,int,int]|None = None,
                 rotate:bool = False, mirror_x:bool = False, mirror_y:bool = False):
        DirtySkin.__init__(self)
        CoreSkin.__init__(self)

        # If the source skin is -itself- a FilterSkin, link directly to that skin's source, and sum with its transforms.
        if isinstance(linked_skin, FilterSkin):
            rotate, mirror_x, mirror_y = self._state_sum(
                (linked_skin.rotate, linked_skin.mirror_x, linked_skin.mirror_y), (rotate, mirror_x, mirror_y)
            )
            self._linked_skin = linked_skin.linked_skin
        else: self._linked_skin = linked_skin

        self.crop = crop
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
        self._bg_colors = self._linked_skin.bg_colors
        self._images = list(self._linked_skin.images)

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
        image_index = index % len(self._linked_skin._images)
        img = self._linked_skin.images[image_index]     # Acquire the original, unmodified image from linked_skin.

        if self.crop is not None: img = img.crop(*self.crop)

        w, h = self._linked_skin.resolution(image_index)
        if self.rotate:                                 # Rotate image as requested.
            img = img.rotate(False)
            w, h = h, w
        img = img.flip(self.mirror_x, self.mirror_y)      # Mirror/flip image as requested.

        if self._linked_skin.usesBgColors():            # Composite background color, if the linked image uses one.
            flood_img = UImage(width=w, height=h)
            if self._bg_colors[index]: flood_img.flood(self._bg_colors[index])
            img.cropTo(flood_img, width=w, height=h)
            img = flood_img

        while len(self._images) <= index: self._images.append(self._empty_image)
        self._images[index] = img

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

    def usesBgColors(self, use:bool=None) -> bool:
        if use is not None:
            if use: self._expand(max(len(self._images), len(self._bg_colors)))
            self.dirty = True

        return super().usesBgColors(use)

    def image(self, index:int=0, length:int=None) -> UImage:
        if length and length != self.length and length > 2: self.length = length
        return super().image(index)

    # _cleanIndex redraws/recalculates dirty images/resolutions and returns an in-range index value.
    def _cleanIndex(self, index:int) -> int:
        if self._img_dirty:
            if index >= len(self._img_dirty): index = index % len(self._img_dirty)
            w, h = (self.breadth, self.length) if self._vertical else (self.length, self.breadth)
            if self._img_dirty[index] or ((w, h) != self._images[index].resolution):
                self._draw(index, w, h)
                self._img_dirty[index] = False
        return index % len(self._images)

    def _draw(self, index:int = 0, w:int = 0, h:int = 0):
        c1w, c1h = self.cap1.resolution(index)
        c2w, c2h = self.cap2.resolution(index)

        if w >= c2w and h >= c2h:
            new_img = UImage(width=w, height=h)
            # If the bar itself uses bg_colors, flood fill the whole new image.
            if self._use_bg_colors:
                new_img.flood(self._bg_colors[index])

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
            self.trough.image(index).tileTo(new_img, bbox)
            # Composite the first cap
            self.cap1.image(index).cropTo(new_img, dest_x=cx, dest_y=cy)
            # Composite the second cap
            self.cap2.image(index).cropTo(new_img, dest_x=cx2, dest_y=cy2)

            self._saveImage(new_img, index)

    def _expand(self, size:int):       # Expands path and image lists to new length.
        for n in range(size):
            if len(self._images) < size: self._images.append(True)       # True appears as though hasImages()


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


""" Adds methods for registering, reporting, and altering children of a widget. """
class Childable():
    def __init__(self, parent, *args, **kwargs):
        # Logical parents may redirect their children to a different physical Tk host.
        master = parent.childMaster() if hasattr(parent, "childMaster") else parent
        super().__init__(master, *args, **kwargs)

        self._children = []
        self._parent = parent
        self._window = parent.window if getattr(parent, 'window', False) else parent

    @property
    def parent(self): return self._parent
    @property
    def window(self): return self._window

    # By default, a widget is its children's physical host and uses the same local coordinate space.
    def childMaster(self): return self
    def mapChildToMaster(self, x:int, y:int) -> tuple[int,int]: return x, y
    def mapMasterToChild(self, x:int, y:int) -> tuple[int,int]: return x, y

    # Rendering is local to the parent by default. Coordinate spaces may override either mapping independently.
    def childRenderArea(self) -> tuple[int,int,int,int]|None:
        return (0, 0, *self.size) if hasattr(self, "size") else None
    def childBackgroundPoint(self, x:int, y:int, width:int=0, height:int=0) -> tuple[int,int]:
        return self.mapChildToMaster(x, y)

    # Parents that host child widgets track their children and provide a list of those children's z-order.
    def getChildren(self): return self._children
    def registerChild(self, child):
        if child not in self._children:
            self._children.insert(0, child)
    def dropChild(self, child):
        if child in self._children: self._children.remove(child)
    def childChanged(self, child): pass     # Override this function in other classes.

    def destroy(self):
        self._parent.dropChild(self)
        super().destroy()

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

    def _afterGeometryChanges(self):
        if isinstance(self._parent, Childable):
            self._parent.childChanged(self)                  # Inform your parent that you've changed.
        self._refreshChildren()

    def _refreshChildren(self):
        for child in self._children: child.refresh()


"""
    Measureable captures geometry events and provides convenient points of access for that info. By tracking as much as
    possible, internally, slow winfo_() calls are avoided, and values are pollable without needing to update idletasks. 
"""
class Measurable(Childable):
    def __init__(self, *args, **kwargs):
        w = kwargs['width'] if 'width' in kwargs else 0
        h = kwargs['height'] if 'height' in kwargs else 0

        self._geometry = (0, 0, w, h)
        self._last_geometry = (0,0,0,0)

        super().__init__(*args, **kwargs)

    # Geometry is tracked, providing much faster access than winfo_ methods can offer.
    @property
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

    # _refresh is meant to run on any <Configure> binded event.
    def refresh(self, event=None): self._refresh(event)
    def _refresh(self, event=None):
        if event is not None:
            x, y = event.x, event.y
            if hasattr(self.parent, "mapMasterToChild"): x, y = self.parent.mapMasterToChild(x, y)

            self._geometry = (x, y, event.width, event.height)

        if self._last_geometry != self._geometry: self._afterGeometryChanges()
        self._last_geometry = self._geometry


""" Placeable intercepts place() methods to extend functionality and return self, for one-line instancing. """
class Placeable(Measurable):
    def __init__(self, *args, **kwargs):
        self._size_declared = [False, False]
        self._placed = False
        super().__init__(*args, **kwargs)

    # TODO: Can route place() through place_configure if we handle auto-expansion in place_configure.
    def place(self, x:int=None, y:int=None, **kwargs):
        self._placed = True

        if 'x' not in kwargs and x is not None: kwargs['x'] = x
        if 'y' not in kwargs and y is not None: kwargs['y'] = y
        if 'width' in kwargs: self._size_declared[0] = True
        if 'height' in kwargs: self._size_declared[1] = True

        # Immediately maintain guiABLE's local geometry.
        local_x = kwargs.get('x', self.x)
        local_y = kwargs.get('y', self.y)
        width = kwargs.get('width', self.width)
        height = kwargs.get('height', self.height)

        self._geometry = (local_x, local_y, width, height)

        # Map local coordinates to the physical Tk host chosen by the logical parent.
        if hasattr(self._parent, "mapChildToMaster"):
            kwargs['x'], kwargs['y'] = self._parent.mapChildToMaster(local_x, local_y)

        super().place(**kwargs)
        return self

    def place_configure(self, x:int=None, y:int=None, **kwargs):
        # Enables passing .place(int, int) for x, y, or .place(x=int, y=int), or no x/y passed.
        if 'x' not in kwargs:
            kwargs['x'] = x if x is not None else self.x
        if 'y' not in kwargs:
            kwargs['y'] = y if y is not None else self.y

        implied = kwargs.pop('implied', False)
        if 'width' in kwargs:
            if not implied: self._size_declared[0] = True
        else: kwargs['width'] = self.width
        if 'height' in kwargs:
            if not implied: self._size_declared[1] = True
        else: kwargs['height'] = self.height

        # 'skip=True' avoids _afterGeometryChanges() by matching _last_geometry to the new geometry.
        self._geometry = (kwargs['x'], kwargs['y'], kwargs['width'], kwargs['height'])
        skip = kwargs.pop('skip', False)
        if skip: self._last_geometry = self._geometry

        # Map local coordinates to the physical Tk host chosen by the logical parent.
        local_x, local_y = kwargs['x'], kwargs['y']
        if hasattr(self._parent, "mapChildToMaster"):
            kwargs['x'], kwargs['y'] = self._parent.mapChildToMaster(local_x, local_y)
        super().place_configure(**kwargs)

        return self     # Enables one-line instantiation and placement. eg. my_btn = Button(...).place(10, 10)

    # Re-apply local geometry to Tk without changing the local coordinates themselves.
    def _reposition(self):
        x, y = self._parent.mapChildToMaster(self.x, self.y) \
            if hasattr(self._parent, "mapChildToMaster") else self.location
        super().place_configure(x=x, y=y, width=self.width, height=self.height)


""" Skinnable is a mixin that provides core Skin() handling functionality to guiABLE widgets. """
class Skinnable(Placeable):
    def __init__(self, *args, skin:Skin|BarSkin|FilterSkin|str|UImage|tuple|list = None, **kwargs):
        default_skin = getattr(self, "_default_skin", None)

        if skin:
            self._skin_passed = True
            # Handle all possible forms of passing a non-skin Skin().
            if isinstance(skin, str|UImage): skin = Skin(skin)
            elif isinstance(skin, list|tuple): skin = Skin(*skin)

            res = skin.resolution()
            if res != (0, 0):   # If no widget dimensions are given at instantiation, use skin dimensions.
                if 'width' not in kwargs or kwargs['width'] is None: kwargs['width'] = res[0]
                if 'height' not in kwargs or kwargs['height'] is None: kwargs['height'] = res[1]
            self._skin = skin

        elif default_skin is not None:
            self._skin_passed = False
            self._skin = default_skin

        else:
            self._skin_passed = False
            self._skin = NoSkin()

        self._skin.bindWidget(self)     # Register widget as a user of skin, so changes to the skin can be propagated.

        super().__init__(*args, **kwargs)

        if isinstance(self._skin, NoSkin): self._skin.resize(self.width, self.height, notify=False)

        self._scratch = UImage(width=self.width, height=self.height)
        self.dirty = True

    @property
    def skin(self) -> CoreSkin: return self._skin

    # Skin registration methods
    def setSkin(self, skin:CoreSkin, implied=False):
        if not implied: self._skin_passed = True
        if self._skin:
            self._skin.unbindWidget(self)
        self._skin = skin
        self._skin.bindWidget(self)

    def dropSkin(self):
        self._skin_passed = False
        if self._skin: self._skin.unbindWidget(self)

        self._skin = NoSkin(self.width, self.height)
        self._skin.bindWidget(self)

    def isOpaque(self): return  self.skin.resolution(self.state) == self.size and \
                               (self.skin.usesBgColors() or self.skin.isOpaque(self.state))

    # Persistent UImage provides an INSTANT redraw canvas in compositing.
    def scratchImage(self): return self._scratch

    # _refresh runs on instantiation, and when any tracked change takes place thereafter.
    def refresh(self): self._refresh()
    def _refresh(self, event=None): super()._refresh(event)

    def _afterGeometryChanges(self):
        if self._last_geometry[2:] != self._geometry[2:]:
            self._scratch = UImage(width=self.width, height=self.height)

            if isinstance(self._skin, NoSkin):
                self._skin.resize(self.width, self.height, notify=False)
                self.dirty = True

        self.redraw()
        super()._afterGeometryChanges()
