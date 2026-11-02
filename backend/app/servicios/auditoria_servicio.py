"""Registro de acciones admin (C-12 R3, D-10, RN-GL-02).

`auditar` agrega el evento con flush dentro de la transaccion del router: se llama DESPUES de que
la accion tuvo exito, asi un 4xx (con rollback) no deja evento. El detalle nunca lleva
contrasenas ni tokens ni datos clinicos: se rechaza por nombre de clave.
"""
SECRETOS = ("password", "contrasena", "token", "secret")


def _clave_secreta(clave: str) -> bool:
    return any(s in clave.lower() for s in SECRETOS)


async def auditar(
    repo,
    actor_id: int | None,
    accion: str,
    objeto_tipo: str,
    objeto_id: int | None = None,
    detalle: dict | None = None,
) -> None:
    """Registra el evento; sin repo o sin actor (llamadas internas y tests de servicio) no hace nada."""
    if repo is None or actor_id is None:
        return None
    detalle = dict(detalle or {})
    prohibidas = [k for k in detalle if _clave_secreta(str(k))]
    if prohibidas:
        raise ValueError(f"el detalle de auditoria no puede incluir un secreto: {prohibidas}")
    await repo.registrar(
        actor_id=actor_id, accion=accion, objeto_tipo=objeto_tipo, objeto_id=objeto_id, detalle=detalle
    )
    return None
