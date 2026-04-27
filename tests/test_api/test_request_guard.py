async def test_oversized_body_rejected_with_413(client):
    big_body = "x" * (2 * 1024 * 1024)
    r = await client.post(
        "/api/v1/auth/register",
        content=big_body,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 413, r.text


async def test_unsupported_content_type_rejected_with_415(client):
    r = await client.post(
        "/api/v1/auth/register",
        content=b"<xml/>",
        headers={"Content-Type": "application/xml"},
    )
    assert r.status_code == 415, r.text


async def test_invalid_content_length_rejected(client):
    r = await client.post(
        "/api/v1/auth/register",
        content=b"{}",
        headers={"Content-Type": "application/json", "Content-Length": "abc"},
    )
    assert r.status_code == 400, r.text


async def test_get_request_unaffected(client):
    r = await client.get("/health")
    assert r.status_code in (200, 503)


async def test_login_form_content_type_allowed(client):
    # Register a user first so /login with correct creds reaches the handler
    await client.post("/api/v1/auth/register", json={
        "username": "guard_user",
        "email": "guard@example.com",
        "password": "tr0ub4dor&3",
    })
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": "guard_user", "password": "tr0ub4dor&3"},
    )
    assert r.status_code == 200, r.text
