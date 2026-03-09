from math import tau

# Internal/performance constants
MAX_FPS = 60                    # FPS = frames/second
MAX_SEQ_COUNT = 2000
MAX_SEQ_LENGTH = 2000
BORDER = 0.1                    # fraction of viewport size
WORKGROUP_SIZE = 64             # defined in compute shader(s)
BLEND_MODE = 'add'              # 'add' or 'blend'
USE_HDR = True
HDR_PIXEL_FORMAT = 'rgba16float'
BLOOM_MIP_LEVELS = 5

class Defaults:
    SEQ_COUNT = 200
    SEQ_LENGTH = 200
    SPEED = tau / 12.5          # radians/sec
    R = tau / 235               # radians
    PARTICLE_SIZE = 3           # pixels normalized to CANVAS_SIZE
    CANVAS_SIZE = (675, 540)
    VIDEO_FILE = 'temp.mp4'
    BLOOM_AMOUNT = 0.04
    BLOOM_SIZE = 0.005
