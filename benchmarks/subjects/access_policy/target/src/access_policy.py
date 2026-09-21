def can_edit(role: str, owner: bool, locked: bool) -> bool:
    if locked:
        return False
    return role == "admin" or (role == "editor" and owner)
