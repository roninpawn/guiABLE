import sys


class WindowBackend:
    def __init__(self, window): self.window = window

    def configureRoot(self) -> bool:
        self.window.overrideredirect(True)
        return False

    def configureChild(self, owner=None, stack_with_parent=True, topmost=False):
        self.window.overrideredirect(True)
        self.setOwner(owner if stack_with_parent else None)
        self.setTopmost(topmost)

    def setOwner(self, owner=None):
        owner = owner._w if owner is not None else ""
        self.window.tk.call("wm", "transient", self.window._w, owner)

    def setTopmost(self, topmost:bool):
        self.window.wm_attributes("-topmost", bool(topmost))

    def minimize(self): self.window.tk.call("wm", "iconify", self.window._w)
    def restore(self): self.window.tk.call("wm", "deiconify", self.window._w)
    def raiseWindow(self): self.window.lift()

    def beginMove(self, x:int, y:int) -> bool: return False
    def moveWindows(self, windows):
        for window in windows:
            window.wm_geometry(f"{window.x:+d}{window.y:+d}")

    def workArea(self, x:int, y:int, width:int, height:int) -> tuple[int,int,int,int]:
        return (self.window.winfo_vrootx(), self.window.winfo_vrooty(),
                self.window.winfo_vrootwidth(), self.window.winfo_vrootheight())

    def acceptConfigureLocation(self, x:int, y:int) -> bool: return True


class WindowsWindowBackend(WindowBackend):
    HWND_TOP = 0

    GWL_STYLE = -16
    GWL_EXSTYLE = -20
    GWLP_HWNDPARENT = -8

    WS_CAPTION = 0x00C00000
    WS_SYSMENU = 0x00080000
    WS_MINIMIZEBOX = 0x00020000

    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_APPWINDOW = 0x00040000

    WM_NCCALCSIZE = 0x0083
    WM_NCLBUTTONDOWN = 0x00A1

    HTCAPTION = 2

    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    SWP_FRAMECHANGED = 0x0020
    SWP_NOOWNERZORDER = 0x0200

    SW_MINIMIZE = 6
    SW_RESTORE = 9

    MONITOR_DEFAULTTONEAREST = 2

    WM_WINDOWPOSCHANGED = 0x0047


    def __init__(self, window):
        super().__init__(window)

        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._user32 = ctypes.windll.user32
        self._comctl32 = ctypes.windll.comctl32
        self._subclassed_hwnd = None

        # Addresses SWMP_NOMOVE Bug by passing last good x/y when incoming x/y are not for use as movement.
        self._last_window_position = self.window.location

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

        self._set_window_long_ptr = getattr(self._user32, "SetWindowLongPtrW", self._user32.SetWindowLongW)
        self._set_window_long_ptr.argtypes = wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t
        self._set_window_long_ptr.restype = ctypes.c_ssize_t

        self._user32.BeginDeferWindowPos.argtypes = (ctypes.c_int,)
        self._user32.BeginDeferWindowPos.restype = wintypes.HANDLE

        self._RECT = wintypes.RECT

        self._user32.GetWindowRect.argtypes = wintypes.HWND, ctypes.POINTER(wintypes.RECT)
        self._user32.GetWindowRect.restype = wintypes.BOOL

        self._user32.PostMessageW.argtypes = wintypes.HWND, wintypes.UINT, wparam_t, lparam_t
        self._user32.PostMessageW.restype = wintypes.BOOL

        self._user32.ReleaseCapture.argtypes = ()
        self._user32.ReleaseCapture.restype = wintypes.BOOL

        self._user32.SendMessageW.argtypes = wintypes.HWND, wintypes.UINT, wparam_t, lparam_t
        self._user32.SendMessageW.restype = result_t

        self._user32.DeferWindowPos.argtypes = (
            wintypes.HANDLE, wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, wintypes.UINT)
        self._user32.DeferWindowPos.restype = wintypes.HANDLE

        self._user32.EndDeferWindowPos.argtypes = (wintypes.HANDLE,)
        self._user32.EndDeferWindowPos.restype = wintypes.BOOL

        class MONITORINFO(self._ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

        self._MONITORINFO = MONITORINFO

        self._user32.MonitorFromRect.argtypes = self._ctypes.POINTER(wintypes.RECT), wintypes.DWORD
        self._user32.MonitorFromRect.restype = wintypes.HANDLE

        self._user32.GetMonitorInfoW.argtypes = wintypes.HANDLE, self._ctypes.c_void_p
        self._user32.GetMonitorInfoW.restype = wintypes.BOOL

        class WINDOWPOS(ctypes.Structure):
            _fields_ = [("hwnd", wintypes.HWND), ("hwndInsertAfter", wintypes.HWND),
                        ("x", ctypes.c_int), ("y", ctypes.c_int), ("cx", ctypes.c_int),
                        ("cy", ctypes.c_int), ("flags", wintypes.UINT)]

        self._WINDOWPOS = WINDOWPOS

    def _hwnd(self, window=None, refresh=True) -> int:
        window = window or self.window
        if refresh: window.update_idletasks()
        return int(str(window.wm_frame()), 0)

    def _windowProc(self, hwnd, message, wparam, lparam, subclass_id, ref_data):
        if message == self.WM_NCCALCSIZE and wparam: return 0

        # Tk wrongly consumes x/y from SWP_NOMOVE signals, so we must sanitize them before Tkinter's <Configure> sees.
        if message == self.WM_WINDOWPOSCHANGED:
            pos = self._ctypes.cast(lparam, self._ctypes.POINTER(self._WINDOWPOS)).contents

            if pos.flags & self.SWP_NOMOVE:
                pos.x, pos.y = self._last_window_position
            else: self._last_window_position = (pos.x, pos.y)

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

        flags = self.SWP_NOSIZE | self.SWP_NOMOVE | self.SWP_NOZORDER | self.SWP_FRAMECHANGED

        if not self._user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, flags):
            raise self._ctypes.WinError()

        window.deiconify()
        return True

    def setOwner(self, owner=None):
        hwnd = self._hwnd()
        owner_hwnd = self._hwnd(owner) if owner is not None else 0
        self._set_window_long_ptr(hwnd, self.GWLP_HWNDPARENT, owner_hwnd)

    def minimize(self): self._user32.ShowWindow(self._hwnd(), self.SW_MINIMIZE)
    def restore(self): self._user32.ShowWindow(self._hwnd(), self.SW_RESTORE)

    def raiseWindow(self):
        flags = self.SWP_NOMOVE | self.SWP_NOSIZE | self.SWP_NOOWNERZORDER
        if not self._user32.SetWindowPos(self._hwnd(), self.HWND_TOP, 0, 0, 0, 0, flags):
            raise self._ctypes.WinError()

    def beginMove(self, x:int, y:int) -> bool:
        lparam = ((int(y) & 0xFFFF) << 16) | (int(x) & 0xFFFF)

        self._user32.ReleaseCapture()

        if not self._user32.PostMessageW(self._hwnd(), self.WM_NCLBUTTONDOWN, self.HTCAPTION, lparam):
            raise self._ctypes.WinError()

        return True

    def moveWindows(self, windows):
        if not windows: return

        batch = self._user32.BeginDeferWindowPos(len(windows))
        if not batch: raise self._ctypes.WinError()

        flags = self.SWP_NOSIZE | self.SWP_NOZORDER | self.SWP_NOACTIVATE | self.SWP_NOOWNERZORDER

        for window in windows:
            batch = self._user32.DeferWindowPos(
                batch, self._hwnd(window, False), None, window.x, window.y, 0, 0, flags)

            if not batch: raise self._ctypes.WinError()

        if not self._user32.EndDeferWindowPos(batch):
            raise self._ctypes.WinError()

    def workArea(self, x:int, y:int, width:int, height:int) -> tuple[int,int,int,int]:
        rect = self._RECT(x, y, x + max(1, width), y + max(1, height))
        monitor = self._user32.MonitorFromRect(self._ctypes.byref(rect), self.MONITOR_DEFAULTTONEAREST)

        info = self._MONITORINFO()
        info.cbSize = self._ctypes.sizeof(info)

        if not self._user32.GetMonitorInfoW(monitor, self._ctypes.byref(info)):
            raise self._ctypes.WinError()

        work = info.rcWork
        return work.left, work.top, work.right - work.left, work.bottom - work.top


def windowBackend(window) -> WindowBackend:
    return WindowsWindowBackend(window) if sys.platform == "win32" else WindowBackend(window)