from collections import deque
from statistics import mean

class TimeSerie:
    def __init__(self, size: int):
        self._elements = deque()
        self._size = size

    def enqueue(self, element):
        self._elements.append(element)
        toobig = len(self._elements)
        while toobig > self._size:
            self.dequeue()
            toobig = len(self._elements)

    def dequeue(self):
        return self._elements.popleft()

    def _fun(self, func):
        if len(self._elements) > 0:
            e = self._elements[0]
            return [func([v[i] for v in self._elements]) for i in range(len(e))]
        return None

    def max(self):
        return self._fun(max)

    def min(self):
        return self._fun(min)

    def average(self):
        return self._fun(mean)

# a = TimeSerie(2)
# a.enqueue((1, 2, 3))
# a.enqueue((4, 5, 6))
# print(a.average())