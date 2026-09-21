import pytest
from src.pagination import page_slice
@pytest.mark.parametrize("args, expected", [((0,1,3),(0,0)),((10,1,3),(0,3)),((10,2,3),(3,6)),((10,4,3),(9,10)),((10,5,3),(10,10)),((1,1,1),(0,1))])
def test_pages(args, expected):
    assert page_slice(*args) == expected
@pytest.mark.parametrize("args", [(-1,1,1),(1,0,1),(1,1,0)])
def test_invalid(args):
    with pytest.raises(ValueError): page_slice(*args)
