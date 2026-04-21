from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, EmailStr, ConfigDict


# ==================================================================
# Schemas para CategoriaProduto
# ==================================================================

class CategoriaProdutoBase(BaseModel):
    nome: str = Field(..., max_length=100)


class CategoriaProdutoCreate(CategoriaProdutoBase):
    pass


class CategoriaProdutoResponse(CategoriaProdutoBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class CategoriaProdutoUpdate(BaseModel):
    nome: Optional[str] = Field(None, max_length=100)

# ==================================================================
# Schemas para MetodoPagamento (complemento)
# ==================================================================

class MetodoPagamentoCreate(BaseModel):
    nome: str = Field(..., max_length=50)
    ativo: bool = True


class MetodoPagamentoUpdate(BaseModel):
    nome: Optional[str] = Field(None, max_length=50)
    ativo: Optional[bool] = None


class MetodoPagamentoResponse(BaseModel):
    id: int
    nome: str
    ativo: bool

    model_config = ConfigDict(from_attributes=True)


# ==================================================================
# Schemas para Produto
# ==================================================================

class ProdutoBase(BaseModel):
    nome: str = Field(..., max_length=200)
    descricao: str
    imagem_link: str
    preco: float = Field(..., gt=0)
    id_categoria: int
    popular: bool = False
    disponivel: bool = True
    tempo_preparo_medio: Optional[int] = Field(None, ge=0, description="minutos")


class ProdutoCreate(ProdutoBase):
    pass


class ProdutoResponse(ProdutoBase):
    id: int
    categoria_rel: Optional[CategoriaProdutoResponse] = None
    # Se quiser incluir combos (evitar loop), pode ser uma lista de ComboResume
    combos: Optional[List['ComboResume']] = None

    model_config = ConfigDict(from_attributes=True)

class ProdutoUpdate(BaseModel):
    nome: Optional[str] = Field(None, max_length=200)
    descricao: Optional[str] = None
    imagem_link: Optional[str] = None
    preco: Optional[float] = Field(None, gt=0)
    id_categoria: Optional[int] = None
    popular: Optional[bool] = None
    disponivel: Optional[bool] = None
    tempo_preparo_medio: Optional[int] = Field(None, ge=0)

# ==================================================================
# Schemas para Combo (com relacionamento com Produto)
# ==================================================================

class ComboBase(BaseModel):
    nome: str = Field(..., max_length=200)
    imagem_link: str
    preco: float = Field(..., gt=0)
    popular: bool = False
    disponivel: bool = True
    tempo_preparo_medio: Optional[int] = Field(None, ge=0)


class ComboCreate(ComboBase):
    produtos_ids: List[int] = Field(..., min_length=1)


class ComboResume(BaseModel):
    id: int
    nome: str
    preco: float

    model_config = ConfigDict(from_attributes=True)


class ComboResponse(ComboBase):
    id: int
    produtos: List[ProdutoResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ComboUpdate(BaseModel):
    nome: Optional[str] = Field(None, max_length=200)
    imagem_link: Optional[str] = None
    preco: Optional[float] = Field(None, gt=0)
    popular: Optional[bool] = None
    disponivel: Optional[bool] = None
    tempo_preparo_medio: Optional[int] = Field(None, ge=0)
    produtos_ids: Optional[List[int]] = Field(None, min_length=1)


# ==================================================================
# Schemas para EnderecoCliente
# ==================================================================

class EnderecoClienteBase(BaseModel):
    apelido: str = Field(..., max_length=50)
    rua: str
    numero: str
    complemento: Optional[str] = None
    bairro: str
    cidade: str
    cep: Optional[str] = Field(None, pattern=r'^\d{5}-?\d{3}$')
    padrao: bool = False


class EnderecoClienteCreate(EnderecoClienteBase):
    pass


class EnderecoClienteResponse(EnderecoClienteBase):
    id: int
    id_cliente: int

    model_config = ConfigDict(from_attributes=True)


# ==================================================================
# Schemas para Cliente (usuário)
# ==================================================================

class ClienteBase(BaseModel):
    nome: str = Field(..., max_length=200)
    email: EmailStr
    telefone: Optional[str] = Field(None, max_length=20)
    documento: Optional[str] = Field(None, max_length=20)


class ClienteCreate(ClienteBase):
    senha: str = Field(..., min_length=6)
    enderecos: Optional[List[EnderecoClienteCreate]] = None  # permite criar endereços junto


class ClienteResponse(ClienteBase):
    id: int
    data_cadastro: datetime
    ultimo_login: Optional[datetime] = None
    ativo: bool
    enderecos: List[EnderecoClienteResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ClienteUpdate(BaseModel):
    nome: Optional[str] = None
    telefone: Optional[str] = None
    documento: Optional[str] = None
    ativo: Optional[bool] = None


# ==================================================================
# Schemas para Funcionario
# ==================================================================

class FuncionarioBase(BaseModel):
    nome: str
    email: EmailStr
    telefone: Optional[str] = None
    cargo: str  # 'garcom', 'cozinha', 'admin', 'gerente'
    ativo: bool = True


class FuncionarioCreate(FuncionarioBase):
    senha: str = Field(..., min_length=6)


class FuncionarioResponse(FuncionarioBase):
    id: int
    data_contratacao: datetime
    ultimo_login: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ==================================================================
# Schemas para Mesa
# ==================================================================

class MesaBase(BaseModel):
    numero: int = Field(..., gt=0)
    qtd_lugares: int = Field(4, ge=1)
    status: str = Field('livre', pattern='^(livre|ocupada|reservada)$')
    codigo_qr: Optional[str] = None


class MesaCreate(MesaBase):
    pass


class MesaResponse(MesaBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ==================================================================
# Schemas para MetodoPagamento
# ==================================================================

class MetodoPagamentoBase(BaseModel):
    nome: str = Field(..., max_length=50)
    ativo: bool = True


class MetodoPagamentoResponse(MetodoPagamentoBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ==================================================================
# Schemas para CodPromocional
# ==================================================================

class CodPromocionalBase(BaseModel):
    codigo: str = Field(..., max_length=50)
    desconto_percentual: float = Field(..., gt=0, le=100)
    data_validade: datetime
    ativo: bool = True


class CodPromocionalCreate(CodPromocionalBase):
    pass


class CodPromocionalResponse(CodPromocionalBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ==================================================================
# Schemas para PedidoItem (itens da comanda)
# ==================================================================

class PedidoItemBase(BaseModel):
    id_produto: Optional[int] = None
    id_combo: Optional[int] = None
    quantidade: int = Field(1, ge=1)
    preco_unitario: float = Field(..., gt=0)
    subtotal: float = Field(..., ge=0)
    observacao: Optional[str] = None


class PedidoItemCreate(PedidoItemBase):
    id_comanda: int


class PedidoItemResponse(PedidoItemBase):
    id: int
    id_comanda: int

    model_config = ConfigDict(from_attributes=True)


# ==================================================================
# Schemas para StatusComandaLog
# ==================================================================

class StatusComandaLogBase(BaseModel):
    status_anterior: Optional[str] = None
    status_novo: str
    alterado_por_tipo: str  # 'cliente', 'funcionario', 'sistema'
    alterado_por_id: Optional[int] = None
    observacao: Optional[str] = None


class StatusComandaLogResponse(StatusComandaLogBase):
    id: int
    id_comanda: int
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================================================================
# Schemas para Comanda (pedido principal)
# ==================================================================

class ComandaBase(BaseModel):
    id_cliente: Optional[int] = None
    id_mesa: Optional[int] = None
    id_garcom: Optional[int] = None
    id_metodo_pagamento: int
    id_cod_promocional: Optional[int] = None
    preco_total: float = 0.0
    desconto_aplicado: float = 0.0
    taxa_entrega: float = 0.0
    valor_a_pagar: float
    troco: float = 0.0
    status_comanda: str = 'aberta'
    status_pagamento: str = 'pendente'
    tipo_entrega: str  # 'delivery', 'local'
    origem: str  # 'web', 'mobile_garcom', 'mobile_cliente'
    observacao_geral: Optional[str] = None


class ComandaCreate(ComandaBase):
    pedido_itens: List[PedidoItemCreate]  # itens devem ser enviados junto


class ComandaResponse(ComandaBase):
    id: int
    data_registro: datetime
    data_finalizacao: Optional[datetime] = None
    cliente_rel: Optional[ClienteResponse] = None
    mesa_rel: Optional[MesaResponse] = None
    garcom_rel: Optional[FuncionarioResponse] = None
    metodo_pagamento_rel: MetodoPagamentoResponse
    cod_promocional_rel: Optional[CodPromocionalResponse] = None
    pedido_itens: List[PedidoItemResponse] = []
    status_logs: List[StatusComandaLogResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ==================================================================
# Schemas para AuditLog
# ==================================================================

class AuditLogResponse(BaseModel):
    id: int
    usuario_tipo: str
    usuario_id: Optional[int] = None
    funcionario_id: Optional[int] = None
    acao: str
    tabela_afetada: Optional[str] = None
    registro_id: Optional[int] = None
    dados_anteriores: Optional[dict] = None
    dados_novos: Optional[dict] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================================================================
# Schemas auxiliares para listas paginadas ou mensagens
# ==================================================================

class ListResponse(BaseModel):
    items: List
    total: int
    page: int
    size: int


class MessageResponse(BaseModel):
    message: str
    success: bool = True


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    nova_senha: str = Field(..., min_length=6)

class PasswordChange(BaseModel):
    senha_atual: str
    nova_senha: str = Field(..., min_length=6)

class CarrinhoItem(BaseModel):
    tipo: str  # 'produto' ou 'combo'
    id_item: int
    quantidade: int = Field(ge=1)
    observacao: Optional[str] = None

class CarrinhoCreate(BaseModel):
    items: List[CarrinhoItem]

class CarrinhoResponse(BaseModel):
    items: List[CarrinhoItem]
    subtotal: float
    taxa_entrega: float
    desconto: float
    total: float

class PagamentoPixRequest(BaseModel):
    comanda_id: int
    valor: float = Field(gt=0)

class PagamentoPixResponse(BaseModel):
    qr_code_text: str
    qr_code_base64: str   # imagem em base64
    expiracao: datetime

class PagamentoConfirmacao(BaseModel):
    comanda_id: int
    transacao_id: str
    status: str  # 'aprovado', 'falhou'




# ==================================================================
# Ajustes para evitar importação circular (resolver referências)
# ==================================================================

ProdutoResponse.model_rebuild()
ComboResponse.model_rebuild()
ClienteResponse.model_rebuild()
ComandaResponse.model_rebuild()


