from src.gui.widgets.map.map_data_buffer import MapDataBuffer
import numpy as np
buf = MapDataBuffer(100,100, default_value=30000)
# paint gradient from left to right with values 0->65535
dirty = buf.paint_gradient(0.0,0.5,1.0,0.5, 0, 65535, width_px=0)
print('gradient dirty:', dirty, 'min max', buf.data.min(), buf.data.max())
# paint brush in center with value=10000
buf.paint_brush(0.5,0.5,10,10000, falloff=0.0)
print('after brush min max', buf.data.min(), buf.data.max())
# now paint gradient of small range 0->10
buf2 = MapDataBuffer(100,100, default_value=0)
buf2.paint_gradient(0.2,0.2,0.8,0.8, 0, 10, width_px=10)
print('buf2 min max', buf2.data.min(), buf2.data.max())
