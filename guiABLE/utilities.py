from tkinter import PhotoImage, TclError, Canvas
import os
import sys
from typing import Optional


def warnPrint(message:any, *, level:str = "warning"):
    COLORS = {
        "info": "\033[96m",
        "warning": "\033[93m",
        "error": "\033[91m"
    }
    color = COLORS.get(level.lower(), "\033[93m")
    print(f"{color}[guiABLE {level.upper()}]\033[0m {message}")


# ---------- Path Functions ----------
def isAbsolute(path:str) -> bool: return os.path.isabs(path)
def appRootDir() -> str: return os.path.dirname(os.path.abspath(sys.argv[0]))    # Return directory of app/entrypoint

def resolvePath(path:str, default_root:str=None) -> Optional[str]:
    if not path or not isinstance(path, str): return None
    path = os.path.normpath(path)           # Normalize slashes, strip weirdness
    if os.path.exists(path) or os.path.isabs(path):     # If it exists of its absolute (but wrong) return unchanged.
        return path

    alt_path = os.path.join(appRootDir() if default_root is None else default_root, path)
    if os.path.exists(alt_path): return alt_path

    warnPrint(f"Resource not found: '{path}'")
    return path


# ---------- Image Functions ----------
def loadImage(image_path:str) -> PhotoImage:
    try:
        return PhotoImage(file=image_path)
    except TclError:
        warnPrint(f"Image not found: {image_path}")
    return PhotoImage(width=0, height=0)


def drawBar(trough_image:PhotoImage, cap_image:PhotoImage, width:int, height:int, horizontal:bool = False) -> PhotoImage:
    """Constructs a full-width or full-height scrollbar image from caps and a tileable mid-section."""
    newimg = PhotoImage(width=width, height=height)
    cap_w, cap_h = cap_image.width(), cap_image.height()

    if horizontal or width > height:
        putToImage(cap_image, newimg, (0, 0, cap_h, cap_w), rotate=True)
        putToImage(trough_image, newimg, (cap_h, 0, width-cap_h, height), rotate=True)
        putToImage(cap_image, newimg, (width-cap_h, 0, width, height), mirror_x=True, rotate=True)
    else:
        putToImage(cap_image, newimg, (0, 0, cap_w, cap_h))
        putToImage(trough_image, newimg, (0, cap_h, width, height-cap_h))
        putToImage(cap_image, newimg, (0, height-cap_h, width, height), mirror_y=True)

    return newimg


def putToImage(brush:PhotoImage, canvas:PhotoImage, bbox:tuple[int,int,int,int],
               mirror_x:bool = False, mirror_y:bool = False, rotate:bool = False):
    value1 = brush.height() if rotate else brush.width()
    value2 = brush.width() if rotate else brush.height()
    start1, end1, step1 = (value1-1, -1, -1) if mirror_x else (0, value1, 1)
    start2, end2, step2 = (value2-1, -1, -1) if mirror_y else (0, value2, 1)

    data = [
        "{" + " ".join(
            f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            for row in range(start1, end1, step1)
            for color in [brush.get(col if rotate else row, row if rotate else col)]
        ) + "}"
        for col in range(start2, end2, step2)
    ]

    canvas.put(" ".join(data), to=bbox)


def cropImage(image:PhotoImage, x:int, y:int, width:int, height:int) -> PhotoImage:
    # Conform geometry to image area.
    x1 = max(0, min(x, image.width() - width))
    y1 = max(0, min(y, image.height() - height))
    w = min(width, image.width() - x1)
    h = min(height, image.height() - y1)

    # Warn if adjustments/corrections were made.
    if w != width or h != height or x1 != x or y1 != y:
        warnPrint(f"Image crop exceeded bounds and was modified:\r"
                  f"x: {x} -> {x1}\r"
                  f"y: {y} -> {y1}\r"
                  f"width: {width} -> {w}\r"
                  f"height: {height} -> {h}")

    # Crop the image and return
    cropped = PhotoImage(width=width, height=height)
    cropped.tk.call(cropped, 'copy', image,
                    '-from', x, y, x + width, y + height,
                    '-to', 0, 0)
    return cropped


def composeImages(base:PhotoImage, *overlays: PhotoImage) -> PhotoImage:
    width, height = base.width(), base.height()
    composed = PhotoImage(width=width, height=height)

    # Copy base
    composed.tk.call(composed, 'copy', base, '-from', 0, 0, width, height, '-to', 0, 0)

    # Overlay each image in order
    for overlay in overlays:
        ow, oh = overlay.width(), overlay.height()
        w = min(width, ow)
        h = min(height, oh)
        composed.tk.call(composed, 'copy', overlay, '-from', 0, 0, w, h, '-to', 0, 0)

    return composed


# ---------- Widget Utility Functions ----------
def getGeometry(widget:Canvas) -> (int, int, int, int):
    return widget.winfo_x(), widget.winfo_y(), widget.winfo_width(), widget.winfo_height()


def geometryFromString(geometry:str) -> tuple[int, int, int, int]:
    try:
        parts = geometry.split("+", 1)
        w, h = [int(n) for n in parts[0].split("x")]
        if len(parts) == 2:
            x, y = [int(n) for n in parts[1].split("+")]
        else: x, y = 0, 0

        return x, y, w, h
    except Exception:
        raise ValueError(f"Invalid geometry string: '{geometry}'")


def limitMove(pos:int, extent:int, min_val:int, max_val:int) -> int:
    if pos < min_val: return min_val
    elif pos + extent > max_val: return max_val - extent
    return pos


def getLocalMouse(widget:Canvas) -> (int, int, bool):
    x = widget.winfo_pointerx() - widget.winfo_rootx()
    y = widget.winfo_pointery() - widget.winfo_rooty()
    if x < 0 or x > widget.winfo_width(): return x, y, False
    if y < 0 or y > widget.winfo_height(): return x, y, False
    return x, y, True


def updateHover(widget):
    if isinstance(widget, Canvas):
        x, y, mouse_in = getLocalMouse(widget)
        if widget.enabled:
            widget.mouseIn(None) if mouse_in else widget.mouseOut(None)
        else:
            widget.disable()
