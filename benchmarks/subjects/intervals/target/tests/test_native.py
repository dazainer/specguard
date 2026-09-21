import pytest
from src.intervals import overlap_length
@pytest.mark.parametrize("args, expected", [((0,5,2,8),3),((2,8,0,5),3),((0,5,5,9),0),((0,2,3,4),0),((0,0,0,3),0),((-5,3,-2,1),3),((0,10,2,3),1)])
def test_overlap(args, expected):
    assert overlap_length(*args) == expected
@pytest.mark.parametrize("args", [(2,1,0,3),(0,3,2,1)])
def test_reversed(args):
    with pytest.raises(ValueError): overlap_length(*args)
