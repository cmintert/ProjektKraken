from src.gui.widgets.map.map_data_buffer import MapDataBuffer, ColorMap
import numpy as np
buf = MapDataBuffer(10,10, default_value=0)
# paint center with high value
buf.paint_brush(0.5,0.5,2,60000, falloff=0.0)
cm = ColorMap(type='gradient', gradient_start='#00000000', gradient_end='#FF000080')
img = buf.colorize(cm)
# inspect alpha stats
ptr = img.bits().tobytes()
arr = np.frombuffer(ptr, dtype=np.uint8).reshape((img.height(), img.width(), 4))
print('alpha min max', arr[:,:,3].min(), arr[:,:,3].max())
print('sample pixel rgba', arr[5,5])
