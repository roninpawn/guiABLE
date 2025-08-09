from guiABLE import *
from guiABLE.utilities import cropImage


def test_gui():
    app = Windowable(geometry="600x400+100+100", title="guiABLE Testbed")
    my_image = tk.PhotoImage(file="../skins/default/bg-600x400.png")
    bg = Backgroundable(app, "600", "400")
    bg.setImage(my_image)
    bg.inner.configure(cursor="fleur")
    bg.place(x=0, y=0)
    app.bindDrag(bg.inner)

    # Create a test Pushable button
    btn_skin = Skin("../skins/default/cog.png", "../skins/default/cog_mo.png", "../skins/default/cog_red.png")
    test_btn = Pushable(bg, lambda: print("Button clicked!"), width=100, height=40)
    test_btn.place(x=20, y=20)

    # Create a Toggleable checkbox
    toggle_skin = Skin.fromSpriteSheet("../skins/default/checkbox-64.png", 64)
    toggle_skin.setBGColors("gray30")
    test_toggle = Toggleable(bg, function=lambda: print("Toggle state:", test_toggle.state()), skin=toggle_skin,
                             width=64, height=64)
    test_toggle.place(x=160, y=20)

    # Create a draggable object
    drag_skin = Skin.fromSpriteSheet("../skins/default/radiobox-64.png", 64)
    test_drag = Draggable(bg, skin=drag_skin, width=64, height=64)
    test_drag.place(x=260, y=20)

    # Create a Labelable (button with text overlay)
    label_skin = Skin("../skins/default/label_normal.png", "../skins/default/label_hover.png", "../skins/default/label_active.png")
    test_label = Labelable(bg, function=lambda: print("Label clicked!"), skin=btn_skin,
                           text="Hello", text_pos=(10, 5), font=("Arial", 12, "bold"), color="white",
                           width=100, height=40)

    test_label.place(x=360, y=20)

    # Create an EXIT button from a Labelable
    x_sprite = Skin.fromImages(cropImage(tk.PhotoImage(file='../skins/default/window-glyphs-40.png'), 80, 0, 40, 40))
    x_sprite.usesBgColors(True)
    exit_button = Pushable(bg, function=app.quit, skin=x_sprite, width=40, height=40)
    exit_button.place(x=550, y=10)

    # Create a scrollable pane with content
    pane_skin = ScrollablePaneSkin()
    scrollpane = ScrollablePane(bg, width=250, height=150, scrollable_pane_skin=pane_skin, auto=(True, True))
    scrollpane.place(x=20, y=100)

    for i in range(30):
        label = tk.Label(scrollpane.inner, text=f"Item {i + 1}", anchor="w")
        label.pack(fill=tk.X, padx=5)

    # Create a Holdable button
    hold_skin = Skin("../skins/default/hold_normal.png", "../skins/default/hold_hover.png", "../skins/default/hold_active.png")
    hold_btn = Holdable(bg, function=lambda: print("Holding..."), skin=hold_skin, width=100, height=40, delay=200)
    hold_btn.place(x=20, y=300)

    # Create a Clickable-only button
    click_skin = Skin("../skins/default/click_normal.png", "../skins/default/click_hover.png", "../skins/default/click_active.png")
    click_btn = Clickable(bg, function=lambda: print("Clicked instantly!"), skin=click_skin, width=100, height=40)
    click_btn.place(x=140, y=300)

    # Create a Troughable area
    trough_skin = Skin("../skins/default/trough_normal.png", "../skins/default/trough_hover.png", "../skins/default/trough_active.png", "../skins/default/trough_disabled.png")
    trough = Troughable(bg, width=150, height=30, skin=trough_skin)
    trough.place(x=400, y=300)

    click_btn.lift(test_toggle)
    #exit_button.lift(test_drag)
    app.mainloop()


if __name__ == "__main__":
    test_gui()
