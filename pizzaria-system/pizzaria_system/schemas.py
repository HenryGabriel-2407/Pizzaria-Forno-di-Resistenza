from pydantic import BaseModel, EmailStr


class Create_User(BaseModel):
    nome: str
    email: EmailStr
    senha: str
    telefone: str
    endereco_num_residencia: str
    endereco_rua: str
    endereco_bairro: str
    endereco_cidade: str
    endereco_complemento: str


class User_Public(BaseModel):
    id: int
    nome: str
    email: EmailStr
    telefone: str
    endereco_num_residencia: str
    endereco_rua: str
    endereco_bairro: str
    endereco_cidade: str
    endereco_complemento: str


class List_User(BaseModel):
    list_users: list[User_Public]
