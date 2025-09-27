from time import time
import tkinter as tk

from .utilities import getLocalMouse, rectsOverlap
from .skinnable import ScrollSkin, BarSkin, Skin, ButtonPack, Measurable
from .widgets import RepeatButton, TroughButton, LoneDrag, Background


class Scrollable(Measurable, tk.Frame):
    def __init__(self, parent, width:int, height:int, scroll_skin:ScrollSkin, skin:Skin = None, **kwargs):
        Measurable.__init__(self, width=width, height=height)
        tk.Frame.__init__(self, parent, width=width, height=height, **kwargs)
        self.bind("<Configure>", self._refresh)

        """ ==OPTIONS==
            smooth_rate is subject to 'magic numbers' due to OS throttling. 15 is excellent on Windows. """
        self.smooth_rate, self.page_scale, self.line_size = 15, [0.95, 0.9], [18, 18]
        self.dominant_axis = 1

        self._scroll_skin = scroll_skin
        v_breadth, h_breadth = self._scroll_skin.vertical.breadth, self._scroll_skin.horizontal.breadth

        self._frame = ScrollFrame(self, width, height, skin)
        self._frame.place(x=0, y=0)
        self.bind_all("<MouseWheel>", self.scrollByWheel, "+")

        # Place the scrollbars, spawning them offscreen, so they only appear if desired.
        self._v_bar = VerticalScrollbar(self, v_breadth, height, self._scroll_skin.vertical, None,
                                         self._scroll_skin.button, v_breadth)
        self._v_bar.place(x=width, y=0)

        self._h_bar = HorizontalScrollbar(self, width - v_breadth, h_breadth, self._scroll_skin.horizontal, None,
                                          self._scroll_skin.button, h_breadth)
        self._h_bar.place(x=0, y=height)

        self._bars = (self._h_bar, self._v_bar)

        self._page_size = [None, None]
        self._scrollwheel_axis, self._scrollwheel_percent, self._scrollwheel_duration = 1, 0.4, 150

        # Scroll Defaults (based on 17ms (~60fps) animation rates.
        self.setPageScroll(180, 300)
        self.setLineScroll(150, 0)
        self.setWheelScroll(150, .4, True)

    @property
    def skin(self): return self._frame.skin
    @property
    def frame(self): return self._frame
    @property
    def plate_geometry(self): return self._frame.plate_geometry
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

    def setPageScroll(self, delay:int = None, init_delay:int = None):
        self._v_bar.setPageScrollDelay(delay, init_delay)
        self._h_bar.setPageScrollDelay(delay, init_delay)
    def setLineScroll(self, delay:int = None, init_delay:int = None):
        self._v_bar.setLineScrollDelay(delay, init_delay)
        self._h_bar.setLineScrollDelay(delay, init_delay)
    def setWheelScroll(self, smooth_duration:int, scroll_amount:float = 1.0, vertical:bool = None):
        self._scrollwheel_duration, self._scrollwheel_percent = smooth_duration, scroll_amount
        if vertical is not None: self._scrollwheel_axis = vertical

    def hide(self, bar):
        bar_geo = list(bar.geometry)

        # If bar is visible... (needs hidden)
        if rectsOverlap((0, 0, *self.size), bar_geo):
            o, o1 = bar.orientation

            # Move the scrollbar just outside the drawable area.
            bar_geo = list(bar_geo)
            bar_geo[o1] = self.size[o1]
            self._bars[o].place_configure(x=bar_geo[0], y=bar_geo[1])

            # Expand parent's scroll frame to occupy the new empty space.
            frame_size = list(self._frame.size)
            frame_size[o1] = bar_geo[o1]
            self._frame.place_configure(width=frame_size[0], height=frame_size[1])

            # Resize the non-dominant bar depending on presence of dominant bar.
            self._applyDominance()

    def show(self, bar):
        bar_geo = list(bar.geometry)
        area_geo = (0, 0, *self.size)

        # If bar is hidden... (needs shown)
        if not rectsOverlap(area_geo, bar_geo):
            o, o1 = bar.orientation
            o3 = o1+2

            # Move scrollbar into position.
            bar_geo[o] = 0
            bar_geo[o1] = area_geo[o3] - bar_geo[o3]
            self._bars[o].place_configure(x=bar_geo[0], y=bar_geo[1])

            # Contract scroll frame to not overlap with the bar.
            frame_size = list(self._frame.size)
            frame_size[o1] = bar_geo[o1]
            self.frame.place_configure(width=frame_size[0], height=frame_size[1])

            # Resize the non-dominant bar depending on presence of dominant bar.
            self._applyDominance()

    def _applyDominance(self):
        h_bar, v_bar = self._bars
        h_visible = rectsOverlap((0,0,*self.size), h_bar.geometry)
        v_visible = rectsOverlap((0,0,*self.size), v_bar.geometry)

        if h_visible and v_visible:
            if self.dominant_axis == 0:     # horizontal dominates
                v_bar.resize(self.size[1] - h_bar.geometry[3])
            else:                           # vertical dominates
                h_bar.resize(self.size[0] - v_bar.geometry[2])
        elif h_visible:
            h_bar.resize(self.size[0])
        elif v_visible:
            v_bar.resize(self.size[1])

    def plateResized(self, size_per:tuple[int,int], location_per:tuple[int, int]):
        self._page_size = [None, None]

        # Hide/Show and Enable/Disable bars, as requested. 0=hide; 1=show; 2=auto (show if needed)
        for i in range(2):
            bar = self._bars[i]
            if bar.mode == 0: self.hide(bar)
            elif bar.mode == 1:
                self.show(bar)
                if size_per[i] < 1: bar.enable()
                else:               bar.disable()
            elif bar.mode == 2:
                if size_per[i] < 1:
                        self.show(bar)
                        bar.enable()
                else:   self.hide(bar)

            bar.recalcHandle(size_per[i], location_per[i])

    def pageSize(self, axis:int) -> int:
        if self._page_size[axis] is None:
            self._page_size[axis] = int(self._frame.size[axis] * self.page_scale[axis])
        return self._page_size[axis]

    def scrollByDelta(self, delta_x:int, delta_y:int, move_handles:bool = True):
        self._movePlate(delta_x, delta_y, move_handles)

    def scrollByDest(self, dest_x:int|None, dest_y:int|None, move_handles:bool = True):
        if dest_x is not None or dest_y is not None:
            # Convert to delta and clamp to scroll range.
            px, py, = self._frame.plate_geometry[:2]
            delta_x = dest_x - px if dest_x is not None else 0
            delta_y = dest_y - py if dest_y is not None else 0

            self._movePlate(delta_x, delta_y, move_handles)

    def scrollByPercent(self, x_per: float | None, y_per: float | None, move_handles:bool = True):
        if x_per is not None or y_per is not None:
            px, py = self._frame.plate_geometry[:2]
            rx, ry = self._frame.scroll_range

            # Convert percentages to pixels and then to the delta of change between them.
            x = int(x_per * rx) if x_per is not None else px
            y = int(y_per * ry) if y_per is not None else py
            delta_x, delta_y = x - px, y - py

            self._movePlate(delta_x, delta_y, move_handles)

    # If mouse is within the boundaries of the Scrollable when wheeled, pass event to ScrollBar for animating.
    def scrollByWheel(self, event):
        if getLocalMouse(self)[2]:
            delta = int(event.delta * self._scrollwheel_percent)        # Adjust rate of change.
            self._bars[self._scrollwheel_axis].mouseWheeled(delta, self._scrollwheel_duration)

    def _movePlate(self, delta_x:int, delta_y:int, move_handles:bool = True):
        if delta_x or delta_y:
            px, py, pw, ph = self._frame.plate_geometry
            sw, sh = self._frame.scroll_range

            # Conform deltas to land within scroll_range
            if delta_x:
                if px+delta_x < sw:     delta_x = sw-px
                elif px+delta_x > 0:    delta_x = -px
            if delta_y:
                if py+delta_y < sh:     delta_y = sh-py
                elif py+delta_y > 0:    delta_y = -py

            # If there's a non-zero delta after conforming...
            if delta_x or delta_y:
                # Move "plate" (imaginary)
                px, py = px + delta_x, py + delta_y
                self._frame.plate_geometry = (px, py, pw, ph)

                # Move children
                fw, fh = self._frame.geometry[2:]
                for child in self._frame.getChildren():
                    cx, cy, cw, ch = child.geometry
                    new_x, new_y = cx+delta_x, cy+delta_y

                    # Is the child visible now -- before we apply the movement?
                    live = rectsOverlap((cx, cy, cw, ch), (0, 0, fw, fh))
                    if not live: new_x, new_y = px+child.scroll_xy[0], py+child.scroll_xy[1]

                    # If the child will be visible after the requested scroll...
                    if rectsOverlap((new_x, new_y, cw, ch), (0, 0, fw, fh)):
                        child.place_configure(x=new_x, y=new_y)

                    # If the child is exiting the screen.
                    elif live:
                        child.scroll_xy = -px + new_x, -py + new_y
                        child._geometry = (0, -ch, cw, ch)
                        child.place_configure(x=0, y=-ch, skip=True)

                # Move scroll handles to match new plate position, if requested.
                if move_handles:
                    if sw: self.h_bar.moveHandle(px / sw)
                    if sh: self.v_bar.moveHandle(py / sh)


class ScrollFrame(Background):
    def __init__(self, parent:Scrollable, width:int, height:int, skin=None, **kwargs):
        super().__init__(parent, width, height, skin, **kwargs)
        self._plate_geometry = (0, 0, 0, 0)
        self._scroll_range = None

    @property
    def plate_geometry(self): return self._plate_geometry
    @plate_geometry.setter
    def plate_geometry(self, xywh:tuple[int,int,int,int]) -> None:
        last_plate = self._plate_geometry
        self._plate_geometry = tuple(xywh)
        if last_plate[2:] != self.plate_geometry[2:]:
            self._scroll_range = None
            rw, rh = self.scroll_range
            rw, rh = -rw, -rh
            size = self.width / self._plate_geometry[2] if rw else 1.0, self.height / self._plate_geometry[3] if rh else 1.0
            loc = self.x / rw if rw else 0.0, self.y / rh if rh else 0.0

            self.parent.plateResized(size, loc)

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
            self.plate_geometry = (*self._plate_geometry[:2], self.winfo_reqwidth(), self.winfo_reqheight())
        else:
            # If .place()'d this works
            cxw, cyh = (max(cx + cw, self._plate_geometry[2]), max(cy + ch, self._plate_geometry[3]))
            self.plate_geometry = (*self._plate_geometry[:2], cxw, cyh)

        # TODO: When and where we recalculate plate_geometry, it must be by the children's scroll_xy.
        child.scroll_xy = cx, cy

    def mouseWheel(self, event=None):
        self.parent.scrollByWheel(event)
        super().mouseWheel(event)

    def _refresh(self, event=None):
        super()._refresh(event)
        self._scroll_range = None

        self.parent._page_size = [None, None]


class ScrollBar(Background):
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
        self._animate = [0.0, 0, 1.0, 0, 0.0, None]     # start, origin, progress, destination, end, directionality

        # Consolidate whiny IDE complaints about undefined variables here, instead of throughout the class.
        self._directions, self._orientation = self._directions, self._orientation

        # State helpers.
        self.mode, self._enabled = 2, True
        self._scheduled_drag, self._next_drag = None, 0.0

    @property
    def directions(self): return self._directions
    @property
    def orientation(self): return self._orientation

    @property
    def enabled(self): return self._enabled
    def enable(self):
        if not self._enabled:
            self._trough.enable()
            if self.button1: self.button1.enable()
            if self.button2: self.button2.enable()
            self._enabled = True
    def disable(self):
        if self._enabled:
            self._trough.disable()
            if self.button1: self.button1.disable()
            if self.button2: self.button2.disable()
            self._enabled = False

    def setPageScrollDelay(self, delay:int = None, init_delay:int = None):
        if delay is not None: self._trough.delay = delay
        if init_delay is not None: self._trough.init_delay = self._trough.delay + init_delay

    def setLineScrollDelay(self, delay:int = None, init_delay:int = None):
        if self.button1 is not None or self.button2 is not None:
            if delay is not None:
                if self.button1 is not None: self.button1.delay = delay
                if self.button2 is not None: self.button2.delay = delay
            if init_delay is not None:
                if self.button1 is not None: self.button1.init_delay = self.button1.delay + init_delay
                if self.button2 is not None: self.button2.init_delay = self.button2.delay + init_delay

    def resize(self, length:int):
        o = self.vertical
        button_area = 0

        # Calculate button area for trough displacement
        if self.button1 is not None: button_area += self.button1.size[o]
        if self.button2 is not None: button_area += self.button2.size[o]
        length = max(length, 3 + button_area)

        # Expand the Scrollbar itself
        bar_size = list(self.size)
        bar_size[o] = length
        self.place_configure(width=bar_size[0], height=bar_size[1])

        tl = length - button_area
        trough_geo = list(self._trough.geometry)
        o2 = o+2

        # Resize the trough
        if tl != trough_geo[o2]:
            self._trough.resize(tl)

            # Move button2
            if self.button2 is not None:
                b2_loc = [0,0]
                b2_loc[o] = trough_geo[o] + tl
                self.button2.place_configure(x=b2_loc[0], y=b2_loc[1])

    @property
    def vertical(self): return bool(self._orientation[0])

    def handleDragged(self):
        p = self._handle.geometry[self.vertical]
        s = self._trough.scroll_range[self.vertical]

        per = [None, None]
        per[self.vertical] = p/-s if s else 0

        # Restrict the frequency of drawing scroll changes to some factor of the parent's smooth rate.
        now = time()
        remains = round((self._next_drag - now) * 1000)
        if remains > 0:
            if self._scheduled_drag is not None: self.after_cancel(self._scheduled_drag)
            self._scheduled_drag = self.after(remains, self._call_drag, per)
        else:
            self._call_drag(per, now)

    def _call_drag(self, per:list, now:float = None) -> None:
        self.parent.scrollByPercent(*per, False)
        self._scheduled_drag = None
        self._next_drag = (now or time()) + (self.parent.smooth_rate * 2 / 1000)    # Half the smooth_rate.

    def moveHandle(self, per:float):
        o = self.vertical
        move = list(self._handle.geometry[:2])
        move[o] = int(per * -self._trough.scroll_range[o])

        self._handle.move(*move)

    def troughClicked(self, click_x:int, click_y:int, duration:int):
        o = self.vertical
        click = (click_x, click_y)
        direction = 1 if click[o] < self._handle.middle[o] else -1

        # Instant scrolling goes straight to the point that was clicked.
        if self.instant_scroll:
            handle_px = click[o] - (self._handle.geometry[o+2] // 2)
            per = handle_px / self._trough.scroll_range[o]
            destination = -(self.parent.frame.plate_geometry[o] + int(per * self.parent.frame.scroll_range[o]))

        # Page scrolling progresses in percentage increments of the scroll frame. (ex: 90% of the viewable area)
        else: destination = self.parent.pageSize(o) * direction

        # Smooth scrolling animates travel to the destination by linear interpolation and deltaTime.
        if self.smooth_scroll: self._beginAnimating(destination, duration)

        # Simple scrolling goes directly to the destination requested.
        else:
            move = [0, 0]
            move[o] = destination
            self.parent.scrollByDelta(*move)

    def buttonClicked(self, direction:int):
        if self.smooth_scroll:
            self._beginAnimating(self.parent.line_size[self.vertical] * direction, self.button1.delay)
        else:
            move = [0, 0]
            move[self.vertical] = self.parent.line_size[self.vertical] * direction
            self.parent.scrollByDelta(*move)

    def mouseWheeled(self, delta:int, duration:int):
        if self.smooth_scroll:
            self._beginAnimating(delta, duration)
        else:
            move = [0, 0]
            move[self.vertical] = delta
            self.parent.scrollByDelta(*move)

    def recalcHandle(self, size_per:float, location_per:float):
        o, o1 = self._orientation
        o2 = o+2
        t, t1 = self._trough.geometry[o2], self._trough.geometry[o1+2]

        geo = list(self._handle.geometry)
        geo[o2] = max(t1, min(t, int(size_per * t)))    # Sets handle size (clamped)
        tr = max(t - geo[o2], 0)                        # True trough scroll range  (trough - handle)
        geo[o] = int(location_per * tr)                 # Repositions handle relative to changes

        self._handle.place_configure(x=geo[0], y=geo[1], width=geo[2], height=geo[3])

    def _beginAnimating(self, delta:int, duration:int):
        origin = self.parent.frame.plate_geometry[self.vertical]

        # If new animation, set origin and begin animating.
        if self._animate[2] == 1:
            end = origin + delta
            self.after_idle(self._animationStep)
        # If animation already active, sum delta to existing end, unless directionality has changed.
        else:
            if self._animate[5] == (delta > 0):
                end = self._animate[3] + delta
            else: end =  origin + delta

        self._animate = [time(), origin, 0.0, end, duration / 1000, delta > 0]

    def _animationStep(self):
        self._animate[2] = min(1.0, (time() - self._animate[0]) / self._animate[4])
        dest = [None, None]

        if self._animate[2] < 1:
            dest[self.vertical] = round(self._animate[1] + (self._animate[3] - self._animate[1]) * self._animate[2])
            self.parent.scrollByDest(*dest)
            self.after(self.parent.smooth_rate, self._animationStep)
        else:
            dest[self.vertical] = self._animate[3]
            self.parent.scrollByDest(*dest)

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
        self.button1 = RepeatButton(self, bskin1, lambda: self.buttonClicked(1), width=b1wh[0], height=b1wh[1])
        self.button2 = RepeatButton(self, bskin2, lambda: self.buttonClicked(-1), width=b2wh[0], height=b2wh[1])
        self.button1.place(x=0, y=0)
        self.button2.place(x=b2x, y=b2y)

        return tx, ty, tw, th


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


class ScrollTrough(TroughButton):
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

    def resize(self, length:int):
        size = list(self.size)
        size[self._vertical] = length
        self.place_configure(width=size[0], height=size[1])

    def handleDragged(self): self.parent.handleDragged()

    def setState(self, state_index:int = 0):
        self._skin.image(state_index, self._geometry[2 + self._vertical])       # Update skin's length.
        super().setState(state_index)

    def clicked(self, event):
        self._clicking = True
        self.setState(2)
        self.parent.troughClicked(event.x, event.y, self.delay)     # Pass click event to parent ScrollBar for handling.
        self.after(self.init_delay, self._keepClicking)

    def registerChild(self, child):
        super().registerChild(child)
        if isinstance(child, ScrollHandle): self._handle = child

    def _refresh(self, event=None):
        super()._refresh(event)
        self._scroll_range = None

    def _keepClicking(self):
        if self._clicking:
            if self._handle:
                mx, my, _ = getLocalMouse(self)
                hx, hy, hw, hh = self._handle.geometry
                if self._vertical:
                    if not hy < my < hy+hh: self.parent.troughClicked(*getLocalMouse(self)[:2], self.delay)
                elif   not hx < mx < hx+hw: self.parent.troughClicked(*getLocalMouse(self)[:2], self.delay)

            self.after(self.delay, self._keepClicking)


class ScrollHandle(LoneDrag):
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
        self.update_idletasks()
        self.parent.handleDragged()

    def _refresh(self, event=None):
        super()._refresh(event)
        if self._last_geometry[2:] != self._geometry[2:]: self._half = None