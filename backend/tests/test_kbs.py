import io

from sqlalchemy import select

from app.models.task import Task, TaskKind, TaskStatus
from tests.conftest import auth_headers, login, make_user


def _create_kb(client, h, name="产品知识库", visibility="private"):
    resp = client.post(
        "/api/kbs", json={"name": name, "description": "测试库", "visibility": visibility}, headers=h
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_kb_crud_and_visibility(client, db):
    make_user(db, "alice")
    make_user(db, "bob")
    alice_h = auth_headers(login(client, "alice")["access_token"])
    bob_h = auth_headers(login(client, "bob")["access_token"])

    kb = _create_kb(client, alice_h)
    assert kb["doc_count"] == 0

    # owner sees it
    resp = client.get("/api/kbs", headers=alice_h)
    assert [k["id"] for k in resp.json()] == [kb["id"]]

    # private: bob cannot see or access
    assert client.get("/api/kbs", headers=bob_h).json() == []
    assert client.get(f"/api/kbs/{kb['id']}", headers=bob_h).status_code == 403

    # make it public
    resp = client.patch(f"/api/kbs/{kb['id']}", json={"visibility": "public"}, headers=alice_h)
    assert resp.status_code == 200
    assert len(client.get("/api/kbs", headers=bob_h).json()) == 1

    # bob cannot delete alice's kb
    assert client.delete(f"/api/kbs/{kb['id']}", headers=bob_h).status_code == 403
    # alice can
    assert client.delete(f"/api/kbs/{kb['id']}", headers=alice_h).status_code == 204
    assert client.get("/api/kbs", headers=alice_h).json() == []


def test_kb_members(client, db):
    alice = make_user(db, "alice")
    bob = make_user(db, "bob")
    alice_h = auth_headers(login(client, "alice")["access_token"])
    bob_h = auth_headers(login(client, "bob")["access_token"])

    kb = _create_kb(client, alice_h, visibility="shared")

    # bob can't access yet
    assert client.get(f"/api/kbs/{kb['id']}", headers=bob_h).status_code == 403

    # add bob as viewer
    resp = client.post(f"/api/kbs/{kb['id']}/members", json={"user_id": str(bob.id)}, headers=alice_h)
    assert resp.status_code == 201, resp.text

    # now bob can see it but not upload (viewer)
    assert client.get(f"/api/kbs/{kb['id']}", headers=bob_h).status_code == 200

    resp = client.get(f"/api/kbs/{kb['id']}/members", headers=alice_h)
    assert resp.status_code == 200 and len(resp.json()) == 1

    # remove member
    assert client.delete(f"/api/kbs/{kb['id']}/members/{bob.id}", headers=alice_h).status_code == 204
    assert client.get(f"/api/kbs/{kb['id']}", headers=bob_h).status_code == 403


def test_document_upload_and_delete(client, db):
    make_user(db, "alice")
    alice_h = auth_headers(login(client, "alice")["access_token"])
    kb = _create_kb(client, alice_h)

    # upload txt
    resp = client.post(
        f"/api/kbs/{kb['id']}/documents",
        files={"file": ("notes.txt", io.BytesIO("你好，这是测试内容。".encode("utf-8")), "text/plain")},
        headers=alice_h,
    )
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["status"] == "pending"
    assert doc["filetype"] == "txt"
    assert doc["size_bytes"] == len("你好，这是测试内容。".encode("utf-8"))

    # list
    resp = client.get(f"/api/kbs/{kb['id']}/documents", headers=alice_h)
    assert len(resp.json()) == 1

    # bad extension rejected
    resp = client.post(
        f"/api/kbs/{kb['id']}/documents",
        files={"file": ("evil.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
        headers=alice_h,
    )
    assert resp.status_code == 400

    # delete
    assert client.delete(f"/api/kbs/{kb['id']}/documents/{doc['id']}", headers=alice_h).status_code == 204
    assert client.get(f"/api/kbs/{kb['id']}/documents", headers=alice_h).json() == []


def test_upload_enqueues_index_task(client, db):
    make_user(db, "alice")
    alice_h = auth_headers(login(client, "alice")["access_token"])
    kb = _create_kb(client, alice_h)

    resp = client.post(
        f"/api/kbs/{kb['id']}/documents",
        files={"file": ("notes.txt", io.BytesIO("内容".encode("utf-8")), "text/plain")},
        headers=alice_h,
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    tasks = db.scalars(select(Task)).all()
    assert len(tasks) == 1
    assert tasks[0].kind == TaskKind.document_index
    assert tasks[0].status == TaskStatus.queued
    assert tasks[0].payload == {"document_id": doc_id}

    # reindex endpoint enqueues again
    resp = client.post(f"/api/kbs/{kb['id']}/documents/{doc_id}/reindex", headers=alice_h)
    assert resp.status_code == 200
    assert len(db.scalars(select(Task)).all()) == 2
