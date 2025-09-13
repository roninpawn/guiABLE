import tkinter as tk
from time import time
from typing import Optional, Callable

from guiABLE.skinnable import Skin, Skinnable, FilterSkin, BarSkin
from guiABLE.utilities import limitMove, rectsOverlap, rectUnion, fastComposite, fastCrop, getGeometry, pointIsInRect

"""
Siblingable adds sibling awareness & overlap tracking to Skinnable. (MRO sucks, true inheritance is less brittle.)  
"""
class Siblingable(Skinnable):
    def __init__(self, skin:Skin|FilterSkin|BarSkin):
        super().__init__(skin)
        self._siblings_atop, self._siblings_beneath = list(), list()     # Overlapping siblings, by below/above z-index.

    # Overlapping siblings track each other for the sake of compositing (faking transparency) during redraw.
    @property
    def siblingsBeneath(self): return self._siblings_beneath
    @property
    def siblingsAbove(self): return self._siblings_above
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

    # Override all attachment methods to track z-order through parent. (and report overlap with siblings if Siblingable)
    def place(self, **kwargs):
        super().place(**kwargs)
        self._bond()
    def pack(self, **kwargs):
        super().pack(**kwargs)
        self._bond()
    def grid(self, **kwargs):
        super().grid(**kwargs)
        self._bond()

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
            elif isinstance(sibling, tk.Canvas) and rectsOverlap(self.geometry, getGeometry(sibling)):
                if sibling in self._siblings_atop or sibling in self._siblings_beneath: sibling.dropSibling(self)
                sibling.trackSibling(self, above)
                if above: self._siblings_beneath.append(sibling)
                else: self._siblings_atop.append(sibling)

    def _bond(self):
        if isinstance(self, tk.Canvas):
            self.after_idle(self.parent.registerChild, self)
        self._findOverlappingSiblings(self.parent.children)


"""
    Baseable is the foundation of all guiABLE's widgets. It defines how to render images to the surface of the widget,
    and establishes the concept of state-tracking.
"""
class Baseable(Siblingable, tk.Canvas):
    def __init__(self, parent, skin=None, **kwargs):
        self._parent = parent
        self._enabled = False

        # Setting the background of widgets to a middle gray reduces the appearance of pop-in while loading...
        kwargs["bg"] = "gray42"     # ...amd widget bg colors aren't used in guiABLE. Bg colors are set through skins.

        Siblingable.__init__(self, skin)
        tk.Canvas.__init__(self, parent, highlightthickness=0, **kwargs)

        self.bind("<Configure>", self.refresh)

        self.bench, self.benches = 0, 0

        self.dirty = True
        self._z_state = None
        self._img, self._z_img = None, None
        self._img_state = 0
        self._drop_list = set()

        self.enable()

    @property
    def parent(self): return self._parent
    @property
    def image(self): return self._img
    @property
    def state(self): return self._img_state

    def redraw(self):
        # If the skin that this widget uses has changed, all of its children must redraw.
        self.setState(self._img_state)
        if self.dirty:
            for child in self._children: child.redraw()
            self.dirty = False

    def render(self, image:tk.PhotoImage, x:int = 0, y:int = 0):
        self._img = image
        self.delete("all")
        self.create_image(x, y, image=image, anchor="nw")

    def enable(self):
        self.setState(self._img_state)
        self._enabled = True

    @property
    def enabled(self) -> bool : return self._enabled
    def disable(self): self._enabled = False

    def setState(self, state_index:int = 0):
        start = time()

        # If widget lacks geometry (has not fully spawned) wait until it has.
        x, y, w, h = self.geometry
        if w < 1 and h < 1:
            self.after_idle(self.redraw)
            return

        self._img_state = state_index

        # Handle opaqueness vs transparency
        if self._skin.usesBgColors():       # Opaque skips siblings beneath it.
            siblings = [self]
            #bg_color = self._skin.bgColor(self._img_state)
        else:       # Transparent inherits parent's bg color if parent isn't using an image.
            siblings = list(self._siblings_beneath)
            siblings.append(self)

        # Add all atop-siblings if any one of them is transparent.
        for sibling in self._siblings_atop:
            if not sibling.skin.usesBgColors():
                siblings.extend(self._siblings_atop)
                break

        # If any sibling has below-siblings, unknown to the caller, add them to the job, beneath that sibling.
        # (Ensures all lower widgets are included in final composite -- No disappearing siblings on hover.)
        out_siblings = []
        for sibling in siblings:
            for sb in sibling.siblingsBeneath:
                if sb not in siblings:
                    out_siblings.append(sb)
            out_siblings.append(sibling)

        self.compositeUnion(out_siblings)

        self.bench += time() - start
        self.benches += 1
        if self.benches >= 100:
            print(f"{round(self.bench / 100, 5)}s per draw.")
            self.bench, self.benches = 0, 0

    def compositeUnion(self, siblings:list):
        u_rect = self.geometry
        for sibling in siblings: u_rect = rectUnion(u_rect, sibling.geometry)
        x, y, w, h = u_rect

        base = tk.PhotoImage(width=w, height=h)
        fastCrop(base, self.parent.skin.image(), *self.parent.skin.resolution(), x, y, w, h)

        # Draw each layer to a base image and then crop from that base to each widget's surface, as we go.
        atop = False
        for sibling in siblings:
            if sibling == self: atop = True
            sx, sy, sw, sh = sibling.geometry
            dx, dy = sx-x, sy-y
            fastComposite(base, w, h, sibling.zImage(), dx, dy, sw, sh)
            final = sibling.scratchImage()
            if atop:
                fastCrop(final, base, w, h, dx, dy, sw, sh)
                sibling.render(final)
            if not rectsOverlap(self.geometry, sibling.geometry):
                sibling.dropSibling(self)
                self.dropSibling(sibling)

    # The ZImage() is a persistent render of what the widget looks like on its own. Only updated if something changed.
    def zImage(self) -> tk.PhotoImage:
        if self._z_state != self._img_state or self.dirty:
            _, _, w, h = self.geometry
            self._z_img = tk.PhotoImage(width=w, height=h)
            fastComposite(self._z_img, w, h, self._skin.image(self._img_state), 0, 0,
                          *self._skin.resolution(self._img_state))
            self._z_state = self._img_state
            self.dirty = False
        return self._z_img


""" Imageable simply displays an image. """
class Imageable(Baseable):
    def __init__(self, parent, skin=None, **kwargs):
        super().__init__(parent, skin, **kwargs)
        self._skin.setBGColors('gray')      # Eliminate interactive colors for simple image.

    def changeImage(self, img_number): self.setState(img_number)

    def disable(self):
        super().disable()
        self.setState(3)


""" Hoverable adds mouse-over awareness and triggers state-change/redraws on mouse-in and mouse-out. """
class Hoverable(Baseable):
    def __init__(self, parent, skin=None, **kwargs):
        self.moused_over = False
        super().__init__(parent, skin, **kwargs)

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
        self.redraw()

    def disable(self):
        super().disable()
        self.unbind("<Enter>")
        self.unbind("<Leave>")
        self.setState(3)


""" Clickable adds left-click awareness and executes a passed function on mouse-down. (Instant-click button) """
class Clickable(Hoverable):
    def __init__(self, parent, function:tuple|Callable=lambda: None, skin=None, **kwargs):
        self.function = function
        super().__init__(parent, skin, **kwargs)

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
    def __init__(self, parent, function=lambda: None, skin=None, **kwargs):
        self._clicking = False
        super().__init__(parent, function, skin, **kwargs)

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
    def __init__(self, parent, function=lambda: None, skin=None, text="", text_pos=(0,0), font="Times", color="gray",
                 drop_pos=(0, 0), drop_color="black", **kwargs):
        self.text, self.text_pos, self.color, self.font = text, text_pos, color, font
        self.drop_pos, self.drop_color, = drop_pos, drop_color
        super().__init__(parent, function, skin, **kwargs)

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
    def __init__(self, parent, state:bool=False, function=lambda: None, skin:Skin = None, **kwargs):
        self._state_offset, self._toggle_state = 0, state
        super().__init__(parent, function, skin, **kwargs)
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


""" Holdable is a Pushable that triggers its function instantly, and then again after every n milliseconds. It supports
    a first-click, initial-delay that can be longer or shorter than the continuous delay thereafter."""
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


class Repeatable(Holdable):
    def __init__(self, parent, function=lambda: None, skin=None, delay=150, init_delay=400, **kwargs):
        super().__init__(parent, function, skin, **kwargs)
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


class LoneDraggable(Holdable):
    def __init__(self, parent, function=lambda:None, skin=None, **kwargs):
        super().__init__(parent, function, skin, **kwargs)
        self._last_geometry = (None, None, None, None)
        self._bounds = None

        self._x_origin, self._y_origin = 0, 0
        #self.after_idle(self._refresh)

    def setBounds(self, x1, y1, x2, y2): self._bounds = (x1, y1, x2, y2)

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
        x = limitMove(x, w, self._bounds[0], self._bounds[2])
        y = limitMove(y, h, self._bounds[1], self._bounds[3])

        self._geometry = (x, y, w, h)
        if self._last_geometry != self._geometry:
            self.place_configure(x=x, y=y)
            self._last_geometry = self._geometry
            self.redraw()
            self.function()

    def _refresh(self, event=None):
        super()._refresh(event)
        if self._bounds is None and self.parent.geometry[2:] != (0, 0):
            self._bounds = (0, 0, *self.parent.geometry[2:])


""" Draggable is dragged by the mouse while left click is held. It remains within its parent's boundaries by default, 
    but its bounds can be overridden using setBounds(). For correct redraw, moving objects like Draggable must be drawn
    atop a Canvasable. Otherwise, tkinter's stale draw rectangle issue creates ghosting/visual stretching. """
class Draggable(LoneDraggable):
    def __init__(self, parent, function=lambda:None, skin=None, **kwargs):
        super().__init__(parent, function, skin, **kwargs)
        self._all_siblings_atop, self._all_siblings_beneath = list(), list()

    def clicked(self, event):
        super().clicked(event)
        self._splitAllSiblings()

    def mouseDrag(self, event=None):
        super().mouseDrag(event)
        self._populateOverlappingSiblings(self._siblings_atop, self._all_siblings_atop, False)
        self._populateOverlappingSiblings(self._siblings_beneath, self._all_siblings_beneath, True)

    def _splitAllSiblings(self):
        atop = False
        self._all_siblings_atop, self._all_siblings_beneath = set(), set()
        for sibling in self.parent.getChildren():
            if sibling is self: atop = True
            else:
                if atop: self._all_siblings_atop.add(sibling)
                else: self._all_siblings_beneath.add(sibling)

    def _populateOverlappingSiblings(self, output_list:list, source_list:list, atop:bool):
        output_list.clear()
        # Using the union of the last position and current position ensures final redraw of just-exited siblings.
        movement_union = rectUnion(self._geometry, self._last_geometry)
        for sibling in source_list:
            if rectsOverlap(movement_union, sibling.geometry):
                output_list.append(sibling)
                sibling.trackSibling(self, atop)

