import tkinter as tk
from time import time

from guiABLE.widgets import Background
from guiABLE.utilities import resolvePath
from guiABLE.uimage import UImage


"""
A ChildWindow() is an OS-ignored window that is positioned relative to its parent window, and will travel with that
window, if it is moved. It does not appear in the taskbar, or in alt+tab overlays. It serves as the basis for a pop-up 
window, a configuration window, or even a persistent, detached floating interface.
"""
class ChildWindow(tk.Toplevel):
    def __init__(self, parent, position=(100, 100), visible=False, **kwargs):
        parent.bindChild(self)
        self._visible = visible

        super().__init__(parent, **kwargs)
        self.overrideredirect(True)
        self.geometry(f"+{self.master.winfo_rootx() + position[0]}+{self.master.winfo_rooty() + position[1]}")
        self.update_idletasks()

        if not self._visible:
            self.withdraw()

    def relative_x(self):
        return self.winfo_rootx() - self.master.winfo_rootx()

    def relative_y(self):
        return self.winfo_rooty() - self.master.winfo_rooty()

    def minimize(self): self.iconify()
    def restore(self): self.deiconify()
    def deiconify(self):
        if self._visible:
            self.geometry(f"+{self.master.winfo_rootx() + self.relative_x()}+{self.master.winfo_rooty() + self.relative_y()}")
            super().deiconify()

    def visible(self, bool=None):
        if bool is not None:
            self._visible = bool
        else:
            return self._visible
        self.deiconify() if self._visible else self.withdraw()


class Window(Background):
    def __init__(self, width:int=400, height:int=300, x:int=100, y:int=100, title=""):
        self._window = Windowable(width, height, x, y, title)
        super().__init__(self._window, width=width, height=height)
        self.place(x=0, y=0)

    def bindDrag(self, widget): self._window.bindDrag(widget)
    def bindChild(self, child_window:ChildWindow): self._window.bindChild(child_window)
    def loadTabImage(self, image_path:str): self._window.loadTabImage(image_path)
    def minimize(self): self._window.minimize()
    def restore(self): self._window.restore()


"""
A Windowable is a primary/parent window without a top bar or any controls. This is accomplished be telling the OS'
window manager to ignore it. Which means that its taskbar presence and alt+tab functionality must be faked back into
place. So a 2nd, invisible, window is spawned and maintained to serve as the OS-tracked window.

Use loadTabImage() to populate the alt+tab overlay with a custom logo/image.
"""
class Windowable(tk.Tk):
    def __init__(self, width:int=400, height:int=300, x:int=100, y:int=100, title=""):
        self._offset_w, self._offset_h = width // 2, height // 2
        self.child_list = []
        self.drag_locked = True
        self._lost_focus = time()
        self._drag_widget = None

        super().__init__()
        self.overrideredirect(True)
        self.title(title)
        self.geometry(f"{width}x{height}+{x}+{y}")

        # overrideredirect() causes the OS to ignore the window. So a taskbar/tab presence is manufactured and managed.
        self.taskbar_handle = tk.Toplevel(self)
        self.taskbar_handle.title(title)

        self.taskbar_handle.geometry(f"0x0+{x + self._offset_w}+{y + self._offset_h}")
        self.taskbar_handle.wm_attributes('-alpha', 0.0)
        self.taskbar_handle.wait_visibility()
        self.taskbar_handle.wm_attributes('-alpha', 0.0)
        self.taskbar_handle.iconify()

        # Establish default bindings
        self.bind("<ButtonRelease-1>", self.mouseUp)
        self.bind("<FocusIn>", self.tookFocus)
        self.bind("<FocusOut>", self.lostFocus)
        self.taskbar_handle.bind("<Map>", self.deiconify)

        self.update_idletasks()
        self._heartbeat()

    def bindDrag(self, widget:tk.Canvas):
        if widget is not None:
            if self._drag_widget is not None: self._drag_widget.unbind("<B1-Motion>")
            widget.bind("<B1-Motion>", self.mouseDrag)
            self._drag_widget = widget

    def bindChild(self, child_window:ChildWindow):
        self.child_list.append(child_window)

    # loadTabImage() draws and fits a custom image to the invisible, OS-tracked window -- to be displayed on alt+tab.
    def loadTabImage(self, image_path):
        img = UImage(file=resolvePath(image_path))
        img_w, img_h = img.width(), img.height()
        self._update_offsets()

        self.drag_locked = False
        self.taskbar_handle.deiconify()
        self.taskbar_handle.geometry(f"{img_w}x{img_h}+"
                                     f"{self.winfo_rootx() + self._offset_w}+"
                                     f"{self.winfo_rooty() + self._offset_h}")
        tab_image = Background.fromImage(self.taskbar_handle, img_w, img_h, img)
        tab_image.place(x=0, y=0)
        self.taskbar_handle.update()
        self.taskbar_handle.iconify()
        self.drag_locked = True

    def mouseDrag(self, event):
        if self.drag_locked:
            self.x = event.x
            self.y = event.y
            self._update_offsets()
            self.drag_locked = False
            self.taskbar_handle.deiconify()
            self.focus_force()
            self.active_children = [child for child in self.child_list if child.visible]

        x = self.winfo_x() + event.x - self.x
        y = self.winfo_y() + event.y - self.y
        self.taskbar_handle.geometry(f"+{x + self._offset_w}+{y + self._offset_h}")
        self.geometry(f"+{x}+{y}")

        for child in self.active_children:
            child.geometry(f"+{x + child.relative_x()}+{y + child.relative_y()}")

    def mouseUp(self, event):
        if not self.drag_locked:
            self.taskbar_handle.wm_iconify()
            self.focus_force()
            self.drag_locked = True

    def tookFocus(self, event):
        for child in self.child_list:
            child.lift()

    def lostFocus(self, event): self._lost_focus = time() + .4

    def minimize(self): self.iconify()
    def iconify(self, event=None):
        for child in self.child_list:
            child.withdraw()
        self.withdraw()
        self.taskbar_handle.iconify()

    def restore(self): self.deiconify()
    def deiconify(self, event=None):
        if self.drag_locked:
            if self.wm_state() == tk.NORMAL and time() < self._lost_focus:
                self.iconify()
            else:
                super().deiconify()
                for child in self.child_list:
                    child.deiconify()
                self.focus_force()
            self.taskbar_handle.wm_iconify()

    """
    _heartbeat(): Tk's update/idletasks system throttles aggressively, preferring to "hibernate" at all costs. This
    induces a kind of stop-and-go stuttering to Tk's overall performance that isn't usually perceivable by a user.
    But because guiABLE is rendering images at high speeds, the stuttering becomes visible in canvas draws.  

    To achieve a steady canvas 'frame rate,' Tk's idletasks system must be explicitly awakened, on a schedule. This
    _heartbeat function uses Tk's .after() method to accomplish that. By simply calling itself once every 'n'
    milliseconds, Tk is awakened to process any events that have stacked up in the queue -- including Canvas operations.

    A 2ms heartbeat is the fastest heartbeat that still throttles to zero CPU use, on modern platforms.
    """
    def _heartbeat(self): self.after(2, self._heartbeat)

    def _update_offsets(self):
        self._offset_w = (self.winfo_width() - self.taskbar_handle.winfo_width()) // 2
        self._offset_h = (self.winfo_height() - self.taskbar_handle.winfo_height()) // 2
