from tests.conftest import auth_headers, login, make_user


def test_only_admin_can_manage_users(client, db):
    make_user(db, "alice")
    tokens = login(client, "alice")
    resp = client.get("/api/users", headers=auth_headers(tokens["access_token"]))
    assert resp.status_code == 403


def test_admin_user_lifecycle(client, db):
    make_user(db, "root", role="admin")
    tokens = login(client, "root")
    h = auth_headers(tokens["access_token"])

    # create
    resp = client.post(
        "/api/users",
        json={"username": "zhang", "password": "secret123", "display_name": "小张", "role": "user"},
        headers=h,
    )
    assert resp.status_code == 201, resp.text
    user = resp.json()
    assert user["username"] == "zhang"

    # duplicate username
    resp = client.post("/api/users", json={"username": "zhang", "password": "secret123"}, headers=h)
    assert resp.status_code == 409

    # list
    resp = client.get("/api/users", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # update display name + deactivate
    resp = client.patch(f"/api/users/{user['id']}", json={"display_name": "张同学"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "张同学"

    # new user can log in
    resp = client.post("/api/auth/login", json={"username": "zhang", "password": "secret123"})
    assert resp.status_code == 200


def test_admin_cannot_demote_or_deactivate_self(client, db):
    admin = make_user(db, "root", role="admin")
    tokens = login(client, "root")
    h = auth_headers(tokens["access_token"])

    resp = client.patch(f"/api/users/{admin.id}", json={"role": "user"}, headers=h)
    assert resp.status_code == 400

    resp = client.patch(f"/api/users/{admin.id}", json={"is_active": False}, headers=h)
    assert resp.status_code == 400
