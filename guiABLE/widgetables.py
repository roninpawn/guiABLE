import tkinter as tk

from time import time
from typing import Callable

from guiABLE.skinnable import Skinnable, Measurable, Skin, BorderSkin, Childable
from guiABLE.fontable import Fontable, FontPack
from guiABLE.utilities import (rectsOverlap, rectUnion, pointIsInRect, getOverlap, decimateRect, rectIntersect,
                               rectsUnion, LimitedDict)
from guiABLE.uimage import UImage


""" Siblingable is a mixin that provides parent/sibling awareness & overlap tracking.  """
class Siblingable:
    def __init__(self, *args, **kwargs):
        self._siblings = []
        self._bond_after = None
        self._bonded = False

        super().__init__(*args, **kwargs)
        self.bind("<Map>", self._bond)

    # Overlapping siblings track each other for the sake of compositing (faking transparency) during redraw.
    def trackSibling(self, new_sibling):
        if new_sibling not in self._siblings:
            family = list(self.parent.getChildren())
            for i in range(len(family)-1, -1, -1):
                if family[i] not in self._siblings and family[i] != new_sibling: family.pop(i)
            self._siblings = family

    def dropSibling(self, sibling):
        if sibling in self._siblings: self._siblings.remove(sibling)

    # Override methods that change z-index, to track and report changes to all interested parties.
    def lift(self, above=None):
        tk.Misc.lift(self, above)
        # TODO: All these after_idle()s are possibly the problem with lift/lowering.
        self.after_idle(self.parent._raiseChildIndex, self, above)
        self.after_idle(self._registerSiblings, self.parent.getChildren())
    def lower(self, below=None):
        tk.Misc.lower(self, below)
        self.after_idle(self.parent._lowerChildIndex, self, below)
        self.after_idle(self._registerSiblings, self.parent.getChildren())

    def destroy(self):
        for sibling in self._siblings:
            sibling.dropSibling(self)
        super().destroy()

    # Find overlapping siblings and store them / register with them, for future tracking.
    def _registerSiblings(self, siblings_list=None, prune=True):
        family = list(siblings_list or self._parent.getChildren())

        current = [
            sibling for sibling in family
            if isinstance(sibling, Measurable)
            and rectsOverlap(self._geometry, sibling.geometry)
        ]

        # During a geometry transition, retain former siblings for one final draw.
        siblings = current if prune else [
            sibling for sibling in family
            if sibling in current or sibling in self._siblings
        ]

        for sibling in current:
            if isinstance(sibling, Siblingable) and sibling not in self._siblings:
                sibling.trackSibling(self)

        if prune:
            for sibling in self._siblings:
                if sibling not in current and isinstance(sibling, Siblingable):
                    sibling.dropSibling(self)

        self._siblings = siblings

    def _bond(self, event=None):
        # Registration is cheap/idempotent and establishes z-order immediately.
        self._parent.registerChild(self)

        # Map/configuration churn collapses into one final sibling pass.
        if self._bond_after is None:
            self._bond_after = self.after_idle(self._finishBond)

    def _finishBond(self):
        self._bond_after = None

        self._registerSiblings()
        self._bonded = True
        self.redraw()

    def _cull_siblings(self, siblings, union):
        new_siblings, overlaps, atop = [], [], True
        opaque_rects, trans_rects = [], []

        for i in range(len(siblings)-1, -1, -1):
            sib = siblings[i]
            overlap = getOverlap(union, sib.geometry)

            if overlap is None: continue

            if sib == self: atop = False
            local_overlap = (*overlap.insert, *overlap.crop[2:])
            if opaque_rects and not decimateRect(local_overlap, opaque_rects): continue

            if atop:
                if sib.isOpaque():
                    opaque_rects.append(local_overlap)
                    for t_rect in trans_rects:
                        if rectsOverlap(t_rect, local_overlap): break
                    else: continue
                else:
                    trans_rects.append(local_overlap)

                if isinstance(sib, tk.Frame): continue

            new_siblings.append(sib)
            overlaps.append(overlap)

        return new_siblings, overlaps, opaque_rects

    def _afterGeometryChanges(self):
        # After initial bonding, geometry changes genuinely alter overlap
        # relationships and must be reflected before redraw.
        if self._bonded: self._registerSiblings(prune=False)
        super()._afterGeometryChanges()
        if self._bonded: self._registerSiblings()


class Renderable(Skinnable):
    def __init__(self, *args, **kwargs):
        self.skin_offset:tuple[int,int] = getattr(kwargs, 'skin_offset', (0, 0))
        self._last_offset = None

        super().__init__(*args, **kwargs)
        self.bench, self.benches = 0, 0

        self.bind("<Configure>", self._refresh)

        self.dirty = True
        self._z_state, self._z_img = None, None
        self._img_state = 0
        self._bases = LimitedDict(maxsize=20)

    @property
    def state(self): return self._img_state

    def redraw(self):
        self.setState(self._img_state)

    @staticmethod
    def contributesToComposite(): return True

    def _renderChildren(self, floor:UImage, draw_area:tuple[int,int,int,int]):
        if not self._children: return

        rendered = set()

        # Child order is top-first, so begin at the bottom. One lower child's
        # composite pass may already render overlapping siblings above it.
        for child in reversed(self._children):
            if child in rendered or not isinstance(child, Renderable): continue
            if child.isOpaque() or not rectsOverlap(draw_area, child.geometry): continue

            rendered.update(
                child.setState(
                    child._img_state,
                    floor=floor,
                    draw_area=draw_area
                )
            )

    # The ZImage() is a persistent render of what the widget looks like on its own. Only updated if something changed.
    def zImage(self) -> UImage:
        if self._z_state != self._img_state or self.dirty:
            self._z_img = self._skin.image(self._img_state).crop()
            self._z_state = self._img_state
            self.dirty = False
        return self._z_img

    def setState(self, state_index:int=0, floor:UImage=None, draw_area:tuple=None):
        start = time()
        rendered = set()
        self._img_state = state_index

        union = rectUnion(self._geometry, self._last_geometry)

        # A parent-context redraw only needs the portion whose floor has changed.
        if draw_area is not None:
            union = rectIntersect(union, draw_area)
            if not union or union[2] <= 0 or union[3] <= 0: return rendered

        """ Reduce union and siblings to only what is visible and necessary to draw. """
        if hasattr(self.parent, "childRenderArea"):
            render_area = self.parent.childRenderArea()

            if render_area is not None:
                visible = rectIntersect(self._geometry, render_area)
                union_visible = rectIntersect(union, render_area)

                if not union_visible or union_visible[2] <= 0 or union_visible[3] <= 0: return rendered

                # Preserve whole-widget composition when this widget itself changes while
                # straddling a rendering boundary. Parent-driven redraws stay restricted.
                if draw_area is not None or visible == self._geometry: union = union_visible

        elif isinstance(self.parent, Measurable):
            union = rectIntersect(union, (0, 0, *self.parent.size))

        if not union or union[2] <= 0 or union[3] <= 0: return rendered

        # Cull caller's siblings by overlap and visibility.
        if not isinstance(self, Siblingable):
            siblings = [self]
            overlaps = [getOverlap(union, self._geometry)]
            opaque_rects = [(0, 0, *union[2:])] if self.isOpaque() else []

        else:
            siblings, overlaps, opaque_rects = self._cull_siblings(self._siblings, union)

            # Remove last_geometry from union if self is opaque and the only sibling.
            if len(siblings) == 1 and self.isOpaque():
                union = self._geometry

            # Shrink the union further where opaque siblings block whole areas.
            union_remains = decimateRect((0, 0, *union[2:]), opaque_rects)

            if union_remains:
                local_union = rectsUnion(*union_remains) if len(union_remains) > 1 else union_remains[0]
                new_union = (union[0] + local_union[0], union[1] + local_union[1], *local_union[2:])

                if union != new_union:
                    union = new_union
                    siblings.reverse()
                    siblings, overlaps, opaque_rects = self._cull_siblings(siblings, union)

        if not siblings: return rendered

        x, y, w, h = union

        # A Renderable child uses its parent's completed raster surface as its floor.
        # Root/non-renderable parents continue using their own Skin below.
        if floor is None and isinstance(self._parent, Renderable):
            floor = self._parent.scratchImage()

        # Non-raster participant with nothing local beneath/above to composite:
        # copy its completed floor directly to its surface.
        if floor is not None and len(siblings) == 1 and siblings[0] == self \
                and not self.contributesToComposite():

            overlap = overlaps[0]
            cx, cy, cw, ch = overlap.crop
            ix, iy = overlap.insert

            final = self.scratchImage()
            floor.cropTo(final, x + ix, y + iy, cw, ch, cx, cy)
            self.render(final, self.skin_offset)

            self.dirty = False
            rendered.add(self)
            self._renderChildren(final, (cx, cy, cw, ch))
            return rendered

        """ Composite local sibling family to one base. """
        res = (w, h)
        if res not in self._bases:
            self._bases[res] = UImage(width=w, height=h)

        base = self._bases[res]

        # Establish the floor only if some of it remains visible.
        if not (len(siblings) == 1 and self.isOpaque()) \
                and decimateRect((0, 0, w, h), opaque_rects):

            if floor is not None:
                floor.cropTo(base, x, y, w, h)

            else:
                bg_x, bg_y = self._parent.childBackgroundPoint(x, y, w, h) \
                    if hasattr(self._parent, "childBackgroundPoint") else (x, y)

                self._parent.skin.image().cropTo(base, bg_x, bg_y, w, h)

        # Composite siblings bottom-to-top, rendering self and necessary siblings above.
        atop = self not in siblings

        for i in range(len(siblings)-1, -1, -1):
            sibling, overlap = siblings[i], overlaps[i]
            cx, cy, cw, ch = overlap.crop
            ix, iy = overlap.insert

            if getattr(sibling, "contributesToComposite", lambda: True)():
                sibling.zImage().cropTo(base, cx, cy, cw, ch, ix, iy)

            if sibling == self: atop = True

            if atop and not (sibling != self and sibling.isOpaque()):
                final = sibling.scratchImage()
                base.cropTo(final, ix, iy, cw, ch, cx, cy)
                sibling.render(final, sibling.skin_offset)

                if isinstance(sibling, Renderable):
                    rendered.add(sibling)
                    sibling._renderChildren(final, (cx, cy, cw, ch))

        self.bench += time() - start
        self.benches += 1

        if self.benches >= 100:
            print(f"{round(self.bench / 100, 5)}s per draw.")
            self.bench, self.benches = 0, 0

        return rendered


""" Canvas defines how to render images to the surface of the tk.Canvas to support parent & sibling transparency. """
class Canvas(Renderable, tk.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, highlightthickness=0, **kwargs)
        self._img = None

    def render(self, image:UImage, xy_offset:tuple[int, int] = (0,0)):
        if xy_offset != self._last_offset:
            self.delete(self._img)
            self._img = self.create_image(xy_offset[0], xy_offset[1], image=image, anchor="nw")
            self._last_offset = xy_offset
        else: self.itemconfig(self._img, image=image)


"""
BareText strips tk.Text down to a chrome-free surface whose physical geometry is controlled in pixels by guiABLE.
It preserves Text's native behavior unless a descendant explicitly disables it.
"""
class BareText(tk.Text):
    def __init__(self, parent, *args, **kwargs):
        kwargs.pop("width", None)
        kwargs.pop("height", None)

        super().__init__(parent, *args, bd=0, borderwidth=0, padx=0, pady=0, highlightthickness=0, **kwargs)

    def place(self, **kwargs):
        if "width" not in kwargs and self.width > 0: kwargs["width"] = self.width
        if "height" not in kwargs and self.height > 0: kwargs["height"] = self.height

        return super().place(**kwargs)


"""
A FakeCanvas is a tk.Text window configured to eliminate all text-features and provide a simple canvas. This is needed
because tkinter's tk.Canvas does not track/update its 'dirty' rectangle correctly. This issue of slow/wrong redraws
was solved in the Text widget, but nowhere else. So tk.Text is used as a render-floor for moving other widgets atop.
"""
class FakeCanvas(BareText):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, takefocus=0, state="disabled", cursor="arrow", **kwargs)

        tags = list(self.bindtags())
        if "Text" in tags: tags.remove("Text")
        self.bindtags(tuple(tags))

        self.configure(bg=self.cget("bg"))
        self._img = self.image_create("end", image=UImage())

    def configure(self, **kw):
        if "bg" in kw:
            kw["selectbackground"] = kw["bg"]
        if "background" in kw:
            kw["selectbackground"] = kw["background"]
        super().configure(**kw)

    def render(self, image:UImage, xy_offset:tuple[int,int] = (0,0)):
        self.image_configure(self._img, image=image, padx=xy_offset[0], pady=xy_offset[1])


"""
TextCanvas uses tk.Text as guiABLE's standard image-rendering surface. Tk's other child widgets can produce incorrect
dirty rectangles when overlapping siblings move across them, causing clipping, stretching, or ghosting. tk.Text's
redisplay handling does not exhibit that behavior, so FakeCanvas provides a stable render floor for guiABLE widgets.
"""
class TextCanvas(Renderable, FakeCanvas): pass


"""
A Backgroundable is a simple, static, one-image canvas to serve as the stage for attaching widgets.
"""
class Backgroundable:
    def __init__(self, *args, **kwargs):
        kwargs["bg"] = "#6B6B6B"
        super().__init__(*args, **kwargs)

    @staticmethod
    def isOpaque(): return True


""" Stateable establishes the base of the widget chain, providing basic access methods and on/off states. """
class Stateable:
    def __init__(self, *args, init_state=0, **kwargs):
        kwargs["bg"] = "#6B6B6B"     # Neutral background color reduces visual pop-in.
        super().__init__(*args, **kwargs)

        self._img_state = init_state
        self._enabled = False
        self.enable()

    @property
    def enabled(self) -> bool : return self._enabled
    def enable(self):
        self.setState(0)
        self._enabled = True
    def disable(self): self._enabled = False


class Anchorable:
    def __init__(self, *args, **kwargs):
        self._anchored_child = None
        self._anchor = "center"
        self._anchor_offset = (0, 0)

        super().__init__(*args, **kwargs)

    def anchorChild(self, child, anchor:str="center", offset:tuple[int,int]=(0, 0)):
        self._anchored_child = child
        self._anchor = anchor
        self._anchor_offset = offset
        self._positionAnchoredChild()

    def setAnchor(self, anchor:str=None, offset:tuple[int,int]=None):
        if anchor is not None: self._anchor = anchor
        if offset is not None: self._anchor_offset = offset
        self._positionAnchoredChild()

    def anchorArea(self) -> tuple[int,int,int,int]: return 0, 0, self.width, self.height
    def anchorOffset(self) -> tuple[int,int]: return self._anchor_offset

    def _positionAnchoredChild(self):
        if self._anchored_child is None: return

        ax, ay, aw, ah = self.anchorArea()
        cw, ch = self._anchored_child.size
        dx, dy = self.anchorOffset()
        anchor = self._anchor

        x = ax if anchor in ("nw", "w", "sw") else \
            ax + aw - cw if anchor in ("ne", "e", "se") else ax + (aw - cw) // 2

        y = ay if anchor in ("nw", "n", "ne") else \
            ay + ah - ch if anchor in ("sw", "s", "se") else ay + (ah - ch) // 2

        x, y = x + dx, y + dy

        if not self._anchored_child._placed:
            self._anchored_child.place(x, y)
        elif self._anchored_child.location != (x, y):
            self._anchored_child.place_configure(x=x, y=y, implied=True)

    def childChanged(self, child):
        super().childChanged(child)
        if child is self._anchored_child: self._positionAnchoredChild()

    def _afterGeometryChanges(self):
        super()._afterGeometryChanges()
        self._positionAnchoredChild()


class Borderable(Anchorable):
    def __init__(self, *args, border=None, expand=None, **kwargs):
        self._explicit_size = [kwargs.get("width") is not None, kwargs.get("height") is not None]

        self._border = (0, 0, 0, 0)             # top, right, bottom, left
        self._border_explicit = border is not None
        self._border_offset_axes = [False, False]
        self._offset_override = [None, None]

        self._expansion = (0, 0)
        self._expansion_axes = [False, False]

        super().__init__(*args, **kwargs)

        # Intrinsically-sized Skins also provide deliberate room in which an offset can operate.
        self._offset_size_axes = [
            self._explicit_size[0] or (getattr(self, "_skin_passed", False) and self.width > 0),
            self._explicit_size[1] or (getattr(self, "_skin_passed", False) and self.height > 0)
        ]

        self._syncBorderSkin()
        if border is not None: self.setBorder(border)
        if expand is not None: self.expand(expand)

    @property
    def border(self) -> tuple[int,int,int,int]: return self._border

    def setBorder(self, border, implied:bool=False):
        if not implied: self._border_explicit = True

        new_border = self._normalizeBorder(border)
        if new_border == self._border: return

        self._border = new_border
        top, right, bottom, left = new_border

        if not implied:
            self._border_offset_axes = [bool(left or right), bool(top or bottom)]

        self._borderChanged()

    def expand(self, width=None, height=None) -> tuple[int,int]:
        if width is None and height is None: return self._expansion

        if isinstance(width, (tuple, list)):
            if len(width) != 2: raise ValueError("expand must contain width and height")
            width, height = width

        elif height is None:
            height = width

        width, height = max(0, int(width)), max(0, int(height))

        if (width, height) != self._expansion:
            self._expansion = (width, height)
            self._expansion_axes = [width > 0, height > 0]
            self._expansionChanged()

        return self._expansion

    def borderedSize(self, width:int, height:int) -> tuple[int,int]:
        top, right, bottom, left = self._border
        return width + left + right, height + top + bottom

    def expandedSize(self, width:int, height:int) -> tuple[int,int]:
        return width + self._expansion[0], height + self._expansion[1]

    def anchorArea(self) -> tuple[int,int,int,int]:
        top, right, bottom, left = self._border

        return (left, top,
                max(0, self.width - left - right),
                max(0, self.height - top - bottom))

    def anchorOffset(self) -> tuple[int,int]:
        dx, dy = super().anchorOffset()
        use_x, use_y = self._usesAnchorOffset()
        return dx if use_x else 0, dy if use_y else 0

    def useAnchorOffset(self, x:bool=None, y:bool=None) -> tuple[bool,bool]:
        if x is not None: self._offset_override[0] = x
        if y is not None: self._offset_override[1] = y

        self._positionAnchoredChild()
        return self._usesAnchorOffset()

    def automaticAnchorOffset(self, x:bool=True, y:bool=True):
        if x: self._offset_override[0] = None
        if y: self._offset_override[1] = None
        self._positionAnchoredChild()

    def _automaticAnchorOffsetAxes(self) -> tuple[bool,bool]:
        return (
            self._offset_size_axes[0] or self._border_offset_axes[0] or self._expansion_axes[0] or self._size_declared[0],
            self._offset_size_axes[1] or self._border_offset_axes[1] or self._expansion_axes[1] or self._size_declared[1]
        )

    def _usesAnchorOffset(self) -> tuple[bool,bool]:
        automatic = self._automaticAnchorOffsetAxes()

        return tuple(
            automatic[axis] if self._offset_override[axis] is None else self._offset_override[axis]
            for axis in range(2)
        )

    def _borderChanged(self): self._positionAnchoredChild()
    def _expansionChanged(self): self._positionAnchoredChild()

    @staticmethod
    def _normalizeBorder(border) -> tuple[int,int,int,int]:
        values = (border,) if isinstance(border, int|float) else tuple(border)

        if len(values) == 1:
            top = right = bottom = left = values[0]
        elif len(values) == 2:
            top = bottom = values[0]
            right = left = values[1]
        elif len(values) == 3:
            top, right, bottom = values
            left = right
        elif len(values) == 4:
            top, right, bottom, left = values
        else:
            raise ValueError("border must contain 1 to 4 values")

        return top, right, bottom, left

    def _syncBorderSkin(self):
        if isinstance(self.skin, BorderSkin):
            if (self.skin.width, self.skin.height) != self.size:
                self.skin.resize(*self.size, notify=False)
                self.dirty = True

            if not self._border_explicit:
                self.setBorder(self.skin.insets(), implied=True)

        elif not self._border_explicit and self._border != (0, 0, 0, 0):
            self.setBorder(0, implied=True)

    def _afterGeometryChanges(self):
        self._syncBorderSkin()
        super()._afterGeometryChanges()


""" Provides one distinguished inner child whose geometry can determine the outer widget's automatic size. """
class Nestable(Borderable):
    def __init__(self, *args, **kwargs):
        width_declared = kwargs.get("width") is not None
        height_declared = kwargs.get("height") is not None
        self._nested_child = None
        self._nested_fill = False

        super().__init__(*args, **kwargs)

        self._auto_width = not width_declared
        self._auto_height = not height_declared

    @property
    def nestedChild(self): return self._nested_child

    def nestChild(self, child, fill:bool=False):
        self._nested_child = child
        self._nested_fill = fill
        self._layoutNested()

    def _layoutNested(self):
        if self._nested_child is None: return

        if self._auto_width or self._auto_height: self._fitToNested()
        if not self._nested_fill: return

        x, y, width, height = self.anchorArea()

        if not self._nested_child._placed:
            self._nested_child.place(x=x, y=y, width=width, height=height)
        elif self._nested_child.geometry != (x, y, width, height):
            self._nested_child.place_configure(x=x, y=y, width=width, height=height, implied=True)

    def _borderChanged(self):
        self._layoutNested()
        super()._borderChanged()

    def _expansionChanged(self):
        self._layoutNested()
        super()._expansionChanged()

    def childChanged(self, child):
        if child is self._nested_child and not self._nested_fill: self._fitToNested()
        super().childChanged(child)

    def _nestedSize(self) -> tuple[int,int]:
        if hasattr(self._nested_child, "naturalSize"):
            return self._nested_child.naturalSize()

        return self._nested_child.size

    def _fitToNested(self):
        if self._nested_child is None: return

        width, height = self.expandedSize(*self._nestedSize())
        width, height = self.borderedSize(width, height)

        width = width if self._auto_width else self.width
        height = height if self._auto_height else self.height

        if (width, height) == self.size: return

        self._geometry = (*self.location, width, height)
        self._scratch = UImage(width=width, height=height)
        self._syncBorderSkin()

        if self._placed:
            self.place_configure(width=width, height=height, implied=True)

    def _afterGeometryChanges(self):
        super()._afterGeometryChanges()
        if getattr(self, "_nested_fill", False): self._layoutNested()


""" Imageable simply displays an image. """
class Imageable(Stateable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not isinstance(self._skin, BorderSkin):
            self._skin.setBGColors('#6B6B6B')     # Eliminate interactive colors for simple image.

    def changeImage(self, img_number, force_draw=False):
        if force_draw or self._img_state != img_number: self.setState(img_number)

    def enable(self):
        self.setState(self._img_state)
        self._enabled = True

""" Hoverable adds mouse-over awareness and triggers state-change/redraws on mouse-in and mouse-out. """
class Hoverable(Stateable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.moused_over = False

    def setSkin(self, skin):
        super().setSkin(skin)
        self.redraw()

    def mouseIn(self, event):
        # If widget has a child and the mouse enters child & parent at the same time, only change child's visual state.
        for child in self._children:
            if not getattr(child, "event_passthrough", False) and pointIsInRect(event.x, event.y, child.geometry):
                return
        self.setState(1)
        self.moused_over = True

    def mouseOut(self, event):
        self.moused_over = False
        self.setState(0)

    def enable(self):
        super().enable()
        self.bind("<Enter>", self.mouseIn)
        self.bind("<Leave>", self.mouseOut)
        #self.redraw()

    def disable(self):
        super().disable()
        self.unbind("<Enter>")
        self.unbind("<Leave>")
        self.setState(3)


""" Clickable adds left-click awareness and executes a passed function on mouse-down. (Instant-click button) """
class Clickable(Hoverable):
    def __init__(self, parent, function:tuple|Callable=lambda: None, **kwargs):
        super().__init__(parent, **kwargs)
        self.function = function

    def clicked(self, event):
        self.setState(2)
        self._call_function(self.function)

    def enable(self):
        super().enable()
        self.bind("<Button-1>", self.clicked)

    def disable(self):
        super().disable()
        self.unbind("<Button-1>")

    def _call_function(self, func):
        if func is not None:
            if callable(func): func()
            elif len(func):
                args = []
                for arg in func[1:]:
                    args.append(arg()) if callable(arg) else args.append(arg)
                func[0](*args) if len(func) > 1 else func[0]()


""" Pushable is a Clickable that executes its function when the left mouse button is released. (Normal button) """
class Pushable(Clickable):
    def __init__(self, *args, **kwargs):
        self._clicking = False
        super().__init__(*args, **kwargs)

    def isHeld(self): return self._clicking

    def enable(self):
        super().enable()
        self.bind("<ButtonRelease-1>", self.mouseUp)

    def disable(self):
        super().disable()
        self.unbind("<ButtonRelease-1>")

    def clicked(self, event):
        self._clicking = True
        self.grab_set()     # Ensures this widget receives all events until mouse-1 is released.
        self.setState(2)

    def mouseUp(self, event):
        self._clicking = False
        self.grab_release()
        self.mouseIn(event) if self.moused_over else self.mouseOut(event)
        if self.moused_over:
            self._call_function(self.function)

    def mouseIn(self, event):
        if self._clicking:
            self.moused_over = True
            self.setState(2)
        else: super().mouseIn(event)


class Labelable(Fontable, Siblingable, Canvas):
    event_passthrough = True

    def __init__(self, parent, text:str="", font_pack:FontPack=None, **kwargs):
        self.text = text
        self._img_text, self._img_text_shadow = None, None

        # A Labelable owns no user-sized interior. Start tiny and fit native text after creation.
        kwargs.pop("width", None)
        kwargs.pop("height", None)
        kwargs.pop("skin", None)

        super().__init__(parent, skin=Skin(UImage()), width=1, height=1, font_pack=font_pack, **kwargs)
        self.drawText()

    @staticmethod
    def isOpaque(): return False
    @staticmethod
    def contributesToComposite(): return False

    def passMouseTo(self, widget):
        self._event_parent = widget

        for sequence in ("<Enter>", "<Leave>", "<B1-Motion>"):
            self.bind(sequence, lambda event, s=sequence: self._forwardMouse(event, s), "+")

        for button in (1, 2, 3):
            self.bind(  f"<Button-{button}>",
                        lambda event, b=button: self._forwardMouse(event, f"<Button-{b}>"), "+" )
            self.bind(  f"<ButtonRelease-{button}>",
                        lambda event, b=button: self._forwardMouse(event, f"<ButtonRelease-{b}>"), "+" )

    def _forwardMouse(self, event, sequence:str):
        if self._event_parent is not None:
            self._event_parent.event_generate(sequence, x=self.x + event.x, y=self.y + event.y, when="now")

    def setText(self, text:str):
        if text != self.text:
            self.text = text
            self.drawText()

    def drawText(self):
        dx, dy = self._fontValue("drop_offset")
        color = self._fontValue("color")
        drop_color = self._fontValue("drop_color")

        if drop_color is None:
            if self._img_text_shadow is not None:
                self.delete(self._img_text_shadow)
                self._img_text_shadow = None

        elif self._img_text_shadow is None:
            self._img_text_shadow = self.create_text(
                dx, dy, text=self.text, fill=drop_color, font=self._tk_font, anchor="nw"
            )

        else:
            self.coords(self._img_text_shadow, dx, dy)
            self.itemconfigure(
                self._img_text_shadow, text=self.text, fill=drop_color, font=self._tk_font
            )

        if self._img_text is None:
            self._img_text = self.create_text(
                0, 0, text=self.text, fill=color, font=self._tk_font, anchor="nw"
            )

        else:
            self.coords(self._img_text, 0, 0)
            self.itemconfigure(self._img_text, text=self.text, fill=color, font=self._tk_font)

        self._fitText()

    def _fontChanged(self): self.drawText()

    def _fitText(self):
        items = tuple(item for item in (self._img_text, self._img_text_shadow) if item is not None)
        bbox = self.bbox(*items) if items else None

        if bbox is None:
            width, height = 1, 1
        else:
            x1, y1, x2, y2 = bbox
            width, height = max(1, x2 - x1), max(1, y2 - y1)

            # Normalize Tk/font overhang into the smallest possible Canvas.
            if x1 or y1:
                for item in items: self.move(item, -x1, -y1)

        if (width, height) == self.size: return

        if self._placed:
            self.place_configure(width=width, height=height, implied=True)

        else:
            self._geometry = (*self.location, width, height)
            self._scratch = UImage(width=width, height=height)
            tk.Canvas.configure(self, width=width, height=height)

    def render(self, image:UImage, xy_offset:tuple[int,int]=(0,0)):
        super().render(image, xy_offset)
        if self._img_text_shadow is not None: self.tag_raise(self._img_text_shadow)
        if self._img_text is not None: self.tag_raise(self._img_text)


class Labeled(Fontable, Anchorable):
    def __init__(self, *args, text:str=None, font_pack:FontPack=None, label_kwargs:dict=None, **kwargs):
        self._label = None
        self._label_options = dict(label_kwargs or {})

        # Font configuration belongs to Labeled. label_kwargs retains only child-specific options.
        for key in tuple(self._label_options):
            if key in self._font_attributes:
                kwargs.setdefault(key, self._label_options.pop(key))

        super().__init__(*args, font_pack=font_pack, **kwargs)

        if text is not None: self._createLabel(text)

    @property
    def label(self): return self._label

    def setText(self, text:str):
        if self._label is None: self._createLabel(text)
        else: self._label.setText(text)

        self._anchorLabel()

    def _createLabel(self, text:str):
        self._label = Labelable(self, text=text, font_pack=self._font_pack, **self._label_options)
        self._syncFontTo(self._label)
        self._label.passMouseTo(self)
        self._anchorLabel()

    def _anchorLabel(self):
        if self._label is None: return
        self.anchorChild(self._label, self._fontValue("anchor"), self._fontValue("text_offset"))

    def _fontChanged(self):
        if self._label is not None:
            self._syncFontTo(self._label)
            self._anchorLabel()


""" Toggleable stores a true/false state and redirects image() calls by index+_state_offset when true. This allows the
    skin to return states 0,1,2,3 for the False state of the Toggleable, and 4,5,6,7 for the True state. (Checkbox) """
class Toggleable(Pushable):
    def __init__(self, *args, state:bool=False, state_span:int=4, **kwargs):
        self._toggle_state = state
        self._state_span = max(1, state_span)
        self._state_offset = self._state_span if state else 0

        super().__init__(*args, **kwargs)

    def mouseUp(self, event):
        self._clicking = False
        self.grab_release()

        if self.moused_over:
            self.setTrue(not self._toggle_state)
            self._call_function(self.function)

        self.mouseIn(event) if self.moused_over else self.mouseOut(event)

    def isTrue(self): return self._toggle_state

    def setTrue(self, true:bool) -> bool:
        self._toggle_state = true
        self._state_offset = self._state_span if true else 0
        self.setState(self._img_state % self._state_span)
        return self._toggle_state

    def setState(self, state_index:int=0, floor:UImage=None, draw_area:tuple=None):
        return super().setState(
            (state_index % self._state_span) + self._state_offset,
            floor, draw_area
        )


class Holdable(Pushable):
    def mouseOut(self, event):
        if self._clicking: self.moused_over = False
        else: super().mouseOut(None)

    def mouseUp(self, event):
        self._clicking = False
        self.grab_release()
        self.mouseIn(event) if self.moused_over else self.mouseOut(event)

    def clicked(self, event):
        super().clicked(event)
        self._call_function(self.function)


""" Repeatable is a Holdable that triggers its function instantly, and then again after every n milliseconds. It
    supports a first-click, initial-delay that can be longer or shorter than the continuous delay thereafter."""
class Repeatable(Holdable):
    def __init__(self, *args, delay=150, init_delay=400, **kwargs):
        super().__init__(*args, **kwargs)
        self.delay = delay
        self.init_delay = init_delay
        self._after = None

    def clicked(self, event):
        super().clicked(event)
        if self.function is not None:
            if self._after: self.after_cancel(self._after)
            self._after = self.after(self.init_delay, self._keepClicking)

    def _keepClicking(self):
        if self._clicking:
            self._call_function(self.function)
            self._after = self.after(self.delay, self._keepClicking)


""" LoneDraggable is dragged by the mouse while left click is held. It remains within its parent's boundaries by default,
    but its bounds can be overridden using setBounds(). It does not have sibling awareness and is expected to be the
    only child of its parent widget. (like a ScrollHandle) For correct redraw, moving objects like Draggable must be
    drawn atop a Canvasable. Otherwise, tkinter's stale draw rectangle issue creates ghosting/visual stretching."""
class LoneDraggable(Holdable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bounds = None
        self._x_origin, self._y_origin = 0, 0

    def setBounds(self, bbox:tuple[int,int,int,int]|None): self._bounds = bbox

    def enable(self):
        self.bind("<B1-Motion>", self.mouseDrag)
        super().enable()

    def disable(self):
        self.unbind("<B1-Motion>")
        super().disable()

    def clicked(self, event):
        self._x_origin = event.x
        self._y_origin = event.y
        self._clicking = True
        self.grab_set()
        self.setState(2)

    def mouseDrag(self, event):
        x = event.x - self._x_origin + self._geometry[0]
        y = event.y - self._y_origin + self._geometry[1]
        self.move(x, y)

    def move(self, x:int, y:int):
        w, h = self._geometry[2:]
        bbox = (0, 0, *self.parent.geometry[2:]) if self._bounds is None else self._bounds
        x = max(bbox[0], min(x, bbox[2] - w))
        y = max(bbox[1], min(y, bbox[3] - h))

        self._geometry = (x, y, w, h)
        if self._last_geometry != self._geometry:
            self.place_configure(x=x, y=y, implied=True)
            self._call_function(self.function)


""" Draggable adds sibling awareness to LoneDraggable, allowing it to composite transparencies with other widgets. """
class Draggable(LoneDraggable):
    def mouseDrag(self, event=None):
        x = event.x - self._x_origin + self._geometry[0]
        y = event.y - self._y_origin + self._geometry[1]
        self.move(x, y)

""" Troughable establishes a one-dimensional space traversed by a child handle and provides normalized position access. """
class Troughable:
    def __init__(self, *args, vertical:bool=None, **kwargs):
        self._handle = None
        super().__init__(*args, **kwargs)

        self._active = int(vertical) if vertical is not None else int(self.height > self.width)

    @property
    def slide_range(self) -> int:
        return max(self.size[self._active] - self._handle.size[self._active], 0) if self._handle else 0

    def getPercent(self) -> float:
        if not self._handle: return 0.0

        p, slide_range = self._handle.location[self._active], self.slide_range
        return p / slide_range if slide_range else 0.0

    def setPercent(self, percent:float, notify:bool=False):
        if self._handle:
            handle_pos = [0, 0]
            handle_pos[self._active] = round(self.slide_range * min(1.0, max(0.0, percent)))

            if notify: self._handle.move(*handle_pos)
            else: self._handle.place_configure(x=handle_pos[0], y=handle_pos[1])

    def percentAt(self, x:int, y:int) -> float:
        slide_range = self.slide_range
        if not self._handle or not slide_range: return 0.0

        p = (x, y)[self._active] - self._handle.size[self._active] * 0.5
        return min(1.0, max(0.0, p / slide_range))

    def isHeld(self): return self._handle.isHeld() if self._handle else False

    def registerChild(self, child):
        super().registerChild(child)
        self._handle = child

    def enable(self):
        super().enable()
        if self._handle: self._handle.enable()

    def disable(self):
        super().disable()
        if self._handle: self._handle.disable()


""" CoordinateSpace preserves child-local geometry when the whole parent space translates or resizes. """
class CoordinateSpace:
    def translate(self, x:int=None, y:int=None):
        x = self.x if x is None else x
        y = self.y if y is None else y

        if (x, y) != self.location:
            self.place_configure(x=x, y=y, implied=True, skip=True)
            if isinstance(self.parent, Childable): self.parent.childChanged(self)
            self.spaceTranslated()

        return self

    def _refreshChildren(self):
        if self._last_geometry[2:] != self._geometry[2:]: self.spaceResized()
        elif self._last_geometry[:2] != self._geometry[:2]: self.spaceTranslated()

    def spaceTranslated(self): pass
    def spaceResized(self): pass


""" LinearAnimator interpolates between two scalar values over time, passing each step to a supplied function. """
class LinearAnimator:
    def __init__(self, *args, **kwargs):
        self._animation, self._animation_after = None, None
        super().__init__(*args, **kwargs)

    def animate(self, origin:float, destination:float, duration:int, function:Callable, rate:int=15,
                finished:Callable=None):
        self.stopAnimation()

        if duration <= 0 or origin == destination:
            function(destination)
            if finished: finished()
            return

        self._animation = [time(), origin, destination, duration / 1000, rate, function, finished]
        self._animation_after = self.after_idle(self._animationStep)

    def extendAnimation(self, delta:float, duration:int) -> bool:
        if self._animation is None: return False

        self._animation[2] += delta
        self._animation[3] += duration / 1000

        return True

    def retargetAnimation(self, destination:float, duration:int, origin:float=None) -> bool:
        if self._animation is None: return False

        start, old_origin, old_destination, old_duration = self._animation[:4]
        now = time()

        if origin is None:
            progress = min(1.0, (now - start) / old_duration)
            origin = old_destination if progress == 1.0 else \
                     old_origin + (old_destination - old_origin) * progress

        self._animation[0] = now
        self._animation[1] = origin
        self._animation[2] = destination
        self._animation[3] = duration / 1000

        return True

    def stopAnimation(self):
        if self._animation_after is not None: self.after_cancel(self._animation_after)
        self._animation, self._animation_after = None, None

    def _animationStep(self):
        animation = self._animation
        if animation is None: return

        self._animation_after = None
        start, origin, destination, duration, rate, function, finished = animation
        progress = min(1.0, (time() - start) / duration)

        function(destination if progress == 1.0 else origin + (destination - origin) * progress)

        # The called function is allowed to begin or cancel an animation.
        if self._animation is not animation: return

        if progress < 1.0:
            self._animation_after = self.after(rate, self._animationStep)
        else:
            self._animation = None
            if finished: finished()

    def destroy(self):
        self.stopAnimation()
        super().destroy()
