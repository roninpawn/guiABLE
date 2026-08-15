""" Public convenience widgets built on top of the core widget hierarchy.

Public classes are thin wrappers that combine one or more core mixins and add the
`parent` kwarg for external users. They do not contain any core constructor logic.
"""

from .widgetables import (
    Canvas, TextCanvas,
    Backgroundable, Siblingable,
    Stateable, Imageable, Hoverable, Clickable, Pushable,
    Labelable, Toggleable, Holdable, Repeatable,
    LoneDraggable, Draggable,
    Groupable, Collection
)


class Background(Backgroundable, TextCanvas):
    def __init__(self, parent, skin=None, **kwargs):
        super().__init__(parent, skin=skin, **kwargs)


class Image(Imageable, Siblingable, TextCanvas):
    def __init__(self, parent, skin=None, show_image=0, **kwargs):
        super().__init__(parent, skin=skin, init_state=show_image, **kwargs)


class Hover(Hoverable, Siblingable, TextCanvas):
    def __init__(self, parent, skin=None, **kwargs):
        super().__init__(parent, skin=skin, **kwargs)


class Button(Pushable, Siblingable, TextCanvas):
    def __init__(self, parent, skin=None, function=lambda:None, **kwargs):
        super().__init__(parent, function, skin=skin, **kwargs)


class InstantButton(Clickable, Siblingable, TextCanvas):
    def __init__(self, parent, skin=None, function=lambda:None, **kwargs):
        super().__init__(parent, function, skin=skin, **kwargs)


class RepeatButton(Repeatable, Siblingable, TextCanvas):
    def __init__(self, parent, skin=None, function=lambda:None, delay=150, init_delay=400, **kwargs):
        super().__init__(parent, function, skin=skin, delay=delay, init_delay=init_delay, **kwargs)


class Label(Labelable, Siblingable, Canvas):
    def __init__(self, parent, skin=None, text="", font_pack=None, function=lambda:None, **kwargs):
        super().__init__(parent, function, skin=skin, text=text, font_pack=font_pack, **kwargs)


class Checkbox(Toggleable, Siblingable, TextCanvas):
    def __init__(self, parent, skin=None, function=lambda:None, state=False, **kwargs):
        super().__init__(parent, function, state=state, skin=skin, **kwargs)


class Drag(Draggable, Siblingable, TextCanvas):
    def __init__(self, parent, skin=None, function=lambda:None, **kwargs):
        super().__init__(parent, function, skin=skin, **kwargs)


class Group(Groupable, Backgroundable, Siblingable, TextCanvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)


class LoneDrag(LoneDraggable, Siblingable, TextCanvas):
    def __init__(self, parent, function=lambda:None, skin=None, **kwargs):
        super().__init__(parent, function, skin=skin, **kwargs)


class TroughButton(Repeatable, Siblingable, TextCanvas):
    def __init__(self, parent, function=lambda:None, skin=None, delay=150, init_delay=400, **kwargs):
        super().__init__(parent, function, skin=skin, delay=delay, init_delay=init_delay, **kwargs)


class SliderHandle(LoneDrag):
    def __init__(self, parent, function, release_function:tuple|None=lambda: None, **kwargs):
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
