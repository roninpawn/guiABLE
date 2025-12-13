import tkinter as tk
from time import time
from typing import Callable

from guiABLE.skinnable import Skinnable, Measurable, Skin, Placeable
from guiABLE.utilities import (rectsOverlap, rectUnion, pointIsInRect, getOverlap, decimateRect, rectIntersect,
                               rectsUnion, LimitedDict, FontPack, Overlap, getGeometry)
from guiABLE.uimage import UImage


""" Siblingable is a mixin that provides parent/sibling awareness & overlap tracking.  """
class Siblingable:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind("<Map>", self._bond)

        self._siblings = []

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
    def _registerSiblings(self, siblings_list = None):
        new_siblings = []
        if siblings_list is None: siblings_list = self._parent.getChildren()

        for sibling in list(siblings_list):
            if isinstance(sibling, Measurable) and rectsOverlap(self._geometry, sibling.geometry):
                new_siblings.append(sibling)
                if isinstance(sibling, Siblingable) and sibling not in self._siblings:
                    sibling.trackSibling(self)

        self._siblings = new_siblings

    def _bond(self, event=None):
        self._parent.registerChild(self)
        self._registerSiblings()
        self.after_idle(self.setState, 0)

    def _cull_siblings(self, siblings, union):
        new_siblings, overlaps, atop = [], [], True
        opaque_rects, trans_rects = [], []

        # Prepare list of rectangles describing how each sibling overlaps the union
        for i in range(len(siblings)-1, -1, -1):
            sib = siblings[i]
            overlap = getOverlap(union, sib.geometry)
            if overlap is None:     # If former sibling nolonger overlaps, stop tracking sibling.
                sib.dropSibling(self)
                self.dropSibling(sib)
                continue

            # Cull siblings by visibility.
            if sib == self: atop = False
            local_overlap = (*overlap.insert, *overlap.crop[2:])
            # Don't draw a sibling that is obscured by the siblings atop it.
            if opaque_rects and not decimateRect(local_overlap, opaque_rects): continue
            if atop:
                if sib.isOpaque():
                    opaque_rects.append(local_overlap)
                    for t_rect in trans_rects:
                        if rectsOverlap(t_rect, local_overlap): break
                    else: continue      # Dont draw opaque widgets that do not have a transparent widget above them.
                else: trans_rects.append(local_overlap)
                if isinstance(sib, tk.Frame): continue       # Don't draw container widgets.

            new_siblings.append(sib)
            overlaps.append(overlap)
        return new_siblings, overlaps, opaque_rects


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

    def redraw(self):
        # If the skin that this widget uses has changed, all of its children must redraw.
        self.setState(self._img_state)
        if self.dirty:
            for child in self._children: child.redraw()
            self.dirty = False

    # The ZImage() is a persistent render of what the widget looks like on its own. Only updated if something changed.
    def zImage(self) -> UImage:
        if self._z_state != self._img_state or self.dirty:
            self._z_img = self._skin.image(self._img_state).crop()
            self._z_state = self._img_state
            self.dirty = False
        return self._z_img

    def setState(self, state_index:int = 0):
        start = time()
        if not self._window.drag_locked: return
        self._img_state = state_index

        union = rectUnion(self._geometry, self._last_geometry)

        """ Reduce union and siblings to only what is visible and necessary to draw. """
        # Reduce union to the visible boundaries of the caller's parent. (Don't draw what is off screen.)
        if isinstance(self.parent, Measurable): union = rectIntersect(union, (0, 0, *self.parent.size))
        if union is None: return

        # Cull caller's siblings by overlap and visibility, and generate a list of any opaque-sibling's geometries.
        if not isinstance(self, Siblingable):
            siblings, overlaps, opaque_rects = [self], [Overlap(self.geometry, (0,0))], [self]
        else:
            siblings, overlaps, opaque_rects = self._cull_siblings(self._siblings, union)
            # Remove last_geometry from union, if self is opaque and only sibling.
            if len(siblings) == 1 and self.isOpaque(): union = self._geometry

            # Determine if the union can be shrunk again, due to opaque siblings blocking whole axes of the union's surface.
            union_remains = decimateRect((0, 0, *union[2:]), opaque_rects)
            if union_remains:
                local_union = rectsUnion(*union_remains) if len(union_remains) > 1 else union_remains[0]
                new_union = (union[0] + local_union[0], union[1] + local_union[1], *local_union[2:])
                # If the union can shrink, shrink it and recalculate how the remaining siblings overlap the union.
                if union != new_union:
                    union = new_union
                    siblings.reverse()
                    siblings, overlaps, opaque_rects = self._cull_siblings(siblings, union)

        """ Composite to base and then blit from the base to the surface of the necessary siblings """
        # Make a base image to composite all sibling zImages onto.
        x, y, w, h = union
        res = (w, h)
        if res not in self._bases: self._bases[res] = UImage(width=w, height=h)
        base = self._bases[res]

        # Blit the parent's background to the base, if it is not fully obscured.
        if not (len(siblings) == 1 and self.isOpaque()) and decimateRect((0, 0, w, h), opaque_rects):
            self._parent.skin.image().cropTo(base, x, y, w, h)

        # Process each sibling in the list.
        atop = False
        for i in range(len(siblings)-1, -1, -1):
            sibling, overlap = siblings[i], overlaps[i]
            cx, cy, cw, ch = overlap.crop
            ix, iy = overlap.insert
            # Composite each sibling's own image onto the base image.
            sibling.zImage().cropTo(base, cx, cy, cw, ch, ix, iy)

            # Start rendering to the surface of self and any widgets atop once we've drawn up to the calling widget.
            if sibling == self: atop = True
            if atop and not (sibling != self and sibling.isOpaque()):
                final = sibling.scratchImage()
                base.cropTo(final, ix, iy, cw, ch, cx, cy)
                sibling.render(final, sibling.skin_offset)       # Render to surface of widget.

        self.bench += time() - start
        self.benches += 1
        if self.benches >= 100:
            print(f"{round(self.bench / 100, 5)}s per draw.")
            self.bench, self.benches = 0, 0


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
    def __init__(self, *args, **kwargs):
        kwargs["bg"] = "#6B6B6B"     # Neutral background color reduces visual pop-in.
        super().__init__(*args, **kwargs)

        self._img_state = 0
        self._enabled = False
        self.enable()

    @property
    def state(self): return self._img_state

    @property
    def enabled(self) -> bool : return self._enabled
    def enable(self):
        self.setState(0)
        self._enabled = True
    def disable(self): self._enabled = False


""" Imageable simply displays an image. """
class Imageable(Stateable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._skin.setBGColors('#6B6B6B')      # Eliminate interactive colors for simple image.

    def changeImage(self, img_number): self.setState(img_number)


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
            if pointIsInRect(event.x, event.y, child.geometry): return
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


class Labelable(Pushable):
    def __init__(self, *args, text:str="", font_pack:FontPack = None, **kwargs):

        # If no skin passed, use a fully transparent skin.
        if 'skin' in kwargs and kwargs['skin'] is None: kwargs['skin'] = Skin(UImage())

        # Ingest FontPack, while allowing overrides, but also maintaining linkage to source FontPack
        self._using = [0] * 8
        self._override_pack = FontPack()

        self._pack = font_pack if font_pack else FontPack()
        if "font" in kwargs:
            self._using[0] = 1
            self._override_pack.name = kwargs.pop("font")
        if "font_size" in kwargs:
            self._using[1] = 1
            self._override_pack.size = kwargs.pop("font_size")
        if "weight" in kwargs:
            self._using[2] = 1
            self._override_pack.weight = kwargs.pop("weight")
        if "color" in kwargs:
            self._using[3] = 1
            self._override_pack.color = kwargs.pop("color")
        if "drop_color" in kwargs:
            self._using[4] = 1
            self._override_pack.drop_color = kwargs.pop("drop_color")
        if "text_pos" in kwargs:
            self._using[5] = 1
            self._override_pack.text_pos = kwargs.pop("text_pos")
        if "drop_pos" in kwargs:
            self._using[6] = 1
            self._override_pack.drop_pos = kwargs.pop("drop_pos")
        if "anchor" in kwargs:
            self._using[7] = 1
            self._override_pack.anchor = kwargs.pop("anchor")

        self._packs = [self._pack, self._override_pack]

        self.text = text
        self._img_text, self._img_text_shadow = None, None
        super().__init__(*args, **kwargs)

    def setText(self, text:str):
        if text != self.text:
            if self._img_text: self.delete(self._img_text)      # Can this be done faster without the delete/create?
            if self._img_text_shadow: self.delete(self._img_text_shadow)
            self._img_text, self._img_text_shadow = None, None
            self.text = text
            self.redraw()

    def setFontPack(self, font_pack:FontPack):
        self._pack = font_pack
        self._using = [0] * 7

    def setFontAttributes(self, **kwargs):
        for kw in kwargs: self._override_pack.__setattr__(kw, kwargs[kw])

    def drawText(self, offset_x:int = 0, offset_y:int = 0):
        x, y = self._packs[self._using[5]].text_pos
        x += offset_x
        y += offset_y

        dx, dy = self._packs[self._using[6]].drop_offset
        dx += offset_x
        dy += offset_y

        color, drop_color = self._packs[self._using[3]].color, self._packs[self._using[4]].drop_color
        anchor = self._packs[self._using[7]].anchor

        # Invert behavior of offsets if right/bottom aligned.
        if 'e' in anchor: x = self.width - x
        if 's' in anchor: y = self.height - y

        # If text has not been rendered yet, create text layers.
        if drop_color is not None and self._img_text_shadow is None:
            self._img_text_shadow = self.create_text(x+dx, y+dy, text=self.text, fill=drop_color, font=self._tk_font,
                                                     anchor=anchor)
        if self._img_text is None:
            self._img_text = self.create_text(x, y, text=self.text, fill=color, font=self._tk_font, anchor=anchor)

    def render(self, image:UImage, xy_offset:tuple[int,int] = (0,0)):
        if xy_offset != self._last_offset:
            if self._img_text: self.delete(self._img_text)
            if self._img_text_shadow: self.delete(self._img_text_shadow)
            self._img_text, self._img_text_shadow = None, None
        super().render(image, xy_offset)
        self.drawText()

    def mouseOut(self, event):
        super().mouseOut(event)
        self.drawText()

    def mouseIn(self, event):
        super().mouseIn(event)
        self.drawText()

    def clicked(self, event):
        super().clicked(event)
        self.drawText()

    def mouseUp(self, event):
        super().mouseUp(event)
        self.drawText()

    def setState(self, state_index:int = 0):
        super().setState(state_index)
        self.drawText()

    @property
    def _tk_font(self):
        return (self._packs[self._using[0]].name, self._packs[self._using[1]].size, self._packs[self._using[2]].weight)


""" Toggleable stores a true/false state and redirects image() calls by index+_state_offset when true. This allows the
    skin to return states 0,1,2,3 for the False state of the Toggleable, and 4,5,6,7 for the True state. (Checkbox) """
class Toggleable(Pushable):
    def __init__(self, *args, state:bool=False, **kwargs):
        self._state_offset, self._toggle_state = 0, state
        super().__init__(*args, **kwargs)
        self.setTrue(state)

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
        self._state_offset = self._toggle_state * 4
        return self._toggle_state

    def setState(self, state_index:int = 0): super().setState(state_index + self._state_offset)


class Holdable(Pushable):
    def mouseOut(self, event):
        if self._clicking: self.moused_over = False
        else: super().mouseOut(None)

    def mouseUp(self, event):
        self._clicking = False
        self.grab_release()
        if self.moused_over: self.mouseIn(event)

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
        self._registerSiblings()
        self.move(x, y)


"""
A FakeCanvas is a tk.Text window configured to eliminate all text-features and provide a simple canvas. This is needed
because tkinter's tk.Canvas does not track/update its 'dirty' rectangle correctly. This issue of slow/wrong redraws
was solved in the Text widget, but nowhere else. So tk.Text is used as a render-floor for moving other widgets atop.
"""
class FakeCanvas(tk.Text):
    def __init__(self, parent, **kwargs):
        w = kwargs.pop('width') if 'width' in kwargs else 0
        h = kwargs.pop('height') if 'height' in kwargs else 0

        super().__init__(parent, bd=0, padx=0, pady=0, state="disabled", cursor="arrow", **kwargs)

        self.configure(bg=self.cget("bg"))
        self._img = self.image_create("end", image=UImage())

        # _placed prevents rendering instanced, but yet unplaced widgets.
        if self._placed:
            self._conform_size(w, h)
        else: self.after_idle(self._conform_size, w, h)     # Allows for fast-loading AND backup checking where needed.

    def configure(self, **kw):
        if "bg" in kw:      # Pass changes to bg through to the 'selectbackground' to maintain non-tk.Text() illusion.
            kw["selectbackground"] = kw["bg"]
        if "background" in kw:
            kw["selectbackground"] = kw["background"]
        super().configure(**kw)

    def render(self, image:UImage, xy_offset:tuple[int,int] = (0,0)):
        self.image_configure(self._img, image=image, padx=xy_offset[0], pady=xy_offset[1])

    # Tkinter's Text widgets are sized, by default, by character and line size. This fixes that fundamentally bad idea.
    def _conform_size(self, width:int, height:int):
        if self._placed and width > 0 and height > 0:
            self.place_configure(width=width, height=height, implied=True)


""" TextCanvas utilizes FakeCanvas to create an alternate widget-chain base. Other [widget]able types can be mixed-in
    with TextCanvas to create (slower) animation-friendly versions that have all the features of that [widget]able. """
class TextCanvas(Renderable, FakeCanvas): pass


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

        # Update geometry and move all children by the delta of x/y.
        self._geometry = (kwargs['x'], kwargs['y'], kwargs['width'] if 'width' in kwargs else self.width,
                                                    kwargs['height'] if 'height' in kwargs else self.height)

        delta_xy = self.x - self._last_geometry[0], self.y - self._last_geometry[1]
        if any(delta_xy):
            for child in self.getChildren():
                child.place_configure(x=child.x + delta_xy[0], y=child.y + delta_xy[1])
        self._last_geometry = self._geometry

    @property
    def skin(self): return self._parent.skin


""" Public Classes and IDE-Helper Definitions """
class Background(Backgroundable, TextCanvas):
    def __init__(self, parent, skin=None, **kwargs):
        super().__init__(parent, skin=skin, **kwargs)
class Image(Imageable, Siblingable, Canvas):
    def __init__(self, parent, skin=None, **kwargs):
        super().__init__(parent, skin=skin, **kwargs)
class Hover(Hoverable, Siblingable, Canvas):
    def __init__(self, parent, skin=None, **kwargs):
        super().__init__(parent, skin=skin, **kwargs)
class Button(Pushable, Siblingable, Canvas):
    def __init__(self, parent, skin=None, function=lambda:None, **kwargs):
        super().__init__(parent, function, skin=skin, **kwargs)
class InstantButton(Clickable, Siblingable, Canvas):
    def __init__(self, parent, skin=None, function=lambda:None, **kwargs):
        super().__init__(parent, function, skin=skin, **kwargs)
class RepeatButton(Repeatable, Siblingable, Canvas):
    def __init__(self, parent, skin=None, function=lambda:None, delay=150, init_delay=400, **kwargs):
        super().__init__(parent, function, skin=skin, delay=delay, init_delay=init_delay, **kwargs)
class Label(Labelable, Siblingable, Canvas):
    def __init__(self, parent, skin=None, text="", font_pack=None, function=lambda:None, **kwargs):
        super().__init__(parent, function, skin=skin, text=text, font_pack=font_pack, **kwargs)
class Checkbox(Toggleable, Siblingable, Canvas):
    def __init__(self, parent, skin=None, function=lambda:None, state=False, **kwargs):
        super().__init__(parent, function, state=state, skin=skin, **kwargs)
class Drag(Draggable, Siblingable, Canvas):
    def __init__(self, parent, skin=None, function=lambda:None, **kwargs):
        super().__init__(parent, function, skin=skin, **kwargs)
class Group(Groupable, Backgroundable, Siblingable, TextCanvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

# Specialized Widgets
class LoneDrag(LoneDraggable, Siblingable, Canvas):
    def __init__(self, parent, function=lambda:None, skin=None, **kwargs):
        super().__init__(parent, function, skin=skin, **kwargs)
class TroughButton(Repeatable, Siblingable, TextCanvas):
    def __init__(self, parent, function=lambda:None, skin=None, delay=150, init_delay=400, **kwargs):
        super().__init__(parent, function, skin=skin, delay=delay, init_delay=init_delay, **kwargs)

# Nested Widgets
class SliderHandle(LoneDrag):
    def __init__(self, parent, function, release_function:tuple|Callable=lambda:None, **kwargs):
        self._release_function = release_function
        super().__init__(parent, function, **kwargs)

    def mouseUp(self, event):
        super().mouseUp(event)
        self._call_function(self._release_function)

class Slider(Imageable, Siblingable, TextCanvas):
    def __init__(self, parent, trough_skin, handle_skin, active_function=lambda:None, release_function=lambda:None,
                 handle_width:int=None, handle_height:int=None,
                 start_percent:float = 0.0, **kwargs):

        super().__init__(parent, skin=trough_skin, **kwargs)
        self._handle = SliderHandle(self, active_function, release_function, skin=handle_skin, **kwargs)

        kwargs['width'], kwargs['height'] = handle_width, handle_height     # Replace width/height for handle instance.

        # Determine active axis and place handle accordingly.
        place_pos = list(self.size)
        if self.height > self.width:
            place_pos[0] = 0
            place_pos[1] = round(min(self.height - self._handle.height, place_pos[1] * min(1.0, max(0.0, start_percent))))
            self._active = 1
        else:
            place_pos[0] = round(min(self.width - self._handle.width, place_pos[0] * min(1.0, max(0.0, start_percent))))
            place_pos[1] = 0
            self._active = 0

        self._handle.place(x=place_pos[0], y=place_pos[1])

    def getPercent(self):
        return self._handle.location[self._active] / (self.size[self._active] - self._handle.size[self._active])

    def setPercent(self, percent:float):
        handle_pos = [0, 0]
        breadth = self.height - self._handle.height if self._active == 1 else self.width - self._handle.width
        handle_pos[self._active] = round(min(breadth, breadth * min(1.0, max(0.0, percent))))
        self._handle.place(x=handle_pos[0], y=handle_pos[1])

    def isHeld(self): return self._handle.isHeld()

    def enable(self):
        super().enable()
        try:
            self._handle.enable()
        except: pass
    def disable(self):
        super().disable()
        try:
            self._handle.disable()
        except: pass
