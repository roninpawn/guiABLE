import tkinter as tk
from math import floor
from time import time

from .utilities import limitMove, getLocalMouse, updateHover, getGeometry, fastCrop
from .windowing import Backgroundable
from .skinnable import ScrollSkin, BarSkin, Skin, FilterSkin, ButtonPack
from .widgets import Draggable, Baseable, Repeatable


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
        self.bench, self.benches = 0, 0

    def setState(self, state_index:int = 0):
        start = time()
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

        self.bench += time() - start
        self.benches += 1
        if self.benches >= 100:
            print(f"{round(self.bench / 100, 5)}s per draw.")
            self.bench, self.benches = 0, 0

    def redraw(self):
        super().redraw()

    def _refresh(self, event=None):
        super()._refresh(event)
        new_w, new_h = self.size

        children = self.winfo_children()
        for c in range(len(children)-1, -1, -1):
            cx, cy, cw, ch = getGeometry(children[c])
            if cx+cw > new_w: new_w = cx+cw
            if cy+ch > new_h: new_h = cy+ch

        self._geometry = self._geometry[0], self._geometry[1], new_w, new_h
        self.redraw()

        #self.after_idle(self._get_req_geometry)

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
    def scroll_plate(self): return self._plate

    def _refresh(self, event=None):
        super()._refresh(event)
        w, h = max(self._plate.winfo_reqwidth(), self.size[0]), max(self._plate.winfo_reqheight(), self.size[1])
        sw, sh = self._plate.size
        if sw != w or sh != h: self._plate.place_configure(width=w, height=h)
        self._plate.refresh()


class Scrollable(tk.Frame):
    def __init__(self, parent, width:int, height:int, scroll_skin:ScrollSkin, skin:Skin = None, **kwargs):
        super().__init__(parent, width=width, height=height, **kwargs)

        # ==OPTIONS==
        self.show_v, self.show_h = 2, 2     # Show scrollbars = 0:False, 1:True, 2:Automatic (if content exceeds frame)
        self.smooth_scroll, self.smooth_rate, self.page_steps, self.line_steps = True, 4, 20, 10
        self.scroll_type, self.page_scale, self.line_size = True, [0.95, 0.9], [14, 14]

        self._scroll_skin = scroll_skin
        v_breadth, h_breadth = self._scroll_skin.vertical.breadth, self._scroll_skin.horizontal.breadth
        bw, bh = width-v_breadth, height-h_breadth

        self._frame = ScrollFrame(self, bw, bh, skin)
        self._frame.place(x=0, y=0)
        self._plate = self._frame.scroll_plate

        # TODO: Remove this BarSkin override when HandleSkins are passable.
        handle_skin = BarSkin(length=v_breadth, breadth=h_breadth)
        handle_skin.setBGColors("gray47", "gray56", "gray83", "gray27")

        # Place the scrollbars.
        self._v_bar = VerticalScrollbar (self, v_breadth, height, self._scroll_skin.vertical, handle_skin,
                                         self._scroll_skin.button, v_breadth)
        self._v_bar.place(x=width - v_breadth, y=0)
        self._h_bar = HorizontalScrollbar(self, width - v_breadth, h_breadth, self._scroll_skin.horizontal, handle_skin,
                                          self._scroll_skin.button, h_breadth)
        self._h_bar.place(x=0, y=height - h_breadth)

        # Page/line scroll variables for both horizontal[0] and vertical[1] states.
        self._page_size, self._scroll_range = [None, None], None
        self._scroll_rate, self._scroll_dest = [None,None], [None,None]   # Smooth scroll
        self._plate_location = [None,None]

    @property
    def skin(self): return self._frame.skin
    @property
    def scroll_plate(self): return self._frame.scroll_plate
    @property
    def v_bar(self): return self._v_bar
    @property
    def h_bar(self): return self._h_bar

    def pageSize(self, axis:int) -> int:
        if self._page_size[axis] is None:
            self._page_size[axis] = int(self._frame.size[axis] * self.page_scale[axis])
        return self._page_size[axis]

    @property
    def scrollRange(self) -> int:
        if self._scroll_range is None:
            self._scroll_range = [self._frame.size[0] - self._plate.size[0], self._frame.size[1] - self._plate.size[1]]
        return self._scroll_range

    def movePlate(self, x:int|None, y:int|None):
        # Conform to min/max
        px, py, pw, ph = self._plate.geometry
        fw, fh = self._frame.size
        x = px if x is None else max(-pw + fw, min(0, x))
        y = py if y is None else max(-ph + fh, min(0, y))

        # Move children
        #dx, dy = px - x, py - y
        #for child in self._plate.winfo_children():
        #    cx, cy, = child.winfo_x(), child.winfo_y()
        #    child.place_configure(x=cx-dx, y=cy-dy)

        # Move plate
        self._plate.place_configure(x=x, y=y)

        # Move scroll handles to match percent of trough travelled.
        sr = self.scrollRange
        if sr[0]: self.h_bar.moveHandle(x/sr[0])
        if sr[1]: self.v_bar.moveHandle(y/sr[1])


class ScrollBar(Backgroundable):
    def __init__(self, parent, width:int, height:int, bar_skin:BarSkin|None = None, handle_skin:BarSkin|None = None,
                 button_pack:ButtonPack|None = None, breadth:int = 0, **kwargs):
        self._bar_skin = bar_skin or BarSkin()
        self._buttons = button_pack

        kwargs["width"], kwargs["height"] = width, height
        super().__init__(parent, **kwargs)

        if breadth < 1: breadth = min(width, height)        # 0/negative = Auto breadth.
        self._bar_skin.usesBgColors(True)       # ScrollBar widgets are "floored" by default. No transparency below.

        # Spawn buttons and calculate positional adjustments for the trough, if a ButtonPack has been declared.
        tx, ty, tw, th = self._spawn_buttons(width, height) if self._buttons else (0, 0, width, height)

        # Make and place Trough and Handle
        self._trough = ScrollTrough(self, self._bar_skin, width=tw, height=th)
        self._handle = ScrollHandle(self._trough, handle_skin or BarSkin(vertical=bool(self._orientation[0]),
                                   breadth=breadth), bool(self._orientation[0]), width=breadth, height=breadth)

        self._trough.place(x=tx, y=ty)
        self._handle.place(x=0, y=0)

        self._step_list = []

    @property
    def vertical(self): return bool(self._orientation[0])

    def handleDragged(self):
        x, y, w, h = self._handle.geometry
        tw, th = self._trough._geometry[2] - w, self._trough._geometry[3] - h
        sw, sh = self.master.scrollRange
        self.master.movePlate(x / tw * sw if tw else None, y / th * sh if th else None)

    def resizeHandle(self, width:int, height:int): self._handle.resize(width, height)

    def moveHandle(self, per:float):
        o = self._orientation[0]
        move = list(self._handle.location)
        move[o] = per * (self._trough.size[self._orientation[0]]-self._handle.size[self._orientation[0]])
        self._handle.move(*move)

    def troughClicked(self, click_x:int, click_y:int):
        o = self._orientation[0]
        click = (click_x, click_y)
        direction = 1 if click[o] < self._handle.middle[o] else -1

        page_size, steps = self.master.pageSize(o) * direction, self.master.page_steps
        destination = self.master.scroll_plate.location[o] + page_size

        move = [None, None]
        # If smooth_scrolling, prepare a complete list of interpolated animation stops.
        if self.master.smooth_scroll: self._beginAnimating(steps, page_size, destination)
        else:
            move[o] = destination       # If not smooth scrolling, just go to the destination.
            self.master.movePlate(*move)

    def buttonPressed(self, direction:int):
        o = self._orientation[0]
        steps, line_size = self.master.line_steps, self.master.line_size[o] * direction
        destination = self.master.scroll_plate.location[o] + line_size

        move = [None, None]
        if self.master.smooth_scroll: move[0] = self._beginAnimating(steps, line_size, destination)
        move[o] = self.master.scroll_plate.location[o] + line_size

        self.master.movePlate(*move)

    def _beginAnimating(self, steps:int, step_size:int, destination:int):
        delta = int(step_size / steps)
        new_scroll = not len(self._step_list)       # If animating a scroll already, just create new steps.
        self._step_list = [destination]     # step_list is populated from last to first for fastest access by pop.
        for i in range(steps-1): self._step_list.append(self._step_list[i] - delta)
        if new_scroll: self._animationStep()

    def _animationStep(self):
        if len(self._step_list):
            move = [None, None]
            move[self._orientation[0]] = self._step_list.pop()
            self.master.movePlate(*move)

            if len(self._step_list): self.after(self.master.smooth_rate, self._animationStep)

    def _spawn_buttons(self, width:int, height:int) -> tuple[int,int,int,int]:
        self._buttons.usesBgColors(True)

        # Set skins to the correct direction [0,1,2,3 == n,e,s,w]
        d1, d2 = self._directions
        bskin1, bskin2 = self._buttons.skins[d1], self._buttons.skins[d2]

        # Front-load local indexable tuples.
        dims = (width, height)
        b1wh = bskin1.resolution()      # b1 and b2 contain [width, height]
        b2wh = bskin2.resolution()

        # Get Button2's x and y
        idx, opp = self._orientation
        b2pos = [0, 0]                  # empty placeholder (preserves 0 for one side of x/y coordinates)
        b2pos[idx] = dims[idx] - b2wh[idx]

        b2x, b2y = b2pos

        # Get the trough's rectangle
        tpos = [0, 0]                   # empty placeholder (preserves 0 for one side of x/y coordinates)
        tpos[idx] = b1wh[idx]           # offset start by button 1 size

        tsize = list(dims)              # copy of dims that won't change the original
        tsize[idx] = dims[idx] - (b2wh[idx] * 2)

        tx, ty = tpos
        tw, th = tsize

        # Make and place buttons
        delay = self.master.smooth_rate * self.master.line_steps    # Match function delay to animation rate.
        button1 = Repeatable(self, lambda: self.buttonPressed(1), bskin1, delay, width=b1wh[0], height=b1wh[1])
        button1.place(x=0, y=0)
        button2 = Repeatable(self, lambda: self.buttonPressed(-1), bskin2, delay, width=b2wh[0], height=b2wh[1])
        button2.place(x=b2x, y=b2y)

        return tx, ty, tw, th


class VerticalScrollbar(ScrollBar):
    def __init__(self, parent, width:int, height:int, bar_skin:BarSkin|None = None, handle_skin:BarSkin|None = None,
                 button_pack:ButtonPack|None = None, breadth:int = 0, **kwargs):
        self._directions = 0, 2
        self._opposites = 1, 3
        self._orientation = 1, 0
        super().__init__(parent, width, height, bar_skin, handle_skin, button_pack, breadth, **kwargs)


class HorizontalScrollbar(ScrollBar):
    def __init__(self, parent, width:int, height:int, bar_skin:BarSkin|None = None, handle_skin:BarSkin|None = None,
                 button_pack:ButtonPack|None = None, breadth:int = 0, **kwargs):
        self._directions = 3, 1
        self._opposites = 0, 2
        self._orientation = 0, 1
        super().__init__(parent, width, height, bar_skin, handle_skin, button_pack, breadth, **kwargs)


class ScrollTrough(Repeatable):
    def __init__(self, parent:ScrollBar, skin:BarSkin = None, **kwargs):
        self._vertical = parent.vertical
        self._default_skin = BarSkin()
        self._handle = None

        super().__init__(parent, skin=skin, **kwargs)

    def handleDragged(self): self.master.handleDragged()

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

        self._middle = None

    @property
    def middle(self) -> tuple[int, int]:
        if self._middle is None:
            x = self._geometry[0] + (self._geometry[2] * 0.5)
            y = self._geometry[1] + (self._geometry[3] * 0.5)
            self._middle = (x, y)
        return self._middle

    def move(self, x:int, y:int):
        w, h = self.size
        x = limitMove(x, w, self._bounds[0], self._bounds[2])
        y = limitMove(y, h, self._bounds[1], self._bounds[3])
        self.place_configure(x=x, y=y)

    def resize(self, w:int, h:int): self.configure(width=w, height=h)

    def setState(self, state_index:int = 0):
        self._skin.image(state_index, self._geometry[2 + self.vertical])
        super().setState(state_index)

    def _drag(self, x:int, y:int):
        super()._drag(x, y)
        self.master.handleDragged()

    def _refresh(self, event=None):
        super()._refresh(event)
        self._middle = None
