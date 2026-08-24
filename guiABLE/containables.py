from .uimage import UImage
from .skinnable import Measurable, Skin
from .utilities import decimateRect, rectsUnion


"""
    Expandable extends Skinnable() to support live resizing of widgets. An expandable expands to envelope a new child
    widget, or to contain a child widget that has moved. It will also shrink when a child moves or is removed. Notably,
    Expandables do NOT alter their top-left origin point. They expand and contract, but do not alter their location.
"""
class Expandable():
    def __init__(self, *args, **kwargs):
        if 'width' not in kwargs:   kwargs['width'] = 0     # If dimensions are undefined, collapse to smallest size.
        if 'height' not in kwargs:  kwargs['height'] = 0

        super().__init__(*args, **kwargs)

    def registerChild(self, child):
        super().registerChild(child)
        self._resize()

    def dropChild(self, child):
        super().dropChild(child)
        self._resize()

    def childChanged(self, child):
        super().childChanged(child)
        self._resize()

    #   _resize() Determines new geometry when children are added, removed, or altered.
    def _resize(self):
        if not any(self._size_declared):        # Only alter dimensions if width/height were not explicitly declared.
            union = (0,0,0,0)
            union = rectsUnion(union, *[child.geometry for child in self.getChildren()])

            if union[2:] != self.size:
                w = self.width if self._size_declared[0] else union[2]
                h = self.height if self._size_declared[1] else union[3]
                self.place_configure(width=w, height=h, implied=True)     # Resize the Expandable itself.


""" A Dead-End class for Collection() to terminate in -- providing a final super().__init__() destination. """
class Nothing():
    def __init__(self, *args, **kwargs): pass


"""A logical, non-rendered group that internally handles coordinate spaces and parent/child relations."""
class Collection(Expandable, Measurable, Nothing):
    is_collection = True

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        # Tk interpreter references (for .bind, .after, etc.)
        self.tk = parent.tk
        self._w = parent._w

        self._size_declared = [False, False]

    # Collections are logical parents; descendants are physically hosted by the nearest real Tk parent.
    def childMaster(self):
        return self._parent.childMaster() if hasattr(self._parent, "childMaster") else self._parent

    def mapChildToMaster(self, x:int, y:int) -> tuple[int,int]:
        x, y = x + self.x, y + self.y
        return self._parent.mapChildToMaster(x, y) if hasattr(self._parent, "mapChildToMaster") else (x, y)

    def mapMasterToChild(self, x:int, y:int) -> tuple[int,int]:
        if hasattr(self._parent, "mapMasterToChild"): x, y = self._parent.mapMasterToChild(x, y)
        return x - self.x, y - self.y

    def place(self, x:int=None, y:int=None, **kwargs):
        if x is None and 'x' in kwargs: x = kwargs['x']
        if y is None and 'y' in kwargs: y = kwargs['y']
        self._geometry = (x, y, 0, 0)
        self._last_geometry = self._geometry
        return self

    def place_configure(self, *args, **kwargs):
        # Enables passing .place(int, int) for x, y, or .place(x=int, y=int), or no x/y passed.
        if 'x' not in kwargs:
            kwargs['x'] = args[0] if len(args) and isinstance(args[0], int) else self.x
        if 'y' not in kwargs:
            kwargs['y'] = args[1] if len(args) > 1 and isinstance(args[1], int) else self.y

        # Update geometry and re-apply child placement without changing child-local geometry.
        last_xy = self.location
        self._geometry = (kwargs['x'], kwargs['y'], kwargs['width'] if 'width' in kwargs else self.width,
                                                    kwargs['height'] if 'height' in kwargs else self.height)

        if last_xy != self.location: self._reposition()
        self._last_geometry = self._geometry

    def _reposition(self):
        for child in self.getChildren():
            if hasattr(child, "_reposition"): child._reposition()

    @property
    def skin(self): return self._parent.skin


""" Groupable() is a skinned Expandable, providing an image-based opaque, transparent, or semi-transparent surface."""
class Groupable(Expandable):
    # If no skin has been passed, we create a "non-skin" that fills the visible area of the Group.
    def _afterGeometryChanges(self):
        if not self._skin_passed:
            visible = decimateRect((0, 0, *self.size), [child.geometry for child in self._children if child.isOpaque()])
            if visible:
                if len(visible) == 1:
                    self._skin_offset = tuple(visible[0][:2])
                    new_img = UImage(width=visible[0][2], height=visible[0][3])
                else: new_img = UImage(width=self.width, height=self.height)
            else: new_img = UImage()
            self.setSkin(Skin(new_img))

        super()._afterGeometryChanges()
