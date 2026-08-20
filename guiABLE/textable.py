import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path

from guiABLE.fontable import Fontable, FontPack
from guiABLE.skinnable import Skin
from guiABLE.uimage import UImage
from guiABLE.utilities import warnPrint
from guiABLE.widgetables import Paddable, Imageable, Siblingable, TextCanvas, Renderable, BareText


""" NText is a fix for Tk's nonsensical, CLI-style text selection standards, developed by Keith Nash. """
def _enableNtext(widget):
    try:
        widget.tk.call("package", "present", "ntext")
    except tk.TclError:
        source = Path(__file__).parent / "vendor" / "ntext" / "ntext.tcl"
        widget.tk.call("source", str(source))

    tags = list(widget.bindtags())

    if "Text" in tags:
        tags[tags.index("Text")] = "Ntext"
    elif "Ntext" not in tags:
        tags.insert(1, "Ntext")

    widget.bindtags(tuple(tags))


"""
Textable is a native tk.Text surface that participates honestly in guiABLE compositing.
Tk renders the native text/caret/selection, while a matching solid-color Skin represents
the widget's opaque surface to the raster compositor.
"""

class Textable(Fontable, Siblingable, Renderable, BareText):
    def __init__(self, parent, width:int, height:int, text:str="",
                 bg_color:str="#6B6B6B", font_pack:FontPack=None,
                 editable:bool=True, align:str="left", **kwargs):

        self._bg_color = bg_color
        self._editable = editable
        self._alignment = self._normalizeAlignment(align)

        kwargs.setdefault("selectbackground", "#252595")
        kwargs.setdefault("selectborderwidth", 0)

        super().__init__(parent, skin=self._backgroundSkin(width, height), width=width, height=height,
                         bg=bg_color, font_pack=font_pack, **kwargs)

        self._fontChanged()
        _enableNtext(self)  # Fix Tk's inane text selection policies.

        self.bind("<Double-Button-1>", self._doubleClick, "+")

        if text: self.insert("1.0", text)
        self._applyAlignment()

        self.editable(editable)
        self.bind("<<Copy>>", self._copySelection)
        self.bind("<Button-1>", lambda event: self.focus_set(), "+")

    def getText(self) -> str: return self.get("1.0", "end-1c")

    def setText(self, text:str):
        state = self.cget("state")

        if state == "disabled": self.configure(state="normal")
        self.delete("1.0", "end")
        self.insert("1.0", text)
        self._applyAlignment()
        if state == "disabled": self.configure(state="disabled")

    def align(self, alignment:str=None) -> str:
        if alignment is not None:
            alignment = self._normalizeAlignment(alignment)

            if alignment != self._alignment:
                self._alignment = alignment
                self._applyAlignment()

        return self._alignment

    def selectAll(self):
        if self.getText():
            self.tag_add("sel", "1.0", "end-1c")
            self.mark_set("insert", "end-1c")

    def setBackground(self, color:str):
        if color == self._bg_color: return

        self._bg_color = color
        self.configure(bg=color)
        self._rebuildBackground()
        self.redraw()

    def editable(self, editable:bool=None) -> bool:
        if editable is not None:
            self._editable = editable
            self.configure(state="normal" if editable else "disabled")

        return self._editable

    def render(self, image:UImage, xy_offset:tuple[int,int]=(0, 0)): pass

    def _fontChanged(self):
        color = self._fontValue("color")
        self.configure(font=self._tk_font, fg=color, insertbackground=color, selectforeground=color)

    def _backgroundSkin(self, width:int=None, height:int=None) -> Skin:
        return Skin.fromColors(self.width if width is None else width,
                               self.height if height is None else height,
                               self._bg_color)

    def _rebuildBackground(self):
        self.setSkin(self._backgroundSkin(), implied=True)
        self.dirty = True

    def _doubleClick(self, event):
        end_info = self.bbox("end-1c")
        line_info = self.dlineinfo("end-1c")

        if end_info is None or line_info is None: return

        end_x = end_info[0]
        line_y, line_h = line_info[1], line_info[3]

        if line_y <= event.y < line_y + line_h and event.x >= end_x:
            self.tag_remove("sel", "1.0", "end")
            self.tag_add("sel", "1.0", "end-1c")
            self.mark_set("insert", "end-1c")
            return "break"

    def _copySelection(self, event=None):
        selection = self.tag_ranges("sel")
        if not selection: return "break"

        start, end = selection
        text_end = self.index("end-1c")

        if self.compare(end, ">", text_end): end = text_end

        text = self.get(start, end)

        self.clipboard_clear()
        self.clipboard_append(text)
        return "break"

    def _applyAlignment(self):
        self.tag_configure("_alignment", justify=self._alignment)
        self.tag_add("_alignment", "1.0", "end-1c")

    @staticmethod
    def _normalizeAlignment(alignment:str) -> str:
        alignment = alignment.lower()

        if alignment not in ("left", "center", "right"):
            warnPrint(f"Unknown text alignment '{alignment}'. Defaulting to 'left'.")
            alignment = "left"

        return alignment

    def _fitText(self):
        font = tkfont.Font(font=self.cget("font"))
        lines = self.getText().split("\n")

        width = max(1, max(font.measure(line) for line in lines))
        height = max(1, font.metrics("linespace") * len(lines))

        if (width, height) == self.size: return

        if self._placed:
            self.place_configure(width=width, height=height, implied=True)
        else:
            self._geometry = (*self.location, width, height)
            self._scratch = UImage(width=width, height=height)

    def _afterGeometryChanges(self):
        if self._last_geometry[2:] != self._geometry[2:]: self._rebuildBackground()
        super()._afterGeometryChanges()


class TextLine(Textable):
    def __init__(self, parent, width:int, height:int, text:str="",
                 editable:bool=True, max_chars:int=None,
                 placeholder:str=None, placeholder_pack:FontPack=None,
                 mask:str=None, masked:bool=False, **kwargs):

        self._text = self._singleLine(text)
        self._max_chars = max_chars
        self._placeholder = placeholder
        self._placeholder_pack = placeholder_pack
        self._mask = mask[:1] if mask else None
        self._masked = bool(masked and self._mask)
        self._has_focus = False

        kwargs["wrap"] = "none"
        kwargs.setdefault("takefocus", 1)

        super().__init__(parent, width, height, text="", editable=editable, **kwargs)

        self.bind("<Return>", self._blockLineBreak)
        self.bind("<KP_Enter>", self._blockLineBreak)
        self.bind("<KeyPress>", self._keyPressed)
        self.bind("<<Paste>>", self._paste)
        self.bind("<<PasteSelection>>", self._pasteSelection)

        self.bind("<Tab>", self._focusNext)
        self.bind("<Shift-Tab>", self._focusPrevious)
        self.bind("<ISO_Left_Tab>", self._focusPrevious)

        self.bind("<FocusIn>", self._focusIn, "+")
        self.bind("<FocusOut>", self._focusOut, "+")

        self._refreshDisplay()

    def getText(self) -> str:
        return self._text

    def setText(self, text:str):
        text = self._singleLine(text)

        if self.validateInput(text):
            self._text = text
            self._refreshDisplay()

    def setMaxChars(self, max_chars:int=None): self._max_chars = max_chars

    def setPlaceholder(self, text:str=None, font_pack:FontPack=None):
        self._placeholder = text

        if font_pack is not None:
            self._placeholder_pack = font_pack

        self._refreshDisplay()

    def setMask(self, character:str=None, masked:bool=None):
        self._mask = character[:1] if character else None

        if self._mask is None:
            self._masked = False
        elif masked is not None: self._masked = masked

        self._refreshDisplay()

    def masked(self, masked:bool=None) -> bool:
        if masked is not None:
            self._masked = bool(masked and self._mask)
            self._refreshDisplay()

        return self._masked

    def validateInput(self, proposed:str) -> bool: return self._max_chars is None or len(proposed) <= self._max_chars

    def _focusIn(self, event=None):
        self._has_focus = True
        self._refreshDisplay()

    def _focusOut(self, event=None):
        self._has_focus = False
        self._refreshDisplay()

    def _replaceSelection(self, text:str):
        if not self.editable(): return False

        text = self._singleLine(text)
        start, end = self.index("insert"), self.index("insert")

        selection = self.tag_ranges("sel")
        if selection: start, end = selection

        offset1, offset2 = int(str(start).split(".")[1]), int(str(end).split(".")[1])

        if self._max_chars is not None:
            available = max(0, self._max_chars - (len(self._text) - (offset2 - offset1)))

            if len(text) > available:
                requested = text
                text = text[:available]
                self.inputOverflow(requested, text)

        proposed = self._text[:offset1] + text + self._text[offset2:]
        if not self.validateInput(proposed): return False

        self._text = proposed
        self._refreshDisplay(offset1 + len(text))
        return True

    def inputOverflow(self, requested:str, accepted:str): pass

    def _keyPressed(self, event):
        if not self.editable(): return

        if event.keysym == "BackSpace": return self._deleteBackward()
        if event.keysym == "Delete": return self._deleteForward()

        if event.char and event.char >= " " and event.keysym != "Tab":
            self._replaceSelection(event.char)
            return "break"

    def _deleteBackward(self):
        selection = self.tag_ranges("sel")
        if selection:
            self._replaceSelection("")
            return "break"

        pos = int(self.index("insert").split(".")[1])
        if pos:
            self.tag_add("sel", f"1.{pos - 1}", f"1.{pos}")
            self._replaceSelection("")

        return "break"

    def _deleteForward(self):
        selection = self.tag_ranges("sel")
        if selection:
            self._replaceSelection("")
            return "break"

        pos = int(self.index("insert").split(".")[1])
        if pos < len(self._text):
            self.tag_add("sel", f"1.{pos}", f"1.{pos + 1}")
            self._replaceSelection("")

        return "break"

    def _refreshDisplay(self, cursor:int=None):
        placeholder = self._placeholderActive()

        display = self._placeholder if placeholder else self._mask * len(self._text) if self._masked else self._text

        state = self.cget("state")
        if state == "disabled": self.configure(state="normal")

        super().delete("1.0", "end")
        super().insert("1.0", display or "")

        if placeholder:
            pack = self._placeholder_pack or self._font_pack

            self.tag_configure("_placeholder", foreground=pack.color, font=(pack.name, pack.size, pack.weight))
            self.tag_add("_placeholder", "1.0", "end-1c")
            self.mark_set("insert", "1.0")

        elif cursor is not None:
            cursor = min(cursor, len(self._text))
            self.mark_set("insert", f"1.{cursor}")
            self.see("insert")

        if state == "disabled": self.configure(state="disabled")
        self._applyAlignment()

    def _paste(self, event=None):
        try: text = self.clipboard_get()
        except tk.TclError: return "break"

        self._replaceSelection(text)
        return "break"

    def _pasteSelection(self, event=None):
        try: text = self.selection_get(selection="PRIMARY")
        except tk.TclError: return "break"

        self._replaceSelection(text)
        return "break"

    def _placeholderActive(self) -> bool: return not self._text and bool(self._placeholder) and not self._has_focus

    @staticmethod
    def _singleLine(text:str) -> str: return text.replace("\r", " ").replace("\n", " ")

    @staticmethod
    def _blockLineBreak(event=None): return "break"

    def _focusNext(self, event=None):
        self.tk_focusNext().focus_set()
        return "break"

    def _focusPrevious(self, event=None):
        self.tk_focusPrev().focus_set()
        return "break"


class TextLabel(Fontable, Paddable, Imageable, Siblingable, TextCanvas):
    def __init__(self, parent, text:str="", skin=None, font_pack:FontPack=None,
                 bg_color:str=None, anchor:str=None, text_offset:tuple[int,int]=None,
                 align:str="left", **kwargs):

        self._bg_color = bg_color

        if anchor is not None: kwargs["anchor"] = anchor
        if text_offset is not None: kwargs["text_offset"] = text_offset

        width_declared = kwargs.get("width") is not None
        height_declared = kwargs.get("height") is not None

        super().__init__(parent, skin=skin, font_pack=font_pack, **kwargs)

        self._auto_width = not width_declared and self.width <= 0
        self._auto_height = not height_declared and self.height <= 0

        self._text = Textable(self, 1, 1, text=text, font_pack=self._font_pack, bg_color=self._textBackground(),
                              editable=False, wrap="none", takefocus=1, align=align)

        self._syncFontTo(self._text)
        self._textChanged()

    def getText(self) -> str: return self._text.getText()

    def setText(self, text:str):
        self._text.setText(text)
        self._textChanged()

    def selectAll(self): self._text.selectAll()
    def align(self, alignment:str=None) -> str: return self._text.align(alignment)

    def setBackground(self, color:str=None):
        self._bg_color = color
        self._syncTextBackground()

    def _textChanged(self):
        self._text._fitText()
        self._fitToText()
        self._anchorText()

    def _fontChanged(self):
        if hasattr(self, "_text"):
            self._syncFontTo(self._text)
            self._textChanged()

    def _textBackground(self) -> str:
        color = self._bg_color if self._bg_color is not None else self.skin.bgColor(self._img_state)
        return color or "#6B6B6B"

    def _syncTextBackground(self):
        if hasattr(self, "_text"):
            color = self._textBackground()
            if self._text._bg_color != color: self._text.setBackground(color)

    def _anchorText(self):
        self.anchorChild(self._text, self._fontValue("anchor"), self._fontValue("text_offset"))

    def _fitToText(self):
        width, height = self.paddedSize(*self._text.size)
        width, height = self.borderedSize(width, height)

        width = width if self._auto_width else self.width
        height = height if self._auto_height else self.height

        if (width, height) == self.size: return

        self._geometry = (*self.location, width, height)
        self._scratch = UImage(width=width, height=height)

        if self._placed:
            self.place_configure(width=width, height=height, implied=True)

    def _borderChanged(self):
        if hasattr(self, "_text"): self._fitToText()
        super()._borderChanged()

    def _paddingChanged(self):
        if hasattr(self, "_text"): self._fitToText()
        super()._paddingChanged()

    def childChanged(self, child):
        if child is self._text: self._fitToText()
        super().childChanged(child)

    def redraw(self):
        self._syncTextBackground()
        return super().redraw()