# To Do

* &#x2705; alpha mode lighten
* &#x2705; compute shader for particles
* &#x2705; M and N independent
* &#x2705; reimplement in Python and wgpu-py
* &#x2705; restructure wgpu initialization as a rendergraph
* &#x2705; ~~image output and~~ video output
  - &#x2705; wgpu-py + numpy + PyAV
* postprocessing
  - &#x2705; HDR + tone mapping
  - bloom
  - lens flare
  - trails
* colors
  - classic RGB
  - HSV colors
  - animated colormap
  - color/gradient the background outside the circle
  - color schemes
    + vaporwave
    + midnight
    + fiesta
* MSAA?
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


## Internal changes

* &#x2705; factor out parameter handling
* Bubbler and BubblerHDR need to be merged.


## Bloom changes

* Redesign subgraph construction
* Use float32
* Does upsampler `filter_radius` need to be a vec2f?
