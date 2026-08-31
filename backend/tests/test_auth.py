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

    # 令牌类型隔离：access 令牌不能冒充 refresh 令牌使用
    resp = client.post("/api/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert resp.status_code == 401


def test_inactive_user_cannot_login(client, db):
    user = make_user(db, "bob")
    user.is_active = False
    db.commit()
    resp = client.post("/api/auth/login", json={"username": "bob", "password": "pass123456"})
    assert resp.status_code == 403


def test_register_creates_regular_user(client):
    """注册成功：直接签发令牌，且角色必为普通用户。"""
    resp = client.post(
        "/api/auth/register",
        json={"username": "newbie", "password": "secret123", "display_name": "新人"},
    )
    assert resp.status_code == 201, resp.text
    tokens = resp.json()
    assert tokens["access_token"]

    me = client.get("/api/auth/me", headers=auth_headers(tokens["access_token"])).json()
    assert me["username"] == "newbie"
    assert me["display_name"] == "新人"
    assert me["role"] == "user"
    # 普通用户访问管理接口被拒
    assert client.get("/api/users", headers=auth_headers(tokens["access_token"])).status_code == 403


def test_register_cannot_self_promote_admin(client):
    """提权尝试：客户端偷传 role=admin 无效（schema 无此字段，直接忽略）。"""
    resp = client.post(
        "/api/auth/register",
        json={"username": "sneaky", "password": "secret123", "role": "admin"},
    )
    assert resp.status_code == 201, resp.text
    me = client.get("/api/auth/me", headers=auth_headers(resp.json()["access_token"])).json()
    assert me["role"] == "user"


def test_register_duplicate_username(client, db):
    make_user(db, "alice")
    resp = client.post("/api/auth/register", json={"username": "alice", "password": "secret123"})
    assert resp.status_code == 409


def test_register_validation(client):
    # 弱密码（<6 位）与非法用户名（含空格）都被 422 拒绝
    assert client.post("/api/auth/register", json={"username": "ok", "password": "123"}).status_code == 422
    assert client.post("/api/auth/register", json={"username": "bad name", "password": "secret123"}).status_code == 422
