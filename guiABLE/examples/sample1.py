from guiABLE import *
from guiABLE.skinnable import ScrollSkin
from guiABLE.utilities import cropImage, rotateImage, loadImage


def test_gui():
    app = Windowable(geometry="600x400+100+100", title="guiABLE Testbed")
    bg_image, _ = loadImage("../skins/default/bg-600x400.png")
    bg = Backgroundable.fromImage(app, 600, 400, bg_image)
    bg.place(x=0, y=0)

    # Make app draggable by grabbing the background.
    bg.configure(cursor="fleur")
    app.bindDrag(bg)

    # Create a test Pushable button
    btn_skin = Skin("../skins/default/cog.png", "../skins/default/cog_mo.png", "../skins/default/cog_red.png")
    test_btn = Pushable(bg, lambda: print("Button clicked!"), skin=btn_skin, width=140, height=24)
    test_btn.place(x=60, y=0)

    # Create a Toggleable checkbox
    toggle_skin = Skin.fromSpriteSheet("../skins/default/checkbox-64.png", 64)
    test_toggle1 = Toggleable(bg, True, lambda: print("Toggle1 state:", test_toggle1.state()), skin=toggle_skin,
                             width=64, height=64)
    test_toggle1.place(x=80, y=24)

    test_toggle2 = Toggleable(bg, function=lambda: print("Toggle2 state:", test_toggle2.state()), skin=toggle_skin,
                             width=64, height=64)
    test_toggle2.place(x=144, y=24)

    # Create a draggable object
    drag_skin = Skin.fromSpriteSheet("../skins/default/radiobox-64.png", 64)
    test_drag = Draggable(bg, skin=drag_skin, width=64, height=64)
    test_drag.place(x=260, y=24)

    # Create a Labelable (button with text overlay)
    test_label = Labelable(bg, function=lambda: print("Label clicked!"), skin=btn_skin,
                           text="Hello", text_pos=(10, 5), font=("Arial", 12, "bold"), color="white",
                           width=100, height=24)

    test_label.place(x=360, y=88)

    # Create an EXIT button from a Labelable
    x_sprite = Skin.fromImages(cropImage(tk.PhotoImage(file='../skins/default/window-glyphs-40.png'), 80, 0, 40, 40))
    x_sprite.usesBgColors(True)
    x_sprite.setBGColor("red", 2)
    exit_button = Pushable(bg, function=app.quit, skin=x_sprite, width=40, height=40)
    exit_button.place(x=550, y=10)

    # Create a scrollable pane with content
#    pane_skin = ScrollablePaneSkin()
#    scrollpane = ScrollFrame(bg, width=250, height=150, scrollable_pane_skin=pane_skin, auto=(True, True))
#    scrollpane.place(x=20, y=100)
#
#    for i in range(30):
#       label = tk.Label(scrollpane.inner, text=f"Item {i + 1}", anchor="w")
#       label.pack(fill=tk.X, padx=5)

    # Create a Holdable button
    hold_btn = Holdable(bg, function=lambda: print("Holding"), width=100, height=40, delay=200)
    hold_btn.place(x=20, y=350)

    # Create a Clickable-only button
    click_btn = Clickable(bg, function=lambda: print("Clicked instantly!"), width=100, height=40)
    click_btn.place(x=140, y=350)

    # Create extra Togglables for above/below testing.
    test_toggle3 = Toggleable(bg, True, lambda: print("Toggle1 state:", test_toggle3.state()), skin=toggle_skin,
                             width=64, height=64)
    test_toggle3.place(x=380, y=24)

    test_toggle4 = Toggleable(bg, function=lambda: print("Toggle2 state:", test_toggle4.state()), skin=toggle_skin,
                             width=64, height=64)
    test_toggle4.place(x=444, y=24)

    from guiABLE.skinnable import BarSkin as BS
    trough_skin = Skin("../skins/default/square-48.png")
    cap_skin = Skin("../skins/default/up_glyph-48.png")

    bar_skin = BS.fromTwo(cap_skin, trough_skin, True)
    mid_skin = Skin.fromImages(bar_skin.image(0, 192))
    c = Clickable(bg, skin=mid_skin, width=48, height=192)
    c.place(x=550, y=200)

    cap_skin2 = Skin.fromImages(rotateImage(cap_skin.image(), False))
    trough_skin2 = Skin.fromImages(rotateImage(trough_skin.image(), False))
    bar_skin2 = BS.fromTwo(cap_skin2, trough_skin2)
    mid_skin2 = Skin.fromImages(bar_skin2.image(0, 192))
    c2 = Clickable(bg, skin=mid_skin2, width=192, height=48)
    c2.place(x=350, y=352)

    trough_skin = Skin("../skins/default/scroll_trough-48.png")
    cap_skin = Skin("../skins/default/up_glyph-48.png", orientation="n")
    scroll_skin = ScrollSkin.fromSkins(cap_skin, trough_skin, None, True, cap_skin, "n")
    scroll_area = Scrollable(bg, 450, 215, scroll_skin)
    scroll_area.skin.setImage(bg_image)
    scroll_area.place(x=20, y=120)

    nude_skin = BS()
    #nude_skin.usesBgColors(False)
    nude_drag = Draggable(bg, nude_skin, width=50, height=50)
    nude_drag.place(x=0, y=0)

    for i in range(30):
       label = tk.Label(scroll_area.scrollPane, text=f"Item {i + 1}", anchor="w", background="blue")
       label.pack(fill=tk.X, padx=10, pady=10)
       label.pack(fill=tk.X, padx=10, pady=10)

    # Prove lower/lift functionality
    click_btn.lift(test_toggle1)
    exit_button.lift(test_toggle1)
    test_toggle2.lift()
    test_toggle3.lower()
    test_toggle4.lift(test_toggle2)

    fps_label = tk.Label(bg, text="FPS", anchor="w")
    fps_label.place(x=518, y=10)

    """
    WOW! Having a live tick is CRUCIAL to getting good redraw performance. mainloop() must throttle hard and need to
    kick up to speed without something to keep it updating idletasks regularly. Damn!
    """
    app.fps = 0
    def tick():
        app.fps += 1
        app.after(8, tick)
    tick()

    def update_fps():
        fps_label.configure(text=app.fps)
        app.fps = 0
        app.after(1000, update_fps)
    update_fps()

    app.mainloop()

if __name__ == "__main__":
    test_gui()
