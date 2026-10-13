import app.routers.auth as auth_router


def test_registro_devuelve_201_sin_hash(client):
    r = client.post("/auth/register", json={"email": "ana@test.com", "password": "secret123", "nombre": "Ana"})
    assert r.status_code == 201
    assert "hashed_password" not in r.json()


def test_registro_duplicado_con_password_falla(client):
    client.post("/auth/register", json={"email": "ana@test.com", "password": "secret123", "nombre": "Ana"})
    r = client.post("/auth/register", json={"email": "ana@test.com", "password": "x", "nombre": "Ana2"})
    assert r.status_code == 400


def test_login_correcto_e_incorrecto(client):
    client.post("/auth/register", json={"email": "ana@test.com", "password": "secret123", "nombre": "Ana"})

    r = client.post("/auth/login", json={"email": "ana@test.com", "password": "secret123"})
    assert r.status_code == 200
    assert "access_token" in r.json()

    r = client.post("/auth/login", json={"email": "ana@test.com", "password": "wrong"})
    assert r.status_code == 401


def test_me_requiere_token_valido(client, auth_headers):
    r = client.get("/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "user@test.com"

    r = client.get("/auth/me")
    assert r.status_code == 401  # sin token

    r = client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401  # token inválido


def test_google_crea_usuario_nuevo_sin_password(client, monkeypatch):
    monkeypatch.setattr(
        auth_router,
        "verify_google_token",
        lambda _token: {"google_id": "g-999", "email": "beto@test.com", "nombre": "Beto"},
    )
    r = client.post("/auth/google", json={"id_token": "whatever"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == "beto@test.com"

    # login por password de esa cuenta (solo Google) -> 400 claro
    r = client.post("/auth/login", json={"email": "beto@test.com", "password": "cualquiera"})
    assert r.status_code == 400


def test_google_no_duplica_usuario_existente(client, monkeypatch):
    monkeypatch.setattr(
        auth_router,
        "verify_google_token",
        lambda _token: {"google_id": "g-999", "email": "beto@test.com", "nombre": "Beto"},
    )
    r1 = client.post("/auth/google", json={"id_token": "a"})
    r2 = client.post("/auth/google", json={"id_token": "b"})
    assert r1.status_code == 200 and r2.status_code == 200

    me1 = client.get("/auth/me", headers={"Authorization": f"Bearer {r1.json()['access_token']}"})
    me2 = client.get("/auth/me", headers={"Authorization": f"Bearer {r2.json()['access_token']}"})
    assert me1.json()["id"] == me2.json()["id"]


def test_google_asocia_cuenta_existente_por_email_sin_duplicar(client, monkeypatch):
    client.post("/auth/register", json={"email": "ana@test.com", "password": "secret123", "nombre": "Ana"})

    monkeypatch.setattr(
        auth_router,
        "verify_google_token",
        lambda _token: {"google_id": "g-ana", "email": "ana@test.com", "nombre": "Ana"},
    )
    r = client.post("/auth/google", json={"id_token": "whatever"})
    assert r.status_code == 200

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["email"] == "ana@test.com"

    # login por password sigue funcionando (no se perdió al asociar Google)
    r = client.post("/auth/login", json={"email": "ana@test.com", "password": "secret123"})
    assert r.status_code == 200


def test_registro_sobre_cuenta_solo_google_agrega_password(client, monkeypatch):
    monkeypatch.setattr(
        auth_router,
        "verify_google_token",
        lambda _token: {"google_id": "g-999", "email": "beto@test.com", "nombre": "Beto"},
    )
    client.post("/auth/google", json={"id_token": "whatever"})

    r = client.post("/auth/register", json={"email": "beto@test.com", "password": "newpass", "nombre": "Beto"})
    assert r.status_code == 201

    r = client.post("/auth/login", json={"email": "beto@test.com", "password": "newpass"})
    assert r.status_code == 200


def test_el_correo_no_distingue_mayusculas(client):
    r = client.post("/auth/register", json={"email": "Juan.Ramirez@Test.com", "password": "secret123", "nombre": "J"})
    assert r.status_code in (200, 201)

    r = client.post("/auth/login", json={"email": "juan.ramirez@test.com", "password": "secret123"})
    assert r.status_code == 200
    # Y no se puede registrar "otra" cuenta que solo cambie las mayúsculas.
    r = client.post("/auth/register", json={"email": "JUAN.RAMIREZ@test.com", "password": "x", "nombre": "Otro"})
    assert r.status_code == 400

