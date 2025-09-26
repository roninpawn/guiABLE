import tkinter as tk
from time import time
from typing import Callable

from guiABLE.skinnable import Skinnable
from guiABLE.utilities import limitMove, rectsOverlap, rectUnion, getGeometry, pointIsInRect, fastBlit

""" Siblingable is a mixin that provides parent/sibling awareness & overlap tracking.  """
class Siblingable:
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.bind("<Map>", self._bond)

        self._parent = parent
        self._siblings_atop, self._siblings_beneath = list(), list()     # Overlapping siblings, by below/above z-index.

    @property
    def parent(self): return self._parent

    # Overlapping siblings track each other for the sake of compositing (faking transparency) during redraw.
    @property
    def siblingsBeneath(self): return self._siblings_beneath
    @property
    def siblingsAtop(self): return self._siblings_atop
    def trackSibling(self, sibling, z_above: bool):
        if z_above:
            if sibling not in self._siblings_atop:
                self._siblings_atop.append(sibling)
            if sibling in self._siblings_beneath:
                self._siblings_beneath.remove(sibling)
        else:
            if sibling not in self._siblings_beneath:
                self._siblings_beneath.append(sibling)
            if sibling in self._siblings_atop:
                self._siblings_atop.remove(sibling)
    def dropSibling(self, sibling):
        if sibling in self._siblings_atop: self._siblings_atop.remove(sibling)
        elif sibling in self._siblings_beneath: self._siblings_beneath.remove(sibling)

    # Override methods that change z-index, to track and report changes to all interested parties.
    def lift(self, above=None):
        tk.Misc.lift(self, above)
        # TODO: All these after_idle()s are possibly the problem with lift/lowering.
        self.after_idle(self.parent._raiseChildIndex, self, above)
        self.after_idle(self._findOverlappingSiblings, self.parent.getChildren())
    def lower(self, below=None):
        tk.Misc.lower(self, below)
        self.after_idle(self.parent._lowerChildIndex, self, below)
        self.after_idle(self._findOverlappingSiblings, self.parent.getChildren())

    # Find overlapping siblings and store them / register with them, for future tracking.
    def _findOverlappingSiblings(self, siblings_list):
        above = True        # z-order state of self in reference to sibling
        for sibling in siblings_list:
            if sibling is self: above = False
            elif isinstance(sibling, Siblingable) and rectsOverlap(self._geometry, sibling.geometry):
                if sibling in self._siblings_atop or sibling in self._siblings_beneath: sibling.dropSibling(self)
                sibling.trackSibling(self, above)
                if above: self._siblings_beneath.append(sibling)
                else: self._siblings_atop.append(sibling)

    def _bond(self, event=None):
        if isinstance(self, tk.Canvas): self.after_idle(self._parent.registerChild, self)
        self._findOverlappingSiblings(self._parent.getChildren())


""" Baseable defines how to render images to the surface of the tk.Canvas. """
class Baseable(Skinnable, Siblingable, tk.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, highlightthickness=0, **kwargs)
        self.bind("<Configure>", self._refresh)

        self.bench, self.benches = 0, 0

        self.dirty = True
        self._z_state, self._z_img = None, None

    def redraw(self):
        # If the skin that this widget uses has changed, all of its children must redraw.
        self.setState(self._img_state)
        if self.dirty:
            for child in self._children: child.redraw()
            self.dirty = False

    def render(self, image:tk.PhotoImage, x:int = 0, y:int = 0):
        self.delete("all")
        self.create_image(x, y, image=image, anchor="nw")

    # The ZImage() is a persistent render of what the widget looks like on its own. Only updated if something changed.
    def zImage(self) -> tk.PhotoImage:
        if self._z_state != self._img_state or self.dirty:
            w, h = self.size
            self._z_img = tk.PhotoImage(width=w, height=h)
            iw, ih = self._skin.resolution(self._img_state)
            fastBlit(self._z_img, w, h, self._skin.image(self._img_state), iw, ih, 0, 0, iw, ih)

            self._z_state = self._img_state
            self.dirty = False
        return self._z_img

    def setState(self, state_index:int = 0):
        start = time()

        self._img_state = state_index

        # Handle opaqueness vs transparency
        if self._skin.usesBgColors():       # Opaque skips siblings beneath it.
            siblings = [self]
        else:
            siblings = list(self._siblings_beneath)
            siblings.append(self)

        # Add all atop-siblings if any one of them is transparent.
        for sibling in self._siblings_atop:
            if not sibling.skin.usesBgColors():
                siblings.extend(self._siblings_atop)
                break

        # If any sibling has siblings below them, unknown to the caller, add them to the job.
        # (Ensures all lower widgets are included in final composite -- No disappearing siblings on hover.)
        out_siblings = []
        for sibling in siblings:
            for sb in sibling.siblingsBeneath:
                if sb not in siblings:
                    out_siblings.append(sb)
            out_siblings.append(sibling)

        self._compositeUnion(out_siblings)

        self.bench += time() - start
        self.benches += 1
        if self.benches >= 100:
            print(f"{round(self.bench / 100, 5)}s per draw.")
            self.bench, self.benches = 0, 0

    def _compositeUnion(self, siblings:list):
        u_rect = self.geometry
        for sibling in siblings: u_rect = rectUnion(u_rect, sibling.geometry)
        x, y, w, h = u_rect

        # TODO: Test whether its faster to maintain a scratch the size of the parent, or make a new image each time.
        base = tk.PhotoImage(width=w, height=h)
        iw, ih = self._parent.skin.resolution()
        fastBlit(base, w, h, self._parent.skin.image(), iw, ih, 0, 0, w, h, x, y)

        # Draw each layer to a base image and then crop from that base to each widget's surface, as we go.
        atop = False
        for sibling in siblings:
            if sibling == self: atop = True
            sx, sy, sw, sh = sibling.geometry
            dx, dy = sx-x, sy-y
            fastBlit(base, w, h, sibling.zImage(), sw, sh, dx, dy, sw, sh)
            final = sibling.scratchImage()
            if atop:
                fastBlit(final, sw, sh, base, w, h, 0, 0, sw, sh, dx, dy)
                sibling.render(final)
            if not rectsOverlap(self.geometry, sibling.geometry):
                sibling.dropSibling(self)
                self.dropSibling(sibling)


""" Imageable simply displays an image. """
class Imageable:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._skin.setBGColors('gray')      # Eliminate interactive colors for simple image.

    def changeImage(self, img_number): self.setState(img_number)


""" Widgetable establishes the base of the widget chain, providing basic access methods and on/off states. """
class Widgetable:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._enabled = False

        kwargs["bg"] = "gray42"     # Neutral background color reduces visual pop-in.

        self._img_state = 0
        self.enable()

    @property
    def state(self): return self._img_state

    @property
    def enabled(self) -> bool : return self._enabled
    def enable(self):
        self.setState(0)
        self._enabled = True
    def disable(self): self._enabled = False


""" Hoverable adds mouse-over awareness and triggers state-change/redraws on mouse-in and mouse-out. """
class Hoverable(Widgetable):
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
    def __init__(self, *args, text="", text_pos=(0,0), font="Times", color="gray", drop_pos=(0, 0), drop_color="black",
                 **kwargs):
        self.text, self.text_pos, self.color, self.font = text, text_pos, color, font
        self.drop_pos, self.drop_color, = drop_pos, drop_color
        super().__init__(*args, **kwargs)

    def drawText(self):
        x, y = self.text_pos
        dx, dy = self.drop_pos
        self.create_text(x + dx, y + dy, text=self.text, fill=self.drop_color, font=self.font, anchor="nw")
        self.create_text(x, y, text=self.text, fill=self.color, font=self.font, anchor="nw")

    def render(self, image:tk.PhotoImage, x:int = 0, y:int = 0):
        super().render(image, x, y)
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
        self.after_idle(self.setTrue, state)

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
        self.redraw()
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

    def clicked(self, event):
        super().clicked(event)
        if self.function is not None:
            self.after(self.init_delay, self._keepClicking)

    def _keepClicking(self):
        if self._clicking:
            self.function()
            self.after(self.delay, self._keepClicking)


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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._all_siblings_atop, self._all_siblings_beneath = list(), list()

    def clicked(self, event):
        super().clicked(event)
        self._splitAllSiblings()

    def mouseDrag(self, event=None):
        x, y, w, h = self._geometry
        x = event.x - self._x_origin + x
        y = event.y - self._y_origin + y
        new_geom = (x, y, w, h)

        self._populateOverlappingSiblings(self._siblings_atop, self._all_siblings_atop, new_geom, False)
        self._populateOverlappingSiblings(self._siblings_beneath, self._all_siblings_beneath, new_geom, True)
        self.move(x, y)

    def _splitAllSiblings(self):
        atop = False
        self._all_siblings_atop, self._all_siblings_beneath = set(), set()
        for sibling in self._parent.getChildren():
            if sibling is self: atop = True
            else:
                if atop: self._all_siblings_atop.add(sibling)
                else: self._all_siblings_beneath.add(sibling)

    def _populateOverlappingSiblings(self, output_list:list, source_list:list, geom:tuple[int,int,int,int], atop:bool):
        output_list.clear()
        # Using the union of the last position and current position ensures final redraw of just-exited siblings.
        movement_union = rectUnion(geom, self._geometry)
        for sibling in source_list:
            if rectsOverlap(movement_union, sibling.geometry):
                output_list.append(sibling)
                sibling.trackSibling(self, atop)


# 3 types of Buttons could be an option under a Button class that returns an object of the correct type.
# 2 types of Drag could be an option...
class Hover(Hoverable, Baseable):
    def __init__(self, parent, skin=None, **kwargs):
        super().__init__(parent, skin=skin, **kwargs)
class InstantButton(Clickable, Baseable):
    def __init__(self, parent, function=lambda:None, skin=None, **kwargs):
        super().__init__(parent, function, skin=skin, **kwargs)
class NormalButton(Pushable, Baseable):
    def __init__(self, parent, function=lambda:None, skin=None, **kwargs):
        super().__init__(parent, function, skin=skin, **kwargs)
class Label(Labelable, Baseable):
    def __init__(self, parent, text="", font=("Arial", 12, "bold"), skin=None, function=lambda:None, **kwargs):
        super().__init__(parent, function, skin=skin, text=text, font=font, **kwargs)
class Checkbox(Toggleable, Baseable):
    def __init__(self, parent, state=False, function=lambda:None, skin=None, **kwargs):
        super().__init__(parent, function, state=state, skin=skin, **kwargs)
class RepeatButton(Repeatable, Baseable):
    def __init__(self, parent, function=lambda:None, skin=None, delay=150, init_delay=400, **kwargs):
        super().__init__(parent, function, skin=skin, delay=delay, init_delay=init_delay, **kwargs)
class LoneDrag(LoneDraggable, Baseable):
    def __init__(self, parent, function=lambda:None, skin=None, **kwargs):
        super().__init__(parent, function, skin=skin, **kwargs)
class Drag(Draggable, Baseable):
    def __init__(self, parent, function=lambda:None, skin=None, **kwargs):
        super().__init__(parent, function, skin=skin, **kwargs)
