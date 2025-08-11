from pwdlib import PasswordHash

pwd_content = PasswordHash.recommended()


def get_password_hash(password: str):
    return pwd_content.hash(password)


def verifry_password_hash(plain_password: str, hashed_password: str):
    return pwd_content.verify(plain_password, hashed_password)
