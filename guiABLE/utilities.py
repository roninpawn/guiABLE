from tkinter import PhotoImage, TclError, Canvas
import os
import sys
from typing import NamedTuple


class Overlap(NamedTuple):
    crop: tuple[int,int,int,int]   # (x,y,w,h) of other's coords -- to crop from
    insert: tuple[int,int]         # (x,y) in self coords -- position to composite to


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

def resolvePath(path:str, default_root:str=None) -> str | None:
    if not path or not isinstance(path, str): return None
    path = os.path.normpath(path)           # Normalize slashes, strip weirdness
    if os.path.exists(path) or os.path.isabs(path):     # If it exists of its absolute (but wrong) return unchanged.
        return path

    alt_path = os.path.join(appRootDir() if default_root is None else default_root, path)
    if os.path.exists(alt_path): return alt_path

    warnPrint(f"Resource not found: '{path}'")
    return path


# ---------- Image Functions ----------
def loadImageByPath(image_path:str) -> PhotoImage | None:
    try:
        return PhotoImage(file=image_path)
    except TclError:
        warnPrint(f"Image not found: {image_path}")
    return None


def loadImage(path_or_image:str | PhotoImage) -> tuple[PhotoImage | None, str | None]:
    # Conform either input type to PhotoImage and path (path used as 'source' in _bySprite())
    if isinstance(path_or_image, str):
        r_path = resolvePath(path_or_image)
        return loadImageByPath(r_path), r_path
    else:
        if isinstance(path_or_image, PhotoImage): image = path_or_image
        else:
            warnPrint(f"Invalid PhotoImage: {path_or_image}")
            return None, None
    return image, "passed internally"


def solidColorImage(width: int, height: int, color: str) -> PhotoImage:
    img = PhotoImage(width=width, height=height)
    hex_color = color if color.startswith("#") else img.tk.call("winfo", "rgb", ".", color)
    img.put("{" + " ".join([hex_color] * width) + "}", to=(0, 0, width, height))
    return img


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


def fastCrop(crop_to: PhotoImage, crop_from:PhotoImage, crop_x:int, crop_y:int, crop_w:int, crop_h:int) -> PhotoImage:
    fw, fh = crop_from.width(), crop_from.height()
    if crop_x <= fw and crop_y <= fh:
        width, height = min(crop_w, fw - crop_x), min(crop_h, fh - crop_y)
        crop_to.copy_replace(crop_from, from_coords=(crop_x, crop_y, crop_x + width, crop_y + height))

def cropImage(image:PhotoImage, x:int, y:int, width:int, height:int) -> PhotoImage:
    cropped = PhotoImage(width=width, height=height)
    fastCrop(cropped, image, x, y, width, height)
    return cropped

def fastComposite(base_image: PhotoImage, overlay_image: PhotoImage, dest_x:int, dest_y:int,
                  src_x: int = 0, src_y: int = 0) -> PhotoImage:
    x2 = min(base_image.width(), dest_x + overlay_image.width())
    y2 = min(base_image.height(), dest_y + overlay_image.height())
    if x2 > dest_x and y2 > dest_y:
        base_image.copy_replace(overlay_image, from_coords=(src_x, src_y, x2 - dest_x, y2 - dest_y), to=(dest_x, dest_y))

def compositeImage(base: PhotoImage, overlay_image: PhotoImage, x:int, y:int) -> PhotoImage:
    fastComposite(base, overlay_image, x, y)
    return base


"""
---------- Widget Utility Functions ----------
getGeometry() fetches Winfo_ geometry by string and parses the string into ints. This was found to be slightly faster
than polling the 4x equivalent Winfo_ (x,y,width,height) access points. replace().split() was also found faster than
regex, .partition(), and .find() with index slicing.
"""
def getGeometry(widget) -> (int, int, int, int):
        w, h, x, y = widget.winfo_geometry().replace("x", "+", 1).split("+")
        return int(x), int(y), int(w), int(h)

# geometryFromString() is useful in parsing geometry passed as an argument, before its been handled or applied.
def geometryFromString(geometry:str) -> tuple[int, int, int, int]:
    try:
        parts = geometry.split("+", 1)
        w, h = parts[0].split("x")
        w, h = int(w), int(h)

        if len(parts) == 2:
            x, y = parts[1].split("+")
            x, y = int(x), int(y)
        else: x, y = 0, 0
        return x, y, w, h

    except Exception:
        raise ValueError(f"Invalid geometry string: '{geometry}'")

""" 
getOverlap() returns the overlapping area of 'other' along with the x, y point in self where the overlap begins.
Passing order is important. The return of this function is used as 'instructions' for cropping the overlapping area from
'other' and compositing them onto 'self' in sibling-transparency.    
"""
def getOverlap(self_xywh:tuple, other_xywh:tuple) -> Overlap | None:
    sx, sy, sw, sh = self_xywh
    ox, oy, ow, oh = other_xywh

    ix  = max(sx, ox)
    iy  = max(sy, oy)
    fx  = min(sx+sw, ox+ow)
    fy  = min(sy+sh, oy+oh)
    if fx <= ix or fy <= iy: return None

    return Overlap(
        crop=(ix-ox, iy-oy, fx-ix, fy-iy),
        insert=(ix-sx, iy-sy),
    )

"""
rectsOverlap() was found to be the fastest method for finding whether two areas overlap each other. It is 2-3x faster
than getOverlap, and therefore suitable as a pre-test to determine which areas need getOverlap().
"""
def rectsOverlap(a_xywh, b_xywh) -> bool:
    ax, ay, aw, ah = a_xywh
    bx, by, bw, bh = b_xywh

    return not (
        ax + aw <= bx or  # a is left of b
        ax >= bx + bw or  # a is right of b
        ay + ah <= by or  # a is above b
        ay >= by + bh     # a is below b
    )

def rectUnion(a_xywh, b_xywh) -> tuple[int, int, int, int]:
    ax, ay, aw, ah = a_xywh
    bx, by, bw, bh = b_xywh
    ox, oy = min(ax, bx), min(ay, by)
    return ox, oy, max(ax+aw, bx+bw)-ox, max(ay+ah, by+bh)-oy

# Below are old utility methods that could probably be rewritten or deprecated entirely.
def limitMove(pos:int, extent:int, min_val:int, max_val:int) -> int:
    return max(min_val, min(pos, max_val - extent))

def getLocalMouse(widget:Canvas) -> (int, int, bool):
    px, py = widget.winfo_pointerxy()
    x = px - widget.winfo_rootx()
    y = py - widget.winfo_rooty()
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
