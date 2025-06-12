import tkinter as tk
from time import time as time
from warnings import warn

from utilities import limitMove, getLocalMouse, updateHover, drawBar, putToImage
from windowing import Windowable, ChildableWindow, Canvasable, Backgroundable
from widgets import Skinnable, Imageable, Hoverable, Clickable, Pushable, Labelable, Toggleable, Holdable, \
    Draggable, Troughable


class Scrollable(Troughable):
    def __init__(self, parent, trough_width, trough_height, handle_width, handle_height, scrollable_skin=None, **kwargs):
        self.scrollwheel_speed = 10
        self.page_percent = .9
        self.init_delay = 400
        self.delay = 100

        skin_troughs = scrollable_skin.troughs if scrollable_skin is not None else None
        self.active_handle_x, self.active_handle_y = True, True

        super().__init__(parent, trough_width, trough_height, skin_troughs, **kwargs)

        if scrollable_skin is None: scrollable_skin = ScrollableSkin()
        self.handle = Draggable(self.inner, skinnable=scrollable_skin.handles, width=handle_width, height=handle_height)
        self.handle.place(x=0, y=0)

    def enable(self):
        if not self.enabled:
            self.handle.enable()
            if self.linked: self._linkTo()
        super().enable()

    def disable(self):
        self.handle.disable()
        super().disable()

    def setSkin(self, scroll_skinnable):
        super().setSkin(scroll_skinnable)
        self.handle.setSkin(scroll_skinnable)

    def linkTo(self, scrollablecanvas, movement_modifier=-1, active_handle_xy=(True, True), canvas_offset=(0.0, 0.0)):
        self.movement_modifier = movement_modifier
        self._linked = scrollablecanvas
        self._linkedwidth, self._linkedheight = self._linked.inner.winfo_width(), self._linked.inner.winfo_height()
        self.active_handle_x, self.active_handle_y = active_handle_xy
        self.x_offset, self.y_offset = canvas_offset
        self._linkTo()

    def _linkTo(self):
        if self.active_handle_y:
            self.bind_all("<MouseWheel>", self.scroll, "+")
        self.handle.bind("<Configure>", self._moveCanvas, "+")
        self.inner.bind("<Button-1>", self.clicked, "+")
        self.inner.bind("<ButtonRelease-1>", self.mouseUp, "+")
        self._linked.inner.bind("<Configure>", self._resize_handle, "+")
        self.bind("<Configure>", self._resize_handle)
        self.linked = True

    def _resize_handle(self, event):
        if self._linkedwidth != self._linked.inner.winfo_width() or self._linkedheight != self._linked.inner.winfo_height():
            self.resize_handle()

    def resize_handle(self):
        if not self.active_handle_x or self._linked.inner.winfo_width() < self._linked.inner_width:
            self.handle.config(width=self.winfo_width())
        else:
            self.enable()
            self._linked.inner.update_idletasks()
            self.handle.config(width=self.winfo_width() / self._linked.inner.winfo_width() * self._linked.inner_width)
        if not self.active_handle_y or self._linked.inner.winfo_height() < self._linked.inner_height:
            self.handle.config(height=self.winfo_height())
        else:
            self.enable()
            self.handle.config(height=self.winfo_height() / self._linked.inner.winfo_height() * self._linked.inner_height)

        self.update_idletasks()
        if self.handle.winfo_width() == self.winfo_width() and \
                self.handle.winfo_height() == self.winfo_height():
            self.disable()

        self.handle._skin.drawBars(self.handle.winfo_width(), self.handle.winfo_height())
        updateHover(self.handle)
        self._skin.drawBars(self.winfo_width(), self.winfo_height())
        updateHover(self)

        self._linkedwidth = self._linked.inner.winfo_width()
        self._linkedheight = self._linked.inner.winfo_height()

    def clicked(self, event):
        if self.active_handle_x:
            new_x = self._limitPage(event.x, self.handle.winfo_x(), self.handle.winfo_width(),
                                    self.winfo_width(), self.page_percent)
            self.handle.place_configure(x=new_x)
        if self.active_handle_y:
            new_y = self._limitPage(event.y, self.handle.winfo_y(), self.handle.winfo_height(),
                                    self.winfo_height(), self.page_percent)
            self.handle.place_configure(y=new_y)

        if not self._clicking:
            self.after(self.init_delay, self._keepClicking)
            self._clicking = True

        super().clicked(event)

    def _keepClicking(self):
        if self._clicking:
            event_x, event_y, mouse_in = getLocalMouse(self.inner)
            self.inner.event_generate("<Button-1>", x=event_x, y=event_y)
            self.after(self.delay, self._keepClicking)

    def scroll(self, event):
        x, y, moused_over = getLocalMouse(self._linked)
        if moused_over and self.enabled:
            y = self.handle.winfo_y()
            speed = event.delta / self.scrollwheel_speed

            if y - speed < 0:
                self.handle.place_configure(y=0)
            else:
                trough_height = self.winfo_height()
                handle_height = self.handle.winfo_height()

                if trough_height < y + handle_height - speed:
                    self.handle.place_configure(y=trough_height-handle_height)
                else:
                    self.handle.place_configure(y=y-speed)

    def _limitPage(self, event, origin, size, max, restrict=1.0):
        if origin < event < origin + size:
            return origin
        if event <= origin:
            size = -size
        return limitMove(origin + size * restrict, size, 0, max)

    def _moveCanvas(self, event):
        if self.active_handle_x:
            if self.handle.winfo_width() < self._linked.inner_width:
                x = event.x * ((self._linked.inner.winfo_width()-self._linked.inner_width) /
                               (self.winfo_width()-self.handle.winfo_width()) * self.movement_modifier)
            else: x = 0.0
            self._linked.inner.place_configure(x=x + self.x_offset)

        if self.active_handle_y:
            if self.handle.winfo_height() < self._linked.inner.winfo_height():
                y = event.y * ((self._linked.inner.winfo_height()-self._linked.inner_height) /
                               (self.winfo_height()-self.handle.winfo_height()) * self.movement_modifier)
            else: y = 0.0
            self._linked.inner.place_configure(y=y + self.y_offset)


class ScrollableCanvas(Backgroundable): pass


class ScrollablePane(ScrollableCanvas):
    def __init__(self, parent, width, height, bar_size=18, scrollable_pane_skin=None, scrollbars=(False, False),
                 auto=(False, False)):
        super().__init__(parent, width=width, height=height)

        self.collapse = tk.Frame(self.inner)
        self.collapse.pack(anchor=tk.W)

        h_on, v_on = scrollbars
        self.h_auto, self.v_auto = auto

        self._skin = scrollable_pane_skin if scrollable_pane_skin is not None else ScrollablePaneSkin()

        self.inner_width = width - bar_size * v_on * (not self.v_auto)
        self.inner_height = height - bar_size * h_on * (not self.h_auto)

        self.v_scroll = Scrollable(self, bar_size, height, bar_size, bar_size, self._skin.v_skin)
        self._skin.v_skin.bindScrollable(self.v_scroll)
        self.v_scroll.place(x=self.inner_width, y=0)
        self.v_scroll.linkTo(self, -1, (False, True))

        self.h_scroll = Scrollable(self, self.inner_width, bar_size, bar_size, bar_size, self._skin.h_skin)
        self._skin.h_skin.bindScrollable(self.h_scroll)
        self.h_scroll.place(x=0, y=self.inner_height)
        self.h_scroll.linkTo(self, -1, (True, False))

        if self.h_auto or self.v_auto:
            self.inner.bind("<Configure>", self.showBars)


    def setSkin(self, scrollablepane_skin):
        if scrollablepane_skin is not None:
            scrollablepane_skin.v_skin.bindScrollable(self.v_scroll)
            scrollablepane_skin.h_skin.bindScrollable(self.h_scroll)

    def showBars(self, event):
        changed = False
        self.update_idletasks()
        if self.v_auto:
            if self.inner.winfo_height() > self.inner_height and self.v_scroll.winfo_x() == self.winfo_width():
                self.inner_width -= self.v_scroll.winfo_width()
                changed = True
            elif self.inner.winfo_height() < self.inner_height and self.v_scroll.winfo_x() < self.winfo_width():
                self.inner_width = self.winfo_width()
                changed = True

        if self.h_auto:
            if self.inner.winfo_width() > self.inner_width and self.h_scroll.winfo_y() == self.winfo_height():
                self.inner_height -= self.h_scroll.winfo_height()
                changed = True
            elif self.inner.winfo_width() < self.inner_width and self.h_scroll.winfo_y() != self.inner_height:
                    self.inner_height = self.winfo_height()
                    changed = True

        if changed:
            if self.v_auto:
                self.h_scroll.configure(width=self.inner_width)
                self.h_scroll.place_configure(width=self.inner_width)
                self.v_scroll.place_configure(x=self.inner_width)
                self.v_scroll.resize_handle()
            if self.h_auto:
                self.h_scroll.place_configure(y=self.inner_height, width=self.inner_width)
                self.h_scroll.configure(width=self.inner_width)
                self.h_scroll.resize_handle()

    def disable(self):
        self.v_scroll.disable()
        self.h_scroll.disable()

    def enable(self):
        self.v_scroll.enable()
        self.h_scroll.enable()


class BarSkin(Skinnable):
    def __init__(self, mids_skinnable=None, ends_skinnable=None, width=20, height=20, horizontal=False):
        super().__init__()
        if mids_skinnable is None:
            mids_skinnable = Skinnable()
        if ends_skinnable is None:
            ends_skinnable = Skinnable()
        self.changeSkins(mids_skinnable, ends_skinnable)

    def drawBars(self, width, height, horizontal=False):
        images = []
        for n in range(4):
            images.append(drawBar(self.mids.images()[n], self.ends.images()[n], width, height, horizontal))
        self.directSetImages(images[0], images[1], images[2], images[3])

    def changeSkins(self, mids_skinnable, ends_skinnable):
        self.mids, self.ends = mids_skinnable, ends_skinnable


class ScrollableSkin:
    def __init__(self, trough_mids=None, trough_caps=None, handle_mids=None, handle_caps=None):
        self.troughs = BarSkin(trough_mids, trough_caps, 0, 0)
        self.handles = BarSkin(handle_mids, handle_caps, 0, 0)
        self._recipients = []

    def redraw(self, width, height, horizontal):
        self.troughs.drawBars(width, height, horizontal)
        self.handles.drawBars(width, height, horizontal)

    def bindScrollable(self, scrollable):
        scrollable.setSkin(self.troughs)
        scrollable.handle.setSkin(self.handles)

    def bindWidget(self, widget):
        self._recipients.append(widget)

    def unbindWidget(self, widget):
        if widget in self._recipients: self._recipients.remove(widget)

    def updateRecipients(self):
        [updateHover(recipient) for recipient in self._recipients]

    def changeSkins(self, trough_mids, trough_caps, handle_mids, handle_caps):
        self.troughs.changeSkins(trough_mids, trough_caps)
        self.handles.changeSkins(handle_mids, handle_caps)


class ScrollablePaneSkin:
    def __init__(self, trough_mids=None, trough_caps=None, handle_mids=None, handle_caps=None):
        self.v_skin = ScrollableSkin(trough_mids, trough_caps, handle_mids, handle_caps)
        self.h_skin = ScrollableSkin(trough_mids, trough_caps, handle_mids, handle_caps)

    def redraw(self, width, height, horizontal):
        self.v_skin.redraw(width, height, horizontal)
        self.h_skin.redraw(width, height, horizontal)

    def bindScrollables(self, scrollable):
        self.v_skin.bindScrollable(scrollable)
        self.h_skin.bindScrollable(scrollable)

    def bindWidget(self, widget):
        self.v_skin.bindWidget(widget)
        self.h_skin.bindWidget(widget)

    def unbindWidget(self, widget):
        self.v_skin.unbindWidget(widget)
        self.h_skin.unbindWidget(widget)

    def updateRecipients(self):
        self.v_skin.updateRecipients()
        self.h_skin.updateRecipients()

    def changeSkins(self, trough_mids, trough_caps, handle_mids, handle_caps):
        self.v_skin.changeSkins(trough_mids, trough_caps, handle_mids, handle_caps)
        self.h_skin.changeSkins(trough_mids, trough_caps, handle_mids, handle_caps)
