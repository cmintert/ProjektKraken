# **High-Performance Cartesian Visualization: A Comprehensive Analysis of the Hybrid Static/Buffer Animation Model in Python 3.13 and PySide6**

## **1\. Introduction**

The visualization of dynamic entities on a Cartesian plane represents a fundamental challenge in computer science, intersecting the domains of data structures, computational geometry, and real-time rendering. In modern industrial applications—ranging from air traffic control systems and maritime logistics trackers to large-scale battlefield simulations—the requirement is not merely to display static icons but to render fluid, temporally accurate representations of moving objects. These systems must handle thousands of entities simultaneously, maintaining high frame rates (typically 60 FPS) while accommodating user interaction, historical playback ("scrubbing"), and complex status indications.

The architectural challenge lies in the dichotomy between the "Static" nature of the visual artifacts and the "Dynamic" nature of the underlying data. A map marker, visually, is often a static asset—a complex vector shape or a rasterized icon that does not change its internal geometry from frame to frame. However, its state—position, rotation, scale, and opacity—is driven by a high-frequency stream of time-series data. Traditional immediate-mode rendering approaches, which rebuild the scene every frame, often falter under the CPU load of managing thousands of Python objects. Conversely, naive retained-mode implementations can suffer from synchronization latency and memory bloat.

This report articulates a rigorous implementation strategy for a "Hybrid Static/Buffer Animation Model," specifically leveraging the architectural advancements in **Python 3.13** and the **PySide6** (Qt 6\) framework. The "Hybrid" model decouples the visual representation (the Static View) from the temporal simulation (the Data Buffer). By treating the animation not as a property of the graphics item but as a function of a lightweight, sorted data buffer, developers can exploit the specific performance characteristics of Python 3.13’s new Just-In-Time (JIT) compiler and the robust culling capabilities of Qt’s Binary Space Partitioning (BSP) trees.

We will explore the theoretical underpinnings and practical implementation details of this model, covering:

1. **The Computational Substrate**: Analyzing how Python 3.13’s JIT and threading improvements (PEP 703, PEP 744\) revolutionize the mathematics of the animation loop.  
2. **Temporal Data Structures**: A comparative analysis of bisect versus sortedcontainers for $O(\\log n)$ keyframe retrieval.  
3. **The Rendering Architecture**: Deep integration with the PySide6 Graphics View Framework to manage scene complexity and prevent recursive event loops.  
4. **Mathematical Frameworks**: Deriving the equations for linear interpolation (LERP), spherical linear interpolation (SLERP), and additive blending for "status effect" animations.  
5. **Artifact Mitigation**: A forensic analysis of "ghosting" artifacts caused by bounding box misalignment and strategies for pixel-perfect invalidation.

## **2\. The Computational Substrate: Python 3.13 and Real-Time Performance**

The selection of the runtime environment is the first critical architectural decision. Historically, Python has been viewed as a "glue" language, less suitable for the tight, arithmetic-heavy loops required for animating thousands of objects. However, the release of Python 3.13 marks a paradigm shift, introducing features that directly address the latency and throughput bottlenecks inherent in previous versions.

### **2.1 The Impact of the Experimental JIT (PEP 744\)**

Python 3.13 introduces an experimental Just-In-Time (JIT) compiler.1 To understand its relevance to the Hybrid Animation Model, one must analyze the "Hot Loop" of an animation system.

In a scene with $N$ markers updating at 60 Hz, the interpolation function is called $60 \\times N$ times per second. This function typically performs the following operations:

1. Retrieving two keyframes (tuples or objects).  
2. Calculating a normalized time factor $\\alpha$ (floating-point division).  
3. Interpolating position: $x \= x\_1 \+ (x\_2 \- x\_1) \\times \\alpha$.  
4. Interpolating rotation: $\\theta \= \\theta\_1 \+ (\\theta\_2 \- \\theta\_1) \\times \\alpha$.

In Python 3.11 or 3.12, each of these arithmetic operations triggers a dynamic dispatch mechanism. The interpreter checks the types of the operands, looks up the \_\_add\_\_ or \_\_mul\_\_ methods, and creates new temporary float objects for the results. This overhead is negligible for a single operation but accumulates disastrously across 100,000 iterations per second.1

The Python 3.13 JIT employs a "copy-and-patch" approach. It identifies traces of bytecode that are executed frequently (the hot traces). If the types in the interpolation function remain stable (e.g., always float), the JIT can compile these sequences into native machine code. This bypasses the standard evaluation loop. For the implementation of our AnimationBuffer, this implies that mathematical throughput for linear interpolation can increase significantly, potentially by factors of 2x to 9x for specific arithmetic-heavy workloads.1 This allows the Hybrid Model to perform complex math—such as easing curves or additive blending—in pure Python without dropping frames, removing the need to drop down to C++ extensions for the logic layer.

### **2.2 Concurrency and the GIL (PEP 703\)**

Real-time mapping applications rarely operate in isolation. They consume data from network sockets (UDP/TCP streams of track data), parse JSON or binary payloads, and update the internal state buffers. In previous versions of Python, the Global Interpreter Lock (GIL) enforced a rule that only one thread could execute Python bytecode at a time. A heavy burst of network traffic processing could block the main thread, causing the GUI animation to "stutter" or freeze momentarily.

Python 3.13 makes significant strides toward a "free-threaded" model.2 Even without running in the fully experimental free-threaded mode, the internal optimizations to lock handling reduce contention. This is pivotal for the Hybrid Model. The architecture demands a "Data Ingestion Thread" that continuously appends new keyframes to the buffers.

* **Thread A (Ingestion):** Receives data, parses it, and uses bisect.insort or append to update the buffer.  
* **Thread B (Main/GUI):** Runs the animation loop, querying the buffer.

With the improvements in Python 3.13, the contention between these threads is minimized. The Ingestion Thread can modify the buffer (protected by a fine-grained lock) without stalling the rendering loop running on the main thread. This ensures that the visualization remains fluid even when the system is under heavy data load.1

## **3\. The Data Layer: Efficient Buffer Architectures**

The "Buffer" in the Hybrid Model is the source of truth for the object's state. It must support two primary operations with extreme efficiency:

1. **Insertion:** Adding new real-time data points (typically at the end) or historical data (anywhere).  
2. **Query:** Finding the interval $\[t\_{start}, t\_{end}\]$ that encompasses the current simulation time $t\_{now}$.

The choice of data structure determines the algorithmic complexity of these operations and, consequently, the scalability of the system.

### **3.1 Algorithmic Analysis: bisect vs. sortedcontainers**

We must evaluate two primary candidates for the buffer implementation: the standard library bisect module and the third-party sortedcontainers library.

**Table 1: Comparative Analysis of Temporal Data Structures**

| Feature | Python list \+ bisect | sortedcontainers.SortedList | Relevance to Animation |
| :---- | :---- | :---- | :---- |
| **Lookup Complexity** | $O(\\log n)$ | $O(\\log n)$ | **Critical**. Both perform well for querying time intervals. |
| **Insertion Complexity** | $O(n)$ (Worst Case) | $O(\\log n)$ | Relevant for out-of-order data ingestion. |
| **Append Complexity** | $O(1)$ (Amortized) | $O(\\log n)$ | Relevant for real-time streaming (chronological). |
| **Memory Overhead** | Low (contiguous array pointers) | Higher (tree/tile overhead) | Affects cache locality during iteration. |
| **Implementation** | C-optimized (Standard Lib) | Pure Python (Highly Optimized) | bisect functions are native C in CPython. |
| **Dependencies** | None | Requires external package | bisect is built-in (Python 3.13). |

#### **3.1.1 The Argument for bisect (Standard Library)**

For the specific use case of an animation buffer, bisect is often the superior choice, primarily due to the nature of the data flow.6 In 90% of real-time mapping scenarios, data arrives in chronological order. We are simply appending (timestamp, position) tuples to the end of a list.

* Appending to a Python list is $O(1)$ amortized.  
* Querying uses bisect\_left or bisect\_right, which employs a binary search algorithm ($O(\\log n)$).6

The bisect module in Python 3.13 is highly optimized C code. It does not check for equality (which is unnecessary for finding intervals) and strictly performs less-than comparisons to locate the insertion point.6 This raw speed is beneficial when the "query" operation happens thousands of times per frame. Furthermore, using a standard list ensures better memory contiguity compared to the segmented lists used in sortedcontainers, potentially offering better CPU cache coherence for the JIT compiler.7

#### **3.1.2 The Argument for sortedcontainers**

The sortedcontainers library (specifically SortedDict or SortedList) maintains the list in sorted order automatically.9 This is advantageous if the application supports "Collaborative Editing" or "Late-Arriving Data," where timestamps might arrive out of sequence. Inserting an item into the middle of a standard list requires shifting all subsequent elements ($O(n)$), which causes a performance spike. sortedcontainers handles this in $O(\\log n)$ time.9

However, for the *rendering* loop—which is a read-only operation during the frame tick—the overhead of the SortedList internal structure can be slightly higher than a raw list binary search.7 Given that we can optimize the write path separately (e.g., by batching updates), the read-path optimization favors bisect.

### **3.2 Implementation Strategy: The Structure-of-Arrays (SoA)**

To maximize Python 3.13’s performance, we should avoid creating millions of small object instances (like Keyframe objects). Instead, we employ a **Structure-of-Arrays (SoA)** layout.

Python

class AnimationBuffer:  
    \_\_slots\_\_ \= ('\_timestamps', '\_x\_coords', '\_y\_coords', '\_rotations')

    def \_\_init\_\_(self):  
        \# Parallel lists  
        self.\_timestamps \=  \# List\[float\]  
        self.\_x\_coords \=    \# List\[float\]  
        self.\_y\_coords \=    \# List\[float\]  
        self.\_rotations \=   \# List\[float\]

    def insert(self, t, x, y, r):  
        \# Optimization: Check if strictly appending (common case)  
        if not self.\_timestamps or t \>= self.\_timestamps\[-1\]:  
            self.\_timestamps.append(t)  
            self.\_x\_coords.append(x)  
            self.\_y\_coords.append(y)  
            self.\_rotations.append(r)  
        else:  
            \# Fallback to bisect for out-of-order data  
            idx \= bisect.bisect\_right(self.\_timestamps, t)  
            self.\_timestamps.insert(idx, t)  
            self.\_x\_coords.insert(idx, x)  
            self.\_y\_coords.insert(idx, y)  
            self.\_rotations.insert(idx, r)

    def get\_state(self, t):  
        \# Binary search on the timestamp array  
        idx \= bisect.bisect\_right(self.\_timestamps, t)  
          
        \# Handle boundary conditions (start/end of buffer)  
        if idx \== 0:  
            return self.\_x\_coords, self.\_y\_coords, self.\_rotations  
        if idx \>= len(self.\_timestamps):  
            return self.\_x\_coords\[-1\], self.\_y\_coords\[-1\], self.\_rotations\[-1\]

        \# Interpolation Logic  
        t0, t1 \= self.\_timestamps\[idx-1\], self.\_timestamps\[idx\]  
        alpha \= (t \- t0) / (t1 \- t0)  
          
        \# Linear Interpolation (Inline for speed)  
        x \= self.\_x\_coords\[idx-1\] \+ (self.\_x\_coords\[idx\] \- self.\_x\_coords\[idx-1\]) \* alpha  
        y \= self.\_y\_coords\[idx-1\] \+ (self.\_y\_coords\[idx\] \- self.\_y\_coords\[idx-1\]) \* alpha  
          
        \# Rotation interpolation requires shortest-path logic  
        r0, r1 \= self.\_rotations\[idx-1\], self.\_rotations\[idx\]  
        diff \= r1 \- r0  
        \# Normalize to \-180 to \+180 range for shortest turn  
        while diff \<= \-180: diff \+= 360  
        while diff \> 180: diff \-= 360  
        r \= r0 \+ diff \* alpha  
          
        return x, y, r

This implementation leverages bisect\_right on a simple float list.6 The parallel arrays ensure that when the JIT compiles the get\_state method, it deals primarily with primitive float arrays, avoiding the pointer chasing overhead of iterating through a list of custom objects.

## **4\. The Rendering Architecture: PySide6 Graphics View Framework**

The visual realization of the data relies on the PySide6 (Qt 6\) Graphics View Framework. This is a retained-mode system, meaning the library maintains a scene graph of objects and handles the logic of what to draw and where.12

### **4.1 The Role of QGraphicsScene and BSP Trees**

The QGraphicsScene is the container for all map markers. It utilizes a Binary Space Partitioning (BSP) tree index to efficiently manage item locations.12 When the view asks "what is visible in this 1920x1080 viewport?", the scene traverses the BSP tree to find only the relevant items.

This indexing mechanism is crucial for the "Static" part of our Hybrid Model. The QGraphicsItem stores the static geometry (the bounding box and shape). When we update the item's position via the "Buffer" logic, we are effectively moving it within the BSP tree.  
Implication: Frequent movement requires frequent updates to the BSP tree. If 10,000 items move every frame, the cost of re-indexing the BSP tree becomes the bottleneck.  
Optimization: To mitigate this, items that move constantly can be flagged to bypass the index or use a more dynamic-friendly structure (like NoIndex), although for standard 2D maps, the BSP tree is usually robust enough provided the boundingRect calculations are correct.13

### **4.2 The "Ghosting" Phenomenon: Forensics and Mitigation**

A persistent issue in custom QGraphicsItem development is "ghosting"—visual artifacts left on the screen after an item moves. This manifests as streaks, partial icons, or lines remaining in the previously occupied space.16

#### **4.2.1 The Mechanics of Dirty Rects**

When an item changes position, QGraphicsScene performs a "damage" calculation:

1. It retrieves the item's *current* boundingRect() (mapped to scene coordinates).  
2. It applies the transformation to move the item.  
3. It retrieves the *new* boundingRect().  
4. It marks the union of these two rectangles as "dirty" in the viewport.  
5. It repaints only the dirty region.

Ghosting occurs when the item paints outside its declared boundingRect.  
If a marker is a 10x10 pixel circle, but has a 4-pixel thick outline, the actual drawn size is 14x14 (extending 2 pixels out on each side). If boundingRect() returns 10x10, the outer 2 pixels are effectively invisible to the damage system. When the circle moves, the scene does not know it needs to clear those outer pixels, leaving them behind as ghosts.16

#### **4.2.2 The Solution: Conservative Bounding and prepareGeometryChange**

To implement a robust MarkerView class, one must adhere to two rules:

1. **Include Pen Width:** The bounding rect must be padded by half the pen width.  
   Python  
   def boundingRect(self):  
       pen\_w \= self.pen().widthF()  
       radius \= self.radius  
       \# Pad by pen width/2 \+ small epsilon for antialiasing  
       margin \= pen\_w / 2.0 \+ 1.0   
       return QRectF(-radius \- margin, \-radius \- margin,  
                     2 \* (radius \+ margin), 2 \* (radius \+ margin))

2. **Signal Geometry Changes:** If any property changes that affects the size (e.g., increasing the radius or changing the pen width), you **must** call self.prepareGeometryChange() *before* changing the value.16  
   Python  
   def set\_radius(self, new\_radius):  
       if self.radius\!= new\_radius:  
           self.prepareGeometryChange() \# Notify scene to cache old bounds  
           self.radius \= new\_radius  
           self.update() \# Schedule repaint

In scenarios involving "Compound Items" (items with child items), ghosting can also occur if child items are deleted or moved without the parent's bounding rect updating. In the Hybrid Model, if we use child items for additive animation effects, the parent's bounding rect must encompass all possible positions of the oscillating child, or the parent must track the child's movement and update its geometry accordingly.17

### **4.3 Recursive Update Loops and ItemSendsGeometryChanges**

For advanced behaviors, such as collision avoidance or snapping to a grid, items may need to react to their own movement. The flag QGraphicsItem.ItemSendsGeometryChanges enables the itemChange() notification hook.18

**The Danger:** If itemChange modifies the position of the item (e.g., to snap it to a grid), it triggers itemChange again. This can lead to an infinite recursion depth error or a complete application freeze.19

**The Pattern:** Use the return value of itemChange to apply the correction, rather than calling setPos recursively.

Python

def itemChange(self, change, value):  
    if change \== QGraphicsItem.ItemPositionChange and self.scene():  
        new\_pos \= value  \# value is the QPointF proposed  
        if self.should\_snap:  
            \# Modify the proposed position  
            grid\_x \= round(new\_pos.x() / 10) \* 10  
            grid\_y \= round(new\_pos.y() / 10) \* 10  
            return QPointF(grid\_x, grid\_y)  
    return super().itemChange(change, value)

This intercepts the change before it is committed to the scene, preventing the recursive loop while achieving the desired constraint.20

## **5\. Mathematical Framework: Additive Blending**

While linear interpolation handles the movement from A to B, modern interfaces often require "Additive Animation Layers." This allows a marker to "breathe" (scale up and down), "shake" (trauma indication), or "bob" (hover effect) *while* moving along its path.21

### **5.1 The Concept of Additive Layers**

Standard animation replaces the state: $P\_{final} \= P\_{keyframe}$.  
Additive animation sums states: $P\_{final} \= P\_{base} \+ \\sum (P\_{layer} \\times W\_{layer})$.  
In a 2D Cartesian system, this is vector addition. However, in an object-oriented graphics system, we must decide *where* this addition happens.

### **5.2 The Scene Graph Approach**

The most robust implementation in PySide6 utilizes the parent-child hierarchy to separate these concerns, avoiding complex matrix math in the Python loop.17

**Structure:**

1. **The Base Carrier (QGraphicsItem):** This item represents the "True Position" derived from the Buffer. It moves linearly from A to B. It has no visual representation (or just a debug box).  
2. **The Offset Container (QGraphicsItem \- Child of Base):** This item applies the additive offsets. If the marker "shakes," this item's position oscillates around $(0,0)$.  
3. **The Visual (QGraphicsPixmapItem \- Child of Offset):** This holds the actual icon.

**Advantages:**

* **Separation of Concerns:** The Buffer logic only talks to the Base Carrier. The "Status Effect" logic only talks to the Offset Container. They do not need to know about each other.  
* **Interaction:** QGraphicsItem.shape() handles hit detection. If the Offset Container moves the visual child, the hit-box moves with it automatically because the transformation matrix propagates down the tree.

Mathematics of the "Shake" Layer:  
To implement a trauma shake:

$$\\Delta x(t) \= A \\cdot \\sin(\\omega t) \\cdot \\text{noise}(t)$$

$$\\Delta y(t) \= A \\cdot \\cos(\\omega t) \\cdot \\text{noise}(t \+ \\phi)$$  
This calculation is performed in the Python controller, and the result is applied to OffsetContainer.setPos(dx, dy). The JIT in Python 3.13 optimizes the trigonometric calls, ensuring this additional layer of math does not degrade frame rates.1

## **6\. MVC Implementation: The Scrubbing Pattern**

One of the most complex interactions in animation systems is "Scrubbing"—dragging a timeline slider to jump to a specific point in time. This stresses the data loading and rendering pipeline.24

### **6.1 The "Unsaved Changes" Dilemma**

Consider a user who pauses the simulation at $t=100$, selects a marker, and drags it to a new location (correcting a GPS error).

1. The Buffer says the marker is at $(x\_1, y\_1)$.  
2. The User moves it to $(x\_2, y\_2)$.  
3. The User scrubs the timeline to $t=105$.

If the system blindly interpolates from the buffer, the marker will jump back to the recorded track, destroying the user's edit. This is the "Unsaved Changes" problem.24

### **6.2 The "Override Layer" Solution**

To solve this, the Hybrid Model introduces an **Override Layer** in the Controller.

**Logic Flow:**

1. **Interaction:** User grabs marker. The Controller flags the marker as EDIT\_MODE.  
2. **Detachment:** The marker stops listening to the Animation Loop updates.  
3. **Recording:** The user's new position is stored in a temporary\_override variable in the MapEntity.  
4. **Scrubbing:** If the user scrubs *while* the marker is modified but unsaved, the system must decide:  
   * **Option A (Auto-Revert):** Discard changes and jump to the buffer state (Data Loss risk).  
   * **Option B (Ghosting):** Show the *actual* buffer position as a semi-transparent "Ghost" marker, while keeping the user's edited marker static at the new location (Visual Clutter).  
   * **Option C (Keyframe Insertion):** Interpret the move as a new keyframe at $t=100$. Re-sort the buffer immediately (sortedcontainers excels here).

**Recommendation:** For professional tools, **Option C** is preferred. The moment the user releases the mouse, insert (t=100, x=new, y=new) into the buffer. Because we use bisect (or SortedList), this insertion maintains the integrity of the animation curve. When the user subsequently scrubs, they see the marker move smoothly to their new point.24

## **7\. Comparison with Alternative Approaches**

It is instructive to compare this Hybrid Model against other common patterns to justify its complexity.

**Table 2: Architectural Comparison**

| Architecture | Description | Pros | Cons |
| :---- | :---- | :---- | :---- |
| **Immediate Mode** | Clear screen and redraw everything every frame (paintEvent). | Simple logic, no state synchronization issues. | **CPU Bound**. Python cannot iterate/draw 10k items at 60fps. No object interaction. |
| **QPropertyAnimation** | Use Qt's built-in animation framework for every item. | Easy to use, smooth interpolation. | **Memory Bloat**. Creating 10,000 QPropertyAnimation objects (each with timers) kills performance. |
| **Pure Python Logic** | Calculate pixels in Python, push QImage to screen. | Total control. | **Slow**. Python is not a rasterizer. JIT helps, but not enough for pixel blitting. |
| **Hybrid Static/Buffer** | **Python calculates state, Qt manages items.** | **Best of both**. Efficient math (Python), hardware accel rendering (Qt). | Higher architectural complexity (MVC separation). |

The Hybrid Static/Buffer model is the only viable option for high-entity-count scenarios (1,000+ objects) in Python. It leverages the "Thin Controller, Fat View" paradigm where the heavy lifting of rendering is done by C++ (Qt), while the intelligent logic of *where things are* remains in Python.12

## **8\. Conclusion**

The implementation of a Hybrid Static/Buffer Animation Model represents the convergence of modern Python performance capabilities with established computer graphics principles. By utilizing **Python 3.13**, developers can finally execute dense arithmetic interpolation loops in real-time without the traditional overhead of the interpreter, thanks to the experimental JIT and improved locking mechanisms.

The architecture relies on a strict separation of concerns:

1. **The Buffer:** Efficient, binary-searchable arrays (bisect or sortedcontainers) that store the temporal truth.  
2. **The View:** A retained-mode QGraphicsScene that manages the visual artifacts, utilizing QGraphicsItem hierarchies to implement additive blending without matrix complexity.  
3. **The Controller:** A synchronized driver that bridges the two, handling the intricacies of timeline scrubbing and state management.

Crucially, the success of this model depends on handling the "edge cases" of graphics programming: preventing ghosting through conservative boundingRect implementations, avoiding recursive event loops with ItemSendsGeometryChanges guards, and managing the user's interaction with the data through robust MVC patterns. When executed correctly, this model allows Python—a language often dismissed for real-time graphics—to power industrial-grade visualization systems capable of rendering thousands of dynamic entities with fluid, artifact-free motion.

#### **Works cited**

1. Why You Should Upgrade to Python 3.13 \- Medium, accessed on January 7, 2026, [https://medium.com/@backendbyeli/why-you-should-upgrade-to-python-3-13-70699aafa538](https://medium.com/@backendbyeli/why-you-should-upgrade-to-python-3-13-70699aafa538)  
2. What's New In Python 3.13 — Python 3.14.2 documentation, accessed on January 7, 2026, [https://docs.python.org/3/whatsnew/3.13.html](https://docs.python.org/3/whatsnew/3.13.html)  
3. How does Python 3.13 perform vs 3.11 in single-threaded mode? \- Reddit, accessed on January 7, 2026, [https://www.reddit.com/r/Python/comments/1k8zcdi/how\_does\_python\_313\_perform\_vs\_311\_in/](https://www.reddit.com/r/Python/comments/1k8zcdi/how_does_python_313_perform_vs_311_in/)  
4. Python 3.13.0 speed \- Core Development, accessed on January 7, 2026, [https://discuss.python.org/t/python-3-13-0-speed/79547](https://discuss.python.org/t/python-3-13-0-speed/79547)  
5. Python 3.13: Blazing New Trails in Performance and Scale, accessed on January 7, 2026, [https://thenewstack.io/python-3-13-blazing-new-trails-in-performance-and-scale/](https://thenewstack.io/python-3-13-blazing-new-trails-in-performance-and-scale/)  
6. bisect — Array bisection algorithm — Python 3.14.2 documentation, accessed on January 7, 2026, [https://docs.python.org/3/library/bisect.html](https://docs.python.org/3/library/bisect.html)  
7. Tip \- Use Python Builtin Binary Search (Bisect) on Sorted List : r/pythontips \- Reddit, accessed on January 7, 2026, [https://www.reddit.com/r/pythontips/comments/10ukodx/tip\_use\_python\_builtin\_binary\_search\_bisect\_on/](https://www.reddit.com/r/pythontips/comments/10ukodx/tip_use_python_builtin_binary_search_bisect_on/)  
8. Check where a value lies within a sorted list \- python \- Stack Overflow, accessed on January 7, 2026, [https://stackoverflow.com/questions/77023994/check-where-a-value-lies-within-a-sorted-list](https://stackoverflow.com/questions/77023994/check-where-a-value-lies-within-a-sorted-list)  
9. Comparing Sorted Containers in Python | by Solomon Bothwell | Medium, accessed on January 7, 2026, [https://medium.com/@ssbothwell/comparing-sorted-containers-in-python-a2c41624bc84](https://medium.com/@ssbothwell/comparing-sorted-containers-in-python-a2c41624bc84)  
10. Python most efficient way to keep sorted data \- Stack Overflow, accessed on January 7, 2026, [https://stackoverflow.com/questions/63679964/python-most-efficient-way-to-keep-sorted-data](https://stackoverflow.com/questions/63679964/python-most-efficient-way-to-keep-sorted-data)  
11. Why are there no sorted containers in Python's standard libraries? \- Stack Overflow, accessed on January 7, 2026, [https://stackoverflow.com/questions/5953205/why-are-there-no-sorted-containers-in-pythons-standard-libraries](https://stackoverflow.com/questions/5953205/why-are-there-no-sorted-containers-in-pythons-standard-libraries)  
12. QGraphics vector graphics interfaces with Python and PySide6, accessed on January 7, 2026, [https://www.pythonguis.com/tutorials/pyside6-qgraphics-vector-graphics/](https://www.pythonguis.com/tutorials/pyside6-qgraphics-vector-graphics/)  
13. Graphics View Framework \- Qt for Python, accessed on January 7, 2026, [https://doc.qt.io/qtforpython-6/overviews/qtwidgets-graphicsview.html](https://doc.qt.io/qtforpython-6/overviews/qtwidgets-graphicsview.html)  
14. QT 4.6.3 bug? QGraphicsItem receives paint even when removed from scene?\! \- Qt Centre, accessed on January 7, 2026, [https://www.qtcentre.org/threads/33730-QT-4-6-3-bug-QGraphicsItem-receives-paint-even-when-removed-from-scene-\!](https://www.qtcentre.org/threads/33730-QT-4-6-3-bug-QGraphicsItem-receives-paint-even-when-removed-from-scene-!)  
15. PySide6.QtWidgets.QGraphicsScene \- Qt for Python, accessed on January 7, 2026, [https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QGraphicsScene.html](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QGraphicsScene.html)  
16. How to remove Ghost Lines drawn in qgraphicsview \- Stack Overflow, accessed on January 7, 2026, [https://stackoverflow.com/questions/40857892/how-to-remove-ghost-lines-drawn-in-qgraphicsview](https://stackoverflow.com/questions/40857892/how-to-remove-ghost-lines-drawn-in-qgraphicsview)  
17. Compound QGraphicsItem object sometimes remains as a "ghost" after deletion, occasionally will crash Python | Qt Forum, accessed on January 7, 2026, [https://forum.qt.io/topic/162768/compound-qgraphicsitem-object-sometimes-remains-as-a-ghost-after-deletion-occasionally-will-crash-python](https://forum.qt.io/topic/162768/compound-qgraphicsitem-object-sometimes-remains-as-a-ghost-after-deletion-occasionally-will-crash-python)  
18. PySide6.QtWidgets.QGraphicsItem \- Qt for Python, accessed on January 7, 2026, [https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QGraphicsItem.html](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QGraphicsItem.html)  
19. Preeventing QGraphicsItem's itemChanged \- python \- Stack Overflow, accessed on January 7, 2026, [https://stackoverflow.com/questions/46848408/preeventing-qgraphicsitems-itemchanged](https://stackoverflow.com/questions/46848408/preeventing-qgraphicsitems-itemchanged)  
20. \[Moved\] QGraphicsItem::itemChange not called | Qt Forum, accessed on January 7, 2026, [https://forum.qt.io/topic/11895/moved-qgraphicsitem-itemchange-not-called](https://forum.qt.io/topic/11895/moved-qgraphicsitem-itemchange-not-called)  
21. Additive blending \- ozz-animation, accessed on January 7, 2026, [https://guillaumeblanc.github.io/ozz-animation/samples/additive/](https://guillaumeblanc.github.io/ozz-animation/samples/additive/)  
22. Animation Tech Intro Part 3: Blending \- Anim Coding, accessed on January 7, 2026, [https://animcoding.com/post/animation-tech-intro-part-3-blending/](https://animcoding.com/post/animation-tech-intro-part-3-blending/)  
23. Can someone who is smarter than me explain exactly how apply additives works in character animation? : r/unrealengine \- Reddit, accessed on January 7, 2026, [https://www.reddit.com/r/unrealengine/comments/k23xyg/can\_someone\_who\_is\_smarter\_than\_me\_explain/](https://www.reddit.com/r/unrealengine/comments/k23xyg/can_someone_who_is_smarter_than_me_explain/)  
24. Notify user of unsaved changes across fields of different types \- Stack Overflow, accessed on January 7, 2026, [https://stackoverflow.com/questions/70151930/notify-user-of-unsaved-changes-across-fields-of-different-types](https://stackoverflow.com/questions/70151930/notify-user-of-unsaved-changes-across-fields-of-different-types)  
25. QTreeView animation updates, data updates, layout updates \- definitive correct way and performance | Qt Forum, accessed on January 7, 2026, [https://forum.qt.io/topic/135712/qtreeview-animation-updates-data-updates-layout-updates-definitive-correct-way-and-performance](https://forum.qt.io/topic/135712/qtreeview-animation-updates-data-updates-layout-updates-definitive-correct-way-and-performance)  
26. Warning users that unsaved changes will be lost \- Stack Overflow, accessed on January 7, 2026, [https://stackoverflow.com/questions/32294414/warning-users-that-unsaved-changes-will-be-lost](https://stackoverflow.com/questions/32294414/warning-users-that-unsaved-changes-will-be-lost)