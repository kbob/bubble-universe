# Bubble Universe

Here are two implementations of the Bubble Universe graphics hack.

The first is in Javascript with WebGPU.  It runs in a browser window.
The second is in Python using wgpu-py.  It runs as a desktop app.  At
this moment (initial commit), they are functionally identical.

The plan is for the Javascript version to become an interactive web page
with GUI controls to vary common parameters, while the 


# Running the Javascript Version

Go into the `javascript` subdirectory and start a web server.  Then load
/bub.html into your browser.  It won't work (for me) from the file://
sccheme because of some browser security issue that I don't care to
understand or bypass.

Here's a quick way to start a web server.

    $ cd javascript
    $ python -m http.server
    $ # now open http://localhost:8000/bub.html in a browser


# Running the Python version

Create a Python venv with the dependencies installed.  The script
`tools/create-venv.sh` will do it.  Activate the venv, then from
the top directory of this repository run `python python/bub.py`.

    $ sh tools/create-venv.sh
    $ source venv/bin/activate
    ((venv) ) $ python bub/bub.py

