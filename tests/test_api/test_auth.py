async def test_register_returns_token_and_user(client):
    r = await client.post("/api/v1/auth/register", json={
        "username": "neo",
        "email": "neo@matrix.io",
        "password": "redpill42",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == "neo"
    assert body["user"]["role"] == "user"


async def test_register_duplicate_username_conflicts(client):
    payload = {"username": "dup", "email": "a@b.c", "password": "password123"}
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201

    r = await client.post("/api/v1/auth/register", json={**payload, "email": "x@y.z"})
    assert r.status_code == 409


async def test_login_with_wrong_password_fails(client):
    await client.post("/api/v1/auth/register", json={
        "username": "bob", "email": "bob@b.c", "password": "rightpass1",
    })
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": "bob", "password": "wrongpass"},
    )
    assert r.status_code == 401


async def test_me_requires_token(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


async def test_me_returns_current_user(client, user_token, auth_header):
    r = await client.get("/api/v1/auth/me", headers=auth_header(user_token))
    assert r.status_code == 200
    assert r.json()["username"] == "alice"
