from datetime import datetime
from typing import Optional, List

from sqlalchemy import ForeignKey, func, CheckConstraint, Index, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, registry, relationship

table_registry = registry()

# ==================================================================
# 1. TABELAS DE DOMÍNIO / CATÁLOGO (cardápio, categorias, pagamentos)
# ==================================================================

@table_registry.mapped_as_dataclass(kw_only=True)
class CategoriaProduto:
    __tablename__ = 'categoria_produto'
    """Organiza os produtos do cardápio (ex: pizzas, bebidas, sobremesas)."""
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    nome: Mapped[str] = mapped_column(unique=True, nullable=False)


@table_registry.mapped_as_dataclass(kw_only=True)
class Produto:
    __tablename__ = 'produto'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    nome: Mapped[str] = mapped_column(nullable=False)
    descricao: Mapped[str] = mapped_column(nullable=False)
    imagem_link: Mapped[str] = mapped_column(nullable=False)
    preco: Mapped[float] = mapped_column(nullable=False)
    id_categoria: Mapped[int] = mapped_column(ForeignKey('categoria_produto.id'), nullable=False)
    tempo_preparo_medio: Mapped[Optional[int]] = mapped_column(nullable=True)  # ← Movido para cima

    # ===== ATRIBUTOS COM VALOR PADRÃO (ficam por último) =====
    popular: Mapped[bool] = mapped_column(default=False)
    disponivel: Mapped[bool] = mapped_column(default=True)

    # Relacionamentos
    categoria_rel: Mapped['CategoriaProduto'] = relationship(init=False)
    combos: Mapped[List['Combo']] = relationship(
        secondary='combo_produto',
        back_populates='produtos',
        init=False
    )

@table_registry.mapped_as_dataclass(kw_only=True)
class Combo:
    __tablename__ = 'combo'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    nome: Mapped[str] = mapped_column(nullable=False)
    imagem_link: Mapped[str] = mapped_column(nullable=False)
    preco: Mapped[float] = mapped_column(nullable=False)
    tempo_preparo_medio: Mapped[Optional[int]] = mapped_column(nullable=True)  # ← Mover para cima
    popular: Mapped[bool] = mapped_column(default=False)
    disponivel: Mapped[bool] = mapped_column(default=True)

    produtos: Mapped[List['Produto']] = relationship(
        secondary='combo_produto',
        back_populates='combos',
        init=False
    )

@table_registry.mapped_as_dataclass(kw_only=True)
class ComboProduto:
    __tablename__ = 'combo_produto'
    """Tabela associativa entre Combo e Produto (muitos-para-muitos)."""
    combo_id: Mapped[int] = mapped_column(ForeignKey('combo.id'), primary_key=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey('produto.id'), primary_key=True)

@table_registry.mapped_as_dataclass(kw_only=True)
class MetodoPagamento:
    __tablename__ = 'metodo_pagamento'
    """Domínio de métodos de pagamento (PIX, dinheiro, cartão)."""
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    nome: Mapped[str] = mapped_column(unique=True, nullable=False)
    ativo: Mapped[bool] = mapped_column(default=True)


# ==================================================================
# 2. CLIENTE (usuário do sistema web/mobile) e ENDEREÇOS
# ==================================================================

@table_registry.mapped_as_dataclass(kw_only=True)
class Cliente:
    __tablename__ = 'cliente'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    nome: Mapped[str] = mapped_column(nullable=False)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    telefone: Mapped[Optional[str]] = mapped_column(nullable=True)
    documento: Mapped[Optional[str]] = mapped_column(unique=True, nullable=True)
    senha_hash: Mapped[str] = mapped_column(nullable=False)
    data_cadastro: Mapped[datetime] = mapped_column(server_default=func.now())
    ultimo_login: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    ativo: Mapped[bool] = mapped_column(default=True)

    # Relacionamentos
    enderecos: Mapped[List['EnderecoCliente']] = relationship(
        back_populates='cliente_rel',
        cascade='all, delete-orphan',
        init=False
    )
    comandas: Mapped[List['Comanda']] = relationship(
        back_populates='cliente_rel',
        init=False
    )

    # Propriedade auxiliar para acessar o endereço padrão (lógica na aplicação)
    @property
    def endereco_padrao(self) -> Optional['EnderecoCliente']:
        return next((e for e in self.enderecos if e.padrao), None)


@table_registry.mapped_as_dataclass(kw_only=True)
class EnderecoCliente:
    __tablename__ = 'endereco_cliente'
    """Múltiplos endereços de entrega para o cliente."""
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    id_cliente: Mapped[int] = mapped_column(ForeignKey('cliente.id'), nullable=False)
    apelido: Mapped[str]  # 'casa', 'trabalho', 'outro'
    rua: Mapped[str] = mapped_column(nullable=False)
    numero: Mapped[str] = mapped_column(nullable=False)
    complemento: Mapped[Optional[str]] = mapped_column(nullable=True)
    bairro: Mapped[str] = mapped_column(nullable=False)
    cidade: Mapped[str] = mapped_column(nullable=False)
    cep: Mapped[Optional[str]] = mapped_column(nullable=True)
    padrao: Mapped[bool] = mapped_column(default=False)

    cliente_rel: Mapped['Cliente'] = relationship(back_populates='enderecos', init=False)

    __table_args__ = (
        # Garante que um cliente tenha no máximo um endereço padrão (unicidade parcial)
        UniqueConstraint('id_cliente', 'padrao', name='unique_padrao_por_cliente'),
    )


# ==================================================================
# 3. FUNCIONÁRIOS (garçons, cozinha, admin) e SESSÕES
# ==================================================================

@table_registry.mapped_as_dataclass(kw_only=True)
class Funcionario:
    __tablename__ = 'funcionario'

    # ===== ATRIBUTOS OBRIGATÓRIOS (sem valor padrão) =====
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    nome: Mapped[str] = mapped_column(nullable=False)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(nullable=False)
    cargo: Mapped[str]                     # obrigatório
    data_contratacao: Mapped[datetime] = mapped_column(server_default=func.now())   # ← movido para cá
    ultimo_login: Mapped[Optional[datetime]] = mapped_column(nullable=True)          # ← movido para cá

    # ===== ATRIBUTOS COM VALOR PADRÃO (ficam por último) =====
    telefone: Mapped[Optional[str]] = mapped_column(nullable=True)
    ativo: Mapped[bool] = mapped_column(default=True)

    # Relacionamentos
    comandas_atendidas: Mapped[List['Comanda']] = relationship(
        back_populates='garcom_rel', foreign_keys='Comanda.id_garcom', init=False
    )
    logs_auditoria: Mapped[List['AuditLog']] = relationship(
        back_populates='funcionario_rel', init=False
    )

# ==================================================================
# 4. MESA (física do salão)
# ==================================================================

@table_registry.mapped_as_dataclass(kw_only=True)
class Mesa:
    __tablename__ = 'mesa'

    # ===== ATRIBUTOS OBRIGATÓRIOS (sem valor padrão) =====
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    numero: Mapped[int] = mapped_column(unique=True, nullable=False)
    codigo_qr: Mapped[Optional[str]] = mapped_column(unique=True, nullable=True)  # obrigatório no __init__ (pode ser None)

    # ===== ATRIBUTOS COM VALOR PADRÃO (ficam por último) =====
    qtd_lugares: Mapped[int] = mapped_column(nullable=False, default=4)
    status: Mapped[str] = mapped_column(default='livre')

    comandas: Mapped[List['Comanda']] = relationship(back_populates='mesa_rel', init=False)

# ==================================================================
# 5. COMANDA (pedido principal) e ITENS
# ==================================================================

@table_registry.mapped_as_dataclass(kw_only=True)
class Comanda:
    __tablename__ = 'comanda'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)

    # ===== CAMPOS OBRIGATÓRIOS (sem valor padrão) =====
    id_cliente: Mapped[Optional[int]] = mapped_column(ForeignKey('cliente.id'), nullable=True)
    id_mesa: Mapped[Optional[int]] = mapped_column(ForeignKey('mesa.id'), nullable=True)
    id_garcom: Mapped[Optional[int]] = mapped_column(ForeignKey('funcionario.id'), nullable=True)
    id_metodo_pagamento: Mapped[int] = mapped_column(ForeignKey('metodo_pagamento.id'), nullable=False)
    id_cod_promocional: Mapped[Optional[int]] = mapped_column(ForeignKey('cod_promocional.id'), nullable=True)

    valor_a_pagar: Mapped[float] = mapped_column(nullable=False)
    tipo_entrega: Mapped[str]  # 'delivery', 'local'
    origem: Mapped[str]  # 'web', 'mobile_garcom', 'mobile_cliente'

    data_registro: Mapped[datetime] = mapped_column(server_default=func.now())
    data_finalizacao: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    observacao_geral: Mapped[Optional[str]] = mapped_column(nullable=True)

    # ===== CAMPOS COM VALOR PADRÃO (ficam por último) =====
    preco_total: Mapped[float] = mapped_column(nullable=False, default=0.0)
    desconto_aplicado: Mapped[float] = mapped_column(default=0.0)
    taxa_entrega: Mapped[float] = mapped_column(default=0.0)
    troco: Mapped[float] = mapped_column(default=0.0)
    status_comanda: Mapped[str] = mapped_column(default='aberta')
    status_pagamento: Mapped[str] = mapped_column(default='pendente')

    # ===== RELACIONAMENTOS =====
    cliente_rel: Mapped[Optional['Cliente']] = relationship(back_populates='comandas', lazy='joined', init=False)
    mesa_rel: Mapped[Optional['Mesa']] = relationship(back_populates='comandas', lazy='joined', init=False)
    garcom_rel: Mapped[Optional['Funcionario']] = relationship(foreign_keys=[id_garcom], init=False)
    metodo_pagamento_rel: Mapped['MetodoPagamento'] = relationship(init=False)
    cod_promocional_rel: Mapped[Optional['CodPromocional']] = relationship(init=False)
    pedido_itens: Mapped[List['PedidoItem']] = relationship(back_populates='comanda_rel', default_factory=list, init=False)
    status_logs: Mapped[List['StatusComandaLog']] = relationship(back_populates='comanda_rel', cascade='all, delete-orphan', init=False)

    # ===== RESTRIÇÕES =====
    __table_args__ = (
        CheckConstraint(
            '(id_cliente IS NOT NULL) OR (id_mesa IS NOT NULL)',
            name='check_cliente_ou_mesa'
        ),
        Index('idx_comanda_status', 'status_comanda'),
        Index('idx_comanda_data', 'data_registro'),
    )


@table_registry.mapped_as_dataclass(kw_only=True)
class PedidoItem:
    __tablename__ = 'pedido_item'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    id_comanda: Mapped[int] = mapped_column(ForeignKey('comanda.id'), nullable=False)
    preco_unitario: Mapped[float] = mapped_column(nullable=False)
    subtotal: Mapped[float] = mapped_column(nullable=False)

    # Opcionais (podem ser None)
    id_produto: Mapped[Optional[int]] = mapped_column(ForeignKey('produto.id'), nullable=True)
    id_combo: Mapped[Optional[int]] = mapped_column(ForeignKey('combo.id'), nullable=True)
    observacao: Mapped[Optional[str]] = mapped_column(nullable=True)
    quantidade: Mapped[int] = mapped_column(default=1)

    comanda_rel: Mapped['Comanda'] = relationship(back_populates='pedido_itens', lazy='joined', init=False)

    __table_args__ = (
        CheckConstraint(
            '(id_produto IS NOT NULL) XOR (id_combo IS NOT NULL)',
            name='check_produto_ou_combo'
        ),
    )


# ==================================================================
# 6. HISTÓRICO DE STATUS DA COMANDA (rastreamento)
# ==================================================================

@table_registry.mapped_as_dataclass(kw_only=True)
class StatusComandaLog:
    __tablename__ = 'status_comanda_log'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    id_comanda: Mapped[int] = mapped_column(ForeignKey('comanda.id'), nullable=False)
    status_anterior: Mapped[Optional[str]] = mapped_column(nullable=True)
    status_novo: Mapped[str] = mapped_column(nullable=False)
    alterado_por_tipo: Mapped[str]  # 'cliente', 'funcionario', 'sistema'
    alterado_por_id: Mapped[Optional[int]] = mapped_column(nullable=True)  # id do cliente ou funcionário
    timestamp: Mapped[datetime] = mapped_column(server_default=func.now())
    observacao: Mapped[Optional[str]] = mapped_column(nullable=True)

    comanda_rel: Mapped['Comanda'] = relationship(back_populates='status_logs', init=False)


# ==================================================================
# 7. CÓDIGO PROMOCIONAL
# ==================================================================

@table_registry.mapped_as_dataclass(kw_only=True)
class CodPromocional:
    __tablename__ = 'cod_promocional'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    codigo: Mapped[str] = mapped_column(unique=True, nullable=False)
    desconto_percentual: Mapped[float] = mapped_column(nullable=False)
    data_validade: Mapped[datetime] = mapped_column(nullable=False)
    ativo: Mapped[bool] = mapped_column(default=True)


# ==================================================================
# 8. SINCronização OFFLINE (para o app Garçom Digital)
# ==================================================================

"""
@table_registry.mapped_as_dataclass
class PedidoSync:
    __tablename__ = 'pedido_sync'
    #Registra pedidos criados offline e controla sincronização com o backend.
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    id_comanda: Mapped[int] = mapped_column(ForeignKey('comanda.id'), nullable=False)
    dispositivo_id: Mapped[str] = mapped_column(nullable=False)   # ID único do dispositivo mobile
    status_sync: Mapped[str] = mapped_column(default='pendente')  # pendente, sincronizado, falha
    tentativas: Mapped[int] = mapped_column(default=0)
    ultima_tentativa: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    dados_offline: Mapped[Optional[dict]] = mapped_column(nullable=True)  # JSON com o pedido original
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())

    comanda_rel: Mapped['Comanda'] = relationship(back_populates='sync_registros', init=False)
"""

# ==================================================================
# 9. AUDITORIA (logs de ações críticas)
# ==================================================================

@table_registry.mapped_as_dataclass(kw_only=True)
class AuditLog:
    __tablename__ = 'audit_log'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    usuario_tipo: Mapped[str]
    usuario_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    funcionario_id: Mapped[Optional[int]] = mapped_column(ForeignKey('funcionario.id'), nullable=True)
    acao: Mapped[str]
    tabela_afetada: Mapped[Optional[str]] = mapped_column(nullable=True)
    registro_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    dados_anteriores: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    dados_novos: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(nullable=True)
    timestamp: Mapped[datetime] = mapped_column(server_default=func.now())

    funcionario_rel: Mapped[Optional['Funcionario']] = relationship(back_populates='logs_auditoria', init=False)