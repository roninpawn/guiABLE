from guiABLE import *


def test_gui():
    app = Window(420, 180, 600, 400, title="guiABLE Testbed")
    bg_image, _ = loadImage("../skins/default/bg-600x400.png")
    app.setSkin(Skin(bg_image))

    app.bindDrag(app)       # Make app Drag by grabbing the background.

    # Create a Label
    label_font = FontPack(color="White", weight="bold")
    test_label = Label(app, "This is a label.", label_font)
    test_label.place(x=0, y=0)

    # Create a Checkbox
    toggle_skin = Skin.fromSpriteSheet("../skins/default/checkbox-64.png", 64)
    test_toggle1 = Checkbox(app, toggle_skin, lambda: print("Toggle1 state:", test_toggle1.isTrue()), True)
    test_toggle1.place(x=76, y=24)

    test_toggle2 = Checkbox(app, toggle_skin, lambda: print("Toggle2 state:", test_toggle2.isTrue()), False)
    test_toggle2.place(x=140, y=24)

    # Create a Drag object
    drag_skin = Skin.fromSpriteSheet("../skins/default/radiobox-64.png", 64)
    test_drag = Drag(app, drag_skin)
    test_drag.place(x=260, y=24)

    btn_skin = Skin("../skins/default/cog.png", "../skins/default/cog_mo.png", "../skins/default/cog_red.png")
    opaque_test = Image(app, btn_skin)
    opaque_test.place(x=280, y=45)

    # Create a Button with text
    test_btn = Button(app, btn_skin, lambda: print("Label clicked!"), "Button!", label_font, width=100, height=0)
    test_btn.place(x=360, y=0)

    glyphs = UImage(file='../skins/default/window-glyphs-40.png')
    exit_x = glyphs.crop(80, 0, 40, 40)
    # Create an EXIT button from a Label
    x_sprite = Skin(exit_x)
    x_sprite.usesBgColors(True)
    x_sprite.setBGColor("red", 2)
    exit_button = Button(app, function=app.quit, skin=x_sprite)
    exit_button.place(x=550, y=10)

    # Create a Holdable button
    hold_btn = RepeatButton(app, function=lambda: print("Holding"), width=80, height=40, delay=200)
    hold_btn.place(x=500, y=120)

    # Create a Clickable-only button
    click_btn = InstantButton(app, function=lambda: print("Clicked instantly!"), width=80, height=40)
    click_btn.place(x=500, y=180)

    from guiABLE.skinnable import BarSkin as BS
    trough_skin = Skin("../skins/default/square-48.png")
    cap_skin = Skin("../skins/default/up_glyph-48.png")

    bar_skin = BS.fromTwo(cap_skin, trough_skin, True)
    mid_skin = Skin(bar_skin.image(0, 192))
    c = InstantButton(app, skin=mid_skin, width=48, height=192)
    c.place(x=550, y=200)

    occlude = TroughButton(app, width=200, height=300)
    #occlude.place(x=400, y=100)

    trough_skin = Skin("../skins/default/scroll_trough-48.png")
    cap_skin = Skin("../skins/default/up_glyph-48.png", orientation="n")
    scroll_skin = ScrollSkin.fromSkins(cap_skin, trough_skin, None, True, cap_skin, "n")
    scroll_win = ScrollWindow(app, 450, 280, scroll_skin, "#3B4F4F")
    scroll_win.place(x=20, y=100)
    #scroll_win.setScrollbarVisibility(1)
    #scroll_win.setScrollbarState(1)

    #scroll_area.dominant_axis = 0
    #scroll_area.showBars(1, 1)

    # Create Togglables for changing the scrollbar settings.
    test_toggle3 = Checkbox(app, toggle_skin, scroll_win.getInstantPage()[0])
    test_toggle3.function = (scroll_win.setInstantPage, test_toggle3.isTrue)
    test_toggle3.place(x=380, y=24)

    # Toggle both line and page smoothing simultaneously
    test_toggle4 = Checkbox(app, toggle_skin, state=True)
    def toggle_smoothing(state):
        scroll_win.setLineSmoothing(state)
        scroll_win.setPageSmoothing(state)
    test_toggle4.function = (toggle_smoothing, test_toggle4.isTrue)
    test_toggle4.place(x=444, y=24)

    nude_skin = BS()
    #nude_skin.usesBgColors(False)
    nude_drag = Drag(app, skin=nude_skin, width=50, height=50)
    #nude_drag.place(x=0, y=0)

    for i in range(50):
        #label = Button(scroll_area.frame, function=lambda: print(f"Label clicked!"), skin=btn_skin, width=24, height=24)
        label = Button(scroll_win.frame, btn_skin, lambda: print("Label clicked!"), f"Item {i + 1}", label_font,
                      width=100, height=24)
        #label = tk.Label(scroll_area.scroll_plate, text=f"Item {i + 1}", anchor="w", background="teal")
        label.place(x=10, y=30*i)
        #label.pack(padx=10, pady=10, fill="both")

    brdr_skin2 = BorderSkin(
        Skin("../skins/default/border-gray-nw-corner-round-4px.png"),
        Skin("../skins/default/border-gray-n-edge-4px.png")
    )

    text_test = InputLine(scroll_win.plate, 200, skin=brdr_skin2, font_pack=label_font, max_chars=12).place(90, 5)
    text_test.setMask("*", True)
    text_test.setSubmitFunction(lambda:text_test.editable(False))
    text_test.setPlaceholder("Enter Password", FontPack(weight="italic", color="#BBBBBB"))
    sel_btn = Button(scroll_win.plate, None, text_test.selectAll, width=28, height=28).place(292, 5)

    brdr_skin = BorderSkin(
        Skin("../skins/default/border-gray-nw-corner-round-4px.png"),
        Skin("../skins/default/border-gray-n-edge-4px.png")
    )
    url = TextLabel(scroll_win.plate, "https://roninpawn.com\nVisit today!\nTry our new centerable text!",
                    brdr_skin, label_font, "#161a1a", align="center").place(90, 69)
    url.setFontAttributes(weight="bold", color="lime")

    class AssignmentBlob(TextBlob):
        def enterPressed(self) -> bool:
            line = self.get("insert linestart", "insert lineend")
            return "=" in line

    brdr_skin3 = BorderSkin(
        Skin("../skins/default/border-gray-nw-corner-round-4px.png"),
        Skin("../skins/default/border-gray-n-edge-4px.png")
    )

    blob = TextBlob(scroll_win.plate, 260, 200, scroll_skin, skin=brdr_skin3, bg_color="#161a1a", tab_focus=False, wrap="word")
    blob.setText("This is an 'editable' (text) blob... And it wraps at the edge. This is an 'editable' (text) blob... And it wraps at the edge. This is an 'editable' (text) blob... And it wraps at the edge. This is an 'editable' (text) blob... And it wraps at the edge. This is an 'editable' (text) blob... And it wraps at the edge. This is an 'editable' (text) blob... And it wraps at the edge. This is an 'editable' (text) blob... And it wraps at the edge. This is an 'editable' (text) blob... And it wraps at the edge. This is an 'editable' (text) blob... And it wraps at the edge. This is an 'editable' (text) blob... And it wraps at the edge. This is an 'editable' (text) blob... And it wraps at the edge. ")
    blob.place(90, 164)

    # Create Togglables for changing the scrollbar settings.
    test_toggle5 = Checkbox(scroll_win.plate, toggle_skin, None, True if blob.getWrap() != "none" else False)
    def changeWrap(on: bool):
        blob.setWrap("word" if on else "none")
    test_toggle5.function = (changeWrap, test_toggle5.isTrue)
    test_toggle5.place(x=300, y=350)

    test_drag2 = Drag(scroll_win.frame, skin=drag_skin)
    test_drag2.place(x=190, y=385)

    # Prove lower/lift functionality    : Buggy right now.
    #click_btn.lift(test_toggle1)
    #exit_button.lift(test_toggle1)
    #test_toggle2.lift()
    #test_toggle3.lower()
    #test_toggle4.lift(test_toggle2)

    fps_label = tk.Label(app, text="FPS", anchor="w")
    fps_label.place(x=518, y=10)

    """
    WOW! Having a live tick is CRUCIAL to getting good redraw performance. mainloop() must throttle hard and need to
    kick up to speed without something to keep it updating idletasks regularly. Damn!
    """
    app.fps = 0
    def tick():
        app.fps += 1
        app.after(15, tick)
    tick()

    def update_fps():
        fps_label.configure(text=app.fps)
        app.fps = 0
        app.after(1000, update_fps)
    update_fps()

    app.mainloop()

if __name__ == "__main__":
    test_gui()
