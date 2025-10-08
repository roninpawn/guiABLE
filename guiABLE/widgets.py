import tkinter as tk
from time import time
from typing import Callable

from pygments.lexers import q

from guiABLE.skinnable import Skinnable, FilterSkin, SingleSkin, Measurable
from guiABLE.utilities import limitMove, rectsOverlap, rectUnion, pointIsInRect, getOverlap, decimateRect, \
    rectIntersect, rectsUnion
from guiABLE.uimage import UImage

""" Siblingable is a mixin that provides parent/sibling awareness & overlap tracking.  """
class Siblingable:
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.bind("<Map>", self._bond)

        self._parent = parent
        self._siblings = []

    @property
    def parent(self): return self._parent

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


""" Canvas defines how to render images to the surface of the tk.Canvas to support parent & sibling transparency. """
class Canvas(Skinnable, Siblingable, tk.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, highlightthickness=0, **kwargs)

        self.bench, self.benches = 0, 0

        self.dirty = True
        self._z_state, self._z_img = None, None
        self._img_state = 0
        self._img = self.create_image(0, 0, anchor="nw")

    def redraw(self):
        # If the skin that this widget uses has changed, all of its children must redraw.
        self.setState(self._img_state)
        if self.dirty:
            for child in self._children: child.redraw()
            self.dirty = False

    def render(self, image:UImage):
        self.itemconfig(self._img, image=image)

    # The ZImage() is a persistent render of what the widget looks like on its own. Only updated if something changed.
    def zImage(self) -> UImage:
        if self._z_state != self._img_state or self.dirty:
            self._z_img = self._skin.image(self._img_state).crop()
            self._z_state = self._img_state
            self.dirty = False
        return self._z_img

    def setState(self, state_index:int = 0):
        start = time()
        self._img_state = state_index

        union = rectUnion(self._geometry, self._last_geometry)

        """ Reduce union and siblings to only what is visible and necessary to draw. """
        # Reduce union to the visible boundaries of the caller's parent. (Don't draw what is off screen.)
        if isinstance(self.parent, Measurable): union = rectIntersect(union, (0, 0, *self.parent.size))
        if union is None: return

        # Cull caller's siblings by overlap and visibility, and generate a list of any opaque-sibling's geometries.
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
        base = UImage(width=w, height=h)

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
            if atop:
                final = sibling.scratchImage()
                base.cropTo(final, ix, iy, cw, ch, cx, cy)
                sibling.render(final)       # Render to surface of widget.

        self.bench += time() - start
        self.benches += 1
        if self.benches >= 100:
            print(f"{round(self.bench / 100, 5)}s per draw.")
            self.bench, self.benches = 0, 0

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
                    for t_ract in trans_rects:
                        if rectsOverlap(t_ract, local_overlap): break
                    else: continue      # Dont draw opaque widgets that do not have a transparent widget above them.
                else: trans_rects.append(local_overlap)
                if isinstance(sib, tk.Frame): continue       # Don't draw container widgets.

            new_siblings.append(sib)
            overlaps.append(overlap)
        return new_siblings, overlaps, opaque_rects


"""
A Backgroundable is a simple, static, one-image canvas to serve as the stage for attaching widgets. 
"""
class Backgroundable:
    def __init__(self, *args, **kwargs):
        kwargs["bg"] = "gray42"
        super().__init__(*args, **kwargs)

    @classmethod
    def fromPath(cls, parent, width:int, height:int, image_path:str, **kwargs):
        bg_able = cls(parent, width, height, SingleSkin(image_path), **kwargs)
        return bg_able

    @classmethod
    def fromImage(cls, parent, width:int, height:int, image:UImage, **kwargs):
        bg_able = cls(parent, width, height, SingleSkin.fromImage(image), **kwargs)
        return bg_able


""" Imageable simply displays an image. """
class Imageable:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._skin.setBGColors('gray42')      # Eliminate interactive colors for simple image.

    def changeImage(self, img_number): self.setState(img_number)


""" Widgetable establishes the base of the widget chain, providing basic access methods and on/off states. """
class Stateable:
    def __init__(self, *args, **kwargs):
        kwargs["bg"] = "gray42"     # Neutral background color reduces visual pop-in.
        super().__init__(*args, **kwargs)

        self._img_state = 0
        self._enabled = False
        self.enable()

    @property
    def state(self): return self._img_state
    def isOpaque(self): return  self.skin.resolution(self.state) == self.size and \
                               (self.skin.usesBgColors() or self.skin.isOpaque(self.state))

    @property
    def enabled(self) -> bool : return self._enabled
    def enable(self):
        self.setState(0)
        self._enabled = True
    def disable(self): self._enabled = False


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
        self._call_function()

    def mouseUp(self, event):
        self.mouseIn(event) if self.moused_over else self.mouseOut(event)

    def enable(self):
        super().enable()
        self.bind("<Button-1>", self.clicked)
        self.bind("<ButtonRelease-1>", self.mouseUp)

    def disable(self):
        super().disable()
        self.unbind("<Button-1>")
        self.unbind("<ButtonRelease-1>")

    def _call_function(self):
        if self.function is not None:
            if callable(self.function): self.function()
            elif len(self.function):
                args = []
                for arg in self.function[1:]:
                    args.append(arg()) if callable(arg) else args.append(arg)
                self.function[0](*args) if len(self.function) > 1 else self.function[0]()


""" Pushable is a Clickable that executes its function on when the left mouse button is released. (Normal button) """
class Pushable(Clickable):
    def __init__(self, *args, **kwargs):
        self._clicking = False
        super().__init__(*args, **kwargs)

    def clicked(self, event):
        self._clicking = True
        self.setState(2)

    def mouseUp(self, event):
        self._clicking = False
        super().mouseUp(event)
        if self.moused_over:
            self.function()

    def mouseIn(self, event):
        if not self._clicking:
            super().mouseIn(event)
        else:
            self.moused_over = True
            self.setState(2)


class Labelable(Pushable):
    def __init__(self, *args, text="", text_pos=(0,0), font="Times", color="gray", drop_pos=(2, 2), drop_color="gray25",
                 **kwargs):
        self.text, self.text_pos, self.color, self.font = text, text_pos, color, font
        self.drop_pos, self.drop_color, = drop_pos, drop_color
        self._img_text, self._img_text_shadow = None, None
        super().__init__(*args, **kwargs)

    def drawText(self):
        x, y = self.text_pos
        dx, dy = self.drop_pos

        # If text has not been rendered yet, create text layers.
        if self._img_text_shadow is None:
            self._img_text_shadow = self.create_text(x + dx, y + dy, text=self.text, fill=self.drop_color,
                                                     font=self.font, anchor="nw")
        if self._img_text is None:
            self._img_text = self.create_text(x, y, text=self.text, fill=self.color, font=self.font, anchor="nw")

    def render(self, image:UImage):
        super().render(image)
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


""" Toggleable stores a true/false state and redirects image() calls by index+_state_offset when true. This allows the
    skin to return states 0,1,2,3 for the False state of the Toggleable, and 4,5,6,7 for the True state. (Checkbox) """
class Toggleable(Pushable):
    def __init__(self, *args, state:bool=False, **kwargs):
        self._state_offset, self._toggle_state = 0, state
        super().__init__(*args, **kwargs)
        self.setTrue(state)

    def mouseUp(self, event):
        self._clicking = False
        if self.moused_over:
            self.setTrue(not self._toggle_state)
            self._call_function()
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
        if self.moused_over: self.mouseIn(event)

    def clicked(self, event):
        super().clicked(event)
        self.function()


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
            self.function()
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
        self.setState(2)

    def mouseDrag(self, event):
        x = event.x - self._x_origin + self._geometry[0]
        y = event.y - self._y_origin + self._geometry[1]
        self.move(x, y)

    def move(self, x:int, y:int):
        w, h = self._geometry[2:]
        bbox = (0, 0, *self.parent.geometry[2:]) if self._bounds is None else self._bounds
        x = limitMove(x, w, bbox[0], bbox[2])
        y = limitMove(y, h, bbox[1], bbox[3])

        self._geometry = (x, y, w, h)
        if self._last_geometry != self._geometry:
            self.place_configure(x=x, y=y)
            self.function()


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
    def __init__(self, parent, width:int, height:int, **kwargs):
        super().__init__(parent, bd=0, padx=0, pady=0, state="disabled", cursor="arrow", **kwargs)

        self.configure(bg=self.cget("bg"))
        self.place_configure(width=width, height=height)

    def configure(self, **kw):
        if "bg" in kw:      # Pass changes to bg through to the 'selectbackground' to maintain non-tk.Text() illusion.
            kw["selectbackground"] = kw["bg"]
        if "background" in kw:
            kw["selectbackground"] = kw["background"]
        super().configure(**kw)

    def render(self, image:UImage, pad_x:int=0, pad_y:int=0):
        self.configure(state="normal")
        self.delete(1.0, "end")
        self.image_create("end", image=image, padx=pad_x, pady=pad_y)
        self.configure(state="disabled")


""" TextCanvas utilizes FakeCanvas to create an alternate widget-chain base. Other [widget]able types can be mixed-in
    with TextCanvas to create an animation-friendly floor, that has all the features of that [widget]able. As a floor-
    widget, TextCanvas does not provide a transparent view of its parent. It is meant to be the visual bottom. """
class TextCanvas(Skinnable, FakeCanvas):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self._img_state = 0
        self._parent = parent

        self.bench, self.benches = 0, 0

    @property
    def parent(self): return self._parent

    def setState(self, state_index:int = 0):
        start = time()

        self._img_state = state_index

        img_size = self._skin.resolution(0)
        canvas_size = self._geometry[2:]

        if img_size != (0,0) and img_size != canvas_size:
            self._skin = FilterSkin(self._skin, crop=(0, 0, *canvas_size) )
            self.dirty = True

        self.render(self._skin.image(self._img_state))

        self.bench += time() - start
        self.benches += 1
        if self.benches >= 100:
            print(f"{round(self.bench / 100, 5)}s per draw. (TextCanvas)")
            self.bench, self.benches = 0, 0

    def redraw(self):
        self.setState(self._img_state)
        if self.dirty:
            for child in self._children: child.redraw()
            self.dirty = False


""" Public Classes and IDE-Helper Definitions """
class Background(Backgroundable, TextCanvas):
    def __init__(self, parent, width:int, height:int, skin:SingleSkin=None, **kwargs):
        super().__init__(parent, width, height, skin=skin, **kwargs)
class Hover(Hoverable, Canvas):
    def __init__(self, parent, skin=None, **kwargs):
        super().__init__(parent, skin=skin, **kwargs)
class Button(Pushable, Canvas):
    def __init__(self, parent, skin=None, function=lambda:None, **kwargs):
        super().__init__(parent, function, skin=skin, **kwargs)
class InstantButton(Clickable, Canvas):
    def __init__(self, parent, skin=None, function=lambda:None, **kwargs):
        super().__init__(parent, function, skin=skin, **kwargs)
class RepeatButton(Repeatable, Canvas):
    def __init__(self, parent, skin=None, function=lambda:None, delay=150, init_delay=400, **kwargs):
        super().__init__(parent, function, skin=skin, delay=delay, init_delay=init_delay, **kwargs)
class Label(Labelable, Canvas):
    def __init__(self, parent, skin=None, text="", font=("Arial", 12, "bold"), function=lambda:None, **kwargs):
        super().__init__(parent, function, skin=skin, text=text, font=font, **kwargs)
class Checkbox(Toggleable, Canvas):
    def __init__(self, parent, skin=None, function=lambda:None, state=False, **kwargs):
        super().__init__(parent, function, state=state, skin=skin, **kwargs)
class Drag(Draggable, Canvas):
    def __init__(self, parent, skin=None, function=lambda:None, **kwargs):
        super().__init__(parent, function, skin=skin, **kwargs)

# Specialized Widgets
class LoneDrag(LoneDraggable, Canvas):
    def __init__(self, parent, function=lambda:None, skin=None, **kwargs):
        super().__init__(parent, function, skin=skin, **kwargs)
class TroughButton(Repeatable, TextCanvas):
    def __init__(self, parent, function=lambda:None, skin=None, delay=150, init_delay=400, **kwargs):
        super().__init__(parent, function, skin=skin, delay=delay, init_delay=init_delay, **kwargs)
