import tkinter as tk

from .utilities import limitMove, getLocalMouse, updateHover, getGeometry
from .windowing import Backgroundable, Frameable
from .skinnable import ScrollSkin, BarSkin, Skin, FilterSkin
from .widgets import Draggable, Holdable, Hoverable, Glassable


class Scrollable():
    def __init__(self, parent, trough_width, trough_height, handle_width, handle_height, scrollable_skin=None, **kwargs):
        self.scrollwheel_speed = 10
        self.page_percent = .9

        if scrollable_skin is None: scrollable_skin = ScrollableSkin()

        self.handle, self.linked = None, False
        super().__init__(parent, trough_width, trough_height, scrollable_skin.troughs, **kwargs)

        self.active_handle_x, self.active_handle_y = True, True
        self.handle = Draggable(self.inner, skin=scrollable_skin.handles, width=handle_width, height=handle_height)
        self.handle.place(x=0, y=0)
        self.enable()

    def enable(self):
        if not self.enabled:
            if self.handle: self.handle.enable()
            if self.linked: self._linkTo()
        super().enable()

    def disable(self):
        self.handle.disable()
        super().disable()

    def setSkin(self, scroll_skin):
        super().setSkin(scroll_skin)
        self.handle.setSkin(scroll_skin)

    def linkTo(self, scrollablecanvas, movement_modifier=-1, active_handle_xy=(True, True), canvas_offset=(0.0, 0.0)):
        self.movement_modifier = movement_modifier
        self._linked = scrollablecanvas
        self._linkedwidth = self._linked.inner.winfo_width()
        self._linkedheight = self._linked.inner.winfo_height()
        self.active_handle_x, self.active_handle_y = active_handle_xy
        self.x_offset, self.y_offset = canvas_offset
        self._linkTo()

    def _linkTo(self):
        if self.active_handle_y:
            self.bind_all("<MouseWheel>", self.scroll, "+")
        self.handle.bind("<Configure>", self._moveCanvas, "+")
        self.inner.bind("<Button-1>", self.clicked, "+")
        self.inner.bind("<ButtonRelease-1>", self.mouseUp, "+")
        self._linked.inner.bind("<Configure>", self.maybe_resize_handle, "+")
        self.bind("<Configure>", self.maybe_resize_handle)
        self.linked = True

    def maybe_resize_handle(self, event=None):
        """
        Checks if the linked canvas has changed in size and triggers handle resizing if needed.
        Logic consolidated from `_resize_handle` and `resize_handle`.
        """
        if not hasattr(self, '_linked') or self._linked is None:
            return

        current_w = self._linked.inner.winfo_width()
        current_h = self._linked.inner.winfo_height()

        if self._linkedwidth == current_w and self._linkedheight == current_h:
            return

        if not self.active_handle_x or current_w < self._linked.inner_width:
            self.handle.config(width=self.winfo_width())
        else:
            self.enable()
            self._linked.inner.update_idletasks()
            ratio_x = self.winfo_width() / current_w * self._linked.inner_width
            self.handle.config(width=ratio_x)

        if not self.active_handle_y or current_h < self._linked.inner_height:
            self.handle.config(height=self.winfo_height())
        else:
            self.enable()
            ratio_y = self.winfo_height() / current_h * self._linked.inner_height
            self.handle.config(height=ratio_y)

        self.update_idletasks()
        if self.handle.winfo_width() == self.winfo_width() and self.handle.winfo_height() == self.winfo_height():
            self.disable()

        self.handle._skin.drawBars(self.handle.winfo_width(), self.handle.winfo_height())
        updateHover(self.handle)
        self._skin.drawBars(self.winfo_width(), self.winfo_height())
        updateHover(self)

        self._linkedwidth = current_w
        self._linkedheight = current_h

    def clicked(self, event):
        if self.active_handle_x:
            new_x = self._limitPage(event.x, self.handle.winfo_x(), self.handle.winfo_width(),
                                    self.winfo_width(), self.page_percent)
            self.handle.place_configure(x=new_x)
        if self.active_handle_y:
            new_y = self._limitPage(event.y, self.handle.winfo_y(), self.handle.winfo_height(),
                                    self.winfo_height(), self.page_percent)
            self.handle.place_configure(y=new_y)

        if not self._clicking:
            self.after(self.init_delay, self._keepClicking)
            self._clicking = True

        super().clicked(event)

    def _keepClicking(self):
        if self._clicking:
            event_x, event_y, mouse_in = getLocalMouse(self.inner)
            self.inner.event_generate("<Button-1>", x=event_x, y=event_y)
            self.after(self.delay, self._keepClicking)

    def scroll(self, event):
        x, y, moused_over = getLocalMouse(self._linked)
        if moused_over and self.enabled:
            y = self.handle.winfo_y()
            speed = event.delta / self.scrollwheel_speed

            if y - speed < 0:
                self.handle.place_configure(y=0)
            else:
                trough_height = self.winfo_height()
                handle_height = self.handle.winfo_height()

                if trough_height < y + handle_height - speed:
                    self.handle.place_configure(y=trough_height - handle_height)
                else:
                    self.handle.place_configure(y=y - speed)

    def _limitPage(self, event, origin, size, max_val, restrict=1.0):
        if origin < event < origin + size:
            return origin
        if event <= origin:
            size = -size
        return limitMove(origin + size * restrict, size, 0, max_val)

    def _moveCanvas(self, event):
        if self.active_handle_x:
            if self.handle.winfo_width() < self._linked.inner_width:
                x = event.x * ((self._linked.inner.winfo_width() - self._linked.inner_width) /
                               (self.winfo_width() - self.handle.winfo_width()) * self.movement_modifier)
            else:
                x = 0.0
            self._linked.inner.place_configure(x=x + self.x_offset)

        if self.active_handle_y:
            if self.handle.winfo_height() < self._linked.inner.winfo_height():
                y = event.y * ((self._linked.inner.winfo_height() - self._linked.inner_height) /
                               (self.winfo_height() - self.handle.winfo_height()) * self.movement_modifier)
            else:
                y = 0.0
            self._linked.inner.place_configure(y=y + self.y_offset)


class Scrollable(Backgroundable):
    def __init__(self, parent, width:int, height:int, scroll_skin: ScrollSkin, **kwargs):
        super().__init__(parent, width=width, height=height, **kwargs)

        self._scroll_skin = scroll_skin
        v_breadth, h_breadth = self._scroll_skin.vertical.breadth, self._scroll_skin.horizontal.breadth
        self._inner.configure(bg='gray55')
        self._inner.place_configure(width=width-h_breadth, height=height-v_breadth)

        self._scroll_plate = Glassable(self)
        self._scroll_plate.place(x=0, y=0, width=width-h_breadth, height=height-v_breadth)
        self._scroll_plate.bind('<Configure>', self._config_plate)

        # Place the scrollbars.
        self.v_bar = ScrollBar(self, v_breadth, height, self._scroll_skin.vertical, None,
                               self._scroll_skin.button, True, v_breadth)
        self.v_bar.place(x=width-v_breadth, y=0)
        self.h_bar = ScrollBar(self, width-v_breadth, h_breadth, self._scroll_skin.horizontal, None,
                               self._scroll_skin.button, False, h_breadth)
        self.h_bar.place(x=0, y=height-h_breadth)

    def _config_plate(self, event):
        w, h = max(self._scroll_plate.winfo_reqwidth(), self.size[0]), max(self._scroll_plate.winfo_reqheight(), self.size[1])
        _, _, sw, sh = getGeometry(self._scroll_plate)
        if sw < w or sh < h:
            self._scroll_plate.place_configure(width=w, height=h)

    @property
    def scrollPane(self): return self._scroll_plate

    def movePane(self, x_per:int, y_per:int):
        # TODO: Store state/minimize calculations.
        frame_w, frame_h = self.size
        ix, iy, iw, ih = getGeometry(self._scroll_plate)
        iw, ih = self._scroll_plate.winfo_reqwidth(), self._scroll_plate.winfo_reqheight()
        min_x = min(0, -(iw - frame_w))
        min_y = min(0, -(ih - frame_h))
        x = min_x * x_per if x_per else ix
        y = min_y * y_per if y_per else iy

        #print(x, y)
        self._scroll_plate.place_configure(x=x, y=y)
        self._scroll_plate.redraw()

        #self.inner._geometry[0], self._geometry[1] = x, y


class ScrollBar(Backgroundable):
    def __init__(self, parent, width:int, height:int, bar_skin: BarSkin | None = None, handle_skin: BarSkin | None = None,
                 button_skin:Skin|None = None, vertical=True, breadth:int = 0, **kwargs):
        super().__init__(parent, width, height, **kwargs)
        self._bar_skin = bar_skin or BarSkin()
        self._handle_skin = handle_skin or BarSkin().fromColors('gray65', 'white', 'red', 'gray10')
        self._button_skin = button_skin
        self._vertical = vertical

        self._handle = None
        self._trough = None

        if breadth < 1: breadth = min(width, height)        # 0/negative = Auto breadth.
        if self._button_skin:
            # Determine button width/height from Skin or as square of trough's breadth.
            if self._button_skin.hasImages():
                bw, bh = self._button_skin.resolution()
            else:
                bw, bh = breadth, breadth
            # Determine 2nd button's x,y location and define trough geometry based on vertical/horizontal orientation.
            if vertical:
                b2x, b2y = 0, height - bh
                tx, ty, tw, th = 0, bh, width, height - (bh * 2)
            else:
                b2x, b2y = width - bw, 0
                tx, ty, tw, th = bw, 0, width - (bw * 2), height

            # Make and place buttons
            button1 = Holdable(self, skin=self._button_skin, width=bw, height=bh)
            button1.place(x=0, y=0)
            button2 = Holdable(self, skin=FilterSkin(self._button_skin, mirror_x=not vertical, mirror_y=vertical),
                               width=bw, height=bh)
            button2.place(x=b2x, y=b2y)
        else:
            tx, ty, tw, th = 0, 0, width, height
        # Place trough
        trough = ScrollTrough(self, self._bar_skin, width=tw, height=th)
        trough.place(x=tx, y=ty)
        # Place Handle
        handle = ScrollHandle(trough, self._handle_skin, width=breadth, height=breadth)
        handle.place(x=0, y=0)

    @property
    def vertical(self): return self._vertical

    def movePane(self, x_percent:float|None, y_percent:float|None):
        self.master.movePane(x_percent, y_percent)

    def resizeHandle(self, width:int, height:int): self._handle.resize(width, height)
    def moveHandle(self, x_percent:int, y_percent:int):
        frame_w, frame_h = self._trough.size
        handle_w, handle_h = self._handle.size
        self._handle.move(x_percent * (frame_w-handle_w), y_percent * (frame_h-handle_h))

    def troughClicked(self, percent:float):
        # Smooth/Instant scrolling? Page/Destination scrolling?
        # Move handle

        # Move scrollPane
        scroll_x, scroll_y = (None, percent) if self.vertical else (percent, None)
        self.movePane(scroll_x, scroll_y)
        pass

class ScrollTrough(Holdable):
    def __init__(self, parent:ScrollBar, skin:BarSkin, **kwargs):
        self.vertical = parent.vertical
        self._default_skin = BarSkin()

        super().__init__(parent, skin=skin, **kwargs)
        self._handle = None

    # Pass handle's percentage of trough traversed to parent ScrollBar
    def handleMoved(self, x:int, y:int, w:int, h:int):
        per_x, per_y = (None, y / (self._geometry[3]-h)) if self.vertical else (x / (self.geometry[2]-w), None)
        self.master.movePane(per_x, per_y)

    def moveHandle(self, x_percent:int, y_percent:int):
        hw, hh = self._handle.size
        self._handle.move(int(x_percent * (self._geometry[2]-hw)), int(y_percent * (self.geometry[3]-hh)))

    def setState(self, state_index:int = 0):
        self._skin.image(state_index, self._geometry[2 + self.vertical])       # Update skin's length.
        super().setState(state_index)

    def clicked(self, event):
        super().clicked(event)
        percent = event.y / self._geometry[3] if self.vertical else event.x / self._geometry[2]
        self.master.troughClicked(percent)      # Pass click event to parent ScrollBar for handling.
        self.after(self.init_delay, self._keepClicking)

    def _keepClicking(self):
        if self._clicking:
            mo = getLocalMouse(self)
            percent = mo[1] / self._geometry[3] if self.vertical else mo[0] / self._geometry[2]
            self.master.troughClicked(percent)
            self.after(self.delay, self._keepClicking)

    def registerChild(self, child):
        if isinstance(child, ScrollHandle): self._handle = child
        super().registerChild(child)


class ScrollHandle(Draggable):
    def __init__(self, parent:ScrollTrough, bar_skin:BarSkin = None, **kwargs):
        self.vertical = parent.vertical
        super().__init__(parent, skin=bar_skin or BarSkin(), **kwargs)

    def move(self, x:int, y:int):
        x = limitMove(x, self._geometry[2], *self._bounds[0], self._bounds[2])
        y = limitMove(y, self._geometry[3], *self._bounds[1], self._bounds[3])
        self.place_configure(x=x, y=y)
        self._geometry[0], self._geometry[1] = x, y

    def resize(self, w:int, h:int):
        self.configure(width=w, height=h)
        self._geometry[2], self._geometry[3] = w, h

    def setState(self, state_index:int = 0):
        self._skin.image(state_index, self._geometry[2 + self.vertical])
        super().setState(state_index)

    def _drag(self, x:int, y:int):
        super()._drag(x, y)
        self.master.handleMoved(*self._geometry)



class ScrollFrame(Frameable):
    def __init__(self, parent, width:int, height:int, scroll_skin:ScrollSkin=None):
        self._skin = scroll_skin or ScrollSkin()
        super().__init__(parent, width, height, self._skin.bgColor())

        self.collapse = tk.Frame(self.inner)
        self.collapse.pack(anchor=tk.W)

        self.h_auto, self.v_auto = auto
        h_on, v_on = scrollbars
        vsize, hsize = self._skin.vertical.breadth, self._skin.horizontal.breadth

        self.inner_width = width - vsize * v_on * (not self.v_auto)
        self.inner_height = height - hsize * h_on * (not self.h_auto)

        self.v_scroll = ScrollBar(self, vsize, height, vsize, hsize, self._skin.vertical)
        self._skin.v_skin.bindScrollable(self.v_scroll)
        self.v_scroll.place(x=self.inner_width, y=0)
        self.v_scroll.linkTo(self, -1, (False, True))

        self.h_scroll = ScrollBar(self, self.inner_width, bar_size, bar_size, bar_size, self._skin.h_skin)
        self._skin.h_skin.bindScrollable(self.h_scroll)
        self.h_scroll.place(x=0, y=self.inner_height)
        self.h_scroll.linkTo(self, -1, (True, False))

        if self.h_auto or self.v_auto:
            self.inner.bind("<Configure>", self.showBars)

    def setSkin(self, scrollablepane_skin):
        if scrollablepane_skin is not None:
            scrollablepane_skin.v_skin.bindScrollable(self.v_scroll)
            scrollablepane_skin.h_skin.bindScrollable(self.h_scroll)

    def showBars(self, event):
        changed = False
        self.update_idletasks()

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
                self.h_scroll.configure(width=self.inner_width)
                self.h_scroll.place_configure(width=self.inner_width)
                self.v_scroll.place_configure(x=self.inner_width)
                self.v_scroll.maybe_resize_handle()
            if self.h_auto:
                self.h_scroll.place_configure(y=self.inner_height, width=self.inner_width)
                self.h_scroll.configure(width=self.inner_width)
                self.h_scroll.maybe_resize_handle()

    def disable(self):
        self.v_scroll.disable()
        self.h_scroll.disable()

    def enable(self):
        self.v_scroll.enable()
        self.h_scroll.enable()