# guiABLE
The project to make Python's tkinter suck considerably less.

guiABLE is a quick, all-inlusive library that allows you to whip up a graphic user interface in Python that:
1.) Doesn't look awful.
2.) Didn't take two weeks to get a simple scrollbar working.
3.) Doesn't require a dozen other libraries to make function.

guiABLE is built on Python's tkinter. Yes, THAT tkinter. Wait! No. Come back! It doesn't smell, I promise!
This library allows you to create and graphically texture all the basic needs of a UI, over-riding the
default visual style of whatever operating system your application is run on. Each class accepts 4 images
to cover the 4 typical states of behavior:

  1.) Normal
  2.) Moused-over (hover)
  3.) Active (clicking)
  4.) Disabled

You can populate as many of those image-states as you choose to, or none at all. (if you like the look of
blank gray boxes) Buttons will look the way YOU want buttons to look; Checkboxes the way YOU want boxes to
check; Snozzberries the way snozz wants berry to YOU!

Design the layout and placement of your UI before you've got the graphics to go with it, and see everything
functioning, mousing-over, reacting to your inputs, well before you know what the program is going to look
like.

And oh yeah, the implementation looks like this:

  config_btn = Pushable(lambda: print("Hi mom!"), ["UI/cog.png", "UI/cog_mo.png", "UI/cog_red.png"], width=22, height=23)
  config_btn.place(x=10 y=10)
  
Won't mom be proud when she sees the button you skineed for her yourself!

Classes include:

  Backgroundable - simple object that accepts a background image.
  Hoverable      - object that changes image when hovered over.
  Clickable      - a 'Hoverable' that fires a function the instant you click it.
  Pushable       - a 'Clickable' that fires a function when you let off the mouse button, while over it.
                   (it's just a button, that's how buttons work)
  Toggleable     - a 'Pushable' that maintains an internal true/false state. (Think 'checkbox')
                   Accepts up to 8 images to represent all ticked/not-ticked visual states.
  Holdable       - also a 'Pushable' that fires a function continuously when held.
                   With optional second-click delay.
  Draggable      - a 'Holdable' that can be dragged anywhere within the boundaries of its parent object.
                   'Why?' you ask? Because scrollbars. Which reminds me!
  Scrollable     - a 133-line-long class containing the insanely convoluted amount of code required to make
                   a simple scrollbar function LIKE IT SHOULD in tkinter.
  ScrollablePane - an object into which you may insert... whatever you feel appropriate... that will manifest
                   vertical and horizontal scrollbars, either as needed, or by your explicit declaration.

...and SO MUCH MORE!

Actually, that's most of it for now. What else do you want? I made tkinter actually work! Isn't that enough for you people?!


-Roninpawn S. Preston, Esq.
  4/27/2019, 5:21pm, hungry and needing to pee.
