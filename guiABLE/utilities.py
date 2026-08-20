from collections import OrderedDict
from tkinter import TclError, Widget
from os import path as osPath
from sys import argv as sysArgV
from typing import NamedTuple

from guiABLE.uimage import UImage


class Overlap(NamedTuple):
    crop: tuple[int,int,int,int]   # (x,y,w,h) of other's coords -- to crop from
    insert: tuple[int,int]         # (x,y) in self coords -- position to composite to


class LimitedDict(OrderedDict):
    def __init__(self, maxsize=10, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.maxsize = maxsize

    def __getitem__(self, key):
        value = super().__getitem__(key)
        # Move key to end, marking it as recently used
        self.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        # Replace existing or insert new
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)

        # Drop least recently used
        if len(self) > self.maxsize:
            oldest_key, oldest_val = self.popitem(last=False)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


def warnPrint(message:any, *, level:str = "warning"):
    COLORS = {
        "info": "\033[96m",
        "warning": "\033[93m",
        "error": "\033[91m"
    }
    color = COLORS.get(level.lower(), "\033[93m")
    print(f"{color}[guiABLE {level.upper()}]\033[0m {message}")


"""
 ---------- Path Functions ----------
"""
def appRootDir() -> str: return osPath.dirname(osPath.abspath(sysArgV[0]))    # Return directory of app/entrypoint

def resolvePath(path:str, default_root:str=None) -> str | None:
    if not path or not isinstance(path, str): return None
    path = osPath.normpath(path)           # Normalize slashes, strip weirdness
    if osPath.exists(path) or osPath.isabs(path):     # If it exists of its absolute (but wrong) return unchanged.
        return path

    alt_path = osPath.join(appRootDir() if default_root is None else default_root, path)
    if osPath.exists(alt_path): return alt_path

    warnPrint(f"Resource not found: '{path}'")
    return path


"""
 ---------- Image Functions ----------
"""
def loadImageByPath(image_path:str) -> UImage | None:
    try: return UImage(file=image_path)
    except TclError: warnPrint(f"Image not found: {image_path}")
    return None

# loadImage(): Conform either input type to UImage and path (path used as 'source' in _bySprite())
def loadImage(path_or_image:str | UImage) -> tuple[UImage | None, str | None]:
    if isinstance(path_or_image, str):
        r_path = resolvePath(path_or_image)
        return loadImageByPath(r_path), r_path
    elif isinstance(path_or_image, UImage): image = path_or_image
    return image, "passed internally"


"""
 ---------- Geometry Functions ----------
getGeometry() fetches Winfo_ geometry by string and parses the string into ints. This was found to be slightly faster
than polling the 4x equivalent Winfo_ (x,y,width,height) access points. replace().split() was also found faster than
regex, .partition(), and .find() with index slicing. Collection() geometry is also managed here.
"""
def getGeometry(widget) -> tuple[int, int, int, int]:
    if not getattr(widget, "is_collection", False):
        w, h, x, y = widget.winfo_geometry().replace("x", "+", 1).split("+")
        x, y, w, h = int(x), int(y), int(w), int(h)

        # If widget is the child of a Collection(), localize its stored geometry for consistency of interface.
        if getattr(widget.parent, "is_collection", False):
            x -= widget.parent.x
            y -= widget.parent.y

        return x, y, w, h
    # If the widget is a Collection(), its geometry is simply the union of all of its children.
    else: return rectsUnion(*[(widget.x + child.x, widget.y + child.y, *child.size) for child in widget.getChildren()])

""" geometryFromString() is useful in parsing geometry passed as an argument, before its been handled or applied. """
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
    inter = rectIntersect(self_xywh, other_xywh)
    if inter is None: return None

    ix, iy, iw, ih = inter
    sx, sy = self_xywh[:2]
    ox, oy = other_xywh[:2]

    return Overlap(
        crop=(ix - ox, iy - oy, iw, ih),        # Overlap region in other's coords, for cropping from other
        insert=(ix - sx, iy - sy)               # Insert location in self's coords
    )

"""
rectsOverlap() was found to be the fastest method for finding whether two areas overlap each other. It is 2-3x faster
than getOverlap, and therefore suitable as a pre-test to determine which areas need getOverlap().
"""
def rectsOverlap(a_xywh, b_xywh) -> bool:
    ax, ay, aw, ah = a_xywh
    bx, by, bw, bh = b_xywh

    return not (            # Inverse formula breaks out of testing if any one returns True.
        ax + aw <= bx or    # a is left of b
        ax >= bx + bw or    # a is right of b
        ay + ah <= by or    # a is above b
        ay >= by + bh       # a is below b
    )

def rectIntersect(a_xywh:tuple, b_xywh:tuple) -> tuple|None:
    ax, ay, aw, ah = a_xywh
    bx, by, bw, bh = b_xywh

    ix = max(ax, bx)
    iy = max(ay, by)
    fx = min(ax + aw, bx + bw)
    fy = min(ay + ah, by + bh)

    if fx <= ix or fy <= iy: return None
    return ix, iy, fx - ix, fy - iy     # (x,y,w,h)

def pointIsInRect(x:int, y:int, rect:tuple[int,int,int,int]) -> bool:
    rx, ry, rw, rh = rect
    return rx+rw > x >= rx and ry+rh > y >= ry

def rectUnion(a_xywh:tuple[int,int,int,int], b_xywh:tuple[int,int,int,int]) -> tuple[int,int,int,int]:
    ax, ay, aw, ah = a_xywh
    bx, by, bw, bh = b_xywh
    ox, oy = min(ax, bx), min(ay, by)
    return ox, oy, max(ax+aw, bx+bw)-ox, max(ay+ah, by+bh)-oy

def rectsUnion(*args:tuple[int,int,int,int]) -> tuple[int,int,int,int]:
    out = args[0]
    if len(args) > 1:
        for rect in args[1:]:
            out = rectUnion(out, rect)
    return out

def subtractRect(base_xywh, cutter_xywh):
    bx, by, bw, bh = base_xywh
    cx, cy, cw, ch = cutter_xywh

    # Convert to outer edges
    b_left, b_top, b_right, b_bottom = bx, by, bx + bw, by + bh
    c_left, c_top, c_right, c_bottom = cx, cy, cx + cw, cy + ch

    # Base survives unchanged if no overlap.
    if c_right <= b_left or c_left >= b_right or c_bottom <= b_top or c_top >= b_bottom: return [base_xywh]
    # Base is completely destroyed if fully overlapped.
    if c_left <= b_left and c_right >= b_right and c_top <= b_top and c_bottom >= b_bottom: return []

    rects = []
    clip_top = max(b_top, c_top)
    clip_bottom = min(b_bottom, c_bottom)
    clip_height = clip_bottom - clip_top

    if c_top > b_top: rects.append((b_left, b_top, bw, c_top - b_top))                          # Top strip
    if c_bottom < b_bottom: rects.append((b_left, c_bottom, bw, b_bottom - c_bottom))           # Bottom strip
    if c_left > b_left: rects.append((b_left, clip_top, c_left - b_left, clip_height))          # Left strip
    if c_right < b_right: rects.append((c_right, clip_top, b_right - c_right, clip_height))     # Right strip

    return [r for r in rects if r[2] > 0 and r[3] > 0]

def decimateRect(rect_xywh, cutter_rects):
    survivors = [rect_xywh]
    for cutter in cutter_rects:
        new_survivors = []
        for s in survivors: new_survivors.extend(subtractRect(s, cutter))
        survivors = new_survivors
        if not survivors: break
    return survivors

"""
---------- Old Functions ----------
Below are old utility methods that could probably be rewritten or deprecated entirely.
"""
def getLocalMouse(widget:Widget) -> tuple[int, int, bool]:
    px, py = widget.winfo_pointerxy()
    x = px - widget.winfo_rootx()
    y = py - widget.winfo_rooty()
    if x < 0 or x >= widget.winfo_width(): return x, y, False
    if y < 0 or y >= widget.winfo_height(): return x, y, False
    return x, y, True
