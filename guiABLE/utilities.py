from tkinter import PhotoImage, TclError, Widget
from os import path as osPath
from sys import argv as sysArgV


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
def loadImageByPath(image_path:str) -> PhotoImage | None:
    try: return PhotoImage(file=image_path)
    except TclError: warnPrint(f"Image not found: {image_path}")
    return None

# loadImage(): Conform either input type to PhotoImage and path (path used as 'source' in _bySprite())
def loadImage(path_or_image:str | PhotoImage) -> tuple[PhotoImage | None, str | None]:
    if isinstance(path_or_image, str):
        r_path = resolvePath(path_or_image)
        return loadImageByPath(r_path), r_path
    elif isinstance(path_or_image, PhotoImage): image = path_or_image
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
    w, h = image.width(), image.height()
    out = PhotoImage(width=h, height=w)
    fastRotate(out, image, w, h, clockwise)
    return out


def fastBlit(dest: PhotoImage, dest_w: int, dest_h: int,            src: PhotoImage, src_w: int, src_h: int,
             dest_x: int, dest_y: int, blit_w: int, blit_h: int,    src_x: int = 0, src_y: int = 0):

    def clamp_positive(p0, size, dest):
        if p0 < 0:
            size += p0  # shrink size by the overflow
            dest -= p0  # shift dest to compensate
            p0 = 0
        return p0, size, dest

    # Clamp destination coordinates to non-negative
    src_x, blit_w, dest_x = clamp_positive(src_x, blit_w, dest_x)
    src_y, blit_h, dest_y = clamp_positive(src_y, blit_h, dest_y)
    dest_x, blit_w, src_x = clamp_positive(dest_x, blit_w, src_x)
    dest_y, blit_h, src_y = clamp_positive(dest_y, blit_h, src_y)

    # Clamp width/height to fit both source and dest
    blit_w = min(blit_w, src_w - src_x, dest_w - dest_x)
    blit_h = min(blit_h, src_h - src_y, dest_h - dest_y)

    # Bail out if the region is invalid
    if blit_w <= 0 or blit_h <= 0: return

    src_x = min(src.width(), src_x)
    src_y = min(src.height(), src_y)
    from_w = min(src.width(), src_x+blit_w)
    from_h = min(src.height(), src_y+blit_h)

    # Perform the blit
    dest.copy_replace( src, from_coords=(src_x, src_y, from_w, from_h), to=(dest_x, dest_y) )

def cropImage(image: PhotoImage, x: int, y: int, width: int, height: int) -> PhotoImage:
    cropped = PhotoImage(width=width, height=height)
    iw, ih = image.width(), image.height()
    fastBlit(cropped, width, height, image, iw, ih, 0, 0, iw, ih, x, y)
    return cropped


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


def isOpaque(image:PhotoImage) -> bool:
    for y in range(image.height()):
        for x in range(image.width()):
            if image.transparency_get(x, y): return False
    return True


"""
 ---------- Widget Utility Functions ----------
getGeometry() fetches Winfo_ geometry by string and parses the string into ints. This was found to be slightly faster
than polling the 4x equivalent Winfo_ (x,y,width,height) access points. replace().split() was also found faster than
regex, .partition(), and .find() with index slicing.
"""
def getGeometry(widget) -> tuple[int, int, int, int]:
    w, h, x, y = widget.winfo_geometry().replace("x", "+", 1).split("+")
    return int(x), int(y), int(w), int(h)

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


""" rectsOverlap() is the fastest method for finding whether two areas overlap each other. """
def rectsOverlap(a_xywh, b_xywh) -> bool:
    ax, ay, aw, ah = a_xywh
    bx, by, bw, bh = b_xywh

    return not (            # Inverse formula breaks out of testing if any one returns True.
        ax + aw <= bx or    # a is left of b
        ax >= bx + bw or    # a is right of b
        ay + ah <= by or    # a is above b
        ay >= by + bh       # a is below b
    )

def pointIsInRect(x:int, y:int, rect:tuple[int,int,int,int]) -> bool:
    rx, ry, rw, rh = rect
    return rx+rw > x >= rx and ry+rh > y >= ry

def rectUnion(a_xywh, b_xywh) -> tuple[int,int,int,int]:
    ax, ay, aw, ah = a_xywh
    bx, by, bw, bh = b_xywh
    ox, oy = min(ax, bx), min(ay, by)
    return ox, oy, max(ax+aw, bx+bw)-ox, max(ay+ah, by+bh)-oy

# Below are old utility methods that could probably be rewritten or deprecated entirely.
def limitMove(pos:int, extent:int, min_val:int, max_val:int) -> int:
    return max(min_val, min(pos, max_val - extent))

def getLocalMouse(widget:Widget) -> tuple[int, int, bool]:
    px, py = widget.winfo_pointerxy()
    x = px - widget.winfo_rootx()
    y = py - widget.winfo_rooty()
    if x < 0 or x >= widget.winfo_width(): return x, y, False
    if y < 0 or y >= widget.winfo_height(): return x, y, False
    return x, y, True
