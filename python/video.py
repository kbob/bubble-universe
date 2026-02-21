import av
import numpy as np
# from PIL import Image

# frame_no = 0

class VideoOutputFile:

    def __init__(self, filename, resolution, fps, pix_fmt='yuv420p'):
        self.filename = filename
        self.container = av.open(filename, mode='w')
        self.stream = self.container.add_stream('mpeg4', rate=fps)
        self.stream.height = resolution[1]
        self.stream.width = resolution[0]
        self.stream.pix_fmt = pix_fmt

    def append_frame(self, array):
        assert isinstance(array, np.ndarray)
        frame = av.VideoFrame.from_ndarray(array, format='rgba')
        for packet in self.stream.encode(frame):
            self.container.mux(packet)

        # global frame_no
        # frame_no += 1
        # image = Image.fromarray(array, 'RGBA')
        # image.save(f'image-{frame_no:02}.png')

    def close(self):
        for packet in self.stream.encode():
            self.container.mux(packet)
        self.container.close()
