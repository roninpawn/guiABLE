import tkinter as tk
from math import floor

from .utilities import limitMove, getLocalMouse, updateHover, getGeometry, fastCrop
from .windowing import Backgroundable
from .skinnable import ScrollSkin, BarSkin, Skin, FilterSkin, ButtonPack
from .widgets import Draggable, Holdable, Baseable


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


class ScrollPlate(Baseable):
    def __init__(self, parent, skin=None, **kwargs):
        super().__init__(parent, skin, **kwargs)

    def setState(self, state_index:int = 0):
        # If widget lacks geometry (has not fully spawned) wait until it has.
        x, y, w, h = self.geometry
        if w < 1 and h < 1:
            self.after_idle(self.redraw)
            return
        if self.master.skin.hasImages():
            w, h = self.master.skin.resolution()[:2]
            fastCrop(self._scratch, self.master.skin.image(), w, h, 0, 0, w, h)
            self.render(self._scratch, -x, -y)
        else:
            bg_color = self.master.skin.bgColor()
            self.configure(background=bg_color)

    def redraw(self):
        super().redraw()

    def _refresh(self, event=None):
        super()._refresh(event)
        self.after_idle(self._get_req_geometry)

    def _get_req_geometry(self):        # TODO: Could be problematic overriding geometry. Store req separate if issues.
        mw, mh = self.master.size
        self._geometry = (*self.location, max(self.winfo_reqwidth(), mw), max(self.winfo_reqheight(), mh))
        self.redraw()


class ScrollFrame(Backgroundable):
    def __init__(self, parent, width:int, height:int, skin=None, **kwargs):
        super().__init__(parent, width, height, skin, **kwargs)
        self._plate = ScrollPlate(self, width=width, height=height)
        self.after_idle(self.refresh)

    @property
    def scrollPlate(self): return self._plate

    def _refresh(self, event=None):
        super()._refresh(event)
        w, h = max(self._plate.winfo_reqwidth(), self.size[0]), max(self._plate.winfo_reqheight(), self.size[1])
        sw, sh = self._plate.size
        if sw != w or sh != h: self._plate.place_configure(width=w, height=h)
        self._plate.refresh()


class Scrollable(tk.Frame):
    def __init__(self, parent, width:int, height:int, scroll_skin:ScrollSkin, skin:Skin = None, **kwargs):
        super().__init__(parent, width=width, height=height, **kwargs)

        self._scroll_skin = scroll_skin
        v_breadth, h_breadth = self._scroll_skin.vertical.breadth, self._scroll_skin.horizontal.breadth
        bw, bh = width-v_breadth, height-h_breadth

        self._frame = ScrollFrame(self, bw, bh, skin)
        self._frame.place(x=0, y=0)
        self._plate = self._frame.scrollPlate

        # Place the scrollbars.
        self._v_bar = ScrollBar(self, v_breadth, height, self._scroll_skin.vertical, None,
                                self._scroll_skin.button, True, v_breadth)
        self._v_bar.place(x=width - v_breadth, y=0)
        self._h_bar = ScrollBar(self, width - v_breadth, h_breadth, self._scroll_skin.horizontal, None,
                                self._scroll_skin.button, False, h_breadth)
        self._h_bar.place(x=0, y=height - h_breadth)

    @property
    def skin(self): return self._frame.skin
    @property
    def scrollPlate(self): return self._frame.scrollPlate
    @property
    def v_bar(self): return self._v_bar
    @property
    def h_bar(self): return self._h_bar

    def movePlate(self, x_per:float|None, y_per:float|None):
        # TODO: Store state/minimize calculations.
        frame_w, frame_h = self._frame.size
        ix, iy, iw, ih = self._plate.geometry

        min_x = min(0, -(iw - frame_w))
        min_y = min(0, -(ih - frame_h))
        x = min_x * max(0.0, min(1.0, x_per)) if x_per is not None else ix
        y = min_y * max(0.0, min(1.0, y_per)) if y_per is not None else iy

        self._plate.place_configure(x=x, y=y)
        self._plate._geometry = (x, y, iw, ih)
        self._plate.redraw()

    def pageScroll(self, direction:int, percentage:float) -> float:
        if direction in (0, 2):
            page_percent = self._getPageScrollPercent(3, 1, -1 if direction == 0 else 1)
            self.movePlate(None, page_percent)
        else:
            page_percent = self._getPageScrollPercent(2, 0, -1 if direction == 1 else 1)
            self.movePlate(page_percent, None)
        return page_percent

    def _getPageScrollPercent(self, wh:int, xy:int, flip:int) -> float:
            # wh = 2|3, xy = 0|1, flip = -1|1
            page = self._frame.geometry[wh] * .9
            page_per = page / self._plate.geometry[wh]
            cur_per = abs(self._plate.geometry[xy]) / (self._plate.geometry[wh] - page)
            return cur_per + (page_per * flip)


class ScrollBar(Backgroundable):
    def __init__(self, parent, width:int, height:int, bar_skin:BarSkin|None = None, handle_skin:BarSkin|None = None,
                 button_pack:ButtonPack|None = None, vertical=True, breadth:int = 0, **kwargs):
        self._bar_skin = bar_skin or BarSkin()
        self._buttons = button_pack
        self._vertical = vertical

        kwargs["width"], kwargs["height"] = width, height
        super().__init__(parent, **kwargs)

        if breadth < 1: breadth = min(width, height)        # 0/negative = Auto breadth.
        self._bar_skin.usesBgColors(True)       # ScrollBar widgets are "floored" by default. No transparency below.

        # Spawn buttons and calculate positional adjustments for the trough, if a ButtonPack has been declared.
        if self._buttons:
            self._buttons.usesBgColors(True)
            if vertical:
                bskin1, bskin2 = self._buttons.north, self._buttons.south
                b1w, b1h = bskin1.resolution()      # b for button
                b2w, b2h = bskin2.resolution()
                b2x, b2y = 0, height - b2h
                tx, ty, tw, th = 0, b1h, width, height-(b2h*2)      # t for trough
            else:
                bskin1, bskin2 = self._buttons.west, self._buttons.east
                b1w, b1h = bskin1.resolution()
                b2w, b2h = bskin2.resolution()
                b2x, b2y = width - b2w, 0
                tx, ty, tw, th = b1w, 0, width-(b2w*2), height

            # Make and place buttons
            button1 = Holdable(self, skin=bskin1, width=b1w, height=b1h)
            button1.place(x=0, y=0)
            button2 = Holdable(self, skin=bskin2, width=b2w, height=b2h)
            button2.place(x=b2x, y=b2y)
        else:
            tx, ty, tw, th = 0, 0, width, height

        # Make and place Trough and Handle
        self._trough = ScrollTrough(self, self._bar_skin, width=tw, height=th)
        self._handle = ScrollHandle(self._trough, handle_skin or BarSkin(vertical=vertical, breadth=breadth),
                                    self._vertical, width=breadth, height=breadth)

        self._trough.place(x=tx, y=ty)
        self._handle.place(x=0, y=0)

    @property
    def vertical(self): return self._vertical

    def handleDragged(self):
        x, y, w, h = self._handle.geometry
        tw, th = self._trough._geometry[2] - w, self._trough._geometry[3] - h
        self.master.movePlate(x / tw if tw else None, y / th if th else None)

    def scrollPlateResized(self, percent:float):
        hw, hh = self._handle.size
        tw, th = self._trough.size
        if self.vertical:   self._handle.resize(self._handle.geometry[2], floor(self._trough.geometry[3] * percent))
        else:               self._handle.resize(floor(self._trough.geometry[2] * percent), self._handle.geometry[3])

    def resizeHandle(self, width:int, height:int): self._handle.resize(width, height)
        # Pass handle's percentage of trough traversed to parent ScrollBar

    def moveHandle(self, x_percent:int, y_percent:int):
        hw, hh = self._handle.size
        self._handle.move(int(x_percent * (self._geometry[2]-hw)), int(y_percent * (self.geometry[3]-hh)))

    def troughClicked(self, click_x:int, click_y:int):
        tw, th = self._trough.size
        hx, hy, hw, hh = self._handle.geometry
        if self._vertical:
            page_percent = self.master.pageScroll(0 if click_y < hy + (hh * 0.5) else 2, click_y / th)
            self._handle.move(0, int(page_percent * (th - hh)))
        else:
            page_percent = self.master.pageScroll(1 if click_x > hx + (hw * 0.5) else 3, click_x / tw)
            self._handle.move(int(page_percent * (tw - hw)), 0)


class ScrollTrough(Holdable):
    def __init__(self, parent:ScrollBar, skin:BarSkin = None, **kwargs):
        self._vertical = parent.vertical
        self._default_skin = BarSkin()
        self._handle = None

        super().__init__(parent, skin=skin, **kwargs)

    def handleDragged(self): self.master.handleDragged()

    def moveHandle(self, x_percent:int|None, y_percent:int|None):
        hw, hh = self._handle.size
        x, y = int((x_percent or 0) * (self._geometry[2]-hw)), int((y_percent or 0) * (self.geometry[3]-hh))
        self._handle.move(x, y)

    def setState(self, state_index:int = 0):
        self._skin.image(state_index, self._geometry[2 + self._vertical])       # Update skin's length.
        super().setState(state_index)

    def clicked(self, event):
        self._clicking = True
        self.setState(2)
        self.master.troughClicked(event.x, event.y)  # Pass click event to parent ScrollBar for handling.
        self.after(self.init_delay, self._keepClicking)

    def registerChild(self, child):
        super().registerChild(child)
        if isinstance(child, ScrollHandle): self._handle = child

    def _getHandlePercents(self):
        x, y, w, h = self._handle.geometry
        return (None, y / (self._geometry[3]-h)) if self._vertical else (x / (self.geometry[2] - w), None)

    def _keepClicking(self):
        if self._clicking:
            if self._handle:
                mx, my, _ = getLocalMouse(self)
                hx, hy, hw, hh = self._handle.geometry
                if self._vertical:
                    if not hy < my < hy+hh: self.master.troughClicked(*getLocalMouse(self)[:2])
                elif   not hx < mx < hx+hw: self.master.troughClicked(*getLocalMouse(self)[:2])

            self.after(self.delay, self._keepClicking)


class ScrollHandle(Draggable):
    def __init__(self, parent:ScrollTrough, bar_skin:BarSkin = None, vertical:bool = True, **kwargs):
        self.vertical = vertical
        super().__init__(parent, skin=bar_skin or BarSkin(vertical=vertical), **kwargs)

    def move(self, x:int, y:int):
        w, h = self.size
        x = limitMove(x, w, self._bounds[0], self._bounds[2])
        y = limitMove(y, h, self._bounds[1], self._bounds[3])
        self.place_configure(x=x, y=y)
        self._geometry = (x, y, w, h)

    def resize(self, w:int, h:int):
        self.configure(width=w, height=h)
        self._geometry = (*self.location, w, h)

    def setState(self, state_index:int = 0):
        self._skin.image(state_index, self._geometry[2 + self.vertical])
        super().setState(state_index)

    def _drag(self, x:int, y:int):
        super()._drag(x, y)
        self.master.handleDragged()
