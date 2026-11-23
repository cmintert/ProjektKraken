"""Renderer-side gestures, stable layout, and saved-result highlights."""

GRAPH_INTERACTION = """
document.addEventListener("DOMContentLoaded", () => {
    new QWebChannel(qt.webChannelTransport, channel => {
        const bridge = channel.objects.bridge;
        const generation = window.__krakenGraphGeneration;
        const graph = document.getElementById("mynetwork");
        if (!graph || typeof network === "undefined") return;

        const positions = Object.assign(Object.create(null), %POSITIONS%);
        let focusId = %FOCUS_ID%;
        let viewState = %VIEW_STATE%;
        let hovered = null;
        let gesture = null;
        let highlighted = [];
        let layoutRevision = 0;
        const handle = document.createElement("button");
        handle.className = "graph-connect-handle";
        handle.textContent = "+";
        handle.title = "Drag to connect";
        handle.setAttribute("aria-label", "Start a connection");
        handle.tabIndex = -1;
        handle.hidden = true;
        graph.appendChild(handle);
        const empty = document.createElement("div");
        empty.className = "message";
        empty.hidden = true;
        const emptyCaption = document.createElement("h2");
        emptyCaption.textContent = "No items match the current graph view.";
        empty.appendChild(emptyCaption);
        graph.appendChild(empty);
        const nodeData = () => network.body.data.nodes;
        const edgeData = () => network.body.data.edges;

        function reportView() {
            Object.assign(positions, network.getPositions());
            bridge.viewStateChanged({
                generation, positions: network.getPositions(),
                scale: network.getScale(), position: network.getViewPosition()
            });
        }

        function placeHandle() {
            const id = gesture?.source ?? hovered ?? network.getSelectedNodes()[0];
            handle.hidden = id == null || !nodeData().get(id);
            if (handle.hidden) return;
            handle.dataset.source = String(id);
            const box = network.getBoundingBox(id);
            const point = network.canvasToDOM({
                x: box.right, y: (box.top + box.bottom) / 2
            });
            handle.style.left = point.x + "px";
            handle.style.top = point.y + "px";
        }

        function pointer(event) {
            const bounds = graph.getBoundingClientRect();
            return {x: event.clientX - bounds.left, y: event.clientY - bounds.top};
        }
        function setPointerGesture(event) {
            if (event.button !== 0 || handle.hidden) return;
            event.stopPropagation();
            event.preventDefault();
            const source = handle.dataset.source;
            const node = nodeData().get(source);
            if (!node) return;
            handle.focus({preventScroll: true});
            handle.setPointerCapture(event.pointerId);
            gesture = {source, sourceKind: node.object_type,
                       start: pointer(event), end: pointer(event)};
        }
        function updatePointerGesture(event) {
            if (!gesture) return;
            event.stopPropagation();
            gesture.end = pointer(event);
            network.redraw();
        }
        function cancelPointerGesture() {
            gesture = null;
            network.redraw();
        }
        function finishPointerGesture(event) {
            if (!gesture || !handle.hasPointerCapture(event.pointerId)) return;
            event.stopPropagation();
            const drop = pointer(event);
            const {source, sourceKind, start} = gesture;
            cancelPointerGesture();
            if (Math.hypot(drop.x - start.x, drop.y - start.y) < 4) return;
            const target = network.getNodeAt(drop);
            if (String(target) === source) return;
            bridge.connectionRequested({
                generation, source, source_kind: sourceKind,
                target: target == null ? "" : String(target),
                position: network.DOMtoCanvas(drop)
            });
        }
        handle.addEventListener("pointerdown", setPointerGesture);
        handle.addEventListener("pointermove", updatePointerGesture);
        handle.addEventListener("pointerup", finishPointerGesture);
        handle.addEventListener("lostpointercapture", cancelPointerGesture);
        handle.addEventListener("click", event => event.stopPropagation());
        graph.addEventListener("keydown", event => {
            if (event.key === "Escape" && gesture) {
                event.stopPropagation();
                event.preventDefault();
                cancelPointerGesture();
            }
        });
        network.on("hoverNode", event => {
            hovered = event.node;
            placeHandle();
        });
        network.on("click", event => {
            const node = event.nodes.length ? nodeData().get(event.nodes[0]) : null;
            if (node) bridge.nodeClicked(node.object_type, String(node.id));
            else bridge.backgroundClicked(generation);
        });
        graph.addEventListener("pointermove", event => {
            if (gesture || event.target === handle) return;
            const node = network.getNodeAt(pointer(event));
            if (node == null && !handle.hidden) {
                const bounds = handle.getBoundingClientRect();
                const near = event.clientX >= bounds.left - 14 &&
                    event.clientX <= bounds.right + 14 &&
                    event.clientY >= bounds.top - 14 &&
                    event.clientY <= bounds.bottom + 14;
                if (near) return;
            }
            hovered = node;
            placeHandle();
        });
        graph.addEventListener("pointerleave", () => {
            hovered = null;
            placeHandle();
        });
        network.on("afterDrawing", context => {
            placeHandle();
            if (gesture) {
                const start = network.DOMtoCanvas(gesture.start);
                const end = network.DOMtoCanvas(gesture.end);
                context.save();
                context.beginPath();
                context.strokeStyle = getComputedStyle(graph)
                    .getPropertyValue("--graph-focus");
                context.lineWidth = 2 / network.getScale();
                context.moveTo(start.x, start.y);
                context.lineTo(end.x, end.y);
                context.stroke();
                context.restore();
            }
        });

        function freezeLayout() {
            network.stopSimulation();
            network.setOptions({physics: {enabled: false}});
            reportView();
        }
        function settleLayout(onSettled) {
            const revision = ++layoutRevision;
            const finish = () => {
                if (revision !== layoutRevision) return;
                ++layoutRevision;
                freezeLayout();
                if (onSettled) onSettled();
            };
            network.once("stabilized", finish);
            setTimeout(finish, 1500);
        }

        window.relayoutGraph = () => {
            network.setOptions({physics: {enabled: true}});
            settleLayout();
            network.stabilize();
        };
        window.highlightGraphRelations = ids => {
            highlighted = ids;
            network.setSelection({
                nodes: network.getSelectedNodes(),
                edges: ids.filter(id => edgeData().get(id))
            }, {highlightEdges: false});
        };
        window.updateGraph = (newNodes, newEdges, newFocusId) => {
            ++layoutRevision;
            freezeLayout();
            const selected = network.getSelectedNodes();
            const center = positions[newFocusId] ?? network.getViewPosition();
            const nodeIds = new Set(newNodes.map(node => node.id));
            empty.hidden = nodeIds.size > 0;
            const edgeIds = new Set(newEdges.map(edge => edge.id));
            edgeData().remove(edgeData().getIds().filter(id => !edgeIds.has(id)));
            nodeData().remove(nodeData().getIds().filter(id => !nodeIds.has(id)));
            let added = 0;
            nodeData().update(newNodes.map(node => {
                const position = positions[node.id] ??
                    (Number.isFinite(node.x) && Number.isFinite(node.y)
                        ? {x: node.x, y: node.y}
                        : {x: center.x + 48 + 28 * (added % 5),
                           y: center.y + 48 + 28 * Math.floor(added++ / 5)});
                return Object.assign({}, node, position);
            }));
            edgeData().update(newEdges);
            if (newFocusId !== focusId && nodeIds.has(newFocusId)) {
                network.selectNodes([newFocusId]);
            } else {
                network.selectNodes(selected.filter(id => nodeIds.has(id)));
            }
            focusId = newFocusId;
            window.highlightGraphRelations(highlighted);
            reportView();
        };

        network.on("dragEnd", reportView);
        let cameraUpdate;
        network.on("zoom", () => {
            clearTimeout(cameraUpdate);
            cameraUpdate = setTimeout(reportView, 160);
        });
        network.on("animationFinished", reportView);
        if (viewState) {
            network.moveTo({
                position: viewState.position, scale: viewState.scale, animation: false
            });
        }
        settleLayout(() => {
            if (focusId && nodeData().get(focusId)) {
                network.selectNodes([focusId]);
                if (!viewState) network.focus(focusId, {scale: 1, animation: false});
            }
            reportView();
        });
        bridge.rendererReady(generation);
    });
});
"""
