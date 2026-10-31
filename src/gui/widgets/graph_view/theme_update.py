"""Renderer-only graph recoloring; do not trigger data/layout notifications."""

import json
from typing import Any


def theme_update_script(
    theme: dict[str, str],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    generation: int,
    revision: int | None = None,
) -> str:
    """Build a readiness-checked operation that leaves graph physics untouched.

    Vis DataSet.update emits data-change notifications that restart physics.
    Recolor the existing renderer objects instead, using their setOptions API.
    Subsequent ordinary data updates are prepared from the current theme as usual.
    """
    payload = json.dumps({"theme": theme, "nodes": nodes, "edges": edges})
    script = """(() => {
        if (window.__krakenGraphGeneration !== %GENERATION%) return false;
        if (document.readyState !== 'complete') return false;
        const graph = document.getElementById('mynetwork');
        if (graph && (typeof network === 'undefined' || !window.updateGraph))
            return false;
        const payload = %PAYLOAD%;
        document.querySelectorAll('html, body, .card, .card-body, #mynetwork')
            .forEach(element => {
                element.style.backgroundColor = payload.theme.background_color;
                element.style.color = payload.theme.text_color;
            });
        document.querySelectorAll('.message h2').forEach(element => {
            element.style.color = payload.theme.text_color;
        });
        if (graph) {
            payload.nodes.forEach(node => {
                const rendered = network.body.nodes[node.id];
                if (rendered) {
                    const options = {color: node.color,
                                     font: {color: payload.theme.text_color}};
                    if (node.image) options.image = node.image;
                    rendered.setOptions(options);
                }
            });
            payload.edges.forEach(edge => {
                const rendered = network.body.edges[edge.id];
                if (rendered) rendered.setOptions({color: edge.color,
                    font: {color: payload.theme.text_color}});
            });
            network.redraw();
        }
        %FRAME%
        return true;
    })()"""
    frame = ""
    if revision is not None:
        frame = f"""
        window.__krakenGraphThemeRevision = {revision};
        window.__krakenGraphThemePainted = -1;
        requestAnimationFrame(() => requestAnimationFrame(() => {{
            if (window.__krakenGraphThemeRevision === {revision} &&
                window.__krakenGraphGeneration === {generation})
                window.__krakenGraphThemePainted = {revision};
        }}));"""
    # Insert authored data last: a label containing our internal placeholders
    # must never be rewritten as JavaScript or lose its exact text.
    return (
        script.replace("%GENERATION%", str(generation))
        .replace("%FRAME%", frame)
        .replace("%PAYLOAD%", payload)
    )


def theme_frame_script(generation: int, revision: int) -> str:
    """Acknowledge a frame for this exact page and theme, never an older callback."""
    return (
        f"Boolean(window.__krakenGraphGeneration === {generation} && "
        f"window.__krakenGraphThemePainted === {revision})"
    )
