from guiABLE import *


def test_gui():
    app = Windowable(geometry="600x400+100+100", title="guiABLE Testbed")
    bg = Backgroundable(app, "600", "400", bg="gray30")
    bg.inner.configure(cursor="fleur")
    bg.place(x=0, y=0)
    app.bindDrag(bg.inner)

    # Create a test Pushable button
    btn_skin = Skinnable("UI/button_normal.png", "UI/button_hover.png", "UI/button_active.png", "UI/button_disabled.png")
    test_btn = Pushable(bg, lambda: print("Button clicked!"), skinnable=btn_skin, width=100, height=40)
    test_btn.place(x=20, y=20)

    # Create a Toggleable checkbox
    toggle_skin1 = Skinnable("UI/toggle_off.png")
    toggle_skin2 = Skinnable("UI/toggle_on.png")
    test_toggle = Toggleable(bg, function=lambda: print("Toggle state:", test_toggle.state()),
                             skinnable_1=toggle_skin1, skinnable_2=toggle_skin2, width=40, height=40)
    test_toggle.place(x=140, y=20)

    # Create a draggable object
    drag_skin = Skinnable("UI/drag_normal.png", "UI/drag_hover.png", "UI/drag_active.png")
    test_drag = Draggable(bg, skinnable=drag_skin, width=50, height=50)
    test_drag.place(x=200, y=20)

    # Create a Labelable (button with text overlay)
    label_skin = Skinnable("UI/label_normal.png", "UI/label_hover.png", "UI/label_active.png")
    test_label = Labelable(bg, function=lambda: print("Label clicked!"), skinnable=label_skin,
                           text="Hello", text_pos=(10, 5), font=("Arial", 12, "bold"), color="white",
                           width=100, height=40)

    test_label.place(x=280, y=20)

    # Create an EXIT button from a Labelable
    exit_button = Labelable(bg, function=app.quit, text="✕", font=("Arial", 20, "bold"), color="black", text_pos=(1,0),
                            width=30, height=30)
    exit_button.place(x=560, y=10)

    # Create a scrollable pane with content
    pane_skin = ScrollablePaneSkin()
    scrollpane = ScrollablePane(bg, width=250, height=150, scrollable_pane_skin=pane_skin, auto=(True, True))
    scrollpane.place(x=20, y=100)

    for i in range(30):
        label = tk.Label(scrollpane.inner, text=f"Item {i+1}", anchor="w")
        label.pack(fill=tk.X, padx=5)

    # Create a Holdable button
    hold_skin = Skinnable("UI/hold_normal.png", "UI/hold_hover.png", "UI/hold_active.png")
    hold_btn = Holdable(bg, function=lambda: print("Holding..."), skinnable=hold_skin, width=100, height=40, delay=200)
    hold_btn.place(x=20, y=300)

    # Create a Clickable-only button
    click_skin = Skinnable("UI/click_normal.png", "UI/click_hover.png", "UI/click_active.png")
    click_btn = Clickable(bg, function=lambda: print("Clicked instantly!"), skinnable=click_skin, width=100, height=40)
    click_btn.place(x=140, y=300)

    # Create a Troughable area
    trough_skin = Skinnable("UI/trough_normal.png", "UI/trough_hover.png", "UI/trough_active.png", "UI/trough_disabled.png")
    trough = Troughable(bg, width=150, height=30, skinnable=trough_skin)
    trough.place(x=400, y=300)

    app.mainloop()


if __name__ == "__main__":
    test_gui()
