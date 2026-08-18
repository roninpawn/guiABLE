""" Public convenience widgets built on top of the core widget hierarchy.

Public classes are thin wrappers that combine one or more core mixins and add the
`parent` kwarg for external users. They do not contain any core constructor logic.
"""

from .widgetables import (
    Canvas, TextCanvas,
    Backgroundable, Siblingable,
    Stateable, Imageable, Hoverable, Clickable, Pushable,
    Labelable, Labeled, Toggleable, Holdable, Repeatable,
    LoneDraggable, Draggable, Troughable, LinearAnimator,
    Groupable, Collection
)


class Background(Backgroundable, TextCanvas):
    def __init__(self, parent, skin=None, **kwargs):
        super().__init__(parent, skin=skin, **kwargs)


class Image(Labeled, Imageable, Siblingable, TextCanvas):
    def __init__(self, parent, skin=None, show_image=0, **kwargs):
        super().__init__(parent, skin=skin, init_state=show_image, **kwargs)


class Hover(Hoverable, Siblingable, TextCanvas):
    def __init__(self, parent, skin=None, **kwargs):
        super().__init__(parent, skin=skin, **kwargs)


class Button(Labeled, Pushable, Siblingable, TextCanvas):
    def __init__(self, parent, skin=None, function=lambda:None, text=None, font_pack=None, **kwargs):
        super().__init__(parent, function, skin=skin, text=text, font_pack=font_pack, **kwargs)


class InstantButton(Labeled, Clickable, Siblingable, TextCanvas):
    def __init__(self, parent, skin=None, function=lambda:None, text=None, font_pack=None, **kwargs):
        super().__init__(parent, function, skin=skin, text=text, font_pack=font_pack, **kwargs)


class RepeatButton(Labeled, Repeatable, Siblingable, TextCanvas):
    def __init__(self, parent, skin=None, function=lambda:None, delay=150, init_delay=400,
                 text=None, font_pack=None, **kwargs):
        super().__init__(parent, function,
                         skin=skin, delay=delay, init_delay=init_delay, text=text, font_pack=font_pack, **kwargs)


class Label(Labelable):
    def __init__(self, parent, text="", font_pack=None, **kwargs):
        super().__init__(parent, text=text, font_pack=font_pack, **kwargs)


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


class Slider(Troughable, Imageable, Siblingable, TextCanvas):
    def __init__(self, parent, trough_skin, handle_skin, active_function=lambda:None, release_function=lambda:None,
                 handle_width:int=None, handle_height:int=None,
                 start_percent:float=0.0, **kwargs):

        super().__init__(parent, skin=trough_skin, **kwargs)

        kwargs['width'], kwargs['height'] = handle_width, handle_height
        self._handle = SliderHandle(self, active_function, release_function, skin=handle_skin, **kwargs)
        self._handle.place(0, 0)

        self.setPercent(start_percent)


class AnimatedSlider(LinearAnimator, Slider):
    def __init__(self, *args, slide_duration:int=0, slide_rate:int=15, **kwargs):
        self.slide_duration, self.slide_rate = slide_duration, slide_rate
        super().__init__(*args, **kwargs)

        self._bindHandle()

    def enable(self):
        super().enable()
        self._bindHandle()

    def _bindHandle(self):
        if self._handle:
            self._handle.bind("<Button-1>", self._handleClicked, "+")

    def _handleClicked(self, event=None):
        self.stopAnimation()

    def slideTo(self, percent:float, duration:int=None, notify:bool=False):
        duration = self.slide_duration if duration is None else duration
        destination = min(1.0, max(0.0, percent))

        self.animate(self.getPercent(), destination, duration,
                     lambda percent: self.setPercent(percent, notify), self.slide_rate)


class DynamicSlider(AnimatedSlider):
    def enable(self):
        super().enable()
        self.bind("<Button-1>", self.troughClicked)

    def disable(self):
        super().disable()
        self.unbind("<Button-1>")

    def troughClicked(self, event):
        self.slideTo(self.percentAt(event.x, event.y), notify=True)