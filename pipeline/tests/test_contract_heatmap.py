import pytest
from pydantic import ValidationError

from statsboteval_pipeline.contract import HeatmapCell, HeatmapGrid, ok


def full_cells() -> list[HeatmapCell]:
    return [HeatmapCell(dow=d, hour=h, cell=ok((d * h) % 5)) for d in range(1, 8) for h in range(24)]


def test_dense_grid_parses() -> None:
    assert len(HeatmapGrid(cells=full_cells()).cells) == 168


def test_missing_cell_rejected() -> None:
    with pytest.raises(ValidationError):
        HeatmapGrid(cells=full_cells()[:-1])


def test_duplicate_cell_rejected() -> None:
    cells = full_cells()[:-1] + [HeatmapCell(dow=1, hour=0, cell=ok(1))]
    with pytest.raises(ValidationError):
        HeatmapGrid(cells=cells)


def test_dow_hour_bounds() -> None:
    with pytest.raises(ValidationError):
        HeatmapCell(dow=0, hour=0, cell=ok(1))
    with pytest.raises(ValidationError):
        HeatmapCell(dow=1, hour=24, cell=ok(1))
