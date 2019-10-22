# Copyright 2019 The Cirq Developers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import List, TYPE_CHECKING, Callable, Optional, Iterator, cast, \
    Iterable, TypeVar

from cirq import circuits
from cirq.contrib.quirk.cells.cell import Cell

if TYPE_CHECKING:
    import cirq

class CompositeCell(Cell):
    """A cell made up of a grid of sub-cells.

    This is used for custom circuit gates.
    """

    def __init__(self,
                 height: int,
                 sub_cell_cols_generator: Iterable[List[Optional[Cell]]],
                 *,
                 weight: int):
        self.height = height
        self._sub_cell_cols_generator = sub_cell_cols_generator
        self._weight = weight
        if weight <= 0:
            self._sub_cell_cols_generator = []

    def gate_count(self) -> int:
        return self._weight

    def _transform_cells(self, func: Callable[[Cell], Cell]) -> 'CompositeCell':
        return CompositeCell(
            height=self.height,
            # It is important that this is a generator instead of a list!
            # We must not list until after global operation counting.
            sub_cell_cols_generator=_iterator_to_iterable(
                [None if cell is None else func(cell)
                 for cell in col]
                for col in self._sub_cell_cols_generator
            ),
            weight=self._weight)

    def _sub_cell_cols_sealed(self) -> List[List[Cell]]:
        if not isinstance(self._sub_cell_cols_generator, list):
            self._sub_cell_cols_generator = list(self._sub_cell_cols_generator)
        return cast(List[List[Cell]], self._sub_cell_cols_generator)

    def with_qubits(self, qubits: List['cirq.Qid']) -> 'Cell':
        return self._transform_cells(lambda cell: cell.with_qubits(qubits))

    def with_input(self, letter, register):
        return self._transform_cells(lambda cell: cell.with_input(
            letter, register))

    def controlled_by(self, qubit):
        return self._transform_cells(lambda cell: cell.controlled_by(qubit))

    def circuit(self) -> 'cirq.Circuit':
        result = circuits.Circuit()
        for col in self._sub_cell_cols_sealed():
            body = circuits.Circuit(
                cell.operations() for cell in col if cell is not None)
            if body:
                basis_change = circuits.Circuit(
                    cell.basis_change() for cell in col if cell is not None)
                result += basis_change
                result += body
                result += basis_change**-1
        return result

    def operations(self) -> 'cirq.OP_TREE':
        return self.circuit()


T = TypeVar('T')


def _iterator_to_iterable(iterator: Iterator[T]) -> Iterable[T]:
    done = False
    items = []

    class IterIntoItems:
        def __iter__(self):
            nonlocal done
            i = 0
            while True:
                if i == len(items) and not done:
                    try:
                        items.append(next(iterator))
                    except StopIteration:
                        done = True
                if i < len(items):
                    yield items[i]
                    i += 1
                elif done:
                    break

    return IterIntoItems()
