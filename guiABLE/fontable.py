from dataclasses import dataclass


@dataclass
class FontPack:
    name: str = "Arial"
    size: int = 12
    weight: str = "normal"
    color: str = "#dddddd"
    drop_color: str = "#222222"
    text_offset: tuple[int,int] = (0, 0)
    drop_offset: tuple[int,int] = (2, 2)
    anchor: str = "nw"


class Fontable:
    _font_attributes = {
        "font":        "name",
        "font_size":   "size",
        "weight":      "weight",
        "color":       "color",
        "drop_color":  "drop_color",
        "text_offset": "text_offset",
        "drop_offset": "drop_offset",
        "anchor":      "anchor"
    }

    def __init__(self, *args, font_pack:FontPack=None, **kwargs):
        self._font_pack = font_pack or FontPack()
        self._font_overrides = {}

        for key in tuple(kwargs):
            if key in self._font_attributes:
                self._font_overrides[self._font_attributes[key]] = kwargs.pop(key)

        super().__init__(*args, **kwargs)

    def setFontPack(self, font_pack:FontPack):
        self._font_pack = font_pack or FontPack()
        self._fontChanged()

    def setFontAttributes(self, **kwargs):
        changed = False

        for key, value in kwargs.items():
            if key not in self._font_attributes:
                raise TypeError(f"Unknown font attribute: {key}")

            attribute = self._font_attributes[key]
            if attribute not in self._font_overrides or self._font_overrides[attribute] != value:
                self._font_overrides[attribute] = value
                changed = True

        if changed: self._fontChanged()

    def _fontValue(self, attribute):
        return self._font_overrides.get(attribute, getattr(self._font_pack, attribute))

    def _syncFontTo(self, recipient):
        recipient._font_pack = self._font_pack
        recipient._font_overrides = self._font_overrides
        recipient._fontChanged()

    @property
    def _tk_font(self):
        return self._fontValue("name"), self._fontValue("size"), self._fontValue("weight")

    def _fontChanged(self): pass