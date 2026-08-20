import tkinter as tk
from time import time
from typing import Callable
from pathlib import Path

from guiABLE.skinnable import Skinnable, Measurable, Skin, Childable
from guiABLE.utilities import (rectsOverlap, rectUnion, pointIsInRect, getOverlap, decimateRect, rectIntersect,
                               rectsUnion, LimitedDict, FontPack)
from guiABLE.uimage import UImage


""" NText is a fix for Tk's nonsensical, CLI-style text selection standards, developed by Keith Nash. """
def _enableNtext(widget):
    try:
        widget.tk.call("package", "present", "ntext")
    except tk.TclError:
        source = Path(__file__).parent / "vendor" / "ntext" / "ntext.tcl"
        widget.tk.call("source", str(source))

    tags = list(widget.bindtags())

    if "Text" in tags:
        tags[tags.index("Text")] = "Ntext"
    elif "Ntext" not in tags:
        tags.insert(1, "Ntext")

    widget.bindtags(tuple(tags))


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

    def _positionAnchoredChild(self):
        child = self._anchored_child
        if child is None: return

        pw, ph = self.size
        cw, ch = child.size
        dx, dy = self._anchor_offset
        anchor = self._anchor

        x = 0 if anchor in ("nw", "w", "sw") else \
            pw - cw if anchor in ("ne", "e", "se") else (pw - cw) // 2

        y = 0 if anchor in ("nw", "n", "ne") else \
            ph - ch if anchor in ("sw", "s", "se") else (ph - ch) // 2

        x, y = x + dx, y + dy

        if not child._placed:
            child.place(x, y)
        elif child.location != (x, y): child.place_configure(x=x, y=y, implied=True)

    def childChanged(self, child):
        super().childChanged(child)
        if child is self._anchored_child: self._positionAnchoredChild()

    def _afterGeometryChanges(self):
        super()._afterGeometryChanges()
        self._positionAnchoredChild()


""" Imageable simply displays an image. """
class Imageable(Stateable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._skin.setBGColors('#6B6B6B')      # Eliminate interactive colors for simple image.

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


class Labelable(Siblingable, Canvas):
    event_passthrough = True

    _font_attributes = {
        "font":        (0, "name"),
        "font_size":   (1, "size"),
        "weight":      (2, "weight"),
        "color":       (3, "color"),
        "drop_color":  (4, "drop_color"),
        "drop_pos":    (5, "drop_offset"),
        "drop_offset": (5, "drop_offset")
    }

    def __init__(self, parent, text:str="", font_pack:FontPack=None, **kwargs):
        self._using = [0] * 6
        self._override_pack = FontPack()
        self._pack = font_pack or FontPack()

        for key in tuple(kwargs):
            if key in self._font_attributes:
                index, attribute = self._font_attributes[key]
                self._using[index] = 1
                setattr(self._override_pack, attribute, kwargs.pop(key))

        self._packs = [self._pack, self._override_pack]
        self.text = text
        self._img_text, self._img_text_shadow = None, None

        # A Labelable owns no user-sized interior. Start tiny and fit native text after creation.
        kwargs.pop("width", None)
        kwargs.pop("height", None)
        kwargs.pop("skin", None)

        super().__init__(parent, skin=Skin(UImage()), width=1, height=1, **kwargs)
        self.drawText()

    @staticmethod
    def isOpaque(): return False
    @staticmethod
    def contributesToComposite(): return False

    def passMouseTo(self, widget):
        self._event_parent = widget

        for button in (1, 2, 3):
            self.bind(
                f"<Button-{button}>",
                lambda event, b=button: self._forwardMouse(event, f"<Button-{b}>"),
                "+"
            )
            self.bind(
                f"<ButtonRelease-{button}>",
                lambda event, b=button: self._forwardMouse(event, f"<ButtonRelease-{b}>"),
                "+"
            )

        self.bind("<B1-Motion>", lambda event: self._forwardMouse(event, "<B1-Motion>"), "+")

    def _forwardMouse(self, event, sequence:str):
        if self._event_parent is not None:
            self._event_parent.event_generate(sequence, x=self.x + event.x, y=self.y + event.y, when="now")

    def setText(self, text:str):
        if text != self.text:
            self.text = text
            self.drawText()

    def setFontPack(self, font_pack:FontPack):
        self._pack = font_pack
        self._packs[0] = font_pack
        self._using = [0] * 6
        self.drawText()

    def setFontAttributes(self, **kwargs):
        for key, value in kwargs.items():
            if key not in self._font_attributes:
                raise TypeError(f"Unknown Labelable font attribute: {key}")

            index, attribute = self._font_attributes[key]
            self._using[index] = 1
            setattr(self._override_pack, attribute, value)

        self.drawText()

    def drawText(self):
        dx, dy = self._packs[self._using[5]].drop_offset
        color = self._packs[self._using[3]].color
        drop_color = self._packs[self._using[4]].drop_color

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

    @property
    def _tk_font(self):
        return (
            self._packs[self._using[0]].name,
            self._packs[self._using[1]].size,
            self._packs[self._using[2]].weight
        )


class Labeled(Anchorable):
    def __init__(self, *args, text:str=None, font_pack:FontPack=None, label_kwargs:dict=None, **kwargs):
        self._label = None
        self._label_pack = font_pack or FontPack()
        self._label_options = dict(label_kwargs or {})

        self._text_pos = self._label_options.pop("text_pos", kwargs.pop("text_pos", None))
        self._text_anchor = self._label_options.pop("anchor", kwargs.pop("anchor", None))

        for key in tuple(kwargs):
            if key in Labelable._font_attributes:
                self._label_options[key] = kwargs.pop(key)

        super().__init__(*args, **kwargs)

        if text is not None:
            self._label = Labelable(self, text=text, font_pack=self._label_pack, **self._label_options)
            self._label.passMouseTo(self)
            self._anchorLabel()

    @property
    def label(self): return self._label

    def _anchorLabel(self):
        if self._label is None: return

        self.anchorChild(   self._label,
                            self._text_anchor or self._label_pack.anchor,
                            self._text_pos if self._text_pos is not None else self._label_pack.text_pos )

    def setText(self, text:str):
        if self._label is None:
            self._label = Labelable(self, text=text, font_pack=self._label_pack, **self._label_options)
            self._label.passMouseTo(self)
        else:
            self._label.setText(text)

        self._anchorLabel()

    def setFontPack(self, font_pack:FontPack):
        self._label_pack = font_pack
        if self._label is not None: self._label.setFontPack(font_pack)
        self._anchorLabel()

    def setFontAttributes(self, **kwargs):
        if "text_pos" in kwargs: self._text_pos = kwargs.pop("text_pos")
        if "anchor" in kwargs: self._text_anchor = kwargs.pop("anchor")

        if self._label is not None and kwargs: self._label.setFontAttributes(**kwargs)

        self._anchorLabel()


"""
Textable is a native tk.Text surface that participates honestly in guiABLE compositing.
Tk renders the native text/caret/selection, while a matching solid-color Skin represents
the widget's opaque surface to the raster compositor.
"""
class Textable(Siblingable, Renderable, BareText):
    def __init__(self, parent, width:int, height:int, text:str="",
                 bg_color:str="#6B6B6B", font_pack:FontPack=None,
                 editable:bool=True, **kwargs):

        self._bg_color = bg_color
        self._font_pack = font_pack or FontPack()
        self._editable = editable

        kwargs.setdefault("font", self._tk_font)
        kwargs.setdefault("fg", self._font_pack.color)
        kwargs.setdefault("insertbackground", self._font_pack.color)
        kwargs.setdefault("selectbackground", "#252595")
        kwargs.setdefault("selectforeground", self._font_pack.color)
        kwargs.setdefault("selectborderwidth", 0)

        super().__init__(parent, skin=self._backgroundSkin(width, height),
                            width=width, height=height,bg=bg_color, **kwargs)
        _enableNtext(self)  # Fix Tk's inane text selection policies.

        self.bind("<Double-Button-1>", self._doubleClick, "+")

        if text: self.insert("1.0", text)

        self.editable(editable)
        self.bind("<<Copy>>", self._copySelection)
        self.bind("<Button-1>", lambda event: self.focus_set(), "+")
        self.bind("<<SelectAll>>", self._emptySelectAll, "+")

    def getText(self) -> str: return self.get("1.0", "end-1c")
    def setText(self, text:str):
        state = self.cget("state")

        if state == "disabled": self.configure(state="normal")
        self.delete("1.0", "end")
        self.insert("1.0", text)
        if state == "disabled": self.configure(state="disabled")

    def setBackground(self, color:str):
        if color == self._bg_color: return

        self._bg_color = color
        self.configure(bg=color)
        self._rebuildBackground()
        self.redraw()

    def editable(self, editable:bool=None) -> bool:
        if editable is not None:
            self._editable = editable
            self.configure(state="normal" if editable else "disabled")

        return self._editable

    def render(self, image:UImage, xy_offset:tuple[int,int]=(0, 0)): pass

    @property
    def _tk_font(self): return self._font_pack.name, self._font_pack.size, self._font_pack.weight

    def _backgroundSkin(self, width:int=None, height:int=None) -> Skin:
        return Skin.fromColors( self.width if width is None else width,
                                self.height if height is None else height,
                                self._bg_color )

    def _rebuildBackground(self):
        self.setSkin(self._backgroundSkin(), implied=True)
        self.dirty = True

    def _emptySelectAll(self, event=None):
        if not self._text:
            self.tag_remove("sel", "1.0", "end")
            self.mark_set("insert", "1.0")
            return "break"

    def _doubleClick(self, event):
        end_info = self.bbox("end-1c")
        line_info = self.dlineinfo("end-1c")

        if end_info is None or line_info is None: return

        end_x = end_info[0]
        line_y, line_h = line_info[1], line_info[3]

        if line_y <= event.y < line_y + line_h and event.x >= end_x:
            self.tag_remove("sel", "1.0", "end")
            self.tag_add("sel", "1.0", "end-1c")
            self.mark_set("insert", "end-1c")
            return "break"

    def _copySelection(self, event=None):
        selection = self.tag_ranges("sel")
        if not selection: return "break"

        start, end = selection
        text_end = self.index("end-1c")

        if self.compare(end, ">", text_end): end = text_end

        text = self.get(start, end)

        self.clipboard_clear()
        self.clipboard_append(text)
        return "break"

    def _afterGeometryChanges(self):
        if self._last_geometry[2:] != self._geometry[2:]: self._rebuildBackground()
        super()._afterGeometryChanges()


class TextLine(Textable):
    def __init__(self, parent, width:int, height:int, text:str="",
                 editable:bool=True, max_chars:int=None,
                 placeholder:str=None, placeholder_pack:FontPack=None,
                 mask:str=None, masked:bool=False, **kwargs):

        self._text = self._singleLine(text)
        self._max_chars = max_chars
        self._placeholder = placeholder
        self._placeholder_pack = placeholder_pack
        self._mask = mask[:1] if mask else None
        self._masked = bool(masked and self._mask)
        self._has_focus = False

        kwargs["wrap"] = "none"
        kwargs.setdefault("takefocus", 1)

        super().__init__(parent, width, height, text="", editable=editable, **kwargs)

        self.bind("<Return>", self._blockLineBreak)
        self.bind("<KP_Enter>", self._blockLineBreak)
        self.bind("<KeyPress>", self._keyPressed)
        self.bind("<<Paste>>", self._paste)
        self.bind("<<PasteSelection>>", self._pasteSelection)

        self.bind("<Tab>", self._focusNext)
        self.bind("<Shift-Tab>", self._focusPrevious)
        self.bind("<ISO_Left_Tab>", self._focusPrevious)

        self.bind("<FocusIn>", self._focusIn, "+")
        self.bind("<FocusOut>", self._focusOut, "+")

        self._refreshDisplay()

    def getText(self) -> str:
        return self._text

    def setText(self, text:str):
        text = self._singleLine(text)

        if self.validateInput(text):
            self._text = text
            self._refreshDisplay()

    def setMaxChars(self, max_chars:int=None): self._max_chars = max_chars

    def setPlaceholder(self, text:str=None, font_pack:FontPack=None):
        self._placeholder = text

        if font_pack is not None:
            self._placeholder_pack = font_pack

        self._refreshDisplay()

    def setMask(self, character:str=None, masked:bool=None):
        self._mask = character[:1] if character else None

        if self._mask is None:
            self._masked = False
        elif masked is not None: self._masked = masked

        self._refreshDisplay()

    def masked(self, masked:bool=None) -> bool:
        if masked is not None:
            self._masked = bool(masked and self._mask)
            self._refreshDisplay()

        return self._masked

    def selectAll(self):
        if self._text:
            self.tag_add("sel", "1.0", f"1.{len(self._text)}")
            self.mark_set("insert", f"1.{len(self._text)}")

    def validateInput(self, proposed:str) -> bool: return self._max_chars is None or len(proposed) <= self._max_chars

    def _focusIn(self, event=None):
        self._has_focus = True
        self._refreshDisplay()

    def _focusOut(self, event=None):
        self._has_focus = False
        self._refreshDisplay()

    def _replaceSelection(self, text:str):
        if not self.editable(): return False

        text = self._singleLine(text)
        start, end = self.index("insert"), self.index("insert")

        selection = self.tag_ranges("sel")
        if selection: start, end = selection

        offset1, offset2 = int(str(start).split(".")[1]), int(str(end).split(".")[1])
        proposed = self._text[:offset1] + text + self._text[offset2:]

        if not self.validateInput(proposed): return False

        self._text = proposed
        self._refreshDisplay(offset1 + len(text))
        return True

    def _keyPressed(self, event):
        if not self.editable(): return

        if event.keysym == "BackSpace": return self._deleteBackward()
        if event.keysym == "Delete": return self._deleteForward()

        if event.char and event.char >= " " and event.keysym != "Tab":
            self._replaceSelection(event.char)
            return "break"

    def _deleteBackward(self):
        selection = self.tag_ranges("sel")
        if selection:
            self._replaceSelection("")
            return "break"

        pos = int(self.index("insert").split(".")[1])
        if pos:
            self.tag_add("sel", f"1.{pos - 1}", f"1.{pos}")
            self._replaceSelection("")

        return "break"

    def _deleteForward(self):
        selection = self.tag_ranges("sel")
        if selection:
            self._replaceSelection("")
            return "break"

        pos = int(self.index("insert").split(".")[1])
        if pos < len(self._text):
            self.tag_add("sel", f"1.{pos}", f"1.{pos + 1}")
            self._replaceSelection("")

        return "break"

    def _refreshDisplay(self, cursor:int=None):
        placeholder = self._placeholderActive()

        display = self._placeholder if placeholder else self._mask * len(self._text) if self._masked else self._text

        state = self.cget("state")
        if state == "disabled": self.configure(state="normal")

        super().delete("1.0", "end")
        super().insert("1.0", display or "")

        if placeholder:
            pack = self._placeholder_pack or self._font_pack

            self.tag_configure("_placeholder", foreground=pack.color, font=(pack.name, pack.size, pack.weight))
            self.tag_add("_placeholder", "1.0", "end-1c")
            self.mark_set("insert", "1.0")

        elif cursor is not None:
            cursor = min(cursor, len(self._text))
            self.mark_set("insert", f"1.{cursor}")
            self.see("insert")

        if state == "disabled": self.configure(state="disabled")

    def _paste(self, event=None):
        try: text = self.clipboard_get()
        except tk.TclError: return "break"

        self._replaceSelection(text)
        return "break"

    def _pasteSelection(self, event=None):
        try: text = self.selection_get(selection="PRIMARY")
        except tk.TclError: return "break"

        self._replaceSelection(text)
        return "break"

    def _placeholderActive(self) -> bool: return not self._text and bool(self._placeholder) and not self._has_focus

    @staticmethod
    def _singleLine(text:str) -> str: return text.replace("\r", " ").replace("\n", " ")

    @staticmethod
    def _blockLineBreak(event=None): return "break"

    def _focusNext(self, event=None):
        self.tk_focusNext().focus_set()
        return "break"

    def _focusPrevious(self, event=None):
        self.tk_focusPrev().focus_set()
        return "break"


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


"""
    Expandable extends Skinnable() to support live resizing of widget. An expandable will expand to envelope a new child
    widget, or to contain a child widget that has moved. It will also shrink when a child moves or is removed. Notably,
    Expandables do NOT alter their top-left origin point. They expand and contract, but do not alter their location.
"""
class Expandable():
    def __init__(self, *args, **kwargs):
        if 'width' not in kwargs:   kwargs['width'] = 0     # If dimensions are undefined, collapse to smallest size.
        if 'height' not in kwargs:  kwargs['height'] = 0

        super().__init__(*args, **kwargs)

    def registerChild(self, child):
        super().registerChild(child)
        self._resize()

    def dropChild(self, child):
        super().dropChild(child)
        self._resize()

    def childChanged(self, child):
        super().childChanged(child)
        self._resize()

    #   _resize() Determines new geometry when children are added, removed, or altered.
    def _resize(self):
        if not any(self._size_declared):        # Only alter dimensions if width/height were not explicitly declared.
            union = (0,0,0,0)
            union = rectsUnion(union, *[child.geometry for child in self.getChildren()])

            if union[2:] != self.size:
                w = self.width if self._size_declared[0] else union[2]
                h = self.height if self._size_declared[1] else union[3]
                self.place_configure(width=w, height=h, implied=True)     # Resize the Expandable itself.


""" Groupable() is a skinned Expandable, providing an image-based opaque, transparent, or semi-transparent surface."""
class Groupable(Expandable):
    # If no skin has been passed, we create a "non-skin" that fills the visible area of the Group.
    def _afterGeometryChanges(self):
        if not self._skin_passed:
            visible = decimateRect((0, 0, *self.size), [child.geometry for child in self._children if child.isOpaque()])
            if visible:
                if len(visible) == 1:
                    self._skin_offset = tuple(visible[0][:2])
                    new_img = UImage(width=visible[0][2], height=visible[0][3])
                else: new_img = UImage(width=self.width, height=self.height)
            else: new_img = UImage()
            self.setSkin(Skin(new_img))

        super()._afterGeometryChanges()


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


""" A Dead-End class for Collection() to terminate in -- providing a final super().__init__() destination. """
class Nothing():
    def __init__(self, *args, **kwargs): pass


"""A logical, non-rendered group that internally handles coordinate spaces and parent/child relations."""
class Collection(Expandable, Measurable, Nothing):
    is_collection = True

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        # Tk interpreter references (for .bind, .after, etc.)
        self.tk = parent.tk
        self._w = parent._w

        self._size_declared = [False, False]

    # Collections are logical parents; descendants are physically hosted by the nearest real Tk parent.
    def childMaster(self):
        return self._parent.childMaster() if hasattr(self._parent, "childMaster") else self._parent

    def mapChildToMaster(self, x:int, y:int) -> tuple[int,int]:
        x, y = x + self.x, y + self.y
        return self._parent.mapChildToMaster(x, y) if hasattr(self._parent, "mapChildToMaster") else (x, y)

    def mapMasterToChild(self, x:int, y:int) -> tuple[int,int]:
        if hasattr(self._parent, "mapMasterToChild"): x, y = self._parent.mapMasterToChild(x, y)
        return x - self.x, y - self.y

    def place(self, x:int=None, y:int=None, **kwargs):
        if x is None and 'x' in kwargs: x = kwargs['x']
        if y is None and 'y' in kwargs: y = kwargs['y']
        self._geometry = (x, y, 0, 0)
        self._last_geometry = self._geometry
        return self

    def place_configure(self, *args, **kwargs):
        # Enables passing .place(int, int) for x, y, or .place(x=int, y=int), or no x/y passed.
        if 'x' not in kwargs:
            kwargs['x'] = args[0] if len(args) and isinstance(args[0], int) else self.x
        if 'y' not in kwargs:
            kwargs['y'] = args[1] if len(args) > 1 and isinstance(args[1], int) else self.y

        # Update geometry and re-apply child placement without changing child-local geometry.
        last_xy = self.location
        self._geometry = (kwargs['x'], kwargs['y'], kwargs['width'] if 'width' in kwargs else self.width,
                                                    kwargs['height'] if 'height' in kwargs else self.height)

        if last_xy != self.location: self._reposition()
        self._last_geometry = self._geometry

    def _reposition(self):
        for child in self.getChildren():
            if hasattr(child, "_reposition"): child._reposition()

    @property
    def skin(self): return self._parent.skin
