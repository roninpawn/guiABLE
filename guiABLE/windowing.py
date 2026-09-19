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
        resized = geometry[2:] != self.size
        self._geometry = geometry

        # Size changes remain Tk-managed. Position changes are committed as one window-family transaction.
        if resized and self.width > 0 and self.height > 0:
            self.wm_geometry(f"{self.width}x{self.height}")

        if moved:
            windows = [self]
            self._collectChildMoves(windows)
            self._backend.moveWindows(windows)

        return self

    def move(self, x:int=None, y:int=None): return self.setGeometry(x=x, y=y)
    def resize(self, width:int=None, height:int=None): return self.setGeometry(width=width, height=height)
    def snapGrid(self, grid:int=4):
        """Snap position to the nearest grid point and contract dimensions to the grid."""
        if grid < 1: raise ValueError("grid must be at least 1")

        snap = lambda value: round(value / grid) * grid
        contract = lambda value: value - value % grid if value >= grid else value

        return self.setGeometry(snap(self.x), snap(self.y), contract(self.width), contract(self.height))

    def _geometryString(self) -> str:
        position = f"+{self.x}+{self.y}"
        return f"{self.width}x{self.height}{position}" if self.width > 0 and self.height > 0 else position

    def _windowConfigured(self, event):
        if event.widget is not self: return

        # Position is controlled by guiABLE. Configure is only needed to learn dimensions Tk resolved for an auto-sized window.
        if (event.width, event.height) != self.size:
            self._geometry = (self.x, self.y, event.width, event.height)

    def _collectChildMoves(self, windows:list):
        for child in self._window_children: child._collectParentMove(windows)


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
        self._drag_press_bind = None
        self._manual_drag = False
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
        self.bind("<Map>", self._windowMapped, "+")
        self.bind("<Unmap>", self._windowUnmapped, "+")

        self.update_idletasks()
        self._heartbeat()

    @property
    def parent(self): return self

    def bindDrag(self, widget:tk.Canvas):
        if self._drag_widget is not None:
            if self._drag_press_bind is not None:
                self._drag_widget.unbind("<ButtonPress-1>", self._drag_press_bind)

            if self._drag_bind is not None:
                self._drag_widget.unbind("<B1-Motion>", self._drag_bind)

        self._drag_widget = widget

        if widget is None:
            self._drag_press_bind = None
            self._drag_bind = None
            return

        self._drag_press_bind = widget.bind("<ButtonPress-1>", self.mouseDown)
        self._drag_bind = widget.bind("<B1-Motion>", self.mouseDrag)

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
        if not self._manual_drag: return "break"

        mx, my = event.x_root, event.y_root

        if self.drag_locked:
            self.dx = mx - self.x
            self.dy = my - self.y
            self._update_offsets()
            self.drag_locked = False
            self.focus_force()

        self.move(mx - self.dx, my - self.dy)
        self.update_idletasks()

    def mouseDown(self, event):
        self._manual_drag = not self._backend.beginMove(event.x_root, event.y_root)
        if not self._manual_drag: return "break"


    def mouseUp(self, event):
        if self._manual_drag and not self.drag_locked:
            self.focus_force()
            self.drag_locked = True

        self._manual_drag = False

    def tookFocus(self, event):
        for child in self._window_children:
            if child.stackWithParent(): child.lift()

    def lostFocus(self, event): self._lost_focus = time() + .4

    def minimize(self): self.iconify()
    def iconify(self, event=None):
        if self.taskbar_handle is None:
            super().iconify()
        else:
            self.withdraw()
            self.taskbar_handle.iconify()

    def restore(self): self.deiconify()
    def deiconify(self, event=None):
        if self.taskbar_handle is None:
            super().deiconify()
            self.focus_force()
            return

        if self.drag_locked:
            if self.wm_state() == tk.NORMAL and time() < self._lost_focus:
                self.iconify()
            else:
                super().deiconify()
                self.focus_force()

            self.taskbar_handle.wm_iconify()

    """
    Tk throttles idle work aggressively enough to make guiABLE's image rendering visibly stutter. Scheduling a 2ms
    no-op timer keeps Tk's event loop awake while still allowing zero-CPU idle behavior with Windows.
    """
    def _heartbeat(self): self.after(2, self._heartbeat)

    def _update_offsets(self):
        self._offset_w = (self.width - self._taskbar_size[0]) // 2
        self._offset_h = (self.height - self._taskbar_size[1]) // 2

    def _windowMapped(self, event):
        if event.widget is not self: return

        for child in self._window_children:
            if child.minimizeWithParent(): child.deiconify()

    def _windowUnmapped(self, event):
        if event.widget is not self: return

        for child in self._window_children:
            if child.minimizeWithParent(): child.withdraw()

    def _windowConfigured(self, event):
        if event.widget is not self: return

        Windowable._windowConfigured(self, event)

        location = (event.x, event.y)
        if location == self.location or not self._backend.acceptConfigureLocation(*location): return

        self._geometry = (*location, self.width, self.height)

        windows = []
        self._collectChildMoves(windows)
        self._backend.moveWindows(windows)


"""
A _ChildWindow is a raw OS window positioned relative to another Windowable. It provides window-management behavior
without imposing a guiABLE rendering surface, allowing specialized windows to supply their own content floor.
"""
class _ChildWindow(Windowable, tk.Toplevel):
    def __init__(self, parent, x:int=100, y:int=100, width:int=0, height:int=0, visible=False, title="",
                 stack_with_parent=True, minimize_with_parent=None, move_with_parent=True,
                 always_on_top=False, **kwargs):

        self._window_parent = parent.window
        self._relative_location = (x, y)
        self._visible = bool(visible)

        self._stack_with_parent = bool(stack_with_parent)
        self._minimize_with_parent = None if minimize_with_parent is None else bool(minimize_with_parent)
        self._move_with_parent = bool(move_with_parent)
        self._topmost = bool(always_on_top)

        if self._stack_with_parent and self._minimize_with_parent is False:
            raise ValueError("A stacked child must minimize with its parent.")

        absolute_x = self._window_parent.x + x
        absolute_y = self._window_parent.y + y

        self._realized = False
        self._realize_after = None

        super().__init__(self._window_parent, x=absolute_x, y=absolute_y,
                         width=width, height=height, title=title, **kwargs)
        super().withdraw()

        self._window_parent.bindChild(self)
        self._realize_after = self.after_idle(self._realize)

    @property
    def parent(self): return self._window_parent
    @property
    def relative_location(self): return self._relative_location

    def visible(self, visible:bool=None):
        if visible is None: return self._visible

        self._visible = bool(visible)
        if not self._realized: return self._visible

        if self._visible:
            self.deiconify()
            self.after_idle(self._backend.raiseWindow)
        else:
            self.withdraw()

        return self._visible

    def withdraw(self):
        for child in self._window_children:
            if child.minimizeWithParent(): child.withdraw()

        super().withdraw()

    def deiconify(self):
        if not self._visible or not self._realized: return

        super().deiconify()

        for child in self._window_children:
            if child.minimizeWithParent(): child.deiconify()

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

    def stackWithParent(self, stack:bool=None):
        if stack is None: return self._stack_with_parent

        stack = bool(stack)
        if stack and self._minimize_with_parent is False:
            raise ValueError("A stacked child must minimize with its parent.")

        self._stack_with_parent = stack
        if self._realized: self._backend.setOwner(self._window_parent if stack else None)
        return self._stack_with_parent

    def minimizeWithParent(self, minimize:bool=None):
        if minimize is None:
            if self._minimize_with_parent is not None: return self._minimize_with_parent
            if self._stack_with_parent: return True
            if isinstance(self._window_parent, _ChildWindow): return self._window_parent.minimizeWithParent()
            return False

        minimize = bool(minimize)
        if self._stack_with_parent and not minimize:
            raise ValueError("A stacked child must minimize with its parent.")

        self._minimize_with_parent = minimize
        return self._minimize_with_parent

    def moveWithParent(self, move_with_parent:bool=None):
        if move_with_parent is None: return self._move_with_parent

        self._move_with_parent = bool(move_with_parent)
        self._relative_location = (self.x - self._window_parent.x, self.y - self._window_parent.y)
        return self._move_with_parent

    def alwaysOnTop(self, always_on_top:bool=None):
        if always_on_top is None: return self._topmost

        self._topmost = bool(always_on_top)
        if self._realized: self._backend.setTopmost(self._topmost)
        return self._topmost

    def snapGrid(self, grid:int=4):
        if grid < 1: raise ValueError("grid must be at least 1")

        snap = lambda value: round(value / grid) * grid
        contract = lambda value: value - value % grid if value >= grid else value

        rx, ry = self._relative_location
        rx, ry = snap(rx), snap(ry)

        self._relative_location = (rx, ry)
        Windowable.setGeometry(self, self._window_parent.x + rx, self._window_parent.y + ry,
                               contract(self.width), contract(self.height))
        return self

    def _collectParentMove(self, windows:list):
        if not self._move_with_parent:
            self._relative_location = (self.x - self._window_parent.x, self.y - self._window_parent.y)
            return

        rx, ry = self._relative_location
        self._geometry = (self._window_parent.x + rx, self._window_parent.y + ry, self.width, self.height)

        windows.append(self)
        self._collectChildMoves(windows)

    def _realize(self):
        self._realize_after = None

        self._backend.configureChild(self._window_parent, self._stack_with_parent, self._topmost)
        self._realized = True

        if self._visible:
            self.deiconify()
            self.after_idle(self._backend.raiseWindow)


"""
Raw popup shell. An anchor determines its desired spawn position; the result is conformed to the virtual desktop.
Menu-specific placement policy belongs to MenuWindow, not here.
"""
class _PopupWindow(_ChildWindow):
    def __init__(self, parent, anchor=None, x:int=0, y:int=0, width:int=0, height:int=0, visible=False, title="",
                 stack_with_parent=True, minimize_with_parent=None, move_with_parent=True,
                 always_on_top=False, **kwargs):

        self._anchor = anchor
        self._anchor_offset = (x, y)
        requested_visible = bool(visible)

        super().__init__(parent, x=x, y=y, width=width, height=height, visible=False, title=title,
                         stack_with_parent=stack_with_parent, minimize_with_parent=minimize_with_parent,
                         move_with_parent=move_with_parent, always_on_top=always_on_top, **kwargs)

        if requested_visible: super().visible(True)

    @property
    def anchor(self): return self._anchor

    def setAnchor(self, anchor):
        self._anchor = anchor
        return self

    def reposition(self):
        ax, ay, _, _ = self._anchorRect()
        ox, oy = self._anchor_offset

        x, y, width, height = self._conformGeometry(ax + ox, ay + oy, self.width, self.height)
        self.setGeometry(x, y, width, height)
        return self

    def deiconify(self):
        if self._realized: self.reposition()
        super().deiconify()

    def _anchorRect(self) -> tuple[int,int,int,int]:
        anchor = self._anchor() if callable(self._anchor) else self._anchor

        if anchor is None: return self._window_parent.rect

        if hasattr(anchor, "winfo_rootx") and hasattr(anchor, "winfo_rooty"):
            width = anchor.width if hasattr(anchor, "width") else anchor.winfo_width()
            height = anchor.height if hasattr(anchor, "height") else anchor.winfo_height()
            return anchor.winfo_rootx(), anchor.winfo_rooty(), width, height

        if len(anchor) == 2: return int(anchor[0]), int(anchor[1]), 0, 0
        if len(anchor) == 4: return tuple(int(value) for value in anchor)

        raise ValueError("PopupWindow anchor must be a widget or resolve to (x, y) or (x, y, width, height).")

    def _conformGeometry(self, x:int, y:int, width:int, height:int) -> tuple[int,int,int,int]:
        dx, dy, dw, dh = self._backend.workArea(x, y, width, height)

        width = min(width, dw) if width > 0 else width
        height = min(height, dh) if height > 0 else height

        x = min(max(x, dx), dx + max(0, dw - width))
        y = min(max(y, dy), dy + max(0, dh - height))

        return x, y, width, height


""" Public popup with an implied guiABLE Background. """
class PopupWindow(Background):
    def __init__(self, parent, anchor=None, x:int=0, y:int=0, width:int=0, height:int=0, visible=False, title="",
                 skin=None, stack_with_parent=True, minimize_with_parent=None, move_with_parent=True,
                 always_on_top=False, **kwargs):

        requested_visible = bool(visible)
        self._window = _PopupWindow(    parent, anchor, x, y, width, height, False, title,
                                        stack_with_parent, minimize_with_parent, move_with_parent, always_on_top )

        width, height = self._window.size
        super().__init__(self._window, skin=skin, width=width, height=height, **kwargs)
        self.place(x=0, y=0)

        self._window.bind("<Configure>", self._syncWindowSize, "+")
        self._syncWindowSize()

        if requested_visible: self._window.visible(True)

    @property
    def window(self): return self._window
    @property
    def anchor(self): return self._window.anchor
    @property
    def relative_location(self): return self._window.relative_location

    def setAnchor(self, anchor): self._window.setAnchor(anchor); return self
    def reposition(self): self._window.reposition(); return self

    def visible(self, visible:bool=None): return self._window.visible(visible)
    def close(self): self._window.close()
    def stackWithParent(self, stack:bool=None): return self._window.stackWithParent(stack)
    def minimizeWithParent(self, minimize:bool=None): return self._window.minimizeWithParent(minimize)
    def moveWithParent(self, move:bool=None): return self._window.moveWithParent(move)
    def alwaysOnTop(self, always_on_top:bool=None): return self._window.alwaysOnTop(always_on_top)

    def windowGeometry(self): return self._window.rect

    def setGeometry(self, x:int=None, y:int=None, width:int=None, height:int=None):
        self._window.setGeometry(x, y, width, height)
        self._syncWindowSize()
        return self

    def move(self, x:int=None, y:int=None): return self.setGeometry(x=x, y=y)
    def resize(self, width:int=None, height:int=None): return self.setGeometry(width=width, height=height)

    def destroy(self):
        super().destroy()
        self._window.destroy()

    def _syncWindowSize(self, event=None):
        if event is not None and event.widget is not self._window: return

        size = (event.width, event.height) if event is not None else self._window.size
        if size != self.size and size[0] > 0 and size[1] > 0:
            self.place_configure(width=size[0], height=size[1], implied=True)


""" Public ChildWindow with an implied guiABLE Background covering its raw child window. """
class ChildWindow(Background):
    def __init__(self, parent, x:int=100, y:int=100, width:int=0, height:int=0, visible=False, title="", skin=None,
                 stack_with_parent=True, minimize_with_parent=None, move_with_parent=True,
                 always_on_top=False, **kwargs):

        self._window = _ChildWindow(parent, x, y, width, height, visible, title,
            stack_with_parent, minimize_with_parent, move_with_parent, always_on_top)

        super().__init__(self._window, skin=skin, width=width, height=height, **kwargs)
        self.place(x=0, y=0)

        self._window.bind("<Configure>", self._syncWindowSize, "+")
        self._syncWindowSize()

    @property
    def window(self): return self._window
    @property
    def relative_location(self): return self._window.relative_location

    def visible(self, visible:bool=None): return self._window.visible(visible)
    def close(self): self._window.close()
    def stackWithParent(self, stack:bool=None): return self._window.stackWithParent(stack)
    def minimizeWithParent(self, minimize:bool=None): return self._window.minimizeWithParent(minimize)
    def moveWithParent(self, move:bool=None): return self._window.moveWithParent(move)
    def alwaysOnTop(self, always_on_top:bool=None): return self._window.alwaysOnTop(always_on_top)

    def windowGeometry(self): return self._window.rect

    def setGeometry(self, x:int=None, y:int=None, width:int=None, height:int=None):
        self._window.setGeometry(x, y, width, height)
        self._syncWindowSize()
        return self

    def move(self, x:int=None, y:int=None): return self.setGeometry(x=x, y=y)
    def resize(self, width:int=None, height:int=None): return self.setGeometry(width=width, height=height)

    def snapGrid(self, grid:int=4):
        self._window.snapGrid(grid)
        self._syncWindowSize()
        return self

    def destroy(self):
        super().destroy()
        self._window.destroy()

    def _syncWindowSize(self, event=None):
        if event is not None and event.widget is not self._window: return

        size = (event.width, event.height) if event is not None else self._window.size
        if size != self.size and size[0] > 0 and size[1] > 0:
            self.place_configure(width=size[0], height=size[1], implied=True)


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
    def snapGrid(self, grid:int=4):
        self._window.snapGrid(grid)

        if self.size != self._window.size:
            self.config(width=self._window.width, height=self._window.height)

        return self
