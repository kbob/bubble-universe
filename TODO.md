# To Do

* &#x2705; alpha mode lighten
* &#x2705; compute shader for particles
* &#x2705; M and N independent
* &#x2705; reimplement in Python and wgpu-py
* restructure wgpu initialization as a rendergrapha
* image output and video output
  - ??? Rust?
  - ??? wgpu-py + PIL?
    + and Jupyter too?
* postprocessing
  - trails
  - HDR + tone mapping
  - bloom
  - lens flare
* colors
  - classic RGB
  - HSV colors
  - animated colormap
* 3D
  - perspective camera
  - rotation
  - map points to 3D somehow
* UI
  - replace alert box with window
  - sliders and buttons
  - hide the cursor when it's inactive.  (css: { cursor: none; })
* Audio
  - ZOMG!  Each particle sequence could totally be an oscilloscope
    waveform!  Convert its (X, Y) to left and right channels, step
    through it at whatever frequency you want, and it's one percussive
    note.  High-pass filter it to get rid of the DC offset.  Not sure
    what to do with all the time steps.  Maybe track a sequence through
    time?  Maybe just use whatever time step is current when the note
    is triggered.