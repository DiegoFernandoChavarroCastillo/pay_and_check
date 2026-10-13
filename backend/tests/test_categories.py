from sqlmodel import Session

from app.db.seed import seed_default_categories

DEFAULT_NAMES = {"comida", "transporte", "entretenimiento", "salud", "servicios", "otros"}


def test_usuario_nuevo_ve_categorias_por_defecto(client, auth_headers, db_engine):
    with Session(db_engine) as session:
        seed_default_categories(session)

    r = client.get("/categories", headers=auth_headers)
    assert r.status_code == 200
    nombres = {c["nombre"] for c in r.json()}
    assert nombres == DEFAULT_NAMES


def test_categories_requiere_autenticacion(client):
    r = client.get("/categories")
    assert r.status_code == 401


def test_categoria_personalizada_aislada_por_usuario(client, make_user, db_engine):
    with Session(db_engine) as session:
        seed_default_categories(session)

    headers_a, _ = make_user("a@test.com")
    headers_b, _ = make_user("b@test.com")

    r = client.post("/categories", json={"nombre": "mascotas"}, headers=headers_a)
    assert r.status_code == 201
    assert r.json()["owner_id"] is not None

    nombres_a = {c["nombre"] for c in client.get("/categories", headers=headers_a).json()}
    nombres_b = {c["nombre"] for c in client.get("/categories", headers=headers_b).json()}
    assert "mascotas" in nombres_a
    assert "mascotas" not in nombres_b


def test_categoria_por_defecto_tipo_opcional_por_defecto(client, auth_headers, db_engine):
    with Session(db_engine) as session:
        seed_default_categories(session)
    comida = next(c for c in client.get("/categories", headers=auth_headers).json() if c["nombre"] == "comida")
    assert comida["tipo"] == "opcional"
    assert comida["limite"] is None


def test_crear_categoria_con_tipo_fijo_y_limite(client, auth_headers):
    r = client.post(
        "/categories", json={"nombre": "arriendo", "tipo": "fijo", "limite": "500000.00"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    assert r.json()["tipo"] == "fijo"
    assert r.json()["limite"] == "500000.00"


def test_no_se_puede_editar_categoria_por_defecto_compartida(client, auth_headers, db_engine):
    with Session(db_engine) as session:
        seed_default_categories(session)
    comida = next(c for c in client.get("/categories", headers=auth_headers).json() if c["nombre"] == "comida")

    # Es compartida entre todos los usuarios: ni el tipo ni el nombre se pueden tocar.
    r = client.patch(f"/categories/{comida['id']}", json={"tipo": "fijo"}, headers=auth_headers)
    assert r.status_code == 400
    r = client.patch(f"/categories/{comida['id']}", json={"nombre": "mercado"}, headers=auth_headers)
    assert r.status_code == 400


def test_cada_persona_pone_su_propio_limite_a_una_categoria_por_defecto(client, auth_headers, db_engine):
    with Session(db_engine) as session:
        seed_default_categories(session)
    comida = next(c for c in client.get("/categories", headers=auth_headers).json() if c["nombre"] == "comida")

    r = client.patch(f"/categories/{comida['id']}", json={"limite": "200000"}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["limite"] == "200000.00"
    mias = {c["nombre"]: c["limite"] for c in client.get("/categories", headers=auth_headers).json()}
    assert mias["comida"] == "200000.00"

    # Otra persona no ve ese límite: es de quien lo puso.
    client.post("/auth/register", json={"email": "otra@test.com", "password": "secret123", "nombre": "Otra"})
    token = client.post("/auth/login", json={"email": "otra@test.com", "password": "secret123"}).json()["access_token"]
    suyas = client.get("/categories", headers={"Authorization": f"Bearer {token}"}).json()
    assert next(c for c in suyas if c["nombre"] == "comida")["limite"] is None

    # Y se puede quitar.
    r = client.patch(f"/categories/{comida['id']}", json={"limite": None}, headers=auth_headers)
    assert r.json()["limite"] is None


def test_transporte_salud_y_servicios_son_gasto_fijo(client, auth_headers, db_engine):
    with Session(db_engine) as session:
        seed_default_categories(session)
    tipos = {c["nombre"]: c["tipo"] for c in client.get("/categories", headers=auth_headers).json()}
    assert [tipos[n] for n in ("transporte", "salud", "servicios")] == ["fijo"] * 3
    assert [tipos[n] for n in ("comida", "entretenimiento", "otros")] == ["opcional"] * 3


def test_editar_categoria_propia(client, auth_headers):
    r = client.post("/categories", json={"nombre": "salidas"}, headers=auth_headers)
    cat_id = r.json()["id"]

    r = client.patch(f"/categories/{cat_id}", json={"tipo": "opcional", "limite": "30000.00"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["limite"] == "30000.00"
