from fastapi import FastAPI

from routers import (
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

app = FastAPI(title="Forno di Resistenza API")

app.include_router(auth.router)
app.include_router(produto.router)
app.include_router(combo.router)
app.include_router(categoria_produto.router)
app.include_router(metodo_pagamento.router)
app.include_router(clientes.router)
app.include_router(mesa.router)
app.include_router(codigo_promocional.router)
app.include_router(funcionario.router)
app.include_router(comanda.router)
