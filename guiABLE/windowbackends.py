import sys


class WindowBackend:
    def __init__(self, window): self.window = window

    def configureRoot(self) -> bool:
        self.window.overrideredirect(True)
        return False

    def configureChild(self, owner=None):
        self.window.overrideredirect(True)

    def minimize(self): self.window.tk.call("wm", "iconify", self.window._w)
    def restore(self): self.window.tk.call("wm", "deiconify", self.window._w)


class WindowsWindowBackend(WindowBackend):
    GWL_STYLE = -16
    GWL_EXSTYLE = -20
    GWLP_HWNDPARENT = -8

    WS_CAPTION = 0x00C00000
    WS_SYSMENU = 0x00080000
    WS_MINIMIZEBOX = 0x00020000

    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_APPWINDOW = 0x00040000

    WM_NCCALCSIZE = 0x0083

    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    SWP_FRAMECHANGED = 0x0020

    SW_MINIMIZE = 6
    SW_RESTORE = 9

    def __init__(self, window):
        super().__init__(window)

        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._user32 = ctypes.windll.user32
        self._comctl32 = ctypes.windll.comctl32
        self._subclassed_hwnd = None

        result_t = ctypes.c_ssize_t
        wparam_t = ctypes.c_size_t
        lparam_t = ctypes.c_ssize_t
        ptr_t = ctypes.c_size_t

        self._SubclassProc = ctypes.WINFUNCTYPE(
            result_t, wintypes.HWND, wintypes.UINT, wparam_t, lparam_t, ptr_t, ptr_t)
        self._subclass_proc = self._SubclassProc(self._windowProc)
        self._subclass_id = id(self)

        self._user32.GetWindowLongW.argtypes = wintypes.HWND, ctypes.c_int
        self._user32.GetWindowLongW.restype = ctypes.c_long
        self._user32.SetWindowLongW.argtypes = wintypes.HWND, ctypes.c_int, ctypes.c_long
        self._user32.SetWindowLongW.restype = ctypes.c_long

        self._user32.SetWindowPos.argtypes = (
            wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, wintypes.UINT)
        self._user32.SetWindowPos.restype = wintypes.BOOL

        self._user32.ShowWindow.argtypes = wintypes.HWND, ctypes.c_int
        self._user32.ShowWindow.restype = wintypes.BOOL

        self._comctl32.SetWindowSubclass.argtypes = wintypes.HWND, self._SubclassProc, ptr_t, ptr_t
        self._comctl32.SetWindowSubclass.restype = wintypes.BOOL

        self._comctl32.DefSubclassProc.argtypes = wintypes.HWND, wintypes.UINT, wparam_t, lparam_t
        self._comctl32.DefSubclassProc.restype = result_t

    def _hwnd(self, window=None) -> int:
        window = window or self.window
        window.update_idletasks()
        return int(str(window.wm_frame()), 0)

    def _windowProc(self, hwnd, message, wparam, lparam, subclass_id, ref_data):
        # Preserve Tk's borderless geometry while allowing Windows to retain normal frame semantics.
        if message == self.WM_NCCALCSIZE and wparam: return 0
        return self._comctl32.DefSubclassProc(hwnd, message, wparam, lparam)

    def _subclass(self, hwnd):
        if self._subclassed_hwnd == hwnd: return

        if not self._comctl32.SetWindowSubclass(hwnd, self._subclass_proc, self._subclass_id, 0):
            raise self._ctypes.WinError()

        self._subclassed_hwnd = hwnd

    def configureRoot(self) -> bool:
        window = self.window

        # Keep Tk's internal geometry model borderless.
        window.overrideredirect(True)
        hwnd = self._hwnd()
        self._subclass(hwnd)

        # Hide while changing Shell identity/style so the taskbar never sees an intermediate state.
        window.withdraw()

        # Give Windows normal application-window semantics without allowing its frame to consume client pixels.
        style = self._user32.GetWindowLongW(hwnd, self.GWL_STYLE)
        style |= self.WS_CAPTION | self.WS_SYSMENU | self.WS_MINIMIZEBOX
        self._user32.SetWindowLongW(hwnd, self.GWL_STYLE, style)

        ex_style = self._user32.GetWindowLongW(hwnd, self.GWL_EXSTYLE)
        ex_style &= ~self.WS_EX_TOOLWINDOW
        ex_style |= self.WS_EX_APPWINDOW
        self._user32.SetWindowLongW(hwnd, self.GWL_EXSTYLE, ex_style)

        flags = self.SWP_NOSIZE | self.SWP_NOMOVE | self.SWP_NOZORDER | \
                self.SWP_NOACTIVATE | self.SWP_FRAMECHANGED

        if not self._user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, flags):
            raise self._ctypes.WinError()

        window.deiconify()
        return True

    def configureChild(self, owner=None):
        self.window.overrideredirect(True)
        if owner is None: return

        hwnd, owner_hwnd = self._hwnd(), self._hwnd(owner)
        setter = getattr(self._user32, "SetWindowLongPtrW", self._user32.SetWindowLongW)
        setter(hwnd, self.GWLP_HWNDPARENT, owner_hwnd)

    def minimize(self): self._user32.ShowWindow(self._hwnd(), self.SW_MINIMIZE)
    def restore(self): self._user32.ShowWindow(self._hwnd(), self.SW_RESTORE)


def windowBackend(window) -> WindowBackend:
    return WindowsWindowBackend(window) if sys.platform == "win32" else WindowBackend(window)