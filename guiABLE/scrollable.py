import tkinter as tk

from .utilities import getLocalMouse, rectsOverlap, pointIsInRect, getGeometry
from .windowing import Backgroundable
from .skinnable import ScrollSkin, BarSkin, Skin, ButtonPack
from .widgets import Repeatable, LoneDraggable


class Scrollable(tk.Frame):
    def __init__(self, parent, width:int, height:int, scroll_skin:ScrollSkin, skin:Skin = None, **kwargs):
        super().__init__(parent, width=width, height=height, **kwargs)

        # ==OPTIONS==
        self.show_v, self.show_h = 2, 2     # Show scrollbars = 0:False, 1:True, 2:Automatic (if content exceeds frame)
        self.smooth_rate, self.page_scale, self.line_size = 17, [0.95, 0.9], [16, 16]

        self._page_size = [None, None]
        self._scrollwheel_axis, self._scrollwheel_percent, self._scrollwheel_duration = True, 1.0, 51

        self._scroll_skin = scroll_skin
        v_breadth, h_breadth = self._scroll_skin.vertical.breadth, self._scroll_skin.horizontal.breadth
        bw, bh = width-v_breadth, height-h_breadth

        self._frame = ScrollFrame(self, bw, bh, skin)
        self._frame.place(x=0, y=0)
        self.bind_all("<MouseWheel>", self.scrollByWheel, "+")

        # Place the scrollbars.
        self._v_bar = VerticalScrollbar(self, v_breadth, height, self._scroll_skin.vertical, None,
                                         self._scroll_skin.button, v_breadth)
        self._v_bar.place(x=width - v_breadth, y=0)
        self._h_bar = HorizontalScrollbar(self, width - v_breadth, h_breadth, self._scroll_skin.horizontal, None,
                                          self._scroll_skin.button, h_breadth)
        self._h_bar.place(x=0, y=height - h_breadth)

        # Scroll Defaults (based on 17ms (~60fps) animation rates.
        self.setPageScroll(153, 290)
        self.setLineScroll(51, 0)
        self.setWheelScroll(68, 1.0, True)

    @property
    def skin(self): return self._frame.skin
    @property
    def frame(self): return self._frame
    @property
    def v_bar(self): return self._v_bar
    @property
    def h_bar(self): return self._h_bar

    def getScrollTypes(self) -> tuple[bool, bool]: return self._h_bar.instant_scroll, self._v_bar.instant_scroll
    def setScrollType(self, instant:bool): self.setScrollTypes(instant, instant)
    def setScrollTypes(self, instant_horizontal:bool = None, instant_vertical:bool = None):
        if instant_horizontal is not None: self._h_bar.instant_scroll = instant_horizontal
        if instant_vertical is not None: self._v_bar.instant_scroll = instant_vertical

    def getSmoothScroll(self) -> tuple[bool, bool]: return self._h_bar.smooth_scroll, self._v_bar.smooth_scroll
    def setSmoothScroll(self, smooth:bool): self.setSmoothScrolls(smooth, smooth)
    def setSmoothScrolls(self, smooth_horizontal:bool = None, smooth_vertical:bool = None):
        if smooth_horizontal is not None: self._h_bar.smooth_scroll = smooth_horizontal
        if smooth_vertical is not None: self._v_bar.smooth_scroll = smooth_vertical

    def setPageScroll(self, delay:int = None, extra_init_delay:int = None):
        self._v_bar.setPageScrollDelay(delay, extra_init_delay)
        self._h_bar.setPageScrollDelay(delay, extra_init_delay)

    def setLineScroll(self, delay:int = None, extra_init_delay:int = None):
        self._v_bar.setLineScrollDelay(delay, extra_init_delay)
        self._h_bar.setLineScrollDelay(delay, extra_init_delay)

    def setWheelScroll(self, smooth_duration:int, scroll_amount:float = 1.0, vertical:bool = None):
        self._scrollwheel_duration, self._scrollwheel_percent = smooth_duration, scroll_amount
        if vertical is not None: self._scrollwheel_axis = vertical
        self._v_bar.resetWheel()

    def pageSize(self, axis:int) -> int:
        if self._page_size[axis] is None:
            self._page_size[axis] = int(self._frame.size[axis] * self.page_scale[axis])
        return self._page_size[axis]

    def scrollByWheel(self, event):
        if getLocalMouse(self)[2]:
            delta = int(event.delta * self._scrollwheel_percent)
            if self._scrollwheel_axis:
                self._v_bar.mouseWheeled(delta, self._scrollwheel_duration)
            else: self._h_bar.mouseWheeled(delta, self._scrollwheel_duration)

    def scrollByClick(self, delta_x:int, delta_y:int):
        if delta_x or delta_y:
            sw, sh = self._frame.scroll_range
            px, py, = self._frame.plate_geometry[:2]

            # Clamp the new plate position inside logical bounds
            new_x = max(min(px + delta_x, 0), sw)
            new_y = max(min(py + delta_y, 0), sh)

            # Recalculate deltas from the clamped target
            delta_x, delta_y = new_x - px, new_y - py

            # Update plate location
            self._movePlate(delta_x, delta_y)
            px, py, = self._frame.plate_geometry[:2]

            # Move handles
            if sw: self.h_bar.moveHandle(px / sw)
            if sh: self.v_bar.moveHandle(py / sh)

    def scrollByDrag(self, x_per:float|None, y_per:float|None):
        px, py, pw, ph = self._frame.plate_geometry

        # Convert percentages to pixels and then to the delta of change between them.
        x = int(x_per * self._frame.scroll_range[0]) if x_per is not None else px
        y = int(y_per * self._frame.scroll_range[1]) if y_per is not None else py
        delta_x, delta_y = x - px, y - py

        if delta_y or delta_x: self._movePlate(delta_x, delta_y)

    def _movePlate(self, delta_x:int, delta_y:int):
            self.update_idletasks()
            px, py, pw, ph = self._frame.plate_geometry
            fw, fh = self._frame.geometry[2:]

            # Move "plate" (imaginary)
            px += delta_x
            py += delta_y
            self._frame.plate_geometry = (px, py, pw, ph)

            # Move children
            for child in self._frame.getChildren():
                cx, cy, cw, ch = child.geometry
                new_x, new_y = cx+delta_x, cy+delta_y

                # Is the child visible now -- before we apply the movement?
                live = rectsOverlap((cx, cy, cw, ch), (0, 0, fw, fh))
                if not live: new_x, new_y = px+child.scroll_xy[0], py+child.scroll_xy[1]

                # If the child will be visible after the requested scroll...
                if rectsOverlap((new_x, new_y, cw, ch), (0, 0, fw, fh)):
                    child._geometry = new_x, new_y, cw, ch      # Instant update avoids waiting for _refresh.
                    child.place_configure(x=new_x, y=new_y)
                    child.redraw()

                # If the child is exiting the screen.
                elif live:
                    child.scroll_xy = -px + new_x, -py + new_y
                    child.place_configure(x=0, y=-ch)


class ScrollFrame(Backgroundable):
    def __init__(self, parent:Scrollable, width:int, height:int, skin=None, **kwargs):
        super().__init__(parent, width, height, skin, **kwargs)
        self.plate_geometry = (0, 0, 0, 0)
        self._scroll_range = None

    @property
    def scroll_range(self):
        if self._scroll_range is None:
            self._scroll_range = (  min(-self.plate_geometry[2] + self.width, 0),
                                    min(-self.plate_geometry[3] + self.height, 0) )
        return self._scroll_range

    def registerChild(self, child):
        super().registerChild(child)
        cx, cy, cw, ch = child.geometry

        # TODO: Better way of distinguishing pack() and place() or deprecate pack() entirely.
        # If .pack()'d this works.
        if cx == 0 and cy <= 0 and cw == 1 and ch == 1:
            self.plate_geometry = (*self.plate_geometry[:2], self.winfo_reqwidth(), self.winfo_reqheight())
        else:
            # If .place()'d this works
            cxw, cyh = (max(cx + cw, self.geometry[2], self.plate_geometry[2]),
                        max(cy + ch, self.geometry[3], self.plate_geometry[3]))
            self.plate_geometry = (*self.plate_geometry[:2], cxw, cyh)

        # TODO: When and where we recalculate plate_geometry, it must be by the children's scroll_xy.
        child.scroll_xy = cx, cy

    def mouseWheel(self, event=None):
        self.parent.scrollByWheel(event)
        super().mouseWheel(event)

    def _refresh(self, event=None):
        super()._refresh(event)
        self._scroll_range = None

        self.parent._page_size = [None, None]
        self.parent.v_bar.refresh()
        self.parent.h_bar.refresh()


class ScrollBar(Backgroundable):
    def __init__(self, parent:Scrollable, width:int, height:int, bar_skin:BarSkin|None = None,
                 handle_skin:BarSkin|None = None, button_pack:ButtonPack|None = None, breadth:int = 0, **kwargs):
        self._bar_skin = bar_skin or BarSkin()
        self._buttons = button_pack

        kwargs["width"], kwargs["height"] = width, height
        super().__init__(parent, **kwargs)

        if breadth < 1: breadth = min(width, height)        # 0/negative = Auto breadth.
        self._bar_skin.usesBgColors(True)       # ScrollBar widgets are "floored" by default. No transparency below.

        # Spawn buttons and calculate positional adjustments for the trough, if a ButtonPack has been declared.
        self.button1, self.button2 = None, None
        tx, ty, tw, th = self._spawnButtons(width, height) if self._buttons else (0, 0, width, height)

        # Make and place Trough and Handle
        self._trough = ScrollTrough(self, self._bar_skin, width=tw, height=th)
        self._handle = ScrollHandle(self._trough, handle_skin or BarSkin(vertical=bool(self._orientation[0]),
                                   breadth=breadth), bool(self._orientation[0]), width=breadth, height=breadth)
        self._trough.place(x=tx, y=ty)
        self._handle.place(x=0, y=0)

        # Scroll options
        self.smooth_scroll, self.instant_scroll = True, False
        self._anim_steps = []
        self._line_steps, self._page_steps, self._wheel_steps = None, None, None
        self._anim_keyframe, self._anim_direction = 0, 0

        # Consolidate whiny IDE complaints about undefined variables here, instead of throughout the class.
        self._directions, self._orientation = self._directions, self._orientation

    def enable(self):
        self._trough.enable()
        if self.button1: self.button1.enable()
        if self.button2: self.button2.enable()
    def disable(self):
        self._trough.disable()
        if self.button1: self.button1.disable()
        if self.button2: self.button2.disable()

    def setPageScrollDelay(self, delay:int = None, extra_init_delay:int = None):
        if delay: self._trough.delay = delay
        if extra_init_delay: self._trough.init_delay = delay + extra_init_delay
        self._page_steps = None

    def setLineScrollDelay(self, delay:int = None, extra_init_delay:int = None):
        if self.button1 is not None and self.button2 is not None:
            if delay is not None:
                self.button1.delay = delay
                self.button2.delay = delay
            if extra_init_delay is not None:
                self.button1.init_delay = delay + extra_init_delay
                self.button2.init_delay = delay + extra_init_delay
            self._line_steps = None

    def resetWheel(self): self._wheel_steps = None

    @property
    def vertical(self): return bool(self._orientation[0])

    def handleDragged(self):
        p = self._handle.geometry[self._orientation[0]]
        s = self._trough.scroll_range[self._orientation[0]]

        per = [None, None]
        per[self._orientation[0]] = p/-s if s else 0
        self.parent.scrollByDrag(*per)

    def resizeHandle(self, width:int, height:int): self._handle.resize(width, height)

    def moveHandle(self, per:float):
        o = self._orientation[0]
        move = list(self._handle.geometry[:2])
        move[o] = int(per * -self._trough.scroll_range[o])

        self._handle.move(*move)

    def troughClicked(self, click_x:int, click_y:int):
        o = self._orientation[0]
        click = (click_x, click_y)
        direction = 1 if click[o] < self._handle.middle[o] else -1
        page_size = self.parent.pageSize(o)

        # Instant scrolling goes straight to the point that was clicked.
        if self.instant_scroll:
            handle_px = click[o] - (self._handle.geometry[o+2] // 2)
            per = handle_px / self._trough.scroll_range[o]
            destination = self.parent.frame.plate_geometry[o] + int(per * self.parent.frame.scroll_range[o])
            direction = -1
        # Page scrolling progresses in percentage increments of the scroll frame. (ex: 90% of the viewable area)
        else: destination = page_size

        # Smooth scrolling animates travel to the destination by linear interpolation.
        if self.smooth_scroll:
            if self.instant_scroll:
                self._beginAnimating(self._conformToAnimation(destination, self._trough.delay), direction)
            else: self._beginAnimating(self.page_steps, direction)

        # Simple scrolling goes directly to the destination requested.
        else:
            move = [0, 0]
            move[o] = destination * direction
            self.parent.scrollByClick(*move)

    def buttonClicked(self, direction:int):
        if self.smooth_scroll:
            self._beginAnimating(self.line_steps, direction)
        else:
            move = [0, 0]
            move[self._orientation[0]] = self.parent.line_size[self._orientation[0]] * direction
            self.parent.scrollByClick(*move)

    def mouseWheeled(self, delta:int, duration:int):
        if self.smooth_scroll:
            if self._wheel_steps is None:
                self._wheel_steps = self._conformToAnimation(abs(delta), duration)
            self._beginAnimating(self._wheel_steps, 1 if delta > 0 else -1)
        else:
            move = [0, 0]
            move[self._orientation[0]] = delta
            self.parent.scrollByClick(*move)

    @property
    def page_steps(self):
        if self._page_steps is None:
            self._page_steps = self._conformToAnimation(self.parent.pageSize(self._orientation[0]), self._trough.delay)
        return self._page_steps
    @property
    def line_steps(self):
        if self._line_steps is None:
           self._line_steps = self._conformToAnimation(self.parent.line_size[self._orientation[0]], self.button1.delay)
        return self._line_steps

    def _beginAnimating(self, instructions:tuple, direction:int):
        new_scroll = self._anim_keyframe >= len(self._anim_steps)
        self._anim_steps = instructions
        self._anim_direction = direction
        self._anim_keyframe = 0

        if new_scroll: self._animationStep()        # If animating a scroll already, just reset pointer.

    def _animationStep(self):
        if self._anim_keyframe < len(self._anim_steps):
            move = [0, 0]
            move[self._orientation[0]] = self._anim_steps[self._anim_keyframe] * self._anim_direction
            self.parent.scrollByClick(*move)        # Request a scroll event.

            self._anim_keyframe += 1                # Keep animating until end of animation steps.
            if self._anim_keyframe < len(self._anim_steps): self.after(self.parent.smooth_rate, self._animationStep)

    def _recalcHandle(self):
        o, o1 = self._orientation[:2]
        o2 = o+2

        # f = frame; t = trough; p = plate; sr = scroll range; tr = trough range
        f, t, t1 = self.parent.frame.geometry[o2], self._trough.geometry[o2], self._trough.geometry[o1 + 2]
        p0, p2 = self.parent.frame.plate_geometry[o], self.parent.frame.plate_geometry[o2]
        geo = list(self._handle.geometry)

        geo[o2] = max(t1, min(t, int(f / p2 * t))) if p2 > 0 else t     # Sets handle size (clamped)
        sr = max(p2 - f, 0)                                             # True content scroll range (content - viewport)
        tr = max(t - geo[o2], 0)                                        # True trough scroll range  (trough - handle)
        geo[o] = int((-p0 / sr) * tr) if sr else 0                      # Repositions handle relative to changes

        self._handle.place_configure(x=geo[0], y=geo[1], width=geo[2], height=geo[3])
        if geo[o2] == t: self.disable()

    """ Conforms scroll timing to pixel-friendly, integer rate by choosing the nearest framerate-matching number of
        steps, the nearest matching pixel delta, and then distributing any remainder, evenly, as step-increases.
        Returns: [p,p,p+1,p,p,p+1] or [p+1,p,p+1,p,p+1,p] """
    def _conformToAnimation(self, delta_px:int, delay_ms:int) -> tuple[int, ...]:
        steps = round(delay_ms / self.parent.smooth_rate)
        base = delta_px // steps
        excess = delta_px % steps
        animation = []

        # Bresenham's distributed linear rasterization method.
        error = 0
        for i in range(steps):
            error += excess
            if error >= steps:
                error -= steps
                animation.append(base+1)
            else: animation.append(base)

        return tuple(animation)

    def _spawnButtons(self, width:int, height:int) -> tuple[int,int,int,int]:
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
        self.button1 = ScrollRepeatable(self, lambda: self.buttonClicked(1), bskin1, width=b1wh[0], height=b1wh[1])
        self.button2 = ScrollRepeatable(self, lambda: self.buttonClicked(-1), bskin2, width=b2wh[0], height=b2wh[1])
        self.button1.place(x=0, y=0)
        self.button2.place(x=b2x, y=b2y)

        return tx, ty, tw, th

    def _refresh(self, event=None):
        super()._refresh(event)
        self._line_steps, self._page_steps = None, None
        self.after_idle(self.after_idle, self._recalcHandle)


class VerticalScrollbar(ScrollBar):
    def __init__(self, parent, width:int, height:int, bar_skin:BarSkin|None = None, handle_skin:BarSkin|None = None,
                 button_pack:ButtonPack|None = None, breadth:int = 0, **kwargs):
        self._directions = 0, 2
        self._orientation = 1, 0
        super().__init__(parent, width, height, bar_skin, handle_skin, button_pack, breadth, **kwargs)


class HorizontalScrollbar(ScrollBar):
    def __init__(self, parent, width:int, height:int, bar_skin:BarSkin|None = None, handle_skin:BarSkin|None = None,
                 button_pack:ButtonPack|None = None, breadth:int = 0, **kwargs):
        self._directions = 3, 1
        self._orientation = 0, 1
        super().__init__(parent, width, height, bar_skin, handle_skin, button_pack, breadth, **kwargs)


class ScrollRepeatable(Repeatable):
    def __init__(self, parent:ScrollBar, function = lambda: None, skin:Skin = None, delay:int=80,
                 extra_init_delay:int=370, **kwargs):
        self._init_delay = delay + extra_init_delay
        super().__init__(parent, function, skin, delay, delay+extra_init_delay, **kwargs)

    # Ensure init_delay is always equal to or greater than the pulsing delay. Otherwise, scroll animations could desync.
    @property
    def init_delay(self): return self._init_delay
    @init_delay.setter
    def init_delay(self, delay:int): self._init_delay = self.delay + delay


class ScrollTrough(ScrollRepeatable):
    def __init__(self, parent:ScrollBar, skin:BarSkin = None, **kwargs):
        self._vertical = parent.vertical
        self._default_skin = BarSkin()
        self._handle = None
        self._scroll_range = None

        super().__init__(parent, skin=skin, **kwargs)

    def enable(self):
        super().enable()
        if self._handle: self._handle.enable()
    def disable(self):
        super().disable()
        if self._handle: self._handle.disable()

    @property
    def scroll_range(self):
        if self._scroll_range is None:
            self._scroll_range = (  min(-self.geometry[2] + self._handle.geometry[2], 0),
                                    min(-self.geometry[3] + self._handle.geometry[3], 0) )
        return self._scroll_range

    def handleDragged(self): self.parent.handleDragged()

    def setState(self, state_index:int = 0):
        self._skin.image(state_index, self._geometry[2 + self._vertical])       # Update skin's length.
        super().setState(state_index)

    def clicked(self, event):
        self._clicking = True
        self.setState(2)
        self.parent.troughClicked(event.x, event.y)  # Pass click event to parent ScrollBar for handling.
        self.after(self.init_delay, self._keepClicking)

    def registerChild(self, child):
        super().registerChild(child)
        if isinstance(child, ScrollHandle): self._handle = child

    def _refresh(self, event=None):
        super()._refresh(event)
        self._scroll_range = None

    def _getHandlePercents(self):
        x, y, w, h = self._handle.geometry
        return (None, y / (self._geometry[3]-h)) if self._vertical else (x / (self.geometry[2] - w), None)

    def _keepClicking(self):
        if self._clicking:
            if self._handle:
                mx, my, _ = getLocalMouse(self)
                hx, hy, hw, hh = self._handle.geometry
                if self._vertical:
                    if not hy < my < hy+hh: self.parent.troughClicked(*getLocalMouse(self)[:2])
                elif   not hx < mx < hx+hw: self.parent.troughClicked(*getLocalMouse(self)[:2])

            self.after(self.delay, self._keepClicking)


class ScrollHandle(LoneDraggable):
    def __init__(self, parent:ScrollTrough, bar_skin:BarSkin = None, vertical:bool = True, **kwargs):
        self.vertical = vertical
        super().__init__(parent, skin=bar_skin or BarSkin(vertical=vertical), **kwargs)
        self._half = None

    @property
    def middle(self) -> tuple[int, int]: return self.geometry[0] + self.half[0], self.geometry[1] + self.half[1]

    @property
    def half(self) -> tuple[int, int]:
        if self._half is None:
            self._half = self._geometry[2] // 2, self._geometry[3] // 2
        return self._half

    def setState(self, state_index:int = 0):        # BarSkin Recipients redraw their bars at varying lengths.
        self._skin.image(state_index, self._geometry[2 + self.vertical])
        super().setState(state_index)

    def mouseDrag(self, event=None):
        super().mouseDrag(event)
        self.parent.handleDragged()

    def _refresh(self, event=None):
        super()._refresh(event)
        if self._last_geometry[2:] != self._geometry[2:]: self._half = None