import tkinter as tk
from time import time

from .skinnable import Skinnable
from .utilities import resolvePath, geometryFromString


"""
A ChildableWindow() is an OS-ignored window that is positioned relative to its parent window, and will travel with that
window, if it is moved. It does not appear in the taskbar, or in alt+tab overlays. It serves as the basis for a pop-up 
window, a configuration window, or even a persistent, detached floating interface.
"""
class ChildableWindow(tk.Toplevel):
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


"""
A Windowable is a primary/parent window without a top bar or any controls. This is accomplished be telling the OS' 
window manager to it. Which means that its taskbar presence and alt+tab functionality must be faked back into place. 
So a 2nd, invisible, window is spawned and maintained to serve as the OS-tracked window.

Use loadTabImage() to populate the alt+tab overlay with a custom logo/image.
"""
class Windowable(tk.Tk):
    def __init__(self, geometry="200x200", title=""):
        x, y, w, h = geometryFromString(geometry)
        self._offset_w, self._offset_h = w // 2, h // 2
        self.child_list = []
        self.drag_locked = True
        self._lost_focus = time()
        self._drag_widget = None

        super().__init__()
        self.overrideredirect(True)
        self.title(title)
        self.geometry(geometry)

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

    def bindChild(self, childable_window:ChildableWindow):
        self.child_list.append(childable_window)

    # loadTabImage() draws and fits a custom image to the invisible, OS-tracked window -- to be displayed on alt+tab.
    def loadTabImage(self, image_path):
        img = tk.PhotoImage(file=resolvePath(image_path))
        img_w, img_h = img.width(), img.height()
        self._update_offsets()

        self.drag_locked = False
        self.taskbar_handle.deiconify()
        self.taskbar_handle.geometry(f"{img_w}x{img_h}+"
                                     f"{self.winfo_rootx() + self._offset_w}+"
                                     f"{self.winfo_rooty() + self._offset_h}")
        tab_image = Backgroundable(self.taskbar_handle, img_w, img_h)
        tab_image.setImage(img)
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

    def lostFocus(self, event):
        self._lost_focus = time() + .4

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

    def _heartbeat(self):
        self.after(8, self._heartbeat)

    def _update_offsets(self):
        self._offset_w = (self.winfo_width() - self.taskbar_handle.winfo_width()) // 2
        self._offset_h = (self.winfo_height() - self.taskbar_handle.winfo_height()) // 2

"""
A Canvasable is a tk.Text window configured to eliminate all of its text-features and provide us with a clean canvas. 
This is necessary because tkinter's tk.Canvas does not track and update its 'dirty' redraw rectangles correctly. The
issue of slow/wrong redraws was solved in the tk.Text widget, but nowhere else. So we use tk.Text as the render canvas.
"""
class Canvasable(tk.Text):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bd=0, padx=0, pady=0, state="disabled", cursor="arrow", **kwargs)

    def configure(self, **kw):
        if "bg" in kw:      # Pass changes to bg through to the 'selectbackground' to maintain non-tk.Text() illusion.
            kw["selectbackground"] = kw["bg"]
        if "background" in kw:
            kw["selectbackground"] = kw["background"]
        super().configure(**kw)


class Frameable(tk.Frame):
    def __init__(self, parent, width, height, bg='gray', **kwargs):
        tk.Frame.__init__(self, parent, width=width, height=height)

        self._inner = Canvasable(self, bg=bg, **kwargs)     # A Frameable's skin() is its Canvasable's
        self.pack_propagate(False)
        self._inner.pack(fill="both", expand=True)

    @property
    def inner(self): return self._inner
    def bind(self, *args): self._inner.bind(*args)
    def unbind(self, *args): self._inner.unbind(*args)
    def configure(self, **kwargs): self._inner.configure(**kwargs)

    def empty(self):
        for child in self.inner.winfo_children(): child.destroy()
        self.inner.configure(width=1, height=1)

"""
A Backgroundable is a tk.Frame containing a .inner Canvasable() that serves as the canvas. It provides a more library-
standard interface for handling the unique configuration calls required to conform the tk.Text widget. And it attempts 
to abstract away the underlying duct-tape solution required to make tk.Canvas function. 
"""
class Backgroundable(Skinnable, Frameable):
    def __init__(self, parent, width, height, image_path=None, bg='gray', **kwargs):
        Skinnable.__init__(self)
        Frameable.__init__(self, parent, width=width, height=height, bg=bg, **kwargs)
        self.bind("<Configure>", self._geometry_changed)

        self._skin.setPaths(image_path)

        self.pack_propagate(False)
        self._inner.pack(fill="both", expand=True)

        self._skin.setBGColors(self._inner.cget("bg"))
        self._inner.configure(selectbackground=self._skin.bgColor())
        self.after_idle(self.redraw)

    @property
    def inner(self): return self._inner

    @classmethod
    def fromPath(cls, parent, width:int, height:int, image_path:str = None, bg:str = 'gray', **kwargs):
        return cls(parent, width, height, image_path, bg, **kwargs)
    @classmethod
    def fromImage(cls, parent, width:int, height:int, image:tk.PhotoImage = None, bg:str ='gray', **kwargs):
        bga = cls(parent, width, height, None, bg, **kwargs)
        bga.skin.setImage(image)
        return bga

    def empty(self):
        for child in self.inner.winfo_children():
            child.destroy()
        self.inner.configure(width=1, height=1)

    def redraw(self):
        if self.skin.hasImages():
            self._inner.configure(state="normal")
            self._inner.delete(1.0, tk.END)
            self._inner.image_create(tk.END, image=self._skin.image())
            self._inner.configure(state="disabled")
