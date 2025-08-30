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


def fastFlood(image:PhotoImage, image_width:int, image_height:int, color:str):
    image.put(color, to=(0, 0, image_width, image_height))

def floodImage(image:PhotoImage, color:str): fastFlood(image, image.width(), image.height(), color)

def newFlood(image_width:int, image_height:int, color:str):
    out = PhotoImage(width=image_width, height=image_height)
    fastFlood(out, image_width, image_height, color)
    return out


def fastFlip(flip_to:PhotoImage, flip_from:PhotoImage, w:int, h:int, flip_x:bool = False, flip_y:bool = False):
    if flip_x and flip_y:
        tmp = PhotoImage(width=w, height=h)
        [tmp.copy_replace(flip_from, from_coords=(col, 0, col + 1, h), to=(w-1-col, 0)) for col in range(w)]
        [flip_to.copy_replace(tmp, from_coords=(0, row, w, row + 1), to=(0, h-1-row)) for row in range(h)]
    elif flip_x: [flip_to.copy_replace(flip_from, from_coords=(col, 0, col + 1, h), to=(w-1-col, 0)) for col in range(w)]
    elif flip_y: [flip_to.copy_replace(flip_from, from_coords=(0, row, w, row + 1), to=(0, h-1-row)) for row in range(h)]

def flipImage(image:PhotoImage, flip_x:bool = False, flip_y:bool = False) -> PhotoImage:
    if isinstance(image, PhotoImage) and (flip_x or flip_y):
        w, h = image.width(), image.height()
        out = PhotoImage(width=w, height=h)
        fastFlip(out, image, w, h, flip_x, flip_y)
        return out
    return image


def fastRotate(rotate_to:PhotoImage, rotate_from:PhotoImage, w:int, h:int, clockwise:bool = True) -> PhotoImage | None:
    for y in range(h):
        yy = h-1-y if clockwise else y
        for x in range(w): rotate_to.copy_replace(rotate_from, from_coords=(x, y, x + 1, y + 1), to=(yy, x))

def rotateImage(image: PhotoImage, clockwise:bool = True) -> PhotoImage:
    if isinstance(image, PhotoImage):
        w, h = image.width(), image.height()
        out = PhotoImage(width=h, height=w)
        fastRotate(out, image, w, h, clockwise)
        return out
    return image


def fastTile(brush:PhotoImage, bw:int, bh:int, canvas:PhotoImage, cw:int, ch:int, bbox:tuple[int,int,int,int]):
    x1, y1, x2, y2 = bbox
    box_w, box_h = x2 - x1, y2 - y1
    bw, bh = min(bw, box_w), min(bh, box_h)
    # TODO: Do the largest blit from brush possible. Do 4 operations instead of 400.
    if bw and bh:
        for y in range(y1, y2, bh):
            h = min(bh, y2-y)
            for x in range(x1, x2, bw):
                w = min(bw, x2-x)
                if w >= 0 and h >= 0:
                    canvas.copy_replace(brush, from_coords=(0, 0, w, h), to=(x, y))

def tileImage(brush:PhotoImage, canvas:PhotoImage, bbox:tuple[int,int,int,int]):
    fastTile(brush, brush.width(), brush.height(), canvas, canvas.width(), canvas.height(), bbox)


def fastCrop(crop_to: PhotoImage, crop_from:PhotoImage, from_w:int, from_h:int,
             crop_x:int, crop_y:int, crop_w:int, crop_h:int) -> PhotoImage:
    if crop_x <= from_w and crop_y <= from_h:
        width, height = min(crop_w, from_w - crop_x), min(crop_h, from_h - crop_y)
        crop_to.copy_replace(crop_from, from_coords=(crop_x, crop_y, crop_x + width, crop_y + height))

def cropImage(image:PhotoImage, x:int, y:int, width:int, height:int) -> PhotoImage:
    cropped = PhotoImage(width=width, height=height)
    fastCrop(cropped, image, image.width(), image.height(), x, y, width, height)
    return cropped


def fastComposite(base_image: PhotoImage, base_w: int, base_h: int,
                  overlay_image: PhotoImage, dest_x:int, dest_y:int, overlay_w:int, overlay_h:int,
                  src_x: int = 0, src_y: int = 0):
    x2, y2 = min(base_w, dest_x + overlay_w), min(base_h, dest_y + overlay_h)
    if x2 > dest_x and y2 > dest_y:
       base_image.copy_replace(overlay_image, from_coords=(src_x, src_y, x2 - dest_x, y2 - dest_y), to=(dest_x, dest_y))

def compositeImage(base_image: PhotoImage, overlay_image: PhotoImage, x:int, y:int) -> PhotoImage:
    bx, bh = base_image.width(), base_image.height()
    ow, oh = overlay_image.width(), overlay_image.height()
    fastComposite(base_image, bx, bh, overlay_image, x, y, ow, oh)
    return base_image


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

def pointOverlapsRect(x:int, y:int, rect:tuple[int,int,int,int]) -> bool:
    rx, ry, rw, rh = rect
    return not (
        rx + rw < x < rx or
        ry + rh < y < y
    )

def rectUnion(a_xywh, b_xywh) -> tuple[int,int,int,int]:
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
