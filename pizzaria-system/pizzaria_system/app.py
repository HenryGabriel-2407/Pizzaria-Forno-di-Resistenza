from fastapi import FastAPI
from routers import produto, combo, categoria_produto, metodo_pagamento

app = FastAPI(title="Forno di Resistenza API")

app.include_router(produto.router)
app.include_router(combo.router)
app.include_router(categoria_produto.router)
app.include_router(metodo_pagamento.router)
