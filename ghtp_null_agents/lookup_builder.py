





def extract_login(usr: dict):
    if not isinstance(usr, dict):
        return None
    return usr.get("login")

