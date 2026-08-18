from app.busca import buscar_por_termo
from app.limpeza import limpar


def busca_legada(termo):
    """Caminho antigo, mantido para o relatorio em lote. Este limpa."""
    return buscar_por_termo(limpar(termo))
