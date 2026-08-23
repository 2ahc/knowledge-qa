from tests.conftest import auth_headers, login, make_user


def test_stats_requires_admin(client, db):
    make_user(db, "alice")
    h = auth_headers(login(client, "alice")["access_token"])
    assert client.get("/api/admin/stats", headers=h).status_code == 403
    assert client.get("/api/admin/tasks", headers=h).status_code == 403


def test_stats_and_tasks(client, db):
    make_user(db, "root", role="admin")
    make_user(db, "alice")
    h = auth_headers(login(client, "root")["access_token"])

    resp = client.get("/api/admin/stats", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_count"] == 2
    assert data["kb_count"] == 0
    assert data["question_count"] == 0
    assert data["daily_questions"] == []
    assert data["top_documents"] == []

    resp = client.get("/api/admin/tasks", headers=h)
    assert resp.status_code == 200
    assert resp.json() == []
