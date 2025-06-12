import tkinter as tk
from .utilities import *


class Skinnable():
    def __init__(self, normal_path=None, hover_path=None, active_path=None, disabled_path=None):
        self._recipients = []
        self._paths = [normal_path, hover_path, active_path, disabled_path]
        self._images = [None, None, None, None]

        self.changePaths(normal_path, hover_path, active_path, disabled_path)

        if self._images[0] is None:
            for n in range(1, 4):
                if self._images[n] is not None:
                    self._images[0] = self._images[n]
                    break
            if self._images[0] is None:
                self._images[0] = tk.PhotoImage(width=0, height=0)

        for n in range(1, 3):
            if self._images[n] is None:
                self._images[n] = self._images[n-1]
                self._paths[n] = self._paths[n-1]

        if self._images[3] is None:
            self._paths[3] = self._paths[0]
            self._images[3] = self._images[0]

    def changePaths(self, normal_path=None, hover_path=None, active_path=None, disabled_path=None, _direct=False):
        paths = [normal_path, hover_path, active_path, disabled_path]
        for n in range(4):
            if paths[n] is not None:
                if not self._checkDuplicates(paths[n], n):
                    self._paths[n] = paths[n]
                    if _direct:
                        self._images[n] = paths[n]
                    else:
                        self._loadImg(paths[n], n)

    def directSetImages(self, normal_img=None, hover_img=None, active_img=None, disabled_img=None):
        self.changePaths(normal_img, hover_img, active_img, disabled_img, True)

    def bindWidget(self, widget): self._recipients.append(widget)

    def unbindWidget(self, widget):
        if widget in self._recipients: self._recipients.remove(widget)

    def updateRecipients(self): [updateHover(recipient) for recipient in self._recipients]

    def paths(self): return self._paths

    def images(self): return self._images

    def _checkDuplicates(self, reference, index):
        for i in range(4):
            if self._images[i] is not None and self._paths[i] == reference:
                self._paths[index] = reference
                self._images[index] = self._images[i]
                return True
        return False

    def _loadImg(self, img_path, index):
        if img_path is not None:
            try:
                self._images[index] = tk.PhotoImage(file=img_path)
            except tk.TclError:
                warn_print(f"Image not found: {img_path}")


class Imageable(tk.Canvas):
    def __init__(self, parent, skinnable=None, **kwargs):
        super().__init__(parent, highlightthickness=0, **kwargs)
        self.enabled = True

        if skinnable is not None:
            self._skin = None
            self.setSkin(skinnable)
        else:
            self._skin = Skinnable()
        self.current_image = 0
        self.enable()

    def setSkin(self, skinnable):
        if self._skin is not None:
            self._skin.unbindWidget(self)
        skinnable.bindWidget(self)
        self._skin = skinnable

    def clearSkin(self):
        if self._skin is not None:
            self._skin.unbindWidget(self)
        self._skin = Skinnable()
        updateHover(self)

    def changeImage(self, img_number):
        self.current_image = img_number
        self.create_image(0, 0, image=self._skin.images()[img_number], anchor=tk.NW)

    def enable(self):
        self.create_image(0, 0, image=self._skin.images()[self.current_image], anchor=tk.NW)
        self.enabled = True

    def disable(self):
        self.create_image(0, 0, image=self._skin.images()[3], anchor=tk.NW)
        self.enabled = False


class Hoverable(tk.Canvas):
    def __init__(self, parent, skinnable=None, **kwargs):
        super().__init__(parent, highlightthickness=0, **kwargs)

        self.enabled = True
        self.moused_over = False

        if skinnable is not None:
            self._skin = None
            self.setSkin(skinnable)
        else:
            self._skin = Skinnable()
        self.enable()

    def setSkin(self, skinnable):
        if self._skin is not None:
            self._skin.unbindWidget(self)
        skinnable.bindWidget(self)
        self._skin = skinnable
        updateHover(self)

    def clearSkin(self):
        if self._skin is not None:
            self._skin.unbindWidget(self)
        self._skin.images = [[],[],[],[]]

    def mouseIn(self, event):
        self.moused_over = True
        self.configure(bg="white")
        self.create_image(0, 0, image=self._skin.images()[1], anchor=tk.NW)

    def mouseOut(self, event):
        self.moused_over = False
        self.configure(bg="gray")
        self.create_image(0, 0, image=self._skin.images()[0], anchor=tk.NW)

    def enable(self):
        self.bind("<Enter>", self.mouseIn)
        self.bind("<Leave>", self.mouseOut)
        self.enabled = True
        updateHover(self)

    def disable(self):
        self.unbind("<Enter>")
        self.unbind("<Leave>")
        self.create_image(0, 0, image=self._skin.images()[3], anchor=tk.NW)
        self.enabled = False


class Clickable(Hoverable):
    def __init__(self, parent, function=lambda: None, skinnable=None, **kwargs):
        self.function = function
        super().__init__(parent, skinnable, **kwargs)

    def clicked(self, event):
        self.configure(bg="red")
        self.create_image(0, 0, image=self._skin.images()[2], anchor=tk.NW)
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
        self.configure(bg="red")
        self.create_image(0, 0, image=self._skin.images()[2], anchor=tk.NW)

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
            self.configure(bg="red")
            self.create_image(0, 0, image=self._skin.images()[2], anchor=tk.NW)


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
    def __init__(self, parent, state=None, function=lambda: None, skinnable_1=None, skinnable_2=None, **kwargs):
        self._state = state
        super().__init__(parent, function, skinnable_1, **kwargs)
        if skinnable_1 is None and skinnable_2 is None:
            self._skins = [[[],[],[],[]], [[],[],[],[]]]
        else:
            if skinnable_2 is None:
                skinnable_1.bindWidget(self)
                skinnable_2 = skinnable_1
            elif skinnable_1 is None:
                skinnable_2.bindWidget(self)
                skinnable_1 = skinnable_2
            else:
                skinnable_1.bindWidget(self)
                skinnable_2.bindWidget(self)

            self._skins = [skinnable_1, skinnable_2]
            self._skin = self._skins[not self._state]

        updateHover(self)

    def mouseUp(self, event):
        self._clicking = False
        if self.moused_over:
            self._state = not self._state
            self._skin = self._skins[not self._state]
            self.function()
            self.configure(bg="gray")
            self.create_image(0, 0, image=self._skin.images()[0], anchor=tk.NW)

    def state(self, state=None):
        if state is None:
            return self._state
        else:
            self._state = state
            self._skin = self._skins[not self._state]
            updateHover(self)


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
