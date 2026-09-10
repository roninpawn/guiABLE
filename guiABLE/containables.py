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
            union = rectsUnion(union, *[self.childGeometry(child) for child in self.getChildren()])

            if union[2:] != self.size:
                w = self.width if self._size_declared[0] else union[2]
                h = self.height if self._size_declared[1] else union[3]
                self.place_configure(width=w, height=h, implied=True)     # Resize the Expandable itself.


class Stackable:
    """ Adds ordered, single-axis layout to a container without defining how that container is rendered. """
    def __init__(self, *args, vertical:bool=True, spacing:int=0, **kwargs):
        self._items = []
        self._item_sizes = {}
        self._item_positions = {}
        self._vertical = bool(vertical)
        self._axis = int(self._vertical)
        self._spacing = max(0, int(spacing))
        self._layout_lock = False
        self._stack_placed = False

        super().__init__(*args, **kwargs)

    @property
    def vertical(self) -> bool: return self._vertical

    def getItems(self) -> tuple: return tuple(self._items)
    def index(self, item) -> int: return self._items.index(item)
    def itemPosition(self, item) -> tuple[int,int]: return self._item_positions[item]

    def spacing(self, spacing:int=None) -> int:
        if spacing is not None:
            spacing = max(0, int(spacing))
            if spacing != self._spacing:
                self._spacing = spacing
                self._layout()
        return self._spacing

    def add(self, *items, index:int=None):
        if not items: return

        for item in items:
            if getattr(item, "parent", None) is not self:
                raise ValueError("Stackable items must be children of the Stackable")

        # Remove existing members first so insertion behaves predictably.
        for item in items:
            if item in self._items: self._items.remove(item)

        if index is None:
            self._items.extend(items)
        else:
            index = max(0, min(len(self._items), index))
            self._items[index:index] = items

        self._layout()

    def remove(self, item):
        if item in self._items: item.destroy()
        return item

    def move(self, item, index:int):
        old_index = self._items.index(item)
        self._items.pop(old_index)
        self._items.insert(index, item)

        if self._items.index(item) != old_index: self._layout()
        return item
    def moveIndex(self, index:int, destination:int): return self.move(self._items[index], destination)

    def dropChild(self, child):
        if child in self._items: self._items.remove(child)
        super().dropChild(child)

    def place(self, *args, **kwargs):
        was_placed = self._stack_placed
        old_location = self.location
        self._stack_placed = True

        super().place(*args, **kwargs)

        # Collection.place() collapses geometry; restore natural size and realize any deferred item placement.
        self._layout()

        # Re-placing an established Stack changes its physical child origin without changing item-local coordinates.
        if was_placed and self.location != old_location: self._reposition()

        return self

    # Expandable reports every child geometry change; only managed size changes alter stack layout.
    def _resize(self):
        if not self._layout_lock and self._itemSizes() != self._item_sizes: self._layout()

    def _layout(self):
        if self._layout_lock: return
        self._layout_lock = True

        try:
            axis, cross_axis = self._axis, 1 - self._axis
            position, cross_size = 0, 0
            positions = {}

            for item in self._items:
                location = [0, 0]
                location[axis] = position
                positions[item] = tuple(location)
                self._positionItem(item, *location)

                position += item.size[axis] + self._spacing
                cross_size = max(cross_size, item.size[cross_axis])

            if self._items: position -= self._spacing

            natural_size = [0, 0]
            natural_size[axis], natural_size[cross_axis] = position, cross_size
            declared = getattr(self, "_size_declared", (False, False))
            width = self.width if declared[0] else natural_size[0]
            height = self.height if declared[1] else natural_size[1]

            if self.size != (width, height): self.place_configure(width=width, height=height, implied=True)

            self._item_positions = positions
            self._item_sizes = self._itemSizes()

        finally:
            self._layout_lock = False

    def _positionItem(self, item, x:int, y:int):
        if not self._stack_placed: return

        if not item._placed:
            item.place(x, y)
        elif item.location != (x, y):
            item.place_configure(x=x, y=y, implied=True)

    def _itemSizes(self) -> dict:
        return {item:item.size for item in self._items}


class Listable(Stackable):
    """ Adds selection tracking to Stackable """
    def __init__(self, *args, multiple:bool=False, **kwargs):
        self._selected = set()
        self._multiple = bool(multiple)

        super().__init__(*args, **kwargs)

    def getSelected(self) -> tuple:
        return tuple(item for item in self._items if item in self._selected)

    def isSelected(self, item) -> bool:
        return item in self._selected

    def multiSelect(self, enabled:bool=None) -> bool:
        if enabled is not None:
            enabled = bool(enabled)

            if self._multiple and not enabled and len(self._selected) > 1:
                keep = next(item for item in self._items if item in self._selected)
                removed = tuple(item for item in self._items if item in self._selected and item is not keep)
                self._selected = {keep}
                self.selectionChanged((), removed)

            self._multiple = enabled

        return self._multiple

    def select(self, item):
        self._validateSelectionItem(item)

        if self._multiple:
            if item not in self._selected:
                self._selected.add(item)
                self.selectionChanged((item,), ())
        else:
            self.selectOnly(item)

        return item

    def selectOnly(self, item):
        self._validateSelectionItem(item)

        added = () if item in self._selected else (item,)
        removed = tuple(entry for entry in self._items if entry in self._selected and entry is not item)

        if added or removed:
            self._selected = {item}
            self.selectionChanged(added, removed)

        return item

    def deselect(self, item):
        if item in self._selected:
            self._selected.remove(item)
            self.selectionChanged((), (item,))

        return item

    def toggle(self, item):
        return self.deselect(item) if item in self._selected else self.select(item)

    def clearSelection(self):
        if self._selected:
            removed = self.getSelected()
            self._selected.clear()
            self.selectionChanged((), removed)

    def selectionChanged(self, selected:tuple, deselected:tuple):
        pass

    def dropChild(self, child):
        if child in self._selected:
            self._selected.remove(child)
            self.selectionChanged((), (child,))

        super().dropChild(child)

    def _validateSelectionItem(self, item):
        if item not in self._items:
            raise ValueError("List selection must reference an item in the List")


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

    # Collection children belong logically to the Collection and physically to its real Tk host.
    def registerChild(self, child):
        super().registerChild(child)
        host = self.childMaster()
        if hasattr(host, "registerChild"): host.registerChild(child)

    def dropChild(self, child):
        host = self.childMaster()
        if hasattr(host, "dropChild"): host.dropChild(child)
        super().dropChild(child)

    def childChanged(self, child):
        super().childChanged(child)
        host = self.childMaster()
        if hasattr(host, "childChanged"): host.childChanged(child)

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
            visible = decimateRect((0, 0, *self.size),
                                   [self.childGeometry(child) for child in self._children if child.isOpaque()])
            if visible:
                if len(visible) == 1:
                    self._skin_offset = tuple(visible[0][:2])
                    new_img = UImage(width=visible[0][2], height=visible[0][3])
                else: new_img = UImage(width=self.width, height=self.height)
            else: new_img = UImage()
            self.setSkin(Skin(new_img))

        super()._afterGeometryChanges()


class Stack(Stackable, Collection):
    def __init__(self, parent, vertical:bool=True, spacing:int=0, **kwargs):
        super().__init__(parent, vertical=vertical, spacing=spacing, **kwargs)

class List(Listable, Collection):
    def __init__(self, parent, vertical:bool=True, spacing:int=0, multiple:bool=False, **kwargs):
        super().__init__(parent, vertical=vertical, spacing=spacing, multiple=multiple, **kwargs)
