from math import tau

# Internal/performance constants
MAX_FPS = 60                    # FPS = frames/second
MAX_SEQ_COUNT = 200
MAX_SEQ_LENGTH = 200
BORDER = 0.1                    # fraction of viewport size
BLEND_MODE = 'blend'            # 'add' or 'blend'
WORKGROUP_SIZE = 64             # defined in compute shader(s)


class Defaults:
    SEQ_COUNT = 200
    SEQ_LENGTH = 200
    SPEED = tau / 12.5          # radians/sec
    R = tau / 235               # radians
    PARTICLE_SIZE = 3           # pixels normalized to CANVAS_SIZE
    VIDEO_FILE = 'temp.mp4'
    CANVAS_SIZE = (675, 540)
