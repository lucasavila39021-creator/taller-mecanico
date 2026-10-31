import bcrypt


def hashear_password(password: str, costo: int) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=costo)).decode()
