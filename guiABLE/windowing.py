import tkinter as tk
from time import time

from guiABLE.windowbackends import windowBackend
from guiABLE.widgets import Background
from guiABLE.utilities import resolvePath
from guiABLE.uimage import UImage


""" Shared geometry and parent/child behavior for guiABLE windows. """
class Windowable:
    def __init__(self, *args, x:int=100, y:int=100, width:int=400, height:int=300, title="", **kwargs):
        self._geometry = (x, y, width, height)
        self._window_children = []

        super().__init__(*args, **kwargs)

        self._backend = windowBackend(self)
        self.title(title)
        self.wm_geometry(self._geometryString())
        self.bind("<Configure>", self._windowConfigured, "+")

    @property
    def rect(self) -> tuple[int,int,int,int]: return self._geometry
    @property
    def location(self) -> tuple[int,int]: return self._geometry[:2]
    @property
    def size(self) -> tuple[int,int]: return self._geometry[2:]
    @property
    def x(self) -> int: return self._geometry[0]
    @property
    def y(self) -> int: return self._geometry[1]
    @property
    def width(self) -> int: return self._geometry[2]
    @property
    def height(self) -> int: return self._geometry[3]
    @property
    def window(self): return self

    def bindChild(self, child):
        if child not in self._window_children: self._window_children.append(child)

    def dropChild(self, child):
        if child in self._window_children: self._window_children.remove(child)

    def setGeometry(self, x:int=None, y:int=None, width:int=None, height:int=None):
        geometry = (self.x if x is None else int(x), self.y if y is None else int(y),
                    self.width if width is None else int(width), self.height if height is None else int(height))

        if geometry == self._geometry: return self

        moved = geometry[:2] != self.location
        self._geometry = geometry
        self.wm_geometry(self._geometryString())

        if moved: self._moveChildren()
        return self

    def move(self, x:int=None, y:int=None): return self.setGeometry(x=x, y=y)
    def resize(self, width:int=None, height:int=None): return self.setGeometry(width=width, height=height)
    def snapSize(self, grid:int=4):
        """Contract width/height to a pixel grid to reduce fractional display-scaling artifacts."""
        if grid < 1: raise ValueError("grid must be at least 1")

        width = self.width - self.width % grid if self.width >= grid else self.width
        height = self.height - self.height % grid if self.height >= grid else self.height

        return self.resize(width, height)

    def _geometryString(self) -> str:
        position = f"+{self.x}+{self.y}"
        return f"{self.width}x{self.height}{position}" if self.width > 0 and self.height > 0 else position

    def _windowConfigured(self, event):
        if event.widget is not self: return

        # Position is controlled by guiABLE. Configure is only needed to learn dimensions Tk resolved for an auto-sized window.
        if (event.width, event.height) != self.size:
            self._geometry = (self.x, self.y, event.width, event.height)

    def _moveChildren(self):
        for child in self._window_children: child._followParent()


"""
A ChildWindow is an OS-ignored window positioned relative to another Windowable. It follows its parent while retaining
its own relative position, and may itself parent additional ChildWindows.
"""
class ChildWindow(Windowable, tk.Toplevel):
    def __init__(self, parent, position=(100, 100), width:int=0, height:int=0, visible=False, title="", **kwargs):
        self._window_parent = parent.window
        self._relative_location = tuple(position)
        self._visible = bool(visible)

        x = self._window_parent.x + position[0]
        y = self._window_parent.y + position[1]

        super().__init__(self._window_parent, x=x, y=y, width=width, height=height, title=title, **kwargs)

        self._backend.configureChild(self._window_parent)
        self._window_parent.bindChild(self)

        if not self._visible: self.withdraw()

    @property
    def parent(self): return self._window_parent
    @property
    def relative_location(self): return self._relative_location

    def visible(self, visible:bool=None):
        if visible is None: return self._visible

        self._visible = bool(visible)
        self.deiconify() if self._visible else self.withdraw()
        return self._visible

    def withdraw(self):
        for child in self._window_children:
            child.withdraw()

        super().withdraw()

    def deiconify(self):
        if not self._visible: return

        super().deiconify()

        for child in self._window_children:
            child.deiconify()

    def close(self): self.visible(False)

    def destroy(self):
        self._window_parent.dropChild(self)
        super().destroy()

    def setGeometry(self, x:int=None, y:int=None, width:int=None, height:int=None):
        old_location = self.location
        super().setGeometry(x, y, width, height)

        if self.location != old_location:
            self._relative_location = (self.x - self._window_parent.x, self.y - self._window_parent.y)

        return self

    def _followParent(self):
        rx, ry = self._relative_location
        Windowable.setGeometry(self, x=self._window_parent.x + rx, y=self._window_parent.y + ry)


class Window(Background):
    def __init__(self, x:int=100, y:int=100, width:int=400, height:int=300, title=""):
        self._window = _RootWindow(width, height, x, y, title)
        super().__init__(self._window, width=width, height=height)
        self.place(x=0, y=0)

    @property
    def window(self): return self._window

    def bindDrag(self, widget): self._window.bindDrag(widget)
    def bindChild(self, child_window:ChildWindow): self._window.bindChild(child_window)
    def loadTabImage(self, image_path:str): self._window.loadTabImage(image_path)
    def minimize(self): self._window.minimize()
    def restore(self): self._window.restore()

    def windowGeometry(self): return self._window.rect

    def setGeometry(self, x:int=None, y:int=None, width:int=None, height:int=None):
        self._window.setGeometry(x, y, width, height)

        if self.size != self._window.size:
            self.config(width=self._window.width, height=self._window.height)

        return self

    def move(self, x:int=None, y:int=None): return self.setGeometry(x=x, y=y)
    def resize(self, width:int=None, height:int=None): return self.setGeometry(width=width, height=height)
    def snapSize(self, grid:int=4):
        """Contract width/height to a pixel grid to reduce fractional display-scaling artifacts."""
        self._window.snapSize(grid)

        if self.size != self._window.size:
            self.config(width=self._window.width, height=self._window.height)

        return self


"""
Root guiABLE window. override-redirect removes system chrome, so an invisible managed Toplevel supplies taskbar and
Alt+Tab presence. Root-only focus/minimize handling and the render heartbeat live here rather than in Windowable.
"""
class _RootWindow(Windowable, tk.Tk):
    def __init__(self, width:int=400, height:int=300, x:int=100, y:int=100, title=""):
        self._offset_w, self._offset_h = width // 2, height // 2
        self._taskbar_size = (0, 0)
        self._drag_widget = None
        self._drag_bind = None
        self._lost_focus = time()
        self.drag_locked = True
        self.taskbar_handle = None

        super().__init__(x=x, y=y, width=width, height=height, title=title)

        managed = self._backend.configureRoot()
        if not managed:
            self.taskbar_handle = tk.Toplevel(self)
            self.taskbar_handle.title(title)
            self.taskbar_handle.geometry(f"0x0+{x + self._offset_w}+{y + self._offset_h}")
            self.taskbar_handle.wm_attributes("-alpha", 0.0)
            self.taskbar_handle.wait_visibility()
            self.taskbar_handle.wm_attributes("-alpha", 0.0)

        self.bind("<ButtonRelease-1>", self.mouseUp)
        self.bind("<FocusIn>", self.tookFocus)
        self.bind("<FocusOut>", self.lostFocus)

        self.update_idletasks()
        self._heartbeat()

    @property
    def parent(self): return self

    def bindDrag(self, widget:tk.Canvas):
        if self._drag_widget is not None and self._drag_bind is not None:
            self._drag_widget.unbind("<B1-Motion>", self._drag_bind)

        self._drag_widget = widget
        self._drag_bind = widget.bind("<B1-Motion>", self.mouseDrag) if widget is not None else None

    # Draws a custom image to the invisible managed window so the OS can use it for Alt+Tab/taskbar previews.
    def loadTabImage(self, image_path):
        if self.taskbar_handle is None: return

        img = UImage(file=resolvePath(image_path))
        img_w, img_h = img.width(), img.height()
        self._taskbar_size = img_w, img_h
        self._update_offsets()

        self.drag_locked = False
        self.taskbar_handle.geometry(f"{img_w}x{img_h}+{self.x + self._offset_w}+{self.y + self._offset_h}")
        tab_image = Background.fromImage(self.taskbar_handle, img_w, img_h, img)
        tab_image.place(x=0, y=0)
        self.taskbar_handle.update()
        self.drag_locked = True

    def setGeometry(self, x:int=None, y:int=None, width:int=None, height:int=None):
        old_geometry = self.rect
        super().setGeometry(x, y, width, height)

        if self.size != old_geometry[2:]: self._update_offsets()
        if self.rect != old_geometry and self.taskbar_handle is not None:
            self.taskbar_handle.geometry(f"+{self.x + self._offset_w}+{self.y + self._offset_h}")

        return self

    def mouseDrag(self, event):
        mx, my = event.x_root, event.y_root

        if self.drag_locked:
            self.dx = mx - self.x
            self.dy = my - self.y
            self._update_offsets()
            self.drag_locked = False
            self.focus_force()

        self.move(mx - self.dx, my - self.dy)

        # Tk defers toplevel movement until idle; flush once after the whole window family has queued its new geometry.
        self.update_idletasks()

    def mouseUp(self, event):
        if not self.drag_locked:
            self.focus_force()
            self.drag_locked = True

    def tookFocus(self, event):
        for child in self._window_children: child.lift()

    def lostFocus(self, event): self._lost_focus = time() + .4

    def minimize(self): self.iconify()
    def iconify(self, event=None):
        for child in self._window_children: child.withdraw()

        if self.taskbar_handle is None:
            super().iconify()
        else:
            self.withdraw()
            self.taskbar_handle.iconify()

    def restore(self): self.deiconify()
    def deiconify(self, event=None):
        if self.taskbar_handle is None:
            super().deiconify()
            for child in self._window_children: child.deiconify()
            self.focus_force()
            return

        if self.drag_locked:
            if self.wm_state() == tk.NORMAL and time() < self._lost_focus:
                self.iconify()
            else:
                super().deiconify()
                for child in self._window_children: child.deiconify()
                self.focus_force()

            self.taskbar_handle.wm_iconify()

    """
    Tk throttles idle work aggressively enough to make guiABLE's image rendering visibly stutter. Scheduling a 2ms
    no-op timer keeps Tk's event loop awake while still allowing zero-CPU idle behavior on tested modern Windows.
    """
    def _heartbeat(self): self.after(2, self._heartbeat)

    def _update_offsets(self):
        self._offset_w = (self.width - self._taskbar_size[0]) // 2
        self._offset_h = (self.height - self._taskbar_size[1]) // 2
