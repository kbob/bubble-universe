# Bubble Universe

![A particle system that shows a mostly round shape filled with
fractal curves](images/example.png)

Here are two implementations of the Bubble Universe graphics hack.

The first is in Javascript with WebGPU.  It runs in a browser window.
The second is in Python using wgpu-py.  It runs as a desktop app.

The plan for the Javascript version is for it to become an interactive
web page with GUI controls to vary a few parameters of the graphics.
I'll get to learn a little about web front end development, CSS,
DOM, page animation, etc.  At this time, the Javascript version has no
parameters; it just runs non-interactively.

Meanwhile, I want the Python version to become a scriptable toolkit
for deeper customization.  It is gradually getting features, it can
record directly to a video file, and many parameters are changeable
in the code.

The original single-file Python version is still here
at `python/bub.py`, too.

# Running the Javascript Version

Go into the `javascript` subdirectory and start a web server.  Then load
/bub.html into your browser.  It won't work (for me) from the file://
URL scheme because of some browser security issue that I don't care to
understand or bypass.

Here's a quick way to start a web server.

    $ cd javascript
    $ python -m http.server
    $ # now open http://localhost:8000/bub.html in a browser

You'll need a WebGPU-capable browser, of course.  I've been using
Vivaldi on MacOS.


# Running the Python version

Create a Python venv with the dependencies installed.  The script
`tools/create-venv.sh` will do it.  Activate the venv, then from
the top directory of this repository run `python python/main.py`.

    $ sh tools/create-venv.sh
    $ source venv/bin/activate
    ((venv) ) $ python python/main.py --help
    usage: main.py [-h] [+h] Command ...

    Explore the bubble universe

    options:
    -h, --help    show this help message and exit
    +h, --no-hdr  do not render in high dynamic range (HDR)

    Subcommands:
    Command       Action
        record      record video to a file


# Running the original Python version

This is feature-compatible with the Javascript version
(*i.e.*, no features.)

As above, you need to use the Python venv.

    $ sh tools/create-venv.sh    # if you haven't already
    $ source venv/bin/activate
    ((venv) ) $ python python/bub.py


# License

This software is licensed under the GNU GPL Version 3, as found in
the LICENSE file.

Portions are copyright 2021 Stefan Gustavson and Ian McEwan under
the MIT license.  That license is available here.
https://github.com/stegu/psrdnoise/
