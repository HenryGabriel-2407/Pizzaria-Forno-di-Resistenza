from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from pizzaria_system.database import engine
from pizzaria_system.seeds import criar_primeiro_admin

# Importa os routers
from routers import (
    auditoria,
    auth,
    categoria_produto,
    clientes,
    codigo_promocional,
    comanda,
    combo,
    funcionario,
    mesa,
    metodo_pagamento,
    produto,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    with Session(engine) as session:
        criar_primeiro_admin(session)
    yield


app = FastAPI(title="Forno di Resistenza API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro dos routers
app.include_router(auth.router)
app.include_router(produto.router)
app.include_router(combo.router)
app.include_router(categoria_produto.router)
app.include_router(metodo_pagamento.router)
app.include_router(clientes.router)
app.include_router(mesa.router)
app.include_router(codigo_promocional.router)
app.include_router(funcionario.router)
app.include_router(auditoria.router)
app.include_router(comanda.router)
