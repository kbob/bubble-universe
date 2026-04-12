import av
import numpy as np
from PIL import Image

EMIT_MP4 = False
EMIT_PNGS = True

frame_no = 0

class VideoOutputFile:

    def __init__(self, filename, resolution, fps, pix_fmt='yuv420p'):
        self.filename = filename
        if EMIT_MP4:
            self.container = av.open(filename, mode='w')
            self.stream = self.container.add_stream(
                'mpeg4',
                rate=fps,
                options={
                    # 'c:v': 'libx264',
                    'c:v': 'libsvtav1',
                    'crf': '0',
                    'qp': '0',
                    # 'tune': 'grain',
                    'preset': 'veryfast',
                },
            )
            self.stream.height = resolution[1]
            self.stream.width = resolution[0]
            self.stream.pix_fmt = pix_fmt

    def append_frame(self, array):
        assert isinstance(array, np.ndarray)

        # Emit video frame through ffmpeg
        if EMIT_MP4:
            frame = av.VideoFrame.from_ndarray(array, format='rgba')
            for packet in self.stream.encode(frame):
                self.container.mux(packet)

        # Save frame as PNG
        if EMIT_PNGS:
            global frame_no
            frame_no += 1
            image = Image.fromarray(array, 'RGBA')
            image.save(f'image-{frame_no:04}.png')

    def close(self):
        if EMIT_MP4:
            for packet in self.stream.encode():
                self.container.mux(packet)
            self.container.close()
            print(f'Video saved to {self.filename}')
        if EMIT_PNGS:
            print(f'Images saved to image-0000.png .. image-{frame_no - 1:04}.png')