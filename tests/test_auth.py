from app.models.user import ROLE_LECTURER, ROLE_ADMIN
from tests.conftest import login, DEMO_PASSWORD


def test_login_success(client, users):
    resp = login(client, ROLE_LECTURER)
    assert resp.status_code == 200
    assert resp.get_json()["user"]["role"] == ROLE_LECTURER


def test_login_wrong_password(client, users):
    resp = client.post("/api/auth/login", json={
        "email": f"{ROLE_LECTURER}@test.com", "password": "wrong",
    })
    assert resp.status_code == 401


def test_login_unknown_email(client, users):
    resp = client.post("/api/auth/login", json={
        "email": "nobody@test.com", "password": DEMO_PASSWORD,
    })
    assert resp.status_code == 401


def test_logout_clears_session(client, users):
    login(client, ROLE_LECTURER)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200

    client.post("/api/auth/logout")
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_lecturer_cannot_access_admin_routes(client, users):
    login(client, ROLE_LECTURER)
    resp = client.get("/dashboard/admin/users")
    assert resp.status_code == 403


def test_admin_can_access_admin_routes(client, users):
    login(client, ROLE_ADMIN)
    resp = client.get("/dashboard/admin/users")
    assert resp.status_code == 200


def test_password_reset_full_flow(client, users):
    resp = client.post("/api/auth/password-reset/request", json={"email": f"{ROLE_LECTURER}@test.com"})
    assert resp.status_code == 200
    token = resp.get_json()["dev_reset_token"]

    resp = client.post("/api/auth/password-reset/confirm", json={
        "token": token, "password": "BrandNewPass123",
    })
    assert resp.status_code == 200

    resp = client.post("/api/auth/login", json={
        "email": f"{ROLE_LECTURER}@test.com", "password": "BrandNewPass123",
    })
    assert resp.status_code == 200


def test_password_reset_token_single_use(client, users):
    resp = client.post("/api/auth/password-reset/request", json={"email": f"{ROLE_LECTURER}@test.com"})
    token = resp.get_json()["dev_reset_token"]
    client.post("/api/auth/password-reset/confirm", json={"token": token, "password": "First12345"})

    resp = client.post("/api/auth/password-reset/confirm", json={"token": token, "password": "Second12345"})
    assert resp.status_code == 400


def test_password_reset_unknown_email_returns_generic_message(client, users):
    resp = client.post("/api/auth/password-reset/request", json={"email": "ghost@test.com"})
    assert resp.status_code == 200
    assert "dev_reset_token" not in resp.get_json()
