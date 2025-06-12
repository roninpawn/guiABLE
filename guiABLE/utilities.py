import tkinter as tk


# ---------- Utility Functions ----------
def limitMove(pos, extent, min_val, max_val):
    if pos < min_val: return min_val
    elif pos + extent > max_val: return max_val - extent
    return pos


def getLocalMouse(widget):
    x = widget.winfo_pointerx() - widget.winfo_rootx()
    y = widget.winfo_pointery() - widget.winfo_rooty()
    if x < 0 or x > widget.winfo_width(): return x, y, False
    if y < 0 or y > widget.winfo_height(): return x, y, False
    return x, y, True


def updateHover(widget):
    x, y, mouse_in = getLocalMouse(widget)
    if widget.enabled:
        widget.mouseIn(None) if mouse_in else widget.mouseOut(None)
    else:
        widget.disable()


def drawBar(trough_image, cap_image, width, height, horizontal=False):
    """Constructs a full-width or full-height scrollbar image from caps and a tileable mid-section."""
    newimg = tk.PhotoImage(width=width, height=height)
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


def putToImage(brush, canvas, bbox, mirror_x=False, mirror_y=False, rotate=False):
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


def warn_print(message, *, level="warning"):
    COLORS = {
        "info": "\033[96m",
        "warning": "\033[93m",
        "error": "\033[91m"
    }
    color = COLORS.get(level.lower(), "\033[93m")
    print(f"{color}[guiABLE {level.upper()}]\033[0m {message}")
