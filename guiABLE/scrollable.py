from time import time
import tkinter as tk

from .utilities import getLocalMouse, rectsOverlap
from .skinnable import ScrollSkin, BarSkin, Skin, ButtonPack, Measurable, Placeable
from .widgetables import Siblingable, Troughable, LinearAnimator, CoordinateSpace
from .widgets import RepeatButton, TroughButton, LoneDrag, Background
from .uimage import UImage


class Scrollable(Measurable, Siblingable, tk.Frame):
    def __init__(self, parent, width:int, height:int, scroll_skin:ScrollSkin,
                 bg_color:str="#6B6B6B", **kwargs):
        kwargs["bg"] = bg_color
        super().__init__(parent, width=width, height=height, **kwargs)

        # Registering as a sibling allows Scrollable to be considered in sibling culling.
        self.scroll_skin = scroll_skin
        self.bind("<Configure>", self._refresh)

        """ ==OPTIONS==
            smooth_rate is subject to 'magic numbers' due to OS throttling. 15 is excellent on Windows. """
        self.smooth_rate, self.page_scale, self.line_size = 15, [0.95, 0.9], [18, 18]
        self.dominant_axis = 1

        self._scroll_skin = scroll_skin
        v_breadth, h_breadth = self._scroll_skin.vertical.breadth, self._scroll_skin.horizontal.breadth

        # ScrollFrame is the clipping viewport. ScrollPlate is the translated local coordinate space within it.
        self._frame = ScrollFrame(self, bg_color, width=width, height=height)
        self._frame.place(x=0, y=0)
        self._plate = ScrollPlate(self._frame, self, bg_color, width=width, height=height)
        self._plate.place(x=0, y=0)

        self.bind_all("<MouseWheel>", self.scrollByWheel, "+")

        # Place the scrollbars offscreen, so they only appear if desired.
        self._v_bar = VerticalScrollbar(self, self._scroll_skin.vertical, None,
                                        self._scroll_skin.button, v_breadth, width=v_breadth, height=height)
        self._v_bar.place(x=width, y=0)

        self._h_bar = HorizontalScrollbar(self, self._scroll_skin.horizontal, None,
                                          self._scroll_skin.button, h_breadth, width=width, height=h_breadth)
        self._h_bar.place(x=0, y=height)

        self._bars = (self._h_bar, self._v_bar)
        self._page_size = [None, None]
        self._scrollwheel_axis, self._scrollwheel_percent, self._scrollwheel_duration = 1, 0.4, 130
        self._layout_lock = False

        # Scroll Defaults (based on 17ms (~60fps) animation rates.
        self.setPageScroll(150, 300)
        self.setLineScroll(130, 0)
        self.setWheelScroll(130, .4, True)

        self._syncLayout()

    # frame remains as a compatibility alias for existing code that attaches content there.
    @property
    def frame(self): return self._plate
    @property
    def plate(self): return self._plate
    @property
    def viewport(self): return self._frame
    @property
    def plate_geometry(self): return self._plate.geometry
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

    # Including these methods allows Scrollable to be considered in sibling culling.
    @staticmethod
    def isOpaque(): return True
    def redraw(self): pass
    def zImage(self): return self._frame.skin.image()
    def setState(self, index:int = 0): pass

    def pageSize(self, axis:int) -> int:
        if self._page_size[axis] is None:
            self._page_size[axis] = int(self._frame.size[axis] * self.page_scale[axis])
        return self._page_size[axis]

    def scrollByDelta(self, delta_x:int, delta_y:int): self._movePlate(delta_x, delta_y)

    def scrollByDest(self, dest_x:int|None, dest_y:int|None):
        if dest_x is not None or dest_y is not None:
            px, py = self._plate.location
            delta_x = dest_x - px if dest_x is not None else 0
            delta_y = dest_y - py if dest_y is not None else 0
            self._movePlate(delta_x, delta_y)

    def scrollByPercent(self, x_per:float|None, y_per:float|None):
        if x_per is not None or y_per is not None:
            px, py = self._plate.location
            rx, ry = self._plate.scroll_range

            x = int(x_per * rx) if x_per is not None else px
            y = int(y_per * ry) if y_per is not None else py
            self._movePlate(x - px, y - py)

    # If mouse is within the boundaries of the Scrollable when wheeled, pass event to ScrollBar for animating.
    def scrollByWheel(self, event):
        if getLocalMouse(self)[2]:
            delta = int(event.delta * self._scrollwheel_percent)        # Adjust rate of change.
            self._bars[self._scrollwheel_axis].mouseWheeled(delta, self._scrollwheel_duration)

    def _movePlate(self, delta_x:int, delta_y:int):
        if delta_x or delta_y:
            px, py = self._plate.location
            sw, sh = self._plate.scroll_range

            if delta_x:
                if px + delta_x < sw:  delta_x = sw - px
                elif px + delta_x > 0: delta_x = -px
            if delta_y:
                if py + delta_y < sh:  delta_y = sh - py
                elif py + delta_y > 0: delta_y = -py

            if delta_x or delta_y:
                px, py = px + delta_x, py + delta_y
                self._plate.translate(px, py)

                if delta_x and sw and not self.h_bar.isHeld(): self.h_bar.moveHandle(px / sw)
                if delta_y and sh and not self.v_bar.isHeld(): self.v_bar.moveHandle(py / sh)

    def _contentChanged(self):
        if hasattr(self, "_bars"): self._syncLayout()

    def _syncLayout(self):
        if self._layout_lock or not hasattr(self, "_bars"): return
        self._layout_lock = True

        width, height = self.size
        content_w, content_h = self._plate.content_size
        h_breadth, v_breadth = self._h_bar.height, self._v_bar.width

        # Showing one bar changes the viewport and can make the other necessary, so settle until stable.
        h_visible, v_visible = self._h_bar.mode == 1, self._v_bar.mode == 1
        for _ in range(3):
            frame_w = max(1, width - (v_breadth if v_visible else 0))
            frame_h = max(1, height - (h_breadth if h_visible else 0))

            new_h = False if self._h_bar.mode == 0 else True if self._h_bar.mode == 1 else content_w > frame_w
            new_v = False if self._v_bar.mode == 0 else True if self._v_bar.mode == 1 else content_h > frame_h

            if (new_h, new_v) == (h_visible, v_visible): break
            h_visible, v_visible = new_h, new_v

        frame_w = max(1, width - (v_breadth if v_visible else 0))
        frame_h = max(1, height - (h_breadth if h_visible else 0))
        self._frame.resize(frame_w, frame_h)

        frame_changed = self._frame.size != (frame_w, frame_h)
        self._frame.resize(frame_w, frame_h)

        plate_w, plate_h = max(frame_w, content_w), max(frame_h, content_h)

        px, py = self._plate.location
        sw, sh = min(frame_w - plate_w, 0), min(frame_h - plate_h, 0)
        px, py = max(sw, min(0, px)), max(sh, min(0, py))

        plate_changed = self._plate.size != (plate_w, plate_h)
        self._plate.resizeAndMove(px, py, plate_w, plate_h)

        self._plate._syncVisible(frame_changed or plate_changed)

        # Place bars after viewport geometry is final.
        if h_visible:
            h_length = width - (v_breadth if v_visible and self.dominant_axis == 1 else 0)
            self._h_bar.resize(h_length)
            self._h_bar.place_configure(x=0, y=height - h_breadth)
        else:
            self._h_bar.place_configure(x=0, y=height)

        if v_visible:
            v_length = height - (h_breadth if h_visible and self.dominant_axis == 0 else 0)
            self._v_bar.resize(v_length)
            self._v_bar.place_configure(x=width - v_breadth, y=0)
        else:
            self._v_bar.place_configure(x=width, y=0)

        can_h_scroll, can_v_scroll = sw != 0, sh != 0
        if h_visible and can_h_scroll: self._h_bar.enable()
        else:                          self._h_bar.disable()
        if v_visible and can_v_scroll: self._v_bar.enable()
        else:                          self._v_bar.disable()

        h_size = frame_w / plate_w if can_h_scroll else 1.0
        v_size = frame_h / plate_h if can_v_scroll else 1.0
        self._h_bar.recalcHandle(h_size, px / sw if sw else 0.0)
        self._v_bar.recalcHandle(v_size, py / sh if sh else 0.0)

        self._page_size = [None, None]
        self._layout_lock = False

    def _refresh(self, event=None):
        last_size = self.size
        super()._refresh(event)
        if hasattr(self, "_bars") and self.size != last_size: self._syncLayout()


class ScrollFrame(CoordinateSpace, Background):
    def __init__(self, parent:Scrollable, bg_color:str, **kwargs):
        self._floor_color = bg_color
        width, height = kwargs.get("width", 1), kwargs.get("height", 1)
        super().__init__(parent, self._floorSkin(width, height), **kwargs)
        self.configure(bg=bg_color)

    def _floorSkin(self, width:int, height:int) -> Skin:
        skin = Skin(UImage(width=max(1, width), height=max(1, height)))
        skin.usesBgColors(True)
        skin.setBGColors(self._floor_color)
        return skin

    def resize(self, width:int, height:int):
        if self.size != (width, height):
            self.place_configure(width=width, height=height, implied=True, skip=True)
            self._scratch = UImage(width=width, height=height)
            self.setSkin(self._floorSkin(width, height), implied=True)
            self.redraw()


class ScrollPlate(CoordinateSpace, Placeable, tk.Frame):
    def __init__(self, parent:ScrollFrame, owner:Scrollable, bg_color:str, **kwargs):
        self._owner = owner
        self._content_size = (0, 0)
        self._visible_children = set()
        super().__init__(parent, bg=bg_color, highlightthickness=0, bd=0, **kwargs)

    @property
    def skin(self): return self.parent.skin
    @property
    def content_size(self): return self._content_size
    @property
    def scroll_range(self):
        return min(self.parent.width - self.width, 0), min(self.parent.height - self.height, 0)

    # Children render only where this translated space intersects the viewport.
    def childRenderArea(self) -> tuple[int,int,int,int]:
        return -self.x, -self.y, self.parent.width, self.parent.height

    # The floor Skin lives in viewport-space, not the potentially enormous plate-space.
    def childBackgroundPoint(self, x:int, y:int, width:int=0, height:int=0) -> tuple[int,int]:
        floor_w, floor_h = self.parent.size

        x += self.x
        y += self.y

        # The plate floor is uniform, so any same-sized region is visually equivalent.
        x = max(0, min(x, floor_w - width))
        y = max(0, min(y, floor_h - height))

        return x, y

    def registerChild(self, child):
        super().registerChild(child)
        self._measureContent()
        if rectsOverlap(child.geometry, self.childRenderArea()): self._visible_children.add(child)

    def dropChild(self, child):
        super().dropChild(child)
        self._visible_children.discard(child)
        self._measureContent()

    def childChanged(self, child):
        if rectsOverlap(child.geometry, self.childRenderArea()): self._visible_children.add(child)
        else: self._visible_children.discard(child)
        self._measureContent()

    def resizeAndMove(self, x:int, y:int, width:int, height:int):
        moved = (x, y) != self.location
        resized = (width, height) != self.size

        if moved or resized:
            self.place_configure(x=x, y=y, width=width, height=height, implied=True, skip=True)
            if moved: self.spaceTranslated()
            if resized: self.spaceResized()

    def spaceTranslated(self): self._syncVisible()
    def spaceResized(self): self._syncVisible()

    def _syncVisible(self, redraw:bool=False):
        visible = {child for child in self.getChildren() if rectsOverlap(child.geometry, self.childRenderArea())}

        # Newly exposed widgets must wait until Tk has physically realized the plate translation.
        entering = visible - self._visible_children
        for child in visible if redraw else entering:
            child.after_idle(child.redraw, True)

        self._visible_children = visible

    def _measureContent(self):
        width = height = 0
        for child in self.getChildren():
            width = max(width, child.x + child.width)
            height = max(height, child.y + child.height)

        content_size = width, height
        if content_size != self._content_size:
            self._content_size = content_size
            self._owner._contentChanged()


class ScrollButton(RepeatButton):
    def __init__(self, parent, direction:int, *args, **kwargs):
        self._direction = direction
        super().__init__(parent, function=lambda: parent.buttonClicked(direction), *args, **kwargs)

    def _keepClicking(self):
        if self._clicking:
            if self.parent.smooth_scroll:
                self.parent.buttonHeld(self._direction)
            else:
                super()._keepClicking()

    def mouseUp(self, event):
        self.parent.buttonReleased()
        super().mouseUp(event)


class ScrollBar(LinearAnimator, Background):
    def __init__(self, parent:Scrollable, bar_skin:BarSkin|None = None,
                 handle_skin:BarSkin|None = None, button_pack:ButtonPack|None = None, breadth:int = 0, **kwargs):
        self._bar_skin = bar_skin or BarSkin()
        self._buttons = button_pack

        super().__init__(parent, **kwargs)

        width, height = kwargs["width"], kwargs["height"]
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
        self.drag_duration = 350

        # Consolidate whiny IDE complaints about undefined variables here, instead of throughout the class.
        self._directions, self._orientation = self._directions, self._orientation

        # State helpers.
        self.mode, self._enabled = 2, True
        self._continuous_scroll = False

    @property
    def directions(self): return self._directions
    @property
    def orientation(self): return self._orientation
    @property
    def vertical(self): return bool(self._orientation[0])

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

    def handleDragged(self):
        o = self.vertical
        percent = self._trough.getPercent()

        if self.smooth_scroll:
            destination = round(percent * self.parent.plate.scroll_range[o])
            origin = self.parent.plate.geometry[o]

            if not self.retargetAnimation(destination, self.drag_duration, origin):
                self.animate(origin, destination, self.drag_duration,
                             self._moveAnimated, self.parent.smooth_rate)
        else:
            per = [None, None]
            per[o] = percent
            self.parent.scrollByPercent(*per)

    def handleReleased(self):
        self.stopAnimation()

        per = [None, None]
        per[self.vertical] = self._trough.getPercent()
        self.parent.scrollByPercent(*per)

    def moveHandle(self, per:float): self._trough.setPercent(per)

    def troughClicked(self, button_clicked: int, click_x:int, click_y:int, duration:int):
        o = self.vertical
        click = (click_x, click_y)
        direction = 1 if click[o] < self._handle.middle[o] else -1

        # Instant scrolling goes straight to the point that was clicked.
        if self.instant_scroll and button_clicked == 1 or not self.instant_scroll and button_clicked == 2:
            per = self._trough.percentAt(click_x, click_y)
            destination = int(per * self.parent.plate.scroll_range[o]) - self.parent.plate.geometry[o]

        # Page scrolling progresses in percentage increments of the scroll frame. (ex: 90% of the viewable area)
        else: destination = self.parent.pageSize(o) * direction

        # Smooth scrolling animates travel to the destination by linear interpolation and deltaTime.
        if self.smooth_scroll: self._beginAnimating(destination, duration)

        # Simple scrolling goes directly to the destination requested.
        else:
            move = [0, 0]
            move[o] = destination
            self.parent.scrollByDelta(*move)

    def isHeld(self): return self._trough.isHeld()

    def buttonClicked(self, direction:int):
        if self.smooth_scroll:
            self._beginAnimating(self.parent.line_size[self.vertical] * direction, self.button1.delay)
        else:
            move = [0, 0]
            move[self.vertical] = self.parent.line_size[self.vertical] * direction
            self.parent.scrollByDelta(*move)

    def buttonHeld(self, direction:int):
        o = self.vertical
        origin = self.parent.plate.geometry[o]
        destination = self.parent.plate.scroll_range[o] if direction < 0 else 0

        distance = abs(destination - origin)
        if not distance: return

        pixels_per_ms = self.parent.line_size[o] / self.button1.delay
        duration = round(distance / pixels_per_ms)

        self._continuous_scroll = True
        self.animate(origin, destination, duration, self._moveAnimated, self.parent.smooth_rate)

    def buttonReleased(self):
        if self._continuous_scroll:
            self.stopAnimation()
            self._continuous_scroll = False

    def mouseWheeled(self, delta:int, duration:int):
        o = self.vertical
        if self.smooth_scroll:
            origin = self.parent.plate.geometry[o]

            if self._animation is not None:
                destination = self._animation[2] + delta
            else:
                destination = origin + delta

            destination = max(self.parent.plate.scroll_range[o], min(0, destination))

            if not self.retargetAnimation(destination, duration, origin):
                self.animate(origin, destination, duration, self._moveAnimated, self.parent.smooth_rate)

        else:
            move = [0, 0]
            move[o] = delta
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
        self._continuous_scroll = False
        o = self.vertical
        origin = self.parent.plate.geometry[o]
        scroll_range = self.parent.plate.scroll_range[o]

        if self._animation is not None:
            old_origin, old_destination = self._animation[1], self._animation[2]
            same_direction = (old_destination > old_origin) == (delta > 0)

            if same_direction:
                destination = max(scroll_range, min(0, old_destination + delta))
                extension = destination - old_destination

                if extension:
                    extension_duration = round(duration * abs(extension / delta))
                    self.extendAnimation(extension, extension_duration)

                return

        destination = max(scroll_range, min(0, origin + delta))
        self.animate(origin, destination, duration, self._moveAnimated, self.parent.smooth_rate)

    def _moveAnimated(self, destination:float):
        dest = [None, None]
        dest[self.vertical] = round(destination)
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
        self.button1 = ScrollButton(self, 1, skin=bskin1, width=b1wh[0], height=b1wh[1])
        self.button2 = ScrollButton(self, -1, skin=bskin2, width=b2wh[0], height=b2wh[1])
        self.button1.place(x=0, y=0)
        self.button2.place(x=b2x, y=b2y)

        return tx, ty, tw, th


class VerticalScrollbar(ScrollBar):
    def __init__(self, parent, bar_skin:BarSkin|None = None, handle_skin:BarSkin|None = None,
                 button_pack:ButtonPack|None = None, breadth:int = 0, **kwargs):
        self._directions = 0, 2
        self._orientation = 1, 0
        super().__init__(parent, bar_skin, handle_skin, button_pack, breadth, **kwargs)


class HorizontalScrollbar(ScrollBar):
    def __init__(self, parent, bar_skin:BarSkin|None = None, handle_skin:BarSkin|None = None,
                 button_pack:ButtonPack|None = None, breadth:int = 0, **kwargs):
        self._directions = 3, 1
        self._orientation = 0, 1
        super().__init__(parent, bar_skin, handle_skin, button_pack, breadth, **kwargs)


class ScrollTrough(Troughable, TroughButton):
    def __init__(self, parent:ScrollBar, skin:BarSkin = None, **kwargs):
        self._vertical = parent.vertical
        self._default_skin = BarSkin()
        super().__init__(parent, skin=skin, vertical=self._vertical, **kwargs)

    def enable(self):
        super().enable()
        self.bind("<Button-2>", self.clicked)
        self.bind("<ButtonRelease-2>", self.mouseUp)
    def disable(self):
        super().disable()
        self.unbind("<Button-2>")
        self.unbind("<ButtonRelease-2>")

    def resize(self, length:int):
        size = list(self.size)
        size[self._vertical] = length
        self.place_configure(width=size[0], height=size[1])

    def handleDragged(self): self.parent.handleDragged()
    def handleReleased(self): self.parent.handleReleased()

    def setState(self, state_index:int = 0):
        self._skin.image(state_index, self._geometry[2 + self._vertical])       # Update skin's length.
        super().setState(state_index)

    def clicked(self, event):
        self._clicking = event.num
        self.setState(2)
        self.parent.troughClicked(event.num, event.x, event.y, self.delay)      # Pass to parent ScrollBar for handling.
        if self._after: self.after_cancel(self._after)
        self._after = self.after(self.init_delay, self._keepClicking)

    def _keepClicking(self):
        if self._clicking:
            if self._handle:
                mx, my, _ = getLocalMouse(self)
                hx, hy, hw, hh = self._handle.geometry
                if self._vertical:
                    if not hy < my < hy+hh: self.parent.troughClicked(self._clicking, *getLocalMouse(self)[:2], self.delay)
                elif   not hx < mx < hx+hw: self.parent.troughClicked(self._clicking, *getLocalMouse(self)[:2], self.delay)

            self._after = self.after(self.delay, self._keepClicking)


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

    def mouseUp(self, event):
        super().mouseUp(event)
        self.parent.handleReleased()

    def _refresh(self, event=None):
        super()._refresh(event)
        if self._last_geometry[2:] != self._geometry[2:]: self._half = None