import tkinter as tk
from typing import Optional

from .utilities import updateHover, warnPrint, limitMove, resolvePath, cropImage


class Skinnable:
    def __init__(self, *paths:str):
        self._recipients, self._paths, self._images = [], [] ,[]
        self._empty_image = tk.PhotoImage(width=0, height=0)
        self._bg_colors = ['gray', 'white', 'red', 'gray25']
        if paths:
            self._expand(len(paths))
            self._byPaths(paths)

    """
    By resource paths. ex: Skinnable("skins/my_skin/checkbox_enabled.png","skins/my_skin/checkbox_hover.png", ...)
    """
    @classmethod
    def fromPaths(cls, *paths:str):
        sk = cls()
        sk._expand(len(paths))
        sk._byPaths(paths)
        return sk
    def setPaths(self, *paths:str):        # Supports insert-updating by list. ex: ["path", None, None, "path"]
        if len(paths) > len(self._paths): self._expand(len(paths))
        self._byPaths(paths, True)
        self.updateRecipients()
    def setPath(self, path:str, index:int):
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
        sk._expand(len(photoimages))
        sk._byPhotoImages(photoimages)
        return sk
    def setImages(self, *photoimages:tk.PhotoImage):
        if len(photoimages) > len(self._images): self._expand(len(photoimages))
        self._byPhotoImages(photoimages, True)
        self.updateRecipients()
    def setImage(self, photoimage:tk.PhotoImage, index:int):
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
    def fromSpriteSheet(cls, path_or_image:Optional[str | tk.PhotoImage], width:int, rows:int = 1, margins:tuple = (0, 0)):
        sk = cls()
        sheet, path = sk._pathOrImage(path_or_image)
        if path is not None: sk._bySprite(sheet, path, width, rows, margins)
        return sk
    def setSprites(self, path_or_image:Optional[str|tk.PhotoImage], width:int, rows:int = 1, margins:tuple = (0,0)):
        sheet, path = self._pathOrImage(path_or_image)
        if path is not None:
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
    def image(self, index:int) -> tk.PhotoImage:
        if len(self._images): return self._images[index % len(self._images)]
        return self._empty_image
    def bg(self, index: int) -> str:
        if len(self._bg_colors): return self._bg_colors[index % len(self._bg_colors)]
        return 'gray'

    def images(self) -> list[tk.PhotoImage]: return self._images
    def paths(self) -> list[str]: return self._paths
    def bg_colors(self) -> list[str]: return self._bg_colors

    def numStates(self): return len(self._images)
    def reset(self): self._recipients, self._paths, self._images = [], [], []

    def bindWidget(self, widget): self._recipients.append(widget)
    def unbindWidget(self, widget):
        if widget in self._recipients: self._recipients.remove(widget)

    def updateRecipients(self): [updateHover(recipient) for recipient in self._recipients]

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
                    self._images[i] = self._empty_image

        self._fillImages()

    def _byPhotoImages(self, images:tuple[tk.PhotoImage, ...], skip_falsy=False, index_offset:int = 0):
        for i, img in enumerate(images):
            if not img and skip_falsy: continue

            i += index_offset
            if img:
                self._images[i] = img
                self._paths[i] = "image loaded internally"
            else:
                self._images[i] = self._empty_image
                self._paths[i] = None

        self._fillImages()

    def _bySprite(self, sheet:tk.PhotoImage, path:str, width:int, rows:int = 1, margins:tuple = (0,0)):
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
                self._paths.append(f"{x1},{y1},{width},{height} from {path}")

        self._fillImages()

    def _pathOrImage(self, path_or_image:Optional[str|tk.PhotoImage]) -> tuple[tk.PhotoImage, Optional[str]]:
        # Conform either input type to PhotoImage and path
        if isinstance(path_or_image, str):
            r_path = resolvePath(path_or_image)
            try:
                image = tk.PhotoImage(file=r_path)
            except tk.TclError:
                warnPrint(f"Sprite sheet not found: {path_or_image}")
                return self._empty_image, None
        else:
            r_path = "internal sheet"
            if isinstance(path_or_image, tk.PhotoImage):
                image = path_or_image
            else:
                warnPrint(f"Invalid sprite source: {path_or_image}")
                return self._empty_image, None
        return image, r_path

    def _expand(self, size:int):       # Expands path and image lists to new length.
        for n in range(min(size - len(self._images), 256)):
            self._paths.append(None)
            self._images.append(self._empty_image)

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
        fallback = next((i for i in self._images if i != self._empty_image), None)  # Find first real image.
        if fallback is None: return

        for i in range(len(self._images)):      # Fill in any gaps by propagating the most recent valid image forward.
            if self._images[i] == self._empty_image: self._images[i] = fallback
            else: fallback = self._images[i]


class Baseable(tk.Canvas):
    def __init__(self, parent, skinnable=None, **kwargs):
        super().__init__(parent, highlightthickness=0, **kwargs)

        self._enabled, self._img_state = None, None

        if skinnable is not None:
            self._skin = None
            self.setSkin(skinnable)
        else:
            self._skin = Skinnable()

        self.enable()

    @property
    def enabled(self) -> bool : return self._enabled
    def enable(self): self._enabled = True
    def disable(self): self._enabled = False

    def setSkin(self, skinnable:Skinnable):
        if self._skin is not None:
            self._skin.unbindWidget(self)
        skinnable.bindWidget(self)
        self._skin = skinnable

    def dropSkin(self):
        if self._skin is not None: self._skin.unbindWidget(self)
        self._skin = Skinnable()

    def setState(self, state_index:int = 0):
        self.configure(bg=self._skin.bg(state_index))
        self.delete("all")
        self.create_image(0, 0, image=self._skin.image(state_index), anchor=tk.NW)
        self._img_state = state_index


class Imageable(Baseable):
    def __init__(self, parent, skinnable=None, **kwargs):
        super().__init__(parent, skinnable, **kwargs)
        self._skin.setBGColors('gray')      # Eliminate interactive colors for simple image.

    def changeImage(self, img_number): self.setState(img_number)
    def enable(self):
        super().enable()
        self.setState(self._img_state)

    def disable(self):
        super().disable()
        self.setState(3)


class Hoverable(Baseable):
    def __init__(self, parent, skinnable=None, **kwargs):
        self.moused_over = False
        super().__init__(parent, skinnable, **kwargs)

    def setSkin(self, skinnable):
        super().setSkin(skinnable)
        updateHover(self)

    def mouseIn(self, event):
        self.moused_over = True
        self.setState(1)

    def mouseOut(self, event):
        self.moused_over = False
        self.setState(0)

    def enable(self):
        super().enable()
        self.bind("<Enter>", self.mouseIn)
        self.bind("<Leave>", self.mouseOut)
        updateHover(self)

    def disable(self):
        super().disable()
        self.unbind("<Enter>")
        self.unbind("<Leave>")
        self.setState(3)


class Clickable(Hoverable):
    def __init__(self, parent, function=lambda: None, skinnable=None, **kwargs):
        self.function = function
        super().__init__(parent, skinnable, **kwargs)

    def clicked(self, event):
        self.setState(2)
        self.function()
        updateHover(self)

    def mouseUp(self, event):
        self.mouseIn(event) if self.moused_over else self.mouseOut(event)

    def enable(self):
        super().enable()
        self.bind("<Button-1>", self.clicked)
        self.bind("<ButtonRelease-1>", self.mouseUp)

    def disable(self):
        super().disable()
        self.unbind("<Button-1>")
        self.unbind("<ButtonRelease-1>")


class Pushable(Clickable):
    def __init__(self, parent, function=lambda: None, skinnable=None, **kwargs):
        self._clicking = False
        super().__init__(parent, function, skinnable, **kwargs)

    def clicked(self, event):
        self._clicking = True
        self.setState(2)

    def mouseUp(self, event):
        self._clicking = False
        super().mouseUp(event)
        if self.moused_over:
            self.function()
            updateHover(self)

    def mouseIn(self, event):
        if not self._clicking:
            super().mouseIn(event)
        else:
            self.moused_over = True
            self.setState(2)


class Labelable(Pushable):
    def __init__(self, parent, function=lambda: None, skinnable=None, text="", text_pos=(0,0), font="Times", color="gray",
                 drop_pos=(0, 0), drop_color="black", **kwargs):
        self.text, self.text_pos, self.color, self.font = text, text_pos, color, font
        self.drop_pos, self.drop_color, = drop_pos, drop_color
        super().__init__(parent, function, skinnable, **kwargs)

    def drawText(self):
        x, y = self.text_pos
        dx, dy = self.drop_pos
        self.create_text(x + dx, y + dy, text=self.text, fill=self.drop_color, font=self.font, anchor=tk.NW)
        self.create_text(x, y, text=self.text, fill=self.color, font=self.font, anchor=tk.NW)

    def mouseOut(self, event):
        super().mouseOut(event)
        self.drawText()

    def mouseIn(self, event):
        super().mouseIn(event)
        self.drawText()

    def clicked(self, event):
        super().clicked(event)
        self.drawText()

    def mouseUp(self, event):
        super().mouseUp(event)
        self.drawText()


class Toggleable(Pushable):
    def __init__(self, parent, state:bool=False, function=lambda: None, skinnable:Skinnable = None, **kwargs):
        self._toggle_state = state
        self._state_offset = 0
        super().__init__(parent, function, skinnable, **kwargs)

    def mouseUp(self, event):
        self._clicking = False
        if self.moused_over:
            self.state(not self._toggle_state)
            self.function()

    def state(self, state:bool=None) -> Optional[bool]:
        if isinstance(state, bool):
            self._toggle_state = state
            self._state_offset = self._toggle_state * 4
            self.setState(1)
        return self._toggle_state

    def setState(self, state_index:int = 0):
        state_index += self._state_offset
        super().setState(state_index)


class Holdable(Pushable):
    def __init__(self, parent, function=lambda: None, skinnable=None, delay=100, init_delay=400, **kwargs):
        self.delay = delay
        self.init_delay = init_delay
        super().__init__(parent, function, skinnable, **kwargs)

    def mouseOut(self, event):
        self.moused_over = False if self._clicking else super().mouseOut(None)

    def mouseUp(self, event):
        self._clicking = False
        if self.moused_over:
            self.mouseIn(event)

    def clicked(self, event):
        super().clicked(event)
        self.function()
        if self.function is not None:
            self.after(self.init_delay, self._keepClicking)

    def _keepClicking(self):
        if self._clicking:
            self.function()
            self.after(self.delay, self._keepClicking)


class Draggable(Holdable):
    def clicked(self, event):
        self.x = event.x
        self.y = event.y
        super().clicked(event)

    def mouseDrag(self, event):
        x = event.x - self.x + self.winfo_x()
        y = event.y - self.y + self.winfo_y()
        x = limitMove(x, self.winfo_width(), 0, self.master.winfo_width())
        y = limitMove(y, self.winfo_height(), 0, self.master.winfo_height())

        self.place_configure(x=x, y=y)

    def enable(self):
        self.bind("<B1-Motion>", self.mouseDrag)
        super().enable()

    def disable(self):
        self.unbind("<B1-Motion>")
        super().disable()
