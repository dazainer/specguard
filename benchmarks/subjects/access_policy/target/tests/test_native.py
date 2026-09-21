import pytest
from src.access_policy import can_edit
@pytest.mark.parametrize("role,owner,locked,expected", [("admin",False,False,True),("admin",True,True,False),("editor",True,False,True),("editor",False,False,False),("editor",True,True,False),("viewer",True,False,False),("Admin",True,False,False),("",False,False,False)])
def test_policy(role,owner,locked,expected):
    assert can_edit(role,owner,locked) is expected
