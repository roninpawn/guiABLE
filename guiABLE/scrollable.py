import tkinter as tk

from .utilities import getLocalMouse, rectsOverlap
from .skinnable import ScrollSkin, ThreeSliceSkin, Skin, ButtonPack, Measurable, Placeable
from .widgetables import Siblingable, Troughable, LinearAnimator, CoordinateSpace
from .widgets import RepeatButton, TroughButton, LoneDrag, Background
from .uimage import UImage


class Scrollable:
    DISABLED = 0
    ENABLED = 1
    AUTO = 2

    def __init__(self, *args, scroll_skin:ScrollSkin, horizontal_scroll:int=AUTO, vertical_scroll:int=AUTO, **kwargs):
        self.scroll_skin = self._scroll_skin = scroll_skin
        self._scroll_visibility = [horizontal_scroll, vertical_scroll]

        self.smooth_rate, self.page_scale, self.line_size = 15, [0.95, 0.9], [18, 18]
        self.dominant_axis = 1

        self._bars = ()
        self._page_size = [None, None]
        self._scrollwheel_axis, self._scrollwheel_percent, self._scrollwheel_duration = 1, 0.4, 130
        self._layout_lock = False
        self._resolved_visibility = [False, False]

        super().__init__(*args, **kwargs)

    @property
    def v_bar(self): return self._v_bar

    @property
    def h_bar(self): return self._h_bar

    @classmethod
    def _normalizeScrollMode(cls, mode:int) -> int:
        if mode not in (cls.DISABLED, cls.ENABLED, cls.AUTO):
            raise ValueError("scroll mode must be DISABLED, ENABLED, or AUTO")
        return mode

    def _spawnScrollbars(self):
        width, height = self.size
        v_breadth = self._scroll_skin.vertical.breadth
        h_breadth = self._scroll_skin.horizontal.breadth

        self._v_bar = VerticalScrollbar(self, self._scroll_skin.vertical, None, self._scroll_skin.button,
                                        v_breadth, width=v_breadth, height=height)
        self._v_bar.place(x=width, y=0)

        self._h_bar = HorizontalScrollbar(self, self._scroll_skin.horizontal, None, self._scroll_skin.button,
                                          h_breadth, width=width, height=h_breadth)
        self._h_bar.place(x=0, y=height)
        self._bars = (self._h_bar, self._v_bar)

        self._h_bar._visibility = self._normalizeScrollMode(self._scroll_visibility[0])
        self._v_bar._visibility = self._normalizeScrollMode(self._scroll_visibility[1])

        self.bind_all("<MouseWheel>", self.scrollByWheel, "+")

        self.setPageScroll(150, 300)
        self.setLineScroll(130, 300)
        self.setWheelScroll(130, .4, True)

    def getScrollbarVisibility(self) -> tuple[int,int]: return self._h_bar.getVisibility(), self._v_bar.getVisibility()
    def getScrollbarState(self) -> tuple[int,int]: return self._h_bar.getStateMode(), self._v_bar.getStateMode()

    def getInstantPage(self) -> tuple[bool,bool]: return self._h_bar.instant_page, self._v_bar.instant_page
    def setInstantPage(self, instant:bool): self._h_bar.instant_page = self._v_bar.instant_page = instant

    def getWheelSmoothing(self) -> tuple[bool,bool]: return self.h_bar.smooth_wheel, self.v_bar.smooth_wheel
    def getDragSmoothing(self) -> tuple[bool,bool]: return self.h_bar.smooth_drag, self.v_bar.smooth_drag
    def getLineSmoothing(self) -> tuple[tuple[bool,bool],tuple[bool,bool]]:
        return ((self.h_bar.button1.smooth, self.h_bar.button2.smooth),
                (self.v_bar.button1.smooth, self.v_bar.button2.smooth))
    def getPageSmoothing(self) -> tuple[bool,bool]: return self.h_bar.smooth_page, self.v_bar.smooth_page

    def setScrollbarVisibility(self, horizontal:int=None, vertical:int=None):
        if horizontal is not None: self._h_bar._setVisibility(horizontal)
        if vertical is not None: self._v_bar._setVisibility(vertical)
        self._syncLayout()
    def setScrollbarState(self, horizontal:int=None, vertical:int=None):
        if horizontal is not None: self._h_bar._setStateMode(horizontal)
        if vertical is not None: self._v_bar._setStateMode(vertical)
        self._syncLayout()

    def setWheelSmoothing(self, smooth:bool): self.h_bar.smooth_wheel = self.v_bar.smooth_wheel = smooth
    def setDragSmoothing(self, smooth:bool): self.h_bar.smooth_drag = self.v_bar.smooth_drag = smooth
    def setPageSmoothing(self, smooth:bool): self.h_bar.smooth_page = self.v_bar.smooth_page = smooth

    def setLineSmoothing(self, smooth:bool):
        for bar in self._bars:
            if bar.button1: bar.button1.smooth = smooth
            if bar.button2: bar.button2.smooth = smooth

    def setPageScroll(self, delay:int=None, init_delay:int=None):
        for bar in self._bars: bar.setPageScrollDelay(delay, init_delay)

    def setLineScroll(self, delay:int=None, init_delay:int=None):
        for bar in self._bars: bar.setLineScrollDelay(delay, init_delay)

    def setWheelScroll(self, smooth_duration:int, scroll_amount:float=1.0, vertical:bool=None):
        self._scrollwheel_duration, self._scrollwheel_percent = smooth_duration, scroll_amount
        if vertical is not None: self._scrollwheel_axis = vertical

    def pageSize(self, axis:int) -> int:
        if self._page_size[axis] is None:
            self._page_size[axis] = int(self._scrollViewportSize(axis) * self.page_scale[axis])
        return self._page_size[axis]

    def scrollByWheel(self, event):
        if getLocalMouse(self)[2]:
            delta = int(event.delta * self._scrollwheel_percent)
            self._bars[self._scrollwheel_axis].mouseWheeled(delta, self._scrollwheel_duration)

    def _scrollPercent(self, axis:int) -> float:
        first, last = self._scrollView(axis)
        visible = last - first
        return first / (1.0 - visible) if visible < 1.0 else 0.0

    def _scrollTravelPixels(self, axis:int) -> float:
        first, last = self._scrollView(axis)
        visible = last - first
        if visible <= 0.0 or visible >= 1.0: return 0.0
        return self._scrollViewportSize(axis) * (1.0 - visible) / visible

    def _scrollPixelDelta(self, axis:int, pixels:float) -> float:
        travel = self._scrollTravelPixels(axis)
        return -pixels / travel if travel else 0.0

    def _viewChanged(self, axis:int, first:float=None, last:float=None):
        bar = self._bars[axis]
        if bar.isHeld(): return

        if first is None or last is None: first, last = self._scrollView(axis)
        bar.setView(first, last)

    def _scrollArea(self) -> tuple[int,int,int,int]:
        return 0, 0, *self.size

    def _scrollOverflow(self, axis:int, viewport_size:tuple[int,int]) -> bool:
        raise NotImplementedError

    def _applyScrollViewport(self, width:int, height:int):
        raise NotImplementedError

    def _syncLayout(self):
        if self._layout_lock or not self._bars: return
        self._layout_lock = True

        try:
            x, y, width, height = self._scrollArea()
            h_breadth, v_breadth = self._h_bar.height, self._v_bar.width

            # Showing one bar changes the viewport and can make the other necessary.
            h_visibility, v_visibility = self.getScrollbarVisibility()
            h_visible = h_visibility == self.ENABLED or \
                        h_visibility == self.AUTO and self._resolved_visibility[0]
            v_visible = v_visibility == self.ENABLED or \
                        v_visibility == self.AUTO and self._resolved_visibility[1]

            for _ in range(3):
                view_w = max(1, width - (v_breadth if v_visible else 0))
                view_h = max(1, height - (h_breadth if h_visible else 0))
                viewport = view_w, view_h

                new_h = False if h_visibility == self.DISABLED else \
                        True if h_visibility == self.ENABLED else self._scrollOverflow(0, viewport)
                new_v = False if v_visibility == self.DISABLED else \
                        True if v_visibility == self.ENABLED else self._scrollOverflow(1, viewport)

                if (new_h, new_v) == (h_visible, v_visible): break
                h_visible, v_visible = new_h, new_v

            self._resolved_visibility[:] = h_visible, v_visible

            view_w = max(1, width - (v_breadth if v_visible else 0))
            view_h = max(1, height - (h_breadth if h_visible else 0))
            self._applyScrollViewport(view_w, view_h)

            if h_visible:
                length = width - (v_breadth if v_visible and self.dominant_axis == 1 else 0)
                self._h_bar.resize(length)
                self._h_bar.place_configure(x=x, y=y + height - h_breadth)
            else:
                self._h_bar.place_configure(x=0, y=self.height)

            if v_visible:
                length = height - (h_breadth if h_visible and self.dominant_axis == 0 else 0)
                self._v_bar.resize(length)
                self._v_bar.place_configure(x=x + width - v_breadth, y=y)
            else:
                self._v_bar.place_configure(x=self.width, y=0)

            for axis, visible in enumerate((h_visible, v_visible)):
                bar = self._bars[axis]
                first, last = self._scrollView(axis)
                can_scroll = first > 0.0 or last < 1.0

                if bar.getStateMode() == bar.ENABLED:
                    bar._applyEnabled(True)
                elif bar.getStateMode() == bar.DISABLED:
                    bar._applyEnabled(False)
                else:
                    bar._applyEnabled(can_scroll)

                bar.setView(first, last)

            self._page_size = [None, None]

        finally:
            self._layout_lock = False


class ScrollWindow(Scrollable, Measurable, Siblingable, tk.Frame):
    def __init__(self, parent, width:int, height:int, scroll_skin:ScrollSkin,
                 bg_color:str="#6B6B6B", **kwargs):
        kwargs["bg"] = bg_color
        super().__init__(parent, width=width, height=height, scroll_skin=scroll_skin, **kwargs)

        # ScrollFrame is the clipping viewport. ScrollPlate is the translated local coordinate space within it.
        self._frame = ScrollFrame(self, bg_color, width=width, height=height)
        self._frame.place(x=0, y=0)

        self._plate = ScrollPlate(self._frame, self, bg_color, width=width, height=height)
        self._plate.place(x=0, y=0)

        self._spawnScrollbars()
        self.bind("<Configure>", self._refresh)

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

    # Including these methods allows Scrollable to be considered in sibling culling.
    @staticmethod
    def isOpaque(): return True
    def redraw(self): pass
    def zImage(self): return self._frame.skin.image()
    def setState(self, index:int = 0): pass

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

    # Internal scrolling protocol. Scroll controls interact with the owner through these methods,
    # never with the owner's particular content implementation.
    def _scrollViewportSize(self, axis:int) -> int:
        return self._frame.size[axis]

    def _scrollView(self, axis:int) -> tuple[float,float]:
        viewport = self._scrollViewportSize(axis)
        content = self._plate.size[axis]
        position = self._plate.location[axis]

        if content <= viewport: return 0.0, 1.0

        first = -position / content
        last = (viewport - position) / content
        return max(0.0, min(1.0, first)), max(0.0, min(1.0, last))

    def _scrollToPercent(self, axis:int, percent:float):
        percent = max(0.0, min(1.0, percent))
        dest = [None, None]
        dest[axis] = percent
        self.scrollByPercent(*dest)

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

                if delta_x and sw: self._viewChanged(0)
                if delta_y and sh: self._viewChanged(1)

    def _contentChanged(self):
        if hasattr(self, "_bars"): self._syncLayout()

    def _scrollOverflow(self, axis:int, viewport_size:tuple[int,int]) -> bool:
        return self._plate.content_size[axis] > viewport_size[axis]

    def _applyScrollViewport(self, width:int, height:int):
        frame_changed = self._frame.size != (width, height)
        self._frame.resize(width, height)

        content_w, content_h = self._plate.content_size
        plate_w, plate_h = max(width, content_w), max(height, content_h)

        px, py = self._plate.location
        sw, sh = min(width - plate_w, 0), min(height - plate_h, 0)
        px, py = max(sw, min(0, px)), max(sh, min(0, py))

        plate_changed = self._plate.size != (plate_w, plate_h)
        self._plate.resizeAndMove(px, py, plate_w, plate_h)
        self._plate._syncVisible(frame_changed or plate_changed)

    def _refresh(self, event=None):
        last_size = self.size
        super()._refresh(event)
        if hasattr(self, "_bars") and self.size != last_size: self._syncLayout()


class ScrollFrame(CoordinateSpace, Background):
    def __init__(self, parent:ScrollWindow, bg_color:str, **kwargs):
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
    def __init__(self, parent:ScrollFrame, owner:ScrollWindow, bg_color:str, **kwargs):
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

        entering = visible - self._visible_children
        for child in visible if redraw else entering:
            child.after_idle(child.redraw)

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
    def __init__(self, parent, direction:int, *args, smooth:bool=True, smooth_duration:int=130, **kwargs):
        self.direction = direction
        self.smooth = smooth
        self.smooth_duration = smooth_duration

        super().__init__(parent, function=self._scroll, *args, **kwargs)

    @property
    def smooth_duration(self): return self._smooth_duration
    @smooth_duration.setter
    def smooth_duration(self, duration:int):
        self._smooth_duration = max(1, int(duration))

    def _scroll(self):
        self.parent.buttonClicked(self)

    def _keepClicking(self):
        if self._clicking:
            if self.smooth:
                self.parent.buttonHeld(self)
            else:
                super()._keepClicking()

    def mouseUp(self, event):
        self.parent.buttonReleased()
        super().mouseUp(event)


class ScrollBar(LinearAnimator, Background):
    DISABLED = 0
    ENABLED = 1
    AUTO = 2

    def __init__(self, parent:Scrollable, bar_skin: ThreeSliceSkin | None = None,
                 handle_skin: ThreeSliceSkin | None = None, button_pack: ButtonPack | None = None, breadth:int = 0, **kwargs):
        self._bar_skin = bar_skin or ThreeSliceSkin()
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
        self._handle = ScrollHandle(self._trough, handle_skin or ThreeSliceSkin(vertical=bool(self._orientation[0]),
                                                                                breadth=breadth), bool(self._orientation[0]), width=breadth, height=breadth)
        self._trough.place(x=tx, y=ty)
        self._handle.place(x=0, y=0)

        # Scroll options
        self.smooth_page, self.smooth_line, self.smooth_wheel, self.smooth_drag = True, True, False, False
        self.instant_page = False
        self.line_duration, self.drag_duration = 130, 350

        # Consolidate whiny IDE complaints about undefined variables here, instead of throughout the class.
        self._directions, self._orientation = self._directions, self._orientation

        # State helpers.
        self._view = (0.0, 1.0)
        self._state_mode = self.AUTO
        self._visibility = self.AUTO
        self._continuous_scroll = False

    @property
    def directions(self): return self._directions
    @property
    def orientation(self): return self._orientation
    @property
    def vertical(self): return bool(self._orientation[0])

    @property
    def enabled(self): return self._trough.enabled
    def enable(self):
        self._state_mode = self.ENABLED
        self._applyEnabled(True)

    def disable(self):
        self._state_mode = self.DISABLED
        self._applyEnabled(False)

    def auto(self):
        self._state_mode = self.AUTO
        self.parent._syncLayout()

    def getVisibility(self) -> int: return self._visibility
    def setVisibility(self, visibility:int):
        self._setVisibility(visibility)
        self.parent._syncLayout()
    def _setVisibility(self, visibility:int): self._visibility = self._normalizeMode(visibility)

    def getStateMode(self) -> int: return self._state_mode
    def setStateMode(self, state:int):
        self._setStateMode(state)
        self.parent._syncLayout()
    def _setStateMode(self, state:int): self._state_mode = self._normalizeMode(state)

    @classmethod
    def _normalizeMode(cls, mode:int) -> int:
        if mode not in (cls.DISABLED, cls.ENABLED, cls.AUTO):
            raise ValueError("mode must be DISABLED, ENABLED, or AUTO")
        return mode

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

        if self.smooth_drag:
            origin = self.parent._scrollPercent(o)

            if not self.retargetAnimation(percent, self.drag_duration, origin):
                self.animate(origin, percent, self.drag_duration, self._moveAnimated, self.parent.smooth_rate)
        else:
            self.stopAnimation()
            self.parent._scrollToPercent(o, percent)

    def handleReleased(self):
        self.stopAnimation()
        self.parent._scrollToPercent(self.vertical, self._trough.getPercent())

    def troughClicked(self, button_clicked:int, click_x:int, click_y:int, duration:int):
        o = self.vertical
        click = (click_x, click_y)
        direction = 1 if click[o] < self._handle.middle[o] else -1

        if self.instant_page and button_clicked == 1 or not self.instant_page and button_clicked == 2:
            destination = self._trough.percentAt(click_x, click_y)
            delta = destination - self.parent._scrollPercent(o)
        else:
            pixels = self.parent.pageSize(o) * direction
            delta = self.parent._scrollPixelDelta(o, pixels)

        if self.smooth_page:
            self._beginAnimating(delta, duration)
        else:
            self.stopAnimation()
            self.parent._scrollToPercent(o, self.parent._scrollPercent(o) + delta)

    def isHeld(self): return self._trough.isHeld()

    def buttonClicked(self, button:ScrollButton):
        o = self.vertical
        pixels = self.parent.line_size[o] * button.direction
        delta = self.parent._scrollPixelDelta(o, pixels)

        if button.smooth:
            self._beginAnimating(delta, button.smooth_duration)
        else:
            self.stopAnimation()
            self.parent._scrollToPercent(o, self.parent._scrollPercent(o) + delta)

    def buttonHeld(self, button:ScrollButton):
        o = self.vertical
        origin = self.parent._scrollPercent(o)
        destination = 1.0 if button.direction < 0 else 0.0

        distance = abs(destination - origin) * self.parent._scrollTravelPixels(o)
        if not distance: return

        pixels_per_ms = self.parent.line_size[o] / button.smooth_duration
        duration = round(distance / pixels_per_ms)

        self._continuous_scroll = True
        self.animate(origin, destination, duration, self._moveAnimated, self.parent.smooth_rate)

    def buttonReleased(self):
        if self._continuous_scroll:
            self.stopAnimation()
            self._continuous_scroll = False

    def mouseWheeled(self, delta:int, duration:int):
        o = self.vertical
        delta = self.parent._scrollPixelDelta(o, delta)

        if self.smooth_wheel:
            origin = self.parent._scrollPercent(o)
            destination = self._animation[2] + delta if self._animation is not None else origin + delta
            destination = max(0.0, min(1.0, destination))

            if not self.retargetAnimation(destination, duration, origin):
                self.animate(origin, destination, duration, self._moveAnimated, self.parent.smooth_rate)
        else:
            self.stopAnimation()
            self.parent._scrollToPercent(o, self.parent._scrollPercent(o) + delta)

    def setView(self, first:float, last:float):
        first = max(0.0, min(1.0, float(first)))
        last = max(first, min(1.0, float(last)))
        self._view = first, last

        if not self.enabled:
            self._setDisabledHandle()
            return

        self._setViewHandle(first, last)

    def _applyEnabled(self, enabled:bool):
        if enabled:
            self._trough.enable()
            self._handle.enable()
            if self.button1: self.button1.enable()
            if self.button2: self.button2.enable()
        else:
            self._trough.disable()
            self._handle.disable()
            if self.button1: self.button1.disable()
            if self.button2: self.button2.disable()

        if enabled:
            self._setViewHandle(*self._view)
        else:
            self._setDisabledHandle()

    def _beginAnimating(self, delta:float, duration:int):
        self._continuous_scroll = False
        o = self.vertical
        origin = self.parent._scrollPercent(o)

        if self._animation is not None:
            old_origin, old_destination = self._animation[1], self._animation[2]
            same_direction = (old_destination > old_origin) == (delta > 0)

            if same_direction:
                destination = max(0.0, min(1.0, old_destination + delta))
                extension = destination - old_destination

                if extension:
                    extension_duration = round(duration * abs(extension / delta))
                    self.extendAnimation(extension, extension_duration)

                return

        destination = max(0.0, min(1.0, origin + delta))
        self.animate(origin, destination, duration, self._moveAnimated, self.parent.smooth_rate)

    def _moveAnimated(self, destination:float):
        self.parent._scrollToPercent(self.vertical, destination)

    def _setViewHandle(self, first:float, last:float):
        o, o1 = self._orientation
        o2 = o + 2

        trough_length = self._trough.geometry[o2]
        minimum_length = self._trough.geometry[o1 + 2]
        visible = last - first

        geo = list(self._handle.geometry)
        geo[o2] = max(minimum_length, min(trough_length, round(visible * trough_length)))

        slide_range = max(trough_length - geo[o2], 0)
        view_range = max(1.0 - visible, 0.0)
        position = first / view_range if view_range else 0.0

        geo[o] = round(position * slide_range)
        self._handle.place_configure(x=geo[0], y=geo[1], width=geo[2], height=geo[3])

    def _setDisabledHandle(self):
        o, o1 = self._orientation
        geo = list(self._handle.geometry)

        geo[o] = 0
        geo[o + 2] = self._trough.geometry[o1 + 2]

        self._handle.place_configure(x=geo[0], y=geo[1], width=geo[2], height=geo[3])

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
    def __init__(self, parent, bar_skin: ThreeSliceSkin | None = None, handle_skin: ThreeSliceSkin | None = None,
                 button_pack:ButtonPack|None = None, breadth:int = 0, **kwargs):
        self._directions = 0, 2
        self._orientation = 1, 0
        super().__init__(parent, bar_skin, handle_skin, button_pack, breadth, **kwargs)


class HorizontalScrollbar(ScrollBar):
    def __init__(self, parent, bar_skin: ThreeSliceSkin | None = None, handle_skin: ThreeSliceSkin | None = None,
                 button_pack:ButtonPack|None = None, breadth:int = 0, **kwargs):
        self._directions = 3, 1
        self._orientation = 0, 1
        super().__init__(parent, bar_skin, handle_skin, button_pack, breadth, **kwargs)


class ScrollTrough(Troughable, TroughButton):
    def __init__(self, parent:ScrollBar, skin:ThreeSliceSkin = None, **kwargs):
        self._vertical = parent.vertical
        self._default_skin = ThreeSliceSkin()
        super().__init__(parent, skin=skin, vertical=self._vertical, **kwargs)

    def enable(self):
        super().enable()
        self.bind("<Button-2>", self.clicked)
        self.bind("<ButtonRelease-2>", self.mouseUp)
    def disable(self):
        self._clicking = False
        if self._after:
            self.after_cancel(self._after)
            self._after = None

        super().disable()
        self.unbind("<Button-2>")
        self.unbind("<ButtonRelease-2>")

    def resize(self, length:int):
        size = list(self.size)
        size[self._vertical] = length
        self.place_configure(width=size[0], height=size[1])

    def handleDragged(self): self.parent.handleDragged()
    def handleReleased(self): self.parent.handleReleased()

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
    def __init__(self, parent:ScrollTrough, bar_skin:ThreeSliceSkin = None, vertical:bool = True, **kwargs):
        self.vertical = vertical
        super().__init__(parent, skin=bar_skin or ThreeSliceSkin(vertical=vertical), **kwargs)
        self._half = None

    @property
    def middle(self) -> tuple[int, int]: return self.geometry[0] + self.half[0], self.geometry[1] + self.half[1]

    @property
    def half(self) -> tuple[int, int]:
        if self._half is None:
            self._half = self._geometry[2] // 2, self._geometry[3] // 2
        return self._half

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