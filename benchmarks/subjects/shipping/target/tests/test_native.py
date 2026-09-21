import pytest
from src.shipping import shipping_charge
@pytest.mark.parametrize("args, expected", [((1,0),400),((1000,4999),400),((1001,4999),700),((1001,5000),0),((1,5001),0)])
def test_charge(args, expected):
    assert shipping_charge(*args) == expected
@pytest.mark.parametrize("args", [(0,6000),(-1,0),(1,-1)])
def test_invalid(args):
    with pytest.raises(ValueError): shipping_charge(*args)
