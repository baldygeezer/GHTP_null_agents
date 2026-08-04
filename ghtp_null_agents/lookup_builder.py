





def extract_login(usr: dict):
    if not isinstance(usr, dict):
        return None
    if usr.get("__typename") == "Bot":
        return None
    return usr.get("login")

class LookupBuilder:
    pass