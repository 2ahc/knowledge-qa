from tests.conftest import auth_headers, login, make_user


def test_login_success_and_me(client, db):
    make_user(db, "alice")
    tokens = login(client, "alice")
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    resp = client.get("/api/auth/me", headers=auth_headers(tokens["access_token"]))
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"


def test_login_wrong_password(client, db):
    make_user(db, "alice")
    resp = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401


def test_me_without_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_refresh_flow(client, db):
    make_user(db, "alice")
    tokens = login(client, "alice")
    resp = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert new_tokens["access_token"]

    # access token cannot be used as refresh token
    resp = client.post("/api/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert resp.status_code == 401


def test_inactive_user_cannot_login(client, db):
    user = make_user(db, "bob")
    user.is_active = False
    db.commit()
    resp = client.post("/api/auth/login", json={"username": "bob", "password": "pass123456"})
    assert resp.status_code == 403
