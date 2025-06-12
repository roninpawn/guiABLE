import tkinter as tk
from warnings import warn
from utilities import updateHover, limitMove
from windowing import Backgroundable


class Skinnable():
    def __init__(self, normal_path=None, hover_path=None, active_path=None, disabled_path=None):
        self._recipients = []
        self._paths = [normal_path, hover_path, active_path, disabled_path]
        self._images = [None, None, None, None]

        self.changePaths(normal_path, hover_path, active_path, disabled_path)

        if self._images[0] is None:
            for n in range(1, 4):
                if self._images[n] is not None:
                    self._images[0] = self._images[n]
                    break
            if self._images[0] is None:
                self._images[0] = tk.PhotoImage(width=0, height=0)

        for n in range(1, 3):
            if self._images[n] is None:
                self._images[n] = self._images[n - 1]
                self._paths[n] = self._paths[n - 1]

        if self._images[3] is None:
            self._paths[3] = self._paths[0]
            self._images[3] = self._images[0]

    def changePaths(self, normal_path=None, hover_path=None, active_path=None, disabled_path=None, _direct=False):
        paths = [normal_path, hover_path, active_path, disabled_path]
        for n in range(4):
            if paths[n] is not None and not self._checkDuplicates(paths[n], n):
                self._paths[n] = paths[n]
                self._images[n] = paths[n] if _direct else self._loadImg(paths[n])

    def directSetImages(self, normal_img=None, hover_img=None, active_img=None, disabled_img=None):
        self.changePaths(normal_img, hover_img, active_img, disabled_img, _direct=True)

    def bindWidget(self, widget):
        self._recipients.append(widget)

    def unbindWidget(self, widget):
        if widget in self._recipients:
            self._recipients.remove(widget)

    def updateRecipients(self):
        for widget in self._recipients:
            updateHover(widget)

    def _checkDuplicates(self, path, index):
        for i, p in enumerate(self._paths):
            if p == path and self._images[i] is not None:
                self._images[index] = self._images[i]
                return True
        return False

    def _loadImg(self, path):
        try:
            return tk.PhotoImage(file=path)
        except tk.TclError:
            warn(f"guiABLE: Image not found: {path}", RuntimeWarning)
            return tk.PhotoImage(width=0, height=0)

    def images(self):
        return self._images


class Imageable(tk.Canvas):
    def __init__(self, parent, skinnable=None, **kwargs):
        super().__init__(parent, highlightthickness=0, **kwargs)
        self._skin = skinnable or Skinnable()
        self._skin.bindWidget(self)
        self.current_image = 0
        self.enabled = True
        self.enable()

    def setSkin(self, skinnable):
        if self._skin:
            self._skin.unbindWidget(self)
        skinnable.bindWidget(self)
        self._skin = skinnable
        updateHover(self)

    def clearSkin(self):
        if self._skin:
            self._skin.unbindWidget(self)
        self._skin = Skinnable()
        updateHover(self)

    def changeImage(self, idx):
        self.current_image = idx
        self.create_image(0, 0, image=self._skin.images()[idx], anchor=tk.NW)

    def enable(self):
        self.changeImage(self.current_image)
        self.enabled = True

    def disable(self):
        self.changeImage(3)
        self.enabled = False
