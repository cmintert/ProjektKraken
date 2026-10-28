"""Collapse exact affine aliases before running temporal shortest paths."""

from __future__ import annotations

from fractions import Fraction


class AffineAliases:
    """Weighted union-find: node time equals root time plus its displacement."""

    def __init__(self, nodes: tuple[str, ...]) -> None:
        """Initialize independent variables without recursion-depth limits."""
        self.parent = {node: node for node in nodes}
        self.offset = dict.fromkeys(nodes, Fraction(0))

    def find(self, node: str) -> tuple[str, Fraction]:
        """Compress a path while retaining lossless day displacements."""
        path = []
        current = node
        amount = Fraction(0)
        while self.parent[current] != current:
            path.append((current, amount))
            amount += self.offset[current]
            current = self.parent[current]
        for item, before in path:
            self.parent[item] = current
            self.offset[item] = amount - before
        return current, amount

    def join(self, source: str, target: str, amount: Fraction) -> bool:
        """Assert target-source=amount, returning False for inconsistent aliases."""
        first, left = self.find(source)
        second, right = self.find(target)
        if first == second:
            return right - left == amount
        displacement = amount + left - right
        if second == "@origin" or (first != "@origin" and second < first):
            self.parent[first] = second
            self.offset[first] = -displacement
        else:
            self.parent[second] = first
            self.offset[second] = displacement
        return True
