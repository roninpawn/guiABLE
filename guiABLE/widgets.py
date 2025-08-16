import tkinter as tk
from time import time
from typing import Optional

from guiABLE.skinnable import Skin, Skinnable
from guiABLE.utilities import (updateHover, limitMove, getGeometry, cropImage, rectsOverlap, getOverlap, rectUnion,
                               fastComposite, copySubRect)


class Baseable(Skinnable, tk.Canvas):
    def __init__(self, parent, skin=None, **kwargs):
        Skinnable.__init__(self, skin)
        tk.Canvas.__init__(self, parent, highlightthickness=0, **kwargs)
        self._enabled = False
        self._drop_list = set()
        self.bench, self.benches = 0, 0

        self.enable()

    @property
    def enabled(self) -> bool : return self._enabled
    def enable(self): self._enabled = True
    def disable(self): self._enabled = False

    @property
    def parent(self): return self.master
    @property
    def image(self): return self._img
    @property
    def state(self): return self._img_state

    def redraw(self,):
        self._geometry = getGeometry(self)
        self.setState(self._img_state)

    def setState(self, state_index:int = 0):
        start = time()
        # If widget lacks geometry (has not fully spawned) wait until it has.
        x, y, w, h = self.geometry
        if w <= 1 and h <= 1:
            self.after_idle(lambda : self.redraw())
            return

        self._img_state = state_index
        bg_color = self._skin.bg(self._img_state)

        for sibling in self._siblings_atop:
            if not sibling.skin.usesBgColors():
                self.compositeUnion()
                break
        else:
            # If skin has no images. Only using bg_colors. (no widget transparency)
            if self._skin.hasImages():
                layers, base = [], None
                w, h = self.geometry[2:]

                # If skin has images but composites atop bg_colors. (no widget transparency)
                if self._skin.usesBgColors():
                    base = tk.PhotoImage(width=w, height=h)

                # If skin has images and declares no background color use. (widget may have transparency)
                else:
                    bg_color = self.master.skin.bg()
                    # If widget's parent has no images, simply use its background color for a base.
                    if not self.master.skin.hasImages():
                        base = tk.PhotoImage(width=w, height=h)
                    # If parent is using an image, crop widget's current geometry from it as the base for compositing.
                    else:
                        base = cropImage(self.master.skin.image(), x, y, w, h)

            # === SIBLINGS BENEATH ===
                # Detect overlap with siblings and composite any to base. Drop siblings that are nolonger touching.
                    for sibling in self._siblings_beneath:
                        if overlap := getOverlap(self.geometry, sibling.geometry):
                            ox, oy = overlap.insert
                            ow, oh = overlap.crop[2:]
                            fastComposite(base, w, h, cropImage(sibling.zImage, *overlap.crop), ox, oy, ow, oh)
                            if sibling in self._drop_list: self._drop_list.remove(sibling)
                        else: self._drop_list.add(sibling)
                # Finish the composite by adding self to the top.
                new_top = self._skin.image(state_index)
                fastComposite(base, w, h, new_top, 0, 0, new_top.width(), new_top.height())

                # Render the state.
                self.render(base)

        self.configure(bg=bg_color)

        self.bench += time() - start
        self.benches += 1
        if self.benches >= 100:
            print(self.bench)
            self.bench, self.benches = 0, 0

    def compositeUnion(self):
        u_siblings = (list(self._siblings_beneath))
        u_siblings.append(self)
        u_siblings.extend(list(self._siblings_atop))

        u_rect = self.geometry
        for sibling in u_siblings:
            u_rect = rectUnion(u_rect, sibling.geometry)
        x, y, w, h = u_rect
        # TODO Order siblings from lowest to highest?
        # TODO Purge siblings that nolonger touch. Here, though? idk.

        base = cropImage(self.master.skin.image(), x, y, w, h) if self.master.skin.hasImages() else tk.PhotoImage(width=w, height=h)

        # Draw each layer to a base image and then crop from that base to each widget's surface, as we go.
        for sibling in u_siblings:
            sx, sy, sw, sh = sibling.geometry
            nx, ny = sx-x, sy-y
            fastComposite(base, w, h, sibling.zImage, nx, ny, sw, sh)
            sibling.render(cropImage(base, nx, ny, sw, sh))

    def render(self, image:tk.PhotoImage, x:int = 0, y:int = 0):
        self._img = image
        self.delete("all")
        self.create_image(x, y, image=image, anchor="nw")

class Imageable(Baseable):
    def __init__(self, parent, skin=None, **kwargs):
        super().__init__(parent, skin, **kwargs)
        self._skin.setBGColors('gray')      # Eliminate interactive colors for simple image.

    def changeImage(self, img_number): self.setState(img_number)
    def enable(self):
        super().enable()
        self.setState(self._img_state)

    def disable(self):
        super().disable()
        self.setState(3)


class Hoverable(Baseable):
    def __init__(self, parent, skin=None, **kwargs):
        self.moused_over = False
        super().__init__(parent, skin, **kwargs)

    def setSkin(self, skin):
        super().setSkin(skin)
        #updateHover(self)

    def mouseIn(self, event):
        self.moused_over = True
        self.setState(1)

    def mouseOut(self, event):
        self.moused_over = False
        self.setState(0)

    def enable(self):
        super().enable()
        self.bind("<Enter>", self.mouseIn)
        self.bind("<Leave>", self.mouseOut)
        updateHover(self)

    def disable(self):
        super().disable()
        self.unbind("<Enter>")
        self.unbind("<Leave>")
        self.setState(3)


class Clickable(Hoverable):
    def __init__(self, parent, function=lambda: None, skin=None, **kwargs):
        self.function = function
        super().__init__(parent, skin, **kwargs)

    def clicked(self, event):
        self.setState(2)
        self.function()
        #updateHover(self)

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
            #updateHover(self)

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


class Toggleable(Pushable):
    def __init__(self, parent, state:bool=False, function=lambda: None, skin:Skin = None, **kwargs):
        self._toggle_state = state
        self._state_offset = 0
        super().__init__(parent, function, skin, **kwargs)

    def mouseUp(self, event):
        self._clicking = False
        if self.moused_over:
            self.state(not self._toggle_state)
            self.function()

    def state(self, state:bool=None) -> Optional[bool]:
        if isinstance(state, bool):
            self._toggle_state = state
            self._state_offset = self._toggle_state * 4
            self.setState(1)
        return self._toggle_state

    def setState(self, state_index:int = 0):
        state_index += self._state_offset
        super().setState(state_index)


class Holdable(Pushable):
    def __init__(self, parent, function=lambda: None, skin=None, delay=100, init_delay=400, **kwargs):
        self.delay = delay
        self.init_delay = init_delay
        super().__init__(parent, function, skin, **kwargs)

    def mouseOut(self, event):
        self.moused_over = False if self._clicking else super().mouseOut(None)

    def mouseUp(self, event):
        self._clicking = False
        if self.moused_over:
            self.mouseIn(event)

    def clicked(self, event):
        super().clicked(event)
        self.function()
        if self.function is not None:
            self.after(self.init_delay, self._keepClicking)

    def _keepClicking(self):
        if self._clicking:
            self.function()
            self.after(self.delay, self._keepClicking)


class Draggable(Holdable):
    def __init__(self, parent, function=lambda: None, skin=None, **kwargs):
        super().__init__(parent, function, skin, **kwargs)
        self._all_siblings_atop, self._all_siblings_beneath = set(), set()
        self._last_siblings_atop, self._last_siblings_beneath = set(), set()

    def clicked(self, event):
        self.x = event.x
        self.y = event.y
        self._splitAllSiblings()
        super().clicked(event)

    def mouseDrag(self, event):
        x, y, w, h = self.geometry
        _, _, mw, mh = self.master.geometry

        x = event.x - self.x + x
        y = event.y - self.y + y
        x = limitMove(x, w, 0, mw)
        y = limitMove(y, h, 0, mh)

        self.place_configure(x=x, y=y)
        # self.update_idletasks()

        self._geometry = x, y, w, h
        self._populateOverlappingSiblings(self._siblings_atop, self._all_siblings_atop, False)
        self._populateOverlappingSiblings(self._siblings_beneath, self._all_siblings_beneath, True)
        self.after_idle(self.redraw)

    def enable(self):
        self.bind("<B1-Motion>", self.mouseDrag)
        super().enable()

    def disable(self):
        self.unbind("<B1-Motion>")
        super().disable()

    def _splitAllSiblings(self):
        atop = False
        self._all_siblings_atop, self._all_siblings_beneath = set(), set()
        for sibling in self.master.getChildren():
            if sibling is self: atop = True
            else:
                if atop: self._all_siblings_atop.add(sibling)
                else: self._all_siblings_beneath.add(sibling)

    def _populateOverlappingSiblings(self, output_set:set, source_set:set, atop:bool):
        output_set.clear()
        for sibling in source_set:
            if rectsOverlap(self.geometry, sibling.geometry):
                output_set.add(sibling)
                sibling.trackSibling(self, atop)
