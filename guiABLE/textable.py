import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path

from guiABLE.fontable import Fontable, FontPack
from guiABLE.skinnable import Skin
from guiABLE.uimage import UImage
from guiABLE.utilities import warnPrint
from guiABLE.history import EditHistory
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

        if text: self.insert("1.0", text)
        self._applyAlignment()

        self.editable(editable)
        self.bind("<<SelectAll>>", self._selectAll)
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

        if hasattr(self, "_tab_size"): self._configureTabs()

    def _backgroundSkin(self, width:int=None, height:int=None) -> Skin:
        return Skin.fromColors(self.width if width is None else width,
                               self.height if height is None else height,
                               self._bg_color)

    def _rebuildBackground(self):
        self.setSkin(self._backgroundSkin(), implied=True)
        self.dirty = True

    def _selectAll(self, event=None):
        self.selectAll()
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
                              editable=False, wrap="none", takefocus=0, align=align)

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


class Inputable:
    def __init__(self, *args, text:str="", editable:bool=True, max_chars:int=None,
                 tab_focus:bool=True, tab_size:int=4, **kwargs):
        self._text = self._normalizeInput(text)
        self._max_chars = max_chars

        self._tab_focus = tab_focus
        self._tab_size = max(1, int(tab_size))

        self._undo_history = EditHistory()

        kwargs.setdefault("takefocus", 1)
        super().__init__(*args, text="", editable=editable, **kwargs)
        self._configureTabs()

        self.bind("<Tab>", self._tabNext)
        self.bind("<Shift-Tab>", self._tabPrevious)
        self.bind("<ISO_Left_Tab>", self._tabPrevious)
        self.bind("<FocusIn>", self._inputFocusIn, "+")

        self.bind("<KeyPress>", self._keyPressed)
        self.bind("<Return>", self._enterPressed)
        self.bind("<KP_Enter>", self._enterPressed)

        self.bind("<<Paste>>", self._paste)
        self.bind("<<PasteSelection>>", self._pasteSelection)
        self.bind("<<Cut>>", self._cut)

        self.bind("<<Undo>>", self._undo)
        self.bind("<<Redo>>", self._redo)
        self.bind("<FocusOut>", lambda event: self._undo_history.breakGroup(), "+")
        self.bind("<Button-1>", lambda event: self._undo_history.breakGroup(), "+")

        self._refreshDisplay()

    @property
    def undoHistory(self): return self._undo_history

    def getText(self) -> str: return self._text
    def setText(self, text:str):
        text = self._normalizeInput(text)

        if self._validateInput(text):
            self._text = text
            self._undo_history.clear()
            self._refreshDisplay()

    def setMaxChars(self, max_chars:int=None): self._max_chars = max_chars

    def enterPressed(self) -> bool: return True
    def _enterPressed(self, event=None):
        if self.editable() and self.enterPressed(): self._replaceSelection("\n", "newline")
        return "break"

    def keyPressed(self, event): pass
    def _keyPressed(self, event):
        if not self.editable(): return

        if event.keysym == "BackSpace": return self._deleteBackward()
        if event.keysym == "Delete": return self._deleteForward()
        if event.keysym in ("Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next"):
            self._undo_history.breakGroup()
            return

        if event.char and event.char >= " ":
            self._replaceSelection(event.char, "insert")
            return "break"

    def validateInput(self, proposed:str) -> bool: return True
    def _validateInput(self, proposed:str) -> bool:
        if self._max_chars is not None and len(proposed) > self._max_chars: return False
        return self.validateInput(proposed)

    def inputOverflow(self, requested:str, accepted:str): pass

    def tabFocus(self, enabled:bool=None) -> bool:
        if enabled is not None: self._tab_focus = bool(enabled)
        return self._tab_focus

    def tabSize(self, size:int=None) -> int:
        if size is not None:
            self._tab_size = max(1, int(size))
            self._configureTabs()

        return self._tab_size

    def _configureTabs(self):
        font = tkfont.Font(font=self.cget("font"))
        tab_width = self._tab_size * font.measure("0")
        self.configure(tabs=(tab_width,), tabstyle="wordprocessor")

    def _tabNext(self, event=None):
        if self._tab_focus:
            self.tk_focusNext().focus_set()
        elif self.editable():
            self._replaceSelection("\t", "tab")

        return "break"

    def _tabPrevious(self, event=None):
        if self._tab_focus:
            self.tk_focusPrev().focus_set()
            return "break"

        if not self.editable(): return "break"

        cursor = self.index("insert")
        line_start = self.index("insert linestart")
        line_end = self.index("insert lineend")

        line = self.get(line_start, line_end)
        line_number, cursor_column = map(int, str(cursor).split("."))
        indent_length = len(line) - len(line.lstrip(" \t"))

        # Beyond the leading whitespace, Shift+Tab only moves the cursor.
        if cursor_column > indent_length:
            destination = max(indent_length, cursor_column - self._tab_size)
            segment = line[destination:cursor_column]

            # Never leap over a tab. Stop at its leading edge instead.
            if "\t" in segment:
                destination += segment.rfind("\t")

            self.mark_set("insert", f"{line_number}.{destination}")
            return "break"

        # Within the leading whitespace, Shift+Tab removes indentation.
        if cursor_column:
            previous = line[cursor_column - 1]

            # A tab is one indentation unit, regardless of its character width.
            if previous == "\t":
                destination = cursor_column - 1

            # Spaces are removed up to tab_size, but never across a preceding tab.
            else:
                destination = max(0, cursor_column - self._tab_size)
                segment = line[destination:cursor_column]

                if "\t" in segment:
                    destination += segment.rfind("\t") + 1

            self._replaceRange(f"{line_number}.{destination}", cursor, "", "tab")

        return "break"

    def _recordUndo(self):
        self._undo_stack.append((self._text, self._textOffset("insert")))
        self._redo_stack.clear()

    def _undo(self, event=None):
        state = self._undo_history.undo(self._captureEditState())
        if state is not None: self._restoreEditState(state)
        return "break"

    def _redo(self, event=None):
        state = self._undo_history.redo(self._captureEditState())
        if state is not None: self._restoreEditState(state)
        return "break"

    def _normalizeInput(self, text:str) -> str: return text

    def _captureEditState(self):
        selection = self.tag_ranges("sel")
        selection = tuple(self._textOffset(index) for index in selection) if selection else None

        return self._text, self._textOffset("insert"), selection

    def _restoreEditState(self, state):
        self._text, cursor, selection = state
        self._refreshDisplay(cursor)

        if selection is not None:
            start, end = selection
            self.tag_add("sel", self._indexFromOffset(start), self._indexFromOffset(end))

    def _replaceSelection(self, text:str, operation:str="replace"):
        if not self.editable(): return False

        start = end = self.index("insert")
        selection = self.tag_ranges("sel")

        if selection: start, end = selection
        return self._replaceRange(start, end, text, "insert")

    def _replaceRange(self, start, end, text:str, operation:str="replace"):
        text = self._normalizeInput(text)
        offset1, offset2 = self._textOffset(start), self._textOffset(end)

        if self._max_chars is not None:
            available = max(0, self._max_chars - (len(self._text) - (offset2 - offset1)))

            if len(text) > available:
                requested = text
                text = text[:available]
                self.inputOverflow(requested, text)

        proposed = self._text[:offset1] + text + self._text[offset2:]
        if not self._validateInput(proposed): return False

        # A replacement may be textually identical while still being a successful UI operation.
        if proposed == self._text:
            self.mark_set("insert", self._indexFromOffset(offset1 + len(text)))
            return True

        self._undo_history.record(
            self._captureEditState(), operation, offset1, offset2 - offset1, text
        )

        self._text = proposed
        self._refreshDisplay(offset1 + len(text))
        return True

    def _deleteBackward(self):
        selection = self.tag_ranges("sel")

        if selection:
            self._replaceSelection("", "backspace")
        else:
            pos = self._textOffset("insert")
            if pos: self._replaceRange(self.index("insert -1c"), self.index("insert"), "", "backspace")

        return "break"

    def _deleteForward(self):
        selection = self.tag_ranges("sel")

        if selection:
            self._replaceSelection("", "delete")
        else:
            pos = self._textOffset("insert")
            if pos < len(self._text): self._replaceRange(self.index("insert"), self.index("insert +1c"), "", "delete")

        return "break"

    def _refreshDisplay(self, cursor:int=None):
        state = self.cget("state")
        if state == "disabled": self.configure(state="normal")

        super().delete("1.0", "end")
        super().insert("1.0", self._text)
        self._applyAlignment()

        if cursor is not None:
            self.mark_set("insert", self._indexFromOffset(cursor))
            self.see("insert")

        if state == "disabled": self.configure(state="disabled")

    def _textOffset(self, index) -> int: return len(self.get("1.0", index))
    def _indexFromOffset(self, offset:int): return self.index(f"1.0 + {offset} chars")

    def _paste(self, event=None):
        try: text = self.clipboard_get()
        except tk.TclError: return "break"

        if self._replaceSelection(text, "paste"):
            self.tag_remove("sel", "1.0", "end")

        return "break"

    def _pasteSelection(self, event=None):
        try: text = self.selection_get(selection="PRIMARY")
        except tk.TclError: return "break"

        if self._replaceSelection(text, "paste"):
            self.tag_remove("sel", "1.0", "end")

        return "break"

    def _cut(self, event=None):
        if not self.editable(): return "break"

        selection = self.tag_ranges("sel")
        if selection:
            self.clipboard_clear()
            self.clipboard_append(self.get(*selection))
            self._replaceSelection("", "cut")

        return "break"

    def _inputFocusIn(self, event=None):
        if not self.editable() and self.getText(): self.selectAll()


class InputLine(Inputable, Textable):
    def __init__(self, parent, width:int, height:int, text:str="",
                 editable:bool=True, max_chars:int=None,
                 placeholder:str=None, placeholder_pack:FontPack=None,
                 mask:str=None, masked:bool=False, submit_function=None, **kwargs):

        self._placeholder = placeholder
        self._placeholder_pack = placeholder_pack
        self._mask = mask[:1] if mask else None
        self._masked = bool(masked and self._mask)
        self._has_focus = False
        self._submit_function = submit_function

        kwargs["wrap"] = "none"
        kwargs.setdefault("takefocus", 1)

        super().__init__(parent, width, height, text=text, editable=editable, max_chars=max_chars, **kwargs)

        self.bind("<FocusIn>", self._focusIn, "+")
        self.bind("<FocusOut>", self._focusOut, "+")

    def setPlaceholder(self, text:str=None, font_pack:FontPack=None):
        self._placeholder = text
        if font_pack is not None: self._placeholder_pack = font_pack
        self._refreshDisplay()

    def setMask(self, character:str=None, masked:bool=None):
        self._mask = character[:1] if character else None

        if self._mask is None: self._masked = False
        elif masked is not None: self._masked = masked

        self._refreshDisplay()

    def masked(self, masked:bool=None) -> bool:
        if masked is not None:
            self._masked = bool(masked and self._mask)
            self._refreshDisplay()

        return self._masked

    def setSubmitFunction(self, function): self._submit_function = function
    def submit(self):
        if self._submit_function is not None: self._submit_function()

    def enterPressed(self) -> bool:
        self.submit()
        return False

    def _normalizeInput(self, text:str) -> str:
        return text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")

    def _refreshDisplay(self, cursor:int=None):
        placeholder = self._placeholderActive()

        display = self._placeholder if placeholder else self._mask * len(self._text) if self._masked else self._text

        state = self.cget("state")
        if state == "disabled": self.configure(state="normal")

        super().delete("1.0", "end")
        super().insert("1.0", display or "")

        if placeholder:
            if self._placeholder_pack:
                pack = self._placeholder_pack
                color, font = pack.color, (pack.name, pack.size, pack.weight)
            else:
                color, font = self._fontValue("color"), self._tk_font

            self.tag_configure("_placeholder", foreground=color, font=font)
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

        self._replaceSelection(text, "paste")
        return "break"

    def _pasteSelection(self, event=None):
        try: text = self.selection_get(selection="PRIMARY")
        except tk.TclError: return "break"

        self._replaceSelection(text, "paste")
        return "break"

    def _placeholderActive(self) -> bool: return not self._text and bool(self._placeholder) and not self._has_focus

    @staticmethod
    def _singleLine(text:str) -> str: return text.replace("\r", " ").replace("\n", " ")

    @staticmethod
    def _blockLineBreak(event=None): return "break"

    def _focusIn(self, event=None):
        self._has_focus = True
        self._refreshDisplay()

    def _focusOut(self, event=None):
        self._has_focus = False
        self._refreshDisplay()


class TextBlob(Inputable, Textable):
    def __init__(self, parent, width:int, height:int, text:str="",
                 editable:bool=True, max_chars:int=None, max_lines:int=None,
                 tab_focus:bool=True, wrap:str="word", **kwargs):

        self._max_lines = max_lines
        kwargs["wrap"] = wrap

        super().__init__(parent, width, height, text=text, editable=editable,
                         max_chars=max_chars, tab_focus=tab_focus, **kwargs)

    def setMaxLines(self, max_lines:int=None): self._max_lines = max_lines

    def _validateInput(self, proposed:str) -> bool:
        if self._max_lines is not None and proposed.count("\n") >= self._max_lines: return False
        return super()._validateInput(proposed)

    def _normalizeInput(self, text:str) -> str: return text.replace("\r\n", "\n").replace("\r", "\n")
