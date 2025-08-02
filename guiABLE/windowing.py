import tkinter as tk
from time import time
from .utilities import warnPrint


class Windowable(tk.Tk):
    def __init__(self, geometry="200x200", title=""):
        self._mid_width = 0
        self._mid_height = 0
        self._lost_focus = time()
        self.child_list = []
        self.drag_locked = True

        super().__init__()
        self.overrideredirect(True)
        self.title(title)
        self.geometry(geometry)

        self.taskbar_handle = tk.Toplevel(self)
        self.taskbar_handle.title(title)

        taskbar_geometry = self.geometry()
        self.taskbar_handle.geometry(f"0x0+{taskbar_geometry.split('+', 1)[1]}")
        self.taskbar_handle.wm_attributes('-alpha', 0.0)
        self.taskbar_handle.wait_visibility()
        self.taskbar_handle.wm_attributes('-alpha', 0.0)
        self.taskbar_handle.iconify()

        self.bind("<ButtonRelease-1>", self.mouseUp)
        self.bind("<FocusIn>", self.tookFocus)
        self.bind("<FocusOut>", self.lostFocus)
        self.taskbar_handle.bind("<Map>", self.deiconify)

        self.update_idletasks()

    def bindDrag(self, widget):
        if widget is None:
            widget.unbind("<B1-Motion>")
        else:
            widget.bind("<B1-Motion>", self.mouseDrag)

    def bindChild(self, ChildableWindow):
        self.child_list.append(ChildableWindow)

    def loadTabImage(self, image_path):
        img = tk.PhotoImage(file=image_path)
        img_w, img_h = img.width(), img.height()
        self._mid_width = int((img_w - self.winfo_width()) / 2)
        self._mid_height = int((img_h - self.winfo_height()) / 2)

        self.drag_locked = False
        self.taskbar_handle.deiconify()
        self.taskbar_handle.geometry(f"{img_w}x{img_h}+{self.winfo_rootx() - self._mid_width}+{self.winfo_rooty() - self._mid_height}")
        tab_image = Backgroundable(self.taskbar_handle, img_w, img_h)
        tab_image.directSetImage(img)
        tab_image.place(x=0, y=0)
        self.taskbar_handle.update()
        self.taskbar_handle.iconify()
        self.drag_locked = True

    def mouseDrag(self, event):
        if self.drag_locked:
            self.x = event.x
            self.y = event.y
            self.drag_locked = False
            self.taskbar_handle.deiconify()
            self.focus_force()
            self.active_children = [child for child in self.child_list if child.visible]

        x = self.winfo_x() + event.x - self.x
        y = self.winfo_y() + event.y - self.y
        self.taskbar_handle.geometry(f"+{x - self._mid_width}+{y - self._mid_height}")
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

    def iconify(self, event=None):
        for child in self.child_list:
            child.withdraw()
        self.withdraw()
        self.taskbar_handle.iconify()

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


class Canvasable(tk.Text):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bd=0, padx=0, pady=0, state=tk.DISABLED, cursor="arrow", **kwargs)
        self.configure(selectbackground=self.cget("bg"))

    def _configure(self, cmd, cnf, kw):
        if "bg" in kw:
            kw["selectbackground"] = kw["bg"]
        if "background" in kw:
            kw["selectbackground"] = kw["background"]
        super()._configure(cmd, cnf, kw)


class Backgroundable(tk.Frame):
    def __init__(self, parent, width, height, image_path=None, **kwargs):
        super().__init__(parent, width=width, height=height)
        self.pack_propagate(tk.FALSE)
        self.inner = Canvasable(self, **kwargs)

        if image_path is not None:
            self.setImage(image_path)
        self.inner.pack(fill=tk.BOTH, expand=True)

    def setImage(self, image_path):
        try:
            self.directSetImage(tk.PhotoImage(file=image_path))
        except tk.TclError:
            warnPrint(f"Image not found: {image_path}")

    def directSetImage(self, image):
        self.inner.configure(state=tk.NORMAL)
        self.inner.delete(1.0, tk.END)
        self._img = image
        self.inner.image_create(tk.END, image=self._img)
        self.inner.configure(state=tk.DISABLED)

    def empty(self):
        for child in self.inner.winfo_children():
            child.destroy()
        self.inner.configure(width=1, height=1)
