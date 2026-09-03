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
    def imageFor(self, recipient, index:int=0) -> UImage: return self.image(index)

    def resolution(self, image_index: int = None) -> tuple[int, int]:
        if any(self._images):
            if image_index is None: return self._skin_res
            else: return self._images[image_index % len(self._images)].resolution
        return (0, 0)
    def resolutionFor(self, recipient, image_index:int=None) -> tuple[int,int]: return self.resolution(image_index)

    def isOpaque(self, image_index: int=0) -> bool:
        if any(self._images):
            image_index %= len(self._images)
            return self._images[image_index].isOpaque()
        return True
    def isOpaqueFor(self, recipient, image_index:int=0) -> bool: return self.imageFor(recipient, image_index).isOpaque()

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
    def usesBgColors(self, use:bool=None) -> bool:
        if use is not None:
            use = bool(use)

            if use != self._use_bg_colors:
                self._use_bg_colors = use
                if not use: self._filter = None
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


class DirtySkin:
    """ A mix-in that adds per-image dirtiness tracking to a CoreSkin descendant. """
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

    def isOpaque(self, image_index:int=0) -> bool: return self.image(image_index).isOpaque()

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


class LinkedSkin(CoreSkin):
    """ Base for Skins that remain live-linked to another Skin. """
    def __init__(self, linked_skin:CoreSkin):
        CoreSkin.__init__(self)
        self._linked_skin = None
        self.link(linked_skin, notify=False)

    @property
    def linked_skin(self): return self._linked_skin

    def link(self, skin:CoreSkin, notify:bool=True):
        if skin is self._linked_skin: return
        if self._linked_skin is not None:
            self._linked_skin.unbindWidget(self)

        self._linked_skin = skin
        skin.bindWidget(self)
        self.dirty = True

        if notify: self.updateRecipients()

    def unlink(self):
        if self._linked_skin is None: return
        self._linked_skin.unbindWidget(self)
        self._linked_skin = None

    def redraw(self):
        self.dirty = True
        self.updateRecipients()


"""
    FilterSkin provides a cached and ready view of another skin, as mirrored/rotated/flood-filled in place.
    Changes to the original skin will be reflected in the FilterSkin as well. 
"""
class FilterSkin(DirtySkin, LinkedSkin):
    def __init__(self, linked_skin:CoreSkin, crop:tuple[int,int,int,int]|None=None,
                 rotate:bool=False, mirror_x:bool=False, mirror_y:bool=False):
        DirtySkin.__init__(self)

        # Flatten FilterSkin chains while preserving the combined transformation.
        if isinstance(linked_skin, FilterSkin):
            rotate, mirror_x, mirror_y = self._state_sum(
                (linked_skin.rotate, linked_skin.mirror_x, linked_skin.mirror_y),
                (rotate, mirror_x, mirror_y)
            )
            linked_skin = linked_skin.linked_skin

        LinkedSkin.__init__(self, linked_skin)

        self.crop = crop
        self.mirror_x = mirror_x
        self.mirror_y = mirror_y
        self.rotate = rotate

        try:
            self._orientation = self._linked_skin.orientation
            if self._orientation: self._transformOrientation()
        except:
            self._orientation = None

        self._cleanSkin()

    def numStates(self) -> int: return self._linked_skin.numStates()

    def set(self, *args, **kwargs):
        raise TypeError(
            "FilterSkin is a live transformation and cannot be set directly. \n"
            "Use filter.linked_skin.set to change the source, or replace the consuming slot instead."
        )

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


class SkinView(LinkedSkin):
    """ Fixed-resolution live view of an AssembledSkin realization. """
    def __init__(self, linked_skin:'AssembledSkin', width:int, height:int):
        CoreSkin.__init__(self)

        self._linked_skin = linked_skin
        self._size = width, height
        self._linked = False

    @property
    def size(self): return self._size

    def image(self, index:int=0) -> UImage:
        return self._linked_skin.imageFor(self, index)

    def imageFor(self, recipient, index:int=0) -> UImage: return self.image(index)

    def resolution(self, image_index:int=None) -> tuple[int,int]: return self._size
    def resolutionFor(self, recipient, image_index:int=None) -> tuple[int,int]: return self._size

    def isOpaque(self, image_index:int=0) -> bool: return self.image(image_index).isOpaque()
    def isOpaqueFor(self, recipient, image_index:int=0) -> bool: return self.isOpaque(image_index)

    def numStates(self): return self._linked_skin.numStates()
    def hasImages(self): return True
    def bgColor(self, index:int=0): return self._linked_skin.bgColor(index)

    def bindWidget(self, widget):
        if not self._linked:
            self._linked_skin.bindWidget(self)
            self._linked = True

        CoreSkin.bindWidget(self, widget)

    def unbindWidget(self, widget):
        CoreSkin.unbindWidget(self, widget)

        if self._linked and not self._recipients:
            self._linked_skin.unbindWidget(self)
            self._linked = False

    def redraw(self):
        self.updateRecipients()


class AssembledSkin(ColorSkin):
    """ Source-driven Skin that caches assembled rasters by recipient geometry. """
    def __init__(self, *parts:CoreSkin, width:int=0, height:int=0):
        super().__init__()

        # Assembled artwork presumes a transparent background unless a subclass or developer says otherwise.
        self._bg_colors = [""]
        self._use_bg_colors = True

        self._parts = tuple(parts)
        self._declared_size = [max(0, int(width)), max(0, int(height))]
        self._size_declared = [width > 0, height > 0]

        self._realizations = {}           # (w,h) -> [state images]
        self._realization_dirty = {}      # (w,h) -> [state dirty flags]
        self._recipient_sizes = {}        # recipient -> (w,h)
        self._size_users = {}             # (w,h) -> {recipients}

        self.dirty = False
        self._bindParts()

    @property
    def width(self): return self._resolvedSize()[0]
    @property
    def height(self): return self._resolvedSize()[1]

    def view(self, width:int=None, height:int=None, enforce_geometry:bool=False) -> SkinView:
        return SkinView(self, *self._viewSize(width, height, enforce_geometry))

    def image(self, index:int=0) -> UImage:
        return self._realizedImage(self._resolvedSize(), index)
    def imageFor(self, recipient, index:int=0) -> UImage:
        size = self._resolvedSize(recipient)
        self._associate(recipient, size)
        return self._realizedImage(size, index)

    def resolution(self, image_index:int=None) -> tuple[int,int]: return self._resolvedSize()
    def resolutionFor(self, recipient, image_index:int=None) -> tuple[int,int]: return self._resolvedSize(recipient)

    def isOpaque(self, image_index:int=0) -> bool: return self.image(image_index).isOpaque()
    def isOpaqueFor(self, recipient, image_index:int=0) -> bool:
        return self.imageFor(recipient, image_index).isOpaque()

    def hasImages(self): return True
    def numStates(self): return max(1, self._stateCount())

    def resize(self, width:int=None, height:int=None, notify:bool=True):
        changed = False

        for axis, value in enumerate((width, height)):
            if value is not None and value > 0:
                value = int(value)

                if value != self._declared_size[axis] or not self._size_declared[axis]:
                    self._declared_size[axis] = value
                    self._size_declared[axis] = True
                    changed = True

        if changed:
            self._markRealizationsDirty()
            if notify: self.updateRecipients()

    def unbindWidget(self, widget):
        super().unbindWidget(widget)
        self._release(widget)

    def redraw(self):
        self.dirty = False
        self.updateRecipients()

    def updateRecipients(self):
        self._markRealizationsDirty()
        super().updateRecipients()

    def _viewSize(self, width:int=None, height:int=None, enforce_geometry:bool=False) -> tuple[int,int]:
        size, requested, = [0, 0], (width, height)

        for axis in range(2):
            if enforce_geometry and self._size_declared[axis]:
                value = self._declared_size[axis]
            elif requested[axis] is not None:
                value = int(requested[axis])
            elif self._size_declared[axis]:
                value = self._declared_size[axis]
            else:
                value = self._naturalSize()[axis]

            size[axis] = max(self._minimumSize()[axis], value)

        return tuple(size)

    def _resolvedSize(self, recipient=None) -> tuple[int,int]:
        natural = self._naturalSize()
        size = list(recipient.size if recipient is not None else natural)

        for axis in range(2):
            if self._size_declared[axis]: size[axis] = self._declared_size[axis]

        minimum = self._minimumSize()
        return max(minimum[0], size[0]), max(minimum[1], size[1])

    def _realizedImage(self, size:tuple[int,int], index:int) -> UImage:
        states = self.numStates()
        images = self._realizations.setdefault(size, [])
        dirty = self._realization_dirty.setdefault(size, [])

        while len(images) < states: images.append(None)
        while len(dirty) < states: dirty.append(True)
        if len(images) > states: del images[states:]
        if len(dirty) > states: del dirty[states:]

        index %= states

        if dirty[index] or images[index] is None:
            images[index] = self._draw(index, *size)
            dirty[index] = False

        return images[index] or self._empty_image

    def _associate(self, recipient, size:tuple[int,int]):
        old_size = self._recipient_sizes.get(recipient)
        if old_size == size: return

        if old_size is not None:
            users = self._size_users.get(old_size)

            if users is not None:
                users.discard(recipient)
                if not users: self._dropRealization(old_size)

        self._recipient_sizes[recipient] = size
        self._size_users.setdefault(size, set()).add(recipient)

    def _release(self, recipient):
        size = self._recipient_sizes.pop(recipient, None)
        if size is None: return

        users = self._size_users.get(size)
        if users is not None:
            users.discard(recipient)
            if not users: self._dropRealization(size)

    def _dropRealization(self, size):
        if all(self._size_declared) and size == tuple(self._declared_size): return

        self._size_users.pop(size, None)
        self._realizations.pop(size, None)
        self._realization_dirty.pop(size, None)

    def _markRealizationsDirty(self):
        for dirty in self._realization_dirty.values():
            dirty[:] = [True] * len(dirty)

    def _setParts(self, *parts:CoreSkin, notify:bool=True):
        old_parts, new_parts = set(self._parts), set(parts)

        for part in old_parts - new_parts: part.unbindWidget(self)
        self._parts = tuple(parts)
        for part in new_parts - old_parts: part.bindWidget(self)

        if notify: self.updateRecipients()
        else: self._markRealizationsDirty()

    def _bindParts(self):
        for part in set(self._parts): part.bindWidget(self)

    def _stateCount(self) -> int:
        colors = len(self._bg_colors) if self._use_bg_colors else 0
        return max(1, colors, *(part.numStates() for part in self._parts))

    def _minimumSize(self) -> tuple[int,int]: return 1, 1
    def _naturalSize(self) -> tuple[int,int]: return self._minimumSize()
    def _draw(self, index:int, width:int, height:int) -> UImage: return self._empty_image


"""
ThreeSliceSkin assembles a variable-size image from optional start, repeatable middle, and end sections.
If only one end is supplied, the opposite end is generated by mirroring it. With no image parts,
background colors provide a dynamically sized stateful surface.
"""
class ThreeSliceSkin(AssembledSkin):
    def __init__(self, start:CoreSkin=None, middle:CoreSkin=None, end:CoreSkin=None,
                 vertical:bool=True, width:int=0, height:int=0):

        self._vertical = bool(vertical)
        self.middle = middle if middle is not None else Skin()

        if start is None and end is None:
            self.start, self.end = Skin(), Skin()

        elif start is None:
            self.end = end
            self.start = FilterSkin(end, mirror_x=not self._vertical, mirror_y=self._vertical)

        else:
            self.start = start
            self.end = end or FilterSkin(start, mirror_x=not self._vertical, mirror_y=self._vertical)

        super().__init__(self.start, self.middle, self.end, width=width, height=height)

        # A graphical ThreeSlice starts transparent, but retains the standard color stack if explicitly enabled.
        self._bg_colors = list(self._default_colors)
        self._use_bg_colors = not (self.start.hasImages() and self.middle.hasImages())

    @property
    def vertical(self) -> bool: return self._vertical

    def _minimumSize(self) -> tuple[int,int]:
        sw, sh = self.start.resolution()
        mw, mh = self.middle.resolution()
        ew, eh = self.end.resolution()

        if self._vertical:
            return max(sw, mw, ew, 1), max(sh + eh, 1)

        return max(sw + ew, 1), max(sh, mh, eh, 1)

    def _naturalSize(self) -> tuple[int,int]:
        min_w, min_h = self._minimumSize()
        thickness = min_w if self._vertical else min_h

        if self._vertical:
            return thickness, max(min_h, thickness * 3)

        return max(min_w, thickness * 3), thickness

    def _draw(self, index:int, width:int, height:int) -> UImage:
        start = self.start.image(index)
        middle = self.middle.image(index)
        end = self.end.image(index)

        sw, sh = start.resolution
        ew, eh = end.resolution

        image = UImage(width=width, height=height)

        if color := self.bgColor(index):
            image.flood(color)

        if self._vertical:
            end_y = height - eh
            bbox = (0, sh, width, end_y)

            start_x = (width - sw) // 2
            end_x = (width - ew) // 2

            middle.tileTo(image, bbox)
            start.cropTo(image, dest_x=start_x)
            end.cropTo(image, dest_x=end_x, dest_y=end_y)

        else:
            end_x = width - ew
            bbox = (sw, 0, end_x, height)

            start_y = (height - sh) // 2
            end_y = (height - eh) // 2

            middle.tileTo(image, bbox)
            start.cropTo(image, dest_y=start_y)
            end.cropTo(image, dest_x=end_x, dest_y=end_y)

        return image


class NineSliceSkin(AssembledSkin):
    """ Nine-slice border assembled from four corners, four repeatable edges, and an optional center color. """
    _PART_NAMES = ("northwest", "north", "northeast", "east",
                   "southeast", "south", "southwest", "west")
    _PART_ALIASES = {"nw":"northwest", "n":"north", "ne":"northeast", "e":"east",
                     "se":"southeast", "s":"south", "sw":"southwest", "w":"west"}

    def __init__(self, northwest:CoreSkin=None, north:CoreSkin=None, northeast:CoreSkin=None, east:CoreSkin=None,
                 southeast:CoreSkin=None, south:CoreSkin=None, southwest:CoreSkin=None, west:CoreSkin=None,
                 width:int=0, height:int=0):

        self._explicit_parts = {
            "northwest": northwest, "north": north, "northeast": northeast, "east": east,
            "southeast": southeast, "south": south, "southwest": southwest, "west": west
        }

        self._resolved_parts, self._generated_parts = self._resolveParts(self._explicit_parts)

        super().__init__(*[self._resolved_parts[name] for name in self._PART_NAMES], width=width, height=height)

    @property
    def northwest(self): return self._resolved_parts["northwest"]
    @property
    def north(self): return self._resolved_parts["north"]
    @property
    def northeast(self): return self._resolved_parts["northeast"]
    @property
    def east(self): return self._resolved_parts["east"]
    @property
    def southeast(self): return self._resolved_parts["southeast"]
    @property
    def south(self): return self._resolved_parts["south"]
    @property
    def southwest(self): return self._resolved_parts["southwest"]
    @property
    def west(self): return self._resolved_parts["west"]

    def part(self, name:str) -> CoreSkin: return self._resolved_parts[self._partName(name)]
    def setPart(self, name:str, skin:CoreSkin=None, relink:bool=False):
        name = self._partName(name)

        # Releasing a slot necessarily requires the topology to be reconsidered.
        if skin is None or relink:
            explicit = dict(self._explicit_parts)
            explicit[name] = skin
            self._relinkParts(explicit)
            return

        old_part = self._resolved_parts[name]
        was_generated = name in self._generated_parts

        if old_part is skin and not was_generated: return

        self._explicit_parts[name] = skin
        self._resolved_parts[name] = skin
        self._generated_parts.discard(name)

        self._setParts(*[self._resolved_parts[n] for n in self._PART_NAMES], notify=False)

        if was_generated and old_part not in self._parts:
            old_part.unlink()

        self.updateRecipients()

    def relinkParts(self): self._relinkParts(dict(self._explicit_parts))
    def _relinkParts(self, explicit:dict):
        old_generated = [self._resolved_parts[name] for name in self._generated_parts]
        resolved, generated = self._resolveParts(explicit)

        self._explicit_parts = explicit
        self._resolved_parts = resolved
        self._generated_parts = generated

        self._setParts(*[resolved[name] for name in self._PART_NAMES], notify=False)

        for part in old_generated:
            if part not in self._parts: part.unlink()

        self.updateRecipients()

    def _resolveParts(self, explicit:dict) -> tuple[dict,set]:
        parts = dict(explicit)
        generated = set()

        corners = ("northwest", "northeast", "southeast", "southwest")
        edges = ("north", "east", "south", "west")

        if not any(parts[name] is not None for name in corners):
            raise ValueError("NineSliceSkin requires at least one corner")
        if not any(parts[name] is not None for name in edges):
            raise ValueError("NineSliceSkin requires at least one edge")

        def derive(target:str, source:str, **kwargs):
            if parts[target] is None and parts[source] is not None:
                parts[target] = FilterSkin(parts[source], **kwargs)
                generated.add(target)

        # Corners: prefer a single-axis mirror. Resolve rows first, then columns.
        derive("northeast", "northwest", mirror_x=True)
        derive("northwest", "northeast", mirror_x=True)
        derive("southeast", "southwest", mirror_x=True)
        derive("southwest", "southeast", mirror_x=True)

        derive("southwest", "northwest", mirror_y=True)
        derive("northwest", "southwest", mirror_y=True)
        derive("southeast", "northeast", mirror_y=True)
        derive("northeast", "southeast", mirror_y=True)

        # Edges: opposite sides mirror each other before crossing axes.
        derive("south", "north", mirror_y=True)
        derive("north", "south", mirror_y=True)
        derive("east", "west", mirror_x=True)
        derive("west", "east", mirror_x=True)

        # Only rotate if an entire edge axis was absent.
        if parts["west"] is None and parts["east"] is None:
            derive("west", "north", rotate=True)
            derive("east", "west", mirror_x=True)

        elif parts["north"] is None and parts["south"] is None:
            derive("north", "west", rotate=True, mirror_x=True, mirror_y=True)
            derive("south", "north", mirror_y=True)

        return parts, generated

    @classmethod
    def _partName(cls, name:str) -> str:
        name = name.lower()
        name = cls._PART_ALIASES.get(name, name)

        if name not in cls._PART_NAMES:
            raise ValueError(f"Unknown NineSlice part: '{name}'")

        return name

    def _draw(self, index:int, w:int, h:int) -> UImage:
        left, right, top, bottom = self._bands(index)
        new_img = UImage(width=w, height=h)

        color = self.bgColor(index)
        if color and w > left + right and h > top + bottom:
            new_img.put(color, to=(left, top, w - right, h - bottom))

        nw, n, ne, e, se, s, sw, west = [part.image(index) for part in self._parts]

        n.tileTo(new_img, (left, 0, w - right, n.height()))
        e.tileTo(new_img, (w - e.width(), top, w, h - bottom))
        s.tileTo(new_img, (left, h - s.height(), w - right, h))
        west.tileTo(new_img, (0, top, west.width(), h - bottom))

        nw.cropTo(new_img)
        ne.cropTo(new_img, dest_x=w - ne.width())
        se.cropTo(new_img, dest_x=w - se.width(), dest_y=h - se.height())
        sw.cropTo(new_img, dest_y=h - sw.height())

        return new_img

    def _bands(self, index:int=0) -> tuple[int,int,int,int]:
        nw, n, ne, e, se, s, sw, west = [part.resolution(index) for part in self._parts]

        left = max(nw[0], west[0], sw[0])
        right = max(ne[0], e[0], se[0])
        top = max(nw[1], n[1], ne[1])
        bottom = max(sw[1], s[1], se[1])

        return left, right, top, bottom

    def insets(self, index:int=0) -> tuple[int,int,int,int]:
        left, right, top, bottom = self._bands(index)
        return top, right, bottom, left

    def _minimumSize(self) -> tuple[int,int]:
        left, right, top, bottom = self._bands()
        return left + right, top + bottom

    def _naturalSize(self) -> tuple[int,int]:
        min_w, min_h = self._minimumSize()
        north_w, south_w = self.north.resolution()[0], self.south.resolution()[0]
        east_h, west_h = self.east.resolution()[1], self.west.resolution()[1]

        return min_w + max(north_w, south_w, 1), min_h + max(east_h, west_h, 1)


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
    ScrollSkin stores two ThreeSliceSkins for use in rendering the vertical and horizontal ScrollBars of a Scrollable.
    It provides a .fromSkins() method that enables creation of all bars from ThreeSliceSkin elements.
    .fromSkins()        - scroll1 = ScrollSkin.fromSkins(cap1, trough, vertical = True)
    When .fromSkins() is given only a start_skin and middle_skin, it generates the end_skin by mirroring the first, and
    generates both the vertical and horizontal BarSkin by rotating whichever one was given. 
"""
class ScrollSkin(SkinPack):
    def __init__(self, vertical_bar:ThreeSliceSkin=None, horizontal_bar:ThreeSliceSkin=None,
                                                                                button_pack:ButtonPack=None):
        vertical_bar = vertical_bar or ThreeSliceSkin(vertical=True)
        horizontal_bar = horizontal_bar or ThreeSliceSkin(vertical=False)
        super().__init__(vertical_bar, horizontal_bar, button_pack)

    @classmethod
    def fromSkins(cls, start_skin:CoreSkin=None, middle_skin:CoreSkin=None, end_skin:CoreSkin=None,
                  vertical:bool=True, button_skin:CoreSkin=None, button_orientation:str="n"):
        buttons = ButtonPack.fromOne(button_skin, button_orientation) if button_skin is not None else None
        return cls(*cls._barsFromSkins(start_skin, middle_skin, end_skin, vertical), buttons)

    @property
    def vertical(self) -> ThreeSliceSkin: return self._skins[0]
    @property
    def horizontal(self) -> ThreeSliceSkin: return self._skins[1]
    @property
    def button(self) -> ButtonPack: return self._skins[2]

    def setBars(self, vertical:ThreeSliceSkin = None, horizontal:ThreeSliceSkin = None):
        if vertical: self._skins[0] = vertical
        if horizontal: self._skins[1] = horizontal

    def setBySkins(self, start_skin:CoreSkin=None, middle_skin:CoreSkin=None, end_skin:CoreSkin=None,
                   vertical:bool=True, button_skin:CoreSkin=None, button_orientation:str="n"):
        self._skins[0], self._skins[1] = self._barsFromSkins(start_skin, middle_skin, end_skin, vertical)
        if button_skin is not None: self._skins[2] = ButtonPack.fromOne(button_skin, button_orientation)

    @classmethod
    def _barsFromSkins(cls, start_skin:CoreSkin=None, middle_skin:CoreSkin=None, end_skin:CoreSkin=None,
                       vertical:bool=True) -> tuple[ThreeSliceSkin,ThreeSliceSkin]:
        bar1 = ThreeSliceSkin(start_skin, middle_skin, end_skin, vertical)

        new_start = FilterSkin(bar1.start, rotate=True, mirror_x=not vertical, mirror_y=not vertical)
        new_middle = FilterSkin(bar1.middle, rotate=True, mirror_x=not vertical, mirror_y=not vertical)
        new_end = FilterSkin(bar1.end, rotate=True, mirror_x=not vertical, mirror_y=not vertical)

        bar2 = ThreeSliceSkin(new_start, new_middle, new_end, not vertical)
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
    def __init__(self, *args, skin:CoreSkin|str|UImage|tuple|list=None, **kwargs):
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

    def destroy(self):
        if self._skin: self._skin.unbindWidget(self)
        super().destroy()

    def isOpaque(self):
        return self.skin.resolutionFor(self, self.state) == self.size and self.skin.isOpaqueFor(self, self.state)

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
