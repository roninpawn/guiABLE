import tkinter as tk
from typing import Optional

from guiABLE.utilities import warnPrint, resolvePath, cropImage, loadImage, getGeometry, rectsOverlap, compositeImage, \
    fastComposite, fastCrop, fastFill


class Skin:
    def __init__(self, *paths: str):
        self._recipients, self._paths, self._images = [], [], []
        self._empty_image = tk.PhotoImage()
        self._bg_colors = ['gray', 'white', 'red', 'gray25']
        self._use_bg_colors = True

        if any(paths):
            self._expand(len(paths))
            self._byPaths(paths)

    """
    By resource paths. ex: Skinnable("skins/my_skin/checkbox_enabled.png","skins/my_skin/checkbox_hover.png", ...)
    """
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
    By PhotoImage references. ex: Skinnable.fromImages(checkbox0, checkbox1, checkbox2, ...)
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
    Example: Skinnable.bySpriteSheet("/skins/default/checkbox.png", width=32, rows=2, margins=(4,4))
    """
    @classmethod
    def fromSpriteSheet(cls, path_or_image:Optional[str | tk.PhotoImage], width:int, rows:int = 1, margins:tuple = (0,0)):
        sk = cls()
        sheet, path = loadImage(path_or_image)
        if sheet is not None: sk._bySprite(sheet, path, width, rows, margins)
        return sk
    def setSprites(self, path_or_image:Optional[str|tk.PhotoImage], width:int, rows:int = 1, margins:tuple = (0,0)):
        sheet, path = loadImage(path_or_image)
        if sheet is not None:
            self._paths, self._images = [], []
            self._bySprite(sheet, path, width, rows, margins)
        self.updateRecipients()

    def setBGColors(self, *colors: str):
        if colors and any(colors):  self._bg_colors = self._fillList([*colors])
        else: warnPrint(f"Skinnable passed list of empty BG colors\n{colors}\nExisting colors retained.")
    def setBGColor(self, color:str, index:int):
        # If index is out of range, extend bg_color list with itself until index is valid
        if color:
            while index < -len(self._bg_colors) or index >= len(self._bg_colors): self._bg_colors.extend(self._bg_colors)
            self._bg_colors[index] = color
        else: warnPrint(f"Skinnable passed empty BG color '{color}' for index {index}; Existing color retained.")
    def appendBGColors(self, *colors: str):
        if colors and any(colors):  self._bg_colors.extend(self._fillList([*colors]))
        else: warnPrint(f"Skinnable passed list of empty BG colors\n{colors}\nExisting colors retained.")

    def path(self, index:int) -> Optional[str]:
        if len(self._paths): return self._paths[index % len(self._paths)]
        return None
    def image(self, index: int = 0) -> tk.PhotoImage:
        if self._images:
            index %= len(self._images)
            img = self._images[index]
            if img is not None: return img
        return self._empty_image

    def bg(self, index: int = 0) -> Optional[str]:
        if self._use_bg_colors and len(self._bg_colors): return self._bg_colors[index % len(self._bg_colors)]
        return None     # Represents alpha

    def images(self) -> list[tk.PhotoImage]: return self._images
    def paths(self) -> list[str]: return self._paths
    def bg_colors(self) -> list[str]: return self._bg_colors

    def usesBgColors(self, use:bool = None) -> bool:
        if isinstance(use, bool): self._use_bg_colors = use
        return self._use_bg_colors

    def hasImages(self): return any(self._images)
    def view(self, index:int = 0) -> (tk.PhotoImage, str|None): return self.image(index), self.bg(index)
    def numStates(self): return len(self._images)
    def reset(self): self._recipients, self._paths, self._images = [], [], []

    def bindWidget(self, widget): self._recipients.append(widget)
    def unbindWidget(self, widget):
        if widget in self._recipients: self._recipients.remove(widget)

    def updateRecipients(self):
        for recipient in self._recipients: recipient.redraw()

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

        self._fillImages()

    def _expand(self, size:int):       # Expands path and image lists to new length.
        for n in range(size - len(self._images)):
            self._paths.append(None)
            self._images.append(None)

    def _existsAt(self, path:str) -> Optional[int]:
        for i in range(len(self._images)):
            if self._images[i] and self._paths[i] == path: return i
        return None

    @staticmethod
    def _fillList(in_list:list) -> list:
        fallback = next(l for l in in_list if l)     # Find first non-Falsy entry

        for i, l in enumerate(in_list):      # Fill in any gaps by propagating the most recent valid data forward.
            if l: fallback = l
            else: in_list[i] = fallback

        return in_list

    def _fillImages(self):
        fallback = next((i for i in self._images if i is not None), None)  # Find first real image.
        if fallback is None: return

        self._use_bg_colors = False     # If images exist, default to transparent background.
        for i in range(len(self._images)):      # Fill in any gaps by propagating the most recent valid image forward.
            if self._images[i] is None: self._images[i] = fallback
            else: fallback = self._images[i]


"""
Skinnable is a mixin that provides core Skin() functionality to tkinter widgets.
"""
class Skinnable:
    def __init__(self, skin:Skin = None):
        if isinstance(skin, Skin):
            skin.bindWidget(self)
            self._skin = skin
        else:
            self._skin = Skin()

        self.dirty, self.zDirty = True, True

        self._z_state = None
        self._img, self._img_state = self._skin.image(0), 0
        self._z_img = self._img
        self._scratch = tk.PhotoImage()
        self._siblings_atop, self._siblings_beneath = list(), list()     # Tracked siblings, separated by above/below self z-index
        self._children = []
        self._geometry = (0, 0, 0, 0)

    @property
    def skin(self) -> Skin: return self._skin

    # The ZImage() is a persistent render of what the widget looks like on its own. The zImage base is transparent.
    @property
    def zImage(self) -> tk.PhotoImage:
        if self._z_state != self._img_state or self.zDirty:
            _, _, w, h = self.geometry
            self._z_img = tk.PhotoImage(width=w, height=h)
            if not self._skin.hasImages() or self._skin.usesBgColors():
                fastFill(self._z_img, w, h, self._skin.bg(self._img_state))
            top_layer = self._skin.image(self._img_state)
            fastComposite(self._z_img, w, h, top_layer, 0, 0, top_layer.width(), top_layer.height())
            self._z_state = self._img_state
            self.zDirty = False
        return self._z_img

    def setSkin(self, skin:Skin):
        if self._skin:
            self._skin.unbindWidget(self)
        skin.bindWidget(self)
        self._skin = skin

    def dropSkin(self):
        if self._skin: self._skin.unbindWidget(self)
        self._skin = Skin()

    @property
    def geometry(self): return self._geometry
    def scratchImage(self): return self._scratch

    def getChildren(self): return self._children
    def registerChild(self, child):
        if child not in self._children: self._children.append(child)
    def dropChild(self, child):
        if child in self._children: self._children.remove(child)

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

    # Override all attachment methods to track z-order trough parent and report overlap with any siblings.
    def place(self, **kwargs):
        super().place(**kwargs)
        self.after_idle(self._bond)
    def pack(self, **kwargs):
        super().pack(**kwargs)
        self.after_idle(self._bond)
    def grid(self, **kwargs):
        super().grid(**kwargs)
        self.after_idle(self._bond)

    def lift(self, above=None):
        tk.Misc.lift(self, above)
        self.master._raiseChildIndex(self, above)
        self.after_idle(self._findOverlappingSiblings, self.master.getChildren())

    def lower(self, below=None):
        tk.Misc.lower(self, below)
        self.master._lowerChildIndex(self, below)
        self.after_idle(self._findOverlappingSiblings, self.master.getChildren())

    def configure(self, **kwargs):
        super().configure(**kwargs)
        self.after_idle(self._bond)

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
        if above in self._children:
            index = self._children.index(above) + 1
            self._children.insert(index, child)
        else:
            self._children.append(child)

    def _lowerChildIndex(self, child, below):
        self.dropChild(child)
        if below in self._children:
            index = self._children.index(below)
            self._children.insert(index, child)
        else:
            self._children.insert(0, child)