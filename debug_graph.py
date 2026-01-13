import logging
import os
import sys

# Setup logging
logging.basicConfig(level=logging.INFO)

# Add project root to sys.path
sys.path.insert(0, os.getcwd())

from src.gui.widgets.graph_view.graph_builder import GraphBuilder


def main():
    print("Generating Graph HTML...")
    builder = GraphBuilder()

    nodes = [{"id": "1", "name": "Node 1", "object_type": "entity"}]
    edges = []

    html = builder.build_html(nodes, edges)

    with open("debug_graph.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"HTML generated. Size: {len(html)}")

    if "unpkg.com" in html:
        print("WARNING: unpkg.com still present in HTML")

    if "vis-network.min.js" in html:
        # This check is weak because the content is embedded, not the filename
        pass

    # Check for the embedded script start
    if (
        '<script type="text/javascript">/**!' in html
        or "<script type='text/javascript'>/**!" in html
    ):
        print("Found embedded script signature (approx)")
    else:
        print("Could not easy find embedded script signature")


if __name__ == "__main__":
    main()
