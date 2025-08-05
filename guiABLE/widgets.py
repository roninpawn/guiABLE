import tkinter as tk
from typing import Optional

from guiABLE.skinnable import Skinnable
from guiABLE.utilities import updateHover, limitMove, composeImages, getGeometry, cropImage


class Baseable(tk.Canvas):
    def __init__(self, parent, skinnable=None, **kwargs):
        super().__init__(parent, highlightthickness=0, **kwargs)

        self._parent = parent
        self._enabled, self._img_state, self._img, self._bg, self._geometry = False, None, None, None, None

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

    def skin(self) -> Skinnable: return self._skin

    def setSkin(self, skinnable:Skinnable):
        if self._skin is not None:
            self._skin.unbindWidget(self)
        skinnable.bindWidget(self)
        self._skin = skinnable

    def dropSkin(self):
        if self._skin is not None: self._skin.unbindWidget(self)
        self._skin = Skinnable()

    def setState(self, state_index:int = 0):
        # Fetch Skinnable() holdings for the new state.
        self._img, bg_color = self._skin.view(state_index)

        # If Skinnable indicates transparency, use parent's background. [Color or Image]
        if bg_color is None:
            if self._parent.skin().useBgColors():       # If parent uses a simple bg color (no image) just use the same.
                bg_color = self._parent.skin().bg(state_index)
                if bg_color is None: bg_color = 'gray'  # Fallback to gray.

            else:       # If parent is using an image, crop widget's geometry from it, and composite.
                self._geometry = getGeometry(self)
                if self._geometry[2] <= 1 or self._geometry[3] <= 1: self.after_idle(lambda : self.setState(state_index))
                self._bg = cropImage(self._parent.skin().image(state_index), *self._geometry)
                self._img = composeImages(self._bg, self._img)

        # Render the state.
        self.delete("all")
        self.configure(bg=bg_color)
        self.create_image(0, 0, image=self._img, anchor="nw")
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
        self.create_text(x + dx, y + dy, text=self.text, fill=self.drop_color, font=self.font, anchor="nw")
        self.create_text(x, y, text=self.text, fill=self.color, font=self.font, anchor="nw")

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
        self.setState(2)    # Bodge to force compositing updates during drag.

    def enable(self):
        self.bind("<B1-Motion>", self.mouseDrag)
        super().enable()

    def disable(self):
        self.unbind("<B1-Motion>")
        super().disable()
