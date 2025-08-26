import tkinter as tk

from guiABLE.utilities import (warnPrint, resolvePath, cropImage, loadImage, getGeometry, rectsOverlap, fastComposite,
                               fastFlood, fastTile, flipImage, rotateImage)


""" CoreSkin establishes the core contents and operations of a Skin. It is a base class. Not for standalone use."""
class CoreSkin:
    def __init__(self):
        self._recipients, self._paths, self._images, self._resolutions = [], [], [], []
        self._empty_image = tk.PhotoImage()
        self._default_colors = ['gray', 'white', 'red', 'gray25']
        self._bg_colors = self._default_colors
        self._use_bg_colors = True

    # Create/manipulate background colors. ex: new_skin = Skin.fromColors('yellow', 'blue', 'orange', 'gray15')
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
            index %= len(self._images)
            img = self._images[index]
            if img: return img
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
        self._recipients, self._paths, self._images, self._resolutions = [], [], [], []
        self._bg_colors = self._default_colors
        self.updateRecipients()

    # Informational methods
    def hasImages(self): return any(self._images)
    def usesBgColors(self, use:bool = None) -> bool:
        if isinstance(use, bool): self._use_bg_colors = use
        return self._use_bg_colors

    def numStates(self): return max(len(self._images), len(self._bg_colors))

    # Widget registration & handling
    def bindWidget(self, widget): self._recipients.append(widget)
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

    # Private
    @staticmethod
    def _fillList(in_list:list) -> list:
        fallback = next(l for l in in_list if l)     # Find first non-Falsy entry

        for i, l in enumerate(in_list):      # Fill in any gaps by propagating the most recent valid data forward.
            if l: fallback = l
            else: in_list[i] = fallback

        return in_list

    def _expand(self, size:int):       # Expands path and image lists to new length.
        for n in range(size - len(self._images)):
            self._paths.append(None)
            self._images.append(None)
            self._resolutions.append((0, 0))


"""
    Skin() provides many different pathways for populating/modifying the image/background colors within the Skin.
    .fromColors()       - new_skin = Skin.fromColors('yellow', 'blue', 'orange', 'gray15')
    .fromPaths()        - new_skin = Skin.fromPaths("skins/skin1/checkbox.png","skins/skin1/checkbox_hover.png", ...)
    .fromImages()       - new_skin = Skin.fromImages(img1, img2, img3, img4) 
    .fromSpriteSheet()  - new_skin = Skin.fromSpriteSheet("/skins/skin1/checkbox.png", width=32, rows=2, margins=(4,4))
    
    The default creation method simply provides a list of resource paths as strings.
    ex: Skin("images/button_norm.png", "images/button_mo.png", "images/button_active.png", "images/button_disabled.png")
    
    While Skin() supports storing any number of images in any order, the library standard length and order of states is:
    (normal, moused_over, active, disabled) 
"""
class Skin(CoreSkin):
    def __init__(self, *paths: str):
        super().__init__()

        if any(paths):
            self._expand(len(paths))
            self._byPaths(paths)

    """ By resource paths. ex: Skin("skins/my_skin/checkbox_enabled.png","skins/my_skin/checkbox_hover.png", ...) """
    @classmethod
    def fromPaths(cls, *paths:str):
        sk = cls()
        if any(paths):
            sk._expand(len(paths))
            sk._byPaths(paths)
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
    def fromImages(cls, *photoimages:tk.PhotoImage):
        sk = cls()
        if any(photoimages):
            sk._expand(len(photoimages))
            sk._byPhotoImages(photoimages)
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
    def fromSpriteSheet(cls, path_or_image:str|tk.PhotoImage, width:int, rows:int = 1, margins:tuple = (0,0)):
        sk = cls()
        sheet, path = loadImage(path_or_image)
        if sheet is not None: sk._bySprite(sheet, path, width, rows, margins)
        return sk
    def setSprites(self, path_or_image:str|tk.PhotoImage, width:int, rows:int = 1, margins:tuple = (0,0)):
        sheet, path = loadImage(path_or_image)
        if sheet is not None:
            self._paths, self._images = [], []
            self._bySprite(sheet, path, width, rows, margins)
        self.updateRecipients()

    """ Private Functions """
    def _byPaths(self, paths:tuple[str, ...], skip_falsy:bool = False, index_offset:int = 0):
        for i, path in enumerate(paths):
            i += index_offset       # index_offset is used by .updateByPath() to insert a single change at one location.
            if not path and skip_falsy: continue        # Preserves existing values, allowing insert-changes by list.
            r_path = resolvePath(path)

            # If this path has already been successfully resolved to an image, store same image reference.
            if e := self._existsAt(r_path):
                self._paths[i] = self._paths[e]
                self._images[i] = self._images[e]

            # Otherwise store resolved path and try to load the image. If fail, store reference to empty image.
            else:
                self._paths[i] = r_path
                try:
                    self._images[i] = tk.PhotoImage(file=r_path)
                except tk.TclError:
                    warnPrint(f"Image not found: {r_path}")
                    self._images[i] = None

        self._fillImages()

    def _byPhotoImages(self, images:tuple[tk.PhotoImage, ...], skip_falsy=False, index_offset:int = 0):
        for i, img in enumerate(images):
            if not img and skip_falsy: continue

            i += index_offset
            if img:
                self._images[i] = img
                self._paths[i] = "image loaded internally"
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
        fallback = next((i for i in self._images if i is not None), None)  # Find first real image.
        if fallback is None: return

        self._use_bg_colors = False     # If images exist, default to transparent background.
        for i in range(len(self._images)):      # Fill in any gaps by propagating the most recent valid image forward.
            if self._images[i] is None:
                self._images[i] = fallback
                self._resolutions[i] = (fallback.width(), fallback.height())
            else:
                fallback = self._images[i]
                self._resolutions[i] = (self._images[i].width(), self._images[i].height())


"""
    FilterSkin provides a cached and ready view of another skin, as mirrored and/or rotated in place.
    Changes to the original skin will cause the FilterSkin to update as well. 
"""
class FilterSkin(CoreSkin):
    def __init__(self, linked_skin:Skin, rotate:bool = False, mirror_x:bool = False, mirror_y:bool = False):
        super().__init__()

        if isinstance(linked_skin, FilterSkin):
            rotate, mirror_x, mirror_y = self._state_sum(
                (linked_skin.rotate, linked_skin.mirror_x, linked_skin.mirror_y), (rotate, mirror_x, mirror_y)
            )
            self._linked_skin = linked_skin.linked_skin

        else: self._linked_skin =linked_skin
        self.mirror_x = mirror_x
        self.mirror_y = mirror_y
        self.rotate = rotate

        self.dirty = True
        self._linked_skin.bindWidget(self)
        self.redraw()

    @property
    def linked_skin(self): return self._linked_skin

    def redraw(self):
        self._paths = self._linked_skin.paths
        self._bg_colors = self._linked_skin.bg_colors
        self._images = list(self._linked_skin.images)
        self._resolutions = self._linked_skin.resolutions

        for i, img in enumerate(self._linked_skin.images):
            if self.rotate:
                img = rotateImage(img, False)
            self._images[i] = flipImage(img, self.mirror_x, self.mirror_y)
            self._resolutions[i] = self._images[i].width(), self._images[i].height()

        self.dirty = False


    def bindWidget(self, widget): self._linked_skin.bindWidget(widget)
    def unbindWidget(self, widget): self._linked_skin.unbindWidget(widget)

    @staticmethod
    def _state_sum(S1, S2) -> tuple[bool, bool, bool]:
        """
        Each state is a tuple (r, x, y) of booleans:
          r: rotate 90° CCW
          x: mirror X
          y: mirror Y

        This formula (dihedral group of the square) simply sees each 90 degree rotation flip the x and y mirror states.
        Meanwhile R, x, and y just sum in binary. (0+1 or 1+0 = 1, 1+1 = 0)
        R,x,y (1,1,1) + R,x,y (1,1,1) = (0,0,0) cancellation
        x,y (0,1,1) + y (0,0,1) = (0,1,0) binary sum
        R (1,0,0) + x (0,1,0) = (1,0,1) R flips x to 0 and y to 1
        """
        r2,x2,y2 = S2  # apply after...
        r1,x1,y1 = S1  # ...this one

        # If S2 rotates, it swaps the meaning of S1’s flips
        if r2: x1, y1 = y1, x1

        # Flips XOR together
        x = x2 ^ x1
        y = y2 ^ y1

        # Rotation is XOR too, but if both rotate (i.e., 180°), fold into flips
        both = r1 and r2
        r = r1 ^ r2
        if both:      # trade 180° for flip-both
            x ^= 1
            y ^= 1
            # r already became False via XOR

        return bool(r), bool(x), bool(y)


"""
    BarSkin accepts 2-3 skins which function as the end-caps and trough of a variable-length image. On request, BarSkin
    composes, stores, and returns the image of a bar, of the last length specified. Length is extended by repeating the
    trough until the area is filled. (the opposite of 'length', throughout the code, is 'breadth')
    
    If no second cap_skin is provided, or the .fromTwo() method is used directly, BarSkin will duplicate the first
    cap_skin given, and flip it's images on the appropriate axis (mirror), to generate a cap2_skin.     
    
    ex: BarSkin(cap1, trough, vertical=True)    # When no cap2 is given, cap1 is mirrored to fill the need.
"""
class BarSkin(CoreSkin):
    def __init__(self, cap_skin: Skin|FilterSkin|None = None, trough_skin: Skin|FilterSkin|None = None,
                 cap2_skin: Skin|FilterSkin|None = None, vertical:bool = False, breadth:int = 0):
        super().__init__()
        self.cap1 = cap_skin or Skin()
        self.trough = trough_skin or Skin()
        self.cap2 = cap2_skin or FilterSkin(self.cap1, mirror_x=not vertical, mirror_y=vertical)
        self._vertical = vertical
        if breadth < 1:
            self.breadth = max(self.cap1.resolution()[not vertical], self.trough.resolution()[not vertical],
                               self.cap2.resolution()[not vertical])
        else: self.breadth = breadth

        self._lengths = []
        size = min(len(self.cap1.images), len(self.trough.images), len(self.cap2.images))
        self._expand(size)

    @classmethod
    def fromTwo(cls, cap_skin:Skin|FilterSkin, trough_skin:Skin|FilterSkin, vertical:bool = False, breadth:int = 0):
        return cls(cap_skin, trough_skin, vertical=vertical, breadth=breadth)

    def image(self, index:int = 0, length:int = None) -> tk.PhotoImage|None:
        if self._images:
            index = index % len(self._images)

            if length and length != self._lengths[index]:
                w, h = (self.breadth, length) if self._vertical else (length, self.breadth)
                cw, ch = self.cap1.resolution(index)
                c2w, c2h = self.cap2.resolution(index)
                c2x, c2y = w-c2w, h-c2h

                if w >= c2w and h >= c2h:
                    new_img = tk.PhotoImage(width=w, height=h)
                    bbox = (0, ch, w, c2y) if self._vertical else (cw, 0, c2x, h)
                    fastTile(self.trough.image(index), *self.trough.resolution(index), new_img, w, h, bbox)
                    fastComposite(new_img, w, h, self.cap1.image(index), 0, 0, *self.cap1.resolution(index))
                    fastComposite(new_img, w, h, self.cap2.image(index), w-c2w, h-c2h, c2w, c2h)

                    self._images[index] = new_img
                    self._resolutions[index] = (w, h)
                    self._lengths[index] = length
                    #self._use_bg_colors = self.trough.usesBgColors()       # For bg_color transparency?
                    #self._bg_colors = self.trough.bg_colors
            return self._images[index]
        return None

    @staticmethod
    def _flipImages(images:list[tk.PhotoImage], vertical:bool):
        new_images = []
        fx, fy = (False, True) if vertical else (True, False)
        for i, img in enumerate(images): new_images.append(flipImage(img, flip_x=fx, flip_y=fy))
        return new_images

    def _expand(self, size:int):       # Expands path and image lists to new length.
        for n in range(size - len(self._images)):
            self._paths.append(None)
            self._images.append(None)
            self._resolutions.append(None)
            self._lengths.append(None)


"""
    ScrollSkin stores two BarSkins for use in rendering the vertical and horizontal ScrollBars of a Scrollable.
    It provides a .fromSkins() method that enables creation by as little as 2 skins.
    .fromSkins()        - scroll1 = ScrollSkin.fromSkins(cap1, trough, vertical = True)
    When .fromSkins() is given only the first cap and a trough, it generates the 2nd cap by mirroring the first, and
    generates both the vertical and horizontal BarSkin by rotating whichever one was given. 
"""
class ScrollSkin(CoreSkin):
    def __init__(self, vertical_bar: BarSkin | None = None, horizontal_bar: BarSkin | None = None,
                 button_skin: Skin | FilterSkin | None = None):
        super().__init__()
        self._v_bar = vertical_bar or BarSkin()
        self._h_bar = horizontal_bar or BarSkin()
        self._button_skin = button_skin

    @classmethod
    def fromSkins(cls, cap_skin:Skin, trough_skin:Skin, cap_skin2:Skin|None = None, vertical:bool = True):
        return cls(*cls._barsFromSkins(cap_skin, trough_skin, cap_skin2, vertical))

    @property
    def vertical(self) -> BarSkin: return self._v_bar
    @property
    def horizontal(self) -> BarSkin: return self._h_bar
    @property
    def button(self) -> Skin | FilterSkin | None: return self._button_skin

    def setBars(self, vertical:BarSkin, horizontal:BarSkin):
        self._v_bar = vertical if isinstance(vertical, BarSkin) else BarSkin()
        self._h_bar = horizontal if isinstance(horizontal, BarSkin) else BarSkin()

    def setBySkins(self, cap_skin:Skin, trough_skin:Skin, cap_skin2:Skin|None = None,
                   breadth:int = 24, vertical:bool = True):
        self._v_bar, self._h_bar = self._barsFromSkins(cap_skin, trough_skin, cap_skin2, breadth, vertical)

    @classmethod
    def _barsFromSkins(cls, cap_skin:Skin, trough_skin:Skin, cap_skin2:Skin|None = None,
                       vertical:bool = True) -> tuple[BarSkin, BarSkin]:
        bar1 = BarSkin(cap_skin, trough_skin, cap_skin2, vertical)
        new_cap = FilterSkin(bar1.cap1, rotate=True)
        new_trough = FilterSkin(bar1.trough, rotate=True)
        new_cap2 = FilterSkin(bar1.cap2, rotate=True)
        bar2 = BarSkin(new_cap, new_trough, new_cap2, not vertical)
        bar2.setBGColors(*bar1.bg_colors)
        return bar1, bar2


"""
Skinnable is a mixin that provides core Skin() functionality to guiABLE widgets.
"""
class Skinnable:
    def __init__(self, skin:Skin|BarSkin|FilterSkin = None):
        # If base class has not defined _default_skin, use Skin()
        try: exists = self._default_skin
        except: self._default_skin = Skin()

        # Register widget as a user of skin, in case skin updates later and needs to issue a redraw of all users.
        if isinstance(skin, CoreSkin):
            skin.bindWidget(self)
            self._skin = skin
        else: self._skin = self._default_skin

        self.dirty = True

        self._z_state = None
        self._img, self._z_img = None, None
        self._img_state = 0
        self._scratch = tk.PhotoImage()
        self._siblings_atop, self._siblings_beneath = list(), list()     # Overlapping siblings, by below/above z-index.
        self._children = []
        self._geometry = (0, 0, 0, 0)

    @property
    def skin(self) -> Skin: return self._skin

    # The ZImage() is a persistent render of what the widget looks like on its own. Only updated if something changed.
    @property
    def zImage(self) -> tk.PhotoImage:
        if self._z_state != self._img_state or self.dirty:
            _, _, w, h = self.geometry
            self._z_img = tk.PhotoImage(width=w, height=h)
            if not self._skin.hasImages() or self._skin.usesBgColors():
                fastFlood(self._z_img, w, h, self._skin.bgColor(self._img_state))
            fastComposite(self._z_img, w, h, self._skin.image(self._img_state), 0, 0,
                          *self._skin.resolution(self._img_state))
            self._z_state = self._img_state
            self.dirty = False
        return self._z_img

    # Skin registration methods
    def setSkin(self, skin:Skin):
        if self._skin:
            self._skin.unbindWidget(self)
        skin.bindWidget(self)
        self._skin = skin
    def dropSkin(self):
        if self._skin: self._skin.unbindWidget(self)
        self._skin = Skin()

    # Speed enhancing methods.
    @property
    def geometry(self): return self._geometry     # Geometry is tracked, providing much faster access than winfo_ gives.
    @property
    def size(self): return self._geometry[2:]
    @property
    def location(self): return self._geometry[:2]
    def scratchImage(self): return self._scratch  # Persistent PhotoImage provides an INSTANT redraw canvas.

    # Parent that host child widgets track and provide a list of those children's z-order.
    def getChildren(self): return self._children
    def registerChild(self, child):
        if child not in self._children: self._children.append(child)
    def dropChild(self, child):
        if child in self._children: self._children.remove(child)

    # Overlapping siblings track each other for the sake of compositing (faking transparency) during redraw.
    @property
    def siblingsBeneath(self): return self._siblings_beneath
    @property
    def siblingsAbove(self): return self._siblings_above
    def trackSibling(self, sibling, z_above: bool):
        if z_above:
            if sibling not in self._siblings_atop:
                self._siblings_atop.append(sibling)
            if sibling in self._siblings_beneath:
                self._siblings_beneath.remove(sibling)
        else:
            if sibling not in self._siblings_beneath:
                self._siblings_beneath.append(sibling)
            if sibling in self._siblings_atop:
                self._siblings_atop.remove(sibling)
    def dropSibling(self, sibling):
        if sibling in self._siblings_atop: self._siblings_atop.remove(sibling)
        elif sibling in self._siblings_beneath: self._siblings_beneath.remove(sibling)

    # Override all attachment methods to track z-order through parent and report overlap with any siblings.
    def place(self, **kwargs):
        super().place(**kwargs)
        self.after_idle(self._bond)
    def pack(self, **kwargs):
        super().pack(**kwargs)
        self.after_idle(self._bond)
    def grid(self, **kwargs):
        super().grid(**kwargs)
        self.after_idle(self._bond)

    # Override methods that change z-index, to track and report changes to all interested parties.
    def lift(self, above=None):
        tk.Misc.lift(self, above)
        self.after_idle(self.master._raiseChildIndex, self, above)
        self.after_idle(self._findOverlappingSiblings, self.master.getChildren())
    def lower(self, below=None):
        tk.Misc.lower(self, below)
        self.after_idle(self.master._lowerChildIndex, self, below)
        self.after_idle(self._findOverlappingSiblings, self.master.getChildren())

    def _geometry_changed(self, event):
        self._geometry = getGeometry(self)

    def _bond(self):        # Form lasting familial relationships with parent and siblings.
        # Refresh stored geometry and register with parent.
        self._geometry = getGeometry(self)
        self._scratch = tk.PhotoImage(width=self._geometry[2], height=self._geometry[3])
        if isinstance(self, tk.Canvas): self.master.registerChild(self)
        self._findOverlappingSiblings(self.master.children)

    # Find overlapping siblings and store them / register with them, for future tracking.
    def _findOverlappingSiblings(self, siblings_list):
        above = True        # z-order state of self in reference to sibling
        for sibling in siblings_list:
            if sibling is self: above = False
            elif isinstance(sibling, tk.Canvas) and rectsOverlap(self.geometry, getGeometry(sibling)):
                if sibling in self._siblings_atop or sibling in self._siblings_beneath: sibling.dropSibling(self)
                sibling.trackSibling(self, above)
                if above: self._siblings_beneath.append(sibling)
                else: self._siblings_atop.append(sibling)

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