import tkinter as tk
from warnings import warn


def _limitMove(start, size, low_bound, high_bound):
    if start < low_bound:
        return low_bound
    elif start + size > high_bound:
        return high_bound - size
    return start


def _getLocalMouse(widget):
    x = widget.winfo_pointerx() - widget.winfo_rootx()
    y = widget.winfo_pointery() - widget.winfo_rooty()
    if x < 0 or x > widget.winfo_width():
        return x, y, False
    if y < 0 or y > widget.winfo_height():
        return x, y, False
    return x, y, True   # Returns local x and y coordinates of mouse, and whether mouse is over widget.


def updateHover(widget):
    x, y, mouse_in = _getLocalMouse(widget)
    widget.mouseIn(None) if mouse_in else widget.mouseOut(None)


class Canvasable(tk.Text):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bd=0, padx=0, pady=0, state=tk.DISABLED, cursor="arrow", **kwargs)
        self.configure(selectbackground=self.cget("bg"))

    def _configure(self, cmd, cnf, kw):
        if "bg" in kw:
            kw["selectbackground"] = kw["bg"]
        if "background" in kw:
            kw["selectbackground"] = kw["background"]
        super()._configure(cmd, cnf, kw)


class Backgroundable(tk.Frame):
    def __init__(self, parent, width, height, image_path=None, **kwargs):
        super().__init__(parent, width=width, height=height)
        self.pack_propagate(tk.FALSE)
        self.inner = Canvasable(self, **kwargs)
        if image_path is not None:
            self.setImage(image_path)
        self.inner.pack(fill=tk.BOTH, expand=tk.TRUE)

    def setImage(self, image_path):
        try:
            self.directSetImage(tk.PhotoImage(file=image_path))
        except tk.TclError:
            warn(f"guiABLE: Image not found: {image_path}", RuntimeWarning)

    def directSetImage(self, image):
        self.inner.configure(state=tk.NORMAL)
        self.inner.delete(1.0, tk.END)
        self._img = image
        self.inner.image_create(tk.END, image=self._img)
        self.inner.configure(state=tk.DISABLED)


class Hoverable(tk.Canvas):
    def __init__(self, parent, image_paths=None, **kwargs):
        super().__init__(parent, highlightthickness=0, **kwargs)

        self.enabled = True
        self.moused_over = False
        self.images = self._loadImages(image_paths)
        self.enable()

    def _loadImages(self, image_paths):
        images = [[], [], [], []]
        if image_paths is not None:
            images = [self._loadImg(img) for img in image_paths] + images[len(image_paths):]
            if len(image_paths) < 4:
                images[3] = images[0]
        return images

    def _loadImg(self, img_location):
        try:
            img_out = tk.PhotoImage(file=img_location)
        except tk.TclError:
            warn(f"guiABLE: Image not found: {img_location}", RuntimeWarning)
            img_out = []
        return img_out

    def loadImages(self, image_paths):
        self.images = self._loadImages(image_paths)
        updateHover(self)

    def mouseIn(self, event):
        self.moused_over = True
        self.configure(bg="white")
        self.create_image(0, 0, image=self.images[1], anchor=tk.NW)

    def mouseOut(self, event):
        self.moused_over = False
        self.configure(bg="gray")
        self.create_image(0, 0, image=self.images[0], anchor=tk.NW)

    def enable(self):
        self.bind("<Enter>", self.mouseIn)
        self.bind("<Leave>", self.mouseOut)
        updateHover(self)
        self.enabled = True

    def disable(self):
        self.unbind("<Enter>")
        self.unbind("<Leave>")
        self.create_image(0, 0, image=self.images[3], anchor=tk.NW)
        self.enabled = False


class Clickable(Hoverable):
    def __init__(self, parent, function=lambda: None, image_paths=None, **kwargs):
        self.function = function
        super().__init__(parent, image_paths, **kwargs)

    def clicked(self, event):
        self.configure(bg="red")
        self.create_image(0, 0, image=self.images[2], anchor=tk.NW)
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
    def __init__(self, parent, function=lambda: None, image_paths=None, **kwargs):
        self._clicking = False
        super().__init__(parent, function, image_paths, **kwargs)

    def mouseIn(self, event):
        if self._clicking:
            self.moused_over = True
            self.clicked(event)
        else:
            super().mouseIn(event)

    def clicked(self, event):
        self._clicking = True
        self.configure(bg="red")
        self.create_image(0, 0, image=self.images[2], anchor=tk.NW)

    def mouseUp(self, event):
        self._clicking = False
        if self.moused_over:
            self.function()
            updateHover(self)


class Toggleable(Pushable):
    def __init__(self, parent, state=False, function=lambda: None, image_paths1=None, image_paths2=None, **kwargs):
        self.state = state
        super().__init__(parent, function, **kwargs)

        self.images = self._loadImages(image_paths1) + self._loadImages(image_paths2)
        if not self.state:
            self.images = self.images[4:8] + self.images[0:4]
        updateHover(self)

    def mouseUp(self, event):
        self._clicking = False
        if self.moused_over:
            self.state = not self.state
            self.images = self.images[4:8] + self.images[0:4]
            self.function()
            updateHover(self)


class Holdable(Pushable):
    def __init__(self, parent, function=lambda: None, image_paths=None, delay=100, init_delay=400, **kwargs):
        self.delay = delay
        self.init_delay = init_delay
        super().__init__(parent, function, image_paths, **kwargs)

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
        x = _limitMove(x, self.winfo_width(), 0, self.master.winfo_width())
        y = _limitMove(y, self.winfo_height(), 0, self.master.winfo_height())

        self.place_configure(x=x, y=y)

    def enable(self):
        self.bind("<B1-Motion>", self.mouseDrag)
        super().enable()

    def disable(self):
        self.unbind("<B1-Motion>")
        super().disable()


class Troughable(Backgroundable):
    def __init__(self, parent, width, height, **kwargs):
        self.enabled = True
        self.images = None
        super().__init__(parent, width=width, height=height, bg="lightgray", **kwargs)

    def setImage(self, img_list):
        self.images = img_list
        self.enable()

    def mouseOut(self, event):
        self.directSetImage(self.images[0])

    def mouseIn(self, event):
        self.directSetImage(self.images[1])

    def clicked(self, event):
        self.directSetImage(self.images[2])

    def mouseUp(self, event):
        self.directSetImage(self.images[1])

    def enable(self):
        if self.images is not None:
            self.inner.bind("<Enter>", self.mouseIn)
            self.inner.bind("<Leave>", self.mouseOut)
            self.inner.bind("<Button-1>", self.clicked, "+")
            self.inner.bind("<ButtonRelease-1>", self.mouseUp, "+")
            updateHover(self)
        self.enabled = True

    def disable(self):
        self.inner.unbind("<Enter>")
        self.inner.unbind("<Leave>")
        self.inner.unbind("<Button-1>")
        self.inner.unbind("<ButtonRelease-1>")
        if self.images is not None:
            self.directSetImage(self.images[3])
        self.enabled = False


class Scrollable(Holdable):
    def __init__(self, parent, trough_width, trough_height, handle_width, handle_height, scrollwheel_speed=10, **kwargs):
        self.scrollwheel_speed = scrollwheel_speed
        self.linked = False
        self.page_percent = .9
        self._skin = None

        super().__init__(parent, lambda: None, width=trough_width, height=trough_height, **kwargs)
        self.trough = Troughable(self, trough_width, trough_height)
        self.trough.place(x=0, y=0)
        self.handle = Draggable(self.trough.inner, width=handle_width, height=handle_height)
        self.handle.place(x=0, y=-0)

    def enable(self):
        if not self.enabled:
            self.trough.enable()
            self.handle.enable()
            if self.linked: self._linkTo()
            if self._skin is not None: self._skin.drawTo(self)
        super().enable()

    def disable(self):
        self.trough.disable()
        self.handle.disable()
        super().disable()

    def setSkin(self, ScrollSkin): self._skin = ScrollSkin

    def linkTo(self, ScrollableCanvas, movement_modifier=-1, active_handle_xy=(True, True), canvas_offset=(0.0, 0.0)):
        self.movement_modifier = movement_modifier
        self._linked = ScrollableCanvas
        self._linkedwidth = self._linked.inner.winfo_width()
        self._linkedheight = self._linked.inner.winfo_height()
        self.active_handle_x, self.active_handle_y = active_handle_xy
        self.x_offset, self.y_offset = canvas_offset
        self._linkTo()

    def _linkTo(self):
        if self.active_handle_y:
            self.bind_all("<MouseWheel>", self.scroll, "+")
        self.handle.bind("<Configure>", self._moveCanvas)
        self.trough.inner.bind("<Button-1>", self.clicked)
        self.trough.inner.bind("<ButtonRelease-1>", self.mouseUp)
        self._linked.inner.bind("<Configure>", self._resize_handle, "+")
        self.bind("<Configure>", self._resize_handle)
        self.linked = True

    def _resize_handle(self, event):
        #self.update_idletasks()
        #self._linked.update_idletasks()
        if self._linkedwidth != self._linked.inner.winfo_width() or self._linkedheight != self._linked.inner.winfo_height():
            self.resize_handle()

    def resize_handle(self):
        if not self.active_handle_x or self._linked.inner.winfo_width() < self._linked.inner_width:
            self.handle.config(width=self.trough.winfo_width())
        else:
            self.enable()
            self.handle.config(width=self.winfo_width() / self._linked.inner.winfo_width() * self._linked.inner_width)
        if not self.active_handle_y or self._linked.inner.winfo_height() <= self._linked.inner_height:
            self.handle.config(height=self.trough.winfo_height())
        else:
            self.enable()
            self.handle.config(height=self.winfo_height() / self._linked.inner.winfo_height() * self._linked.inner_height)

        if self._skin is not None:
            self._skin.drawTo(self)

        if self.handle.winfo_width() == self.trough.winfo_width() and \
                self.handle.winfo_height() == self.trough.winfo_height():
            self.disable()

        self._linkedwidth = self._linked.inner.winfo_width()
        self._linkedheight = self._linked.inner.winfo_height()

    def clicked(self, event):
        if self.active_handle_x:
            new_x = self._limitPage(event.x, self.handle.winfo_x(), self.handle.winfo_width(),
                                    self.trough.winfo_width(), self.page_percent)
            self.handle.place_configure(x=new_x)
        if self.active_handle_y:
            new_y = self._limitPage(event.y, self.handle.winfo_y(), self.handle.winfo_height(),
                                    self.trough.winfo_height(), self.page_percent)
            self.handle.place_configure(y=new_y)

        if not self._clicking:
            self.after(self.init_delay, self._keepClicking)
            self._clicking = True

    def _keepClicking(self):
        if self._clicking:
            event_x, event_y, mouse_in = _getLocalMouse(self.trough.inner)
            self.trough.inner.event_generate("<Button-1>", x=event_x, y=event_y)
            self.after(self.delay, self._keepClicking)

    def scroll(self, event):
        x, y, moused_over = _getLocalMouse(self._linked)
        if moused_over and self.enabled:
            y = self.handle.winfo_y()
            speed = event.delta / self.scrollwheel_speed

            if y - speed < 0:
                self.handle.place_configure(y=0)
            else:
                trough_height = self.trough.winfo_height()
                handle_height = self.handle.winfo_height()

                if trough_height < y + handle_height - speed:
                    self.handle.place_configure(y=trough_height-handle_height)
                else:
                    self.handle.place_configure(y=y-speed)

    def _limitPage(self, event, origin, size, max, restrict=1.0):
        if origin < event < origin + size:
            return origin
        if event <= origin:
            size = -size
        return _limitMove(origin + size * restrict, size, 0, max)

    def _moveCanvas(self, event):
        if self.active_handle_x:
            if self.handle.winfo_width() < self._linked.inner_width:
                x = event.x * ((self._linked.inner.winfo_width()-self._linked.inner_width) /
                               (self.trough.winfo_width()-self.handle.winfo_width()) * self.movement_modifier)
            else: x = 0.0
            self._linked.inner.place_configure(x=x + self.x_offset)

        if self.active_handle_y:
            if self.handle.winfo_height() < self._linked.inner_height:
                y = event.y * ((self._linked.inner.winfo_height()-self._linked.inner_height) /
                               (self.trough.winfo_height()-self.handle.winfo_height()) * self.movement_modifier)
            else: y = 0.0
            self._linked.inner.place_configure(y=y + self.y_offset)


class ScrollableCanvas(Troughable): pass


class ScrollablePane(ScrollableCanvas):
    def __init__(self, parent, width, height, bar_size, scrollbars=(False, False), auto=(False, False)):
        super().__init__(parent, width=width, height=height)
        h_on, v_on = scrollbars
        self.h_auto, self.v_auto = auto

        self._skin = None
        if self.h_auto or self.v_auto:
            self.inner.bind("<Configure>", self.showBars)
        self.inner_width = width - bar_size * v_on * (not self.v_auto)
        self.inner_height = height - bar_size * h_on * (not self.h_auto)

        self.v_scroll = Scrollable(self, bar_size, height, bar_size, bar_size)
        self.v_scroll.place(x=self.inner_width, y=0)
        self.v_scroll.linkTo(self, -1, (False, True))

        self.h_scroll = Scrollable(self, self.inner_width, bar_size, bar_size, bar_size)
        self.h_scroll.place(x=0, y=self.inner_height)
        self.h_scroll.linkTo(self, -1, (True, False))

    def showBars(self, event):
        changed = False
        if self.v_auto:
            if self.inner.winfo_height() > self.inner_height and self.v_scroll.winfo_x() == self.winfo_width():
                self.inner_width -= self.v_scroll.winfo_width()
                changed = True
            elif self.inner.winfo_height() < self.inner_height and self.v_scroll.winfo_x() < self.winfo_width():
                self.inner_width = self.winfo_width()
                changed = True

        if self.h_auto:
            if self.inner.winfo_width() > self.inner_width and self.h_scroll.winfo_y() == self.winfo_height():
                self.inner_height -= self.h_scroll.winfo_height()
                changed = True
            elif self.inner.winfo_width() < self.inner_width and self.h_scroll.winfo_y() != self.inner_height:
                    self.inner_height = self.winfo_height()
                    changed = True

        if changed:
            if self.v_auto:
                self.h_scroll.trough.configure(width=self.inner_width)
                self.h_scroll.place_configure(width=self.inner_width)
                self.v_scroll.place_configure(x=self.inner_width)
                self.v_scroll.resize_handle()
            if self.h_auto:
                self.h_scroll.place_configure(y=self.inner_height, width=self.inner_width)
                self.h_scroll.trough.configure(width=self.inner_width)
                self.h_scroll.resize_handle()

    def setSkin(self, ScrollSkin):
        self.v_scroll._skin = ScrollSkin
        self.h_scroll._skin = ScrollSkin

    def disable(self):
        self.v_scroll.disable()
        self.h_scroll.disable()
        super().disable()

    def enable(self):
        self.v_scroll.enable()
        self.h_scroll.enable()
        super().enable()


class ScrollSkin:
    def __init__(self, trough_paths, handle_paths, linkTo=None):
        self._trough_paths = self._conform_pairs(trough_paths)
        self._handle_paths = self._conform_pairs(handle_paths)
        if linkTo is not None:
            self.linkTo(linkTo)

    def linkTo(self, Scrollable): Scrollable.setSkin(self)

    def drawTo(self, Scrollable, horizontal=False):
        trough_sprites = [tk.PhotoImage(file=n) for n in self._trough_paths]
        handle_sprites = [tk.PhotoImage(file=n) for n in self._handle_paths]

        troughs, handles = ([], [])
        Scrollable.update_idletasks()
        for pair in range(0, 8, 2):
            self._drawPairs(self._trough_paths, trough_sprites, pair, troughs, Scrollable.trough, horizontal)
            self._drawPairs(self._handle_paths, handle_sprites, pair, handles, Scrollable.handle, horizontal)
        Scrollable.trough.setImage(troughs)
        Scrollable.handle.images = handles
        updateHover(Scrollable.trough)
        updateHover(Scrollable.handle)

    def _drawPairs(self, in_paths, in_images, pair, out_imgs, widget, override=False):
        if len(in_paths) > pair:
            out_imgs.append(self.drawBar(in_images[pair:pair+2], widget.winfo_width(), widget.winfo_height(), override))
        else:
            out_imgs.append(out_imgs[0])

    def drawBar(self, images, width, height, horizontal):
        newimg = tk.PhotoImage(width=width, height=height)
        cap_w, cap_h = (images[1].width(), images[1].height())

        if horizontal or width > height:
            pass
            self._putToImage(images[1], newimg, (0, 0, cap_h, cap_w), rotate=True)
            self._putToImage(images[0], newimg, (cap_h, 0, width-cap_h, height), rotate=True)
            self._putToImage(images[1], newimg, (width-cap_h, 0, width, height), mirror_x=True, rotate=True)
        else:
            cap_h = images[1].height()
            self._putToImage(images[1], newimg, (0, 0, cap_w, cap_h))
            self._putToImage(images[0], newimg, (0, cap_h, width, height-cap_h))
            self._putToImage(images[1], newimg, (0, height-cap_h, width, height), mirror_y=True)
        return newimg

    def _conform_pairs(self, pairs_list):
        # If 2nd position in [mid, cap] pair is None, set to [mid, mid]
        for n in range(0, len(pairs_list), 2):
            if len(pairs_list) == n+1:
                pairs_list.append(pairs_list[n])
            elif pairs_list[n+1] is None:
                pairs_list[n+1] = pairs_list[n]
        return pairs_list

    def _putToImage(self, brush, canvas, bbox, mirror_x=False, mirror_y=False, rotate=False):
        value1 = brush.height() if rotate else brush.width()
        value2 = brush.width() if rotate else brush.height()
        start1, end1, increment1 = (value1-1, -1, -1) if mirror_x else (0, value1, 1)
        start2, end2, increment2 = (value2-1, -1, -1) if mirror_y else (0, value2, 1)

        data = ""
        for col in range(start2, end2, increment2):
            data = data + "{"
            for row in range(start1, end1, increment1):
                data = data + "#%02x%02x%02x " % brush.get(col if rotate else row, row if rotate else col)
            data = data + "} "
        canvas.put(data, to=bbox)
