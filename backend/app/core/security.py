"""Stub C-01: JWT real llega en C-03. Falla explicito si alguien lo usa antes."""

_MSG = "seguridad JWT no implementada en C-01 (llega en C-03)"


def crear_token(_subject: str) -> str:
    raise NotImplementedError(_MSG)


def verificar_token(_token: str) -> str:
    raise NotImplementedError(_MSG)
