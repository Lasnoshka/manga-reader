async def _create_manga(client, admin_header, **overrides):
    payload = {
        "title": "Berserk",
        "description": "Dark fantasy.",
        "author": "Miura",
        "genres": ["Action", "Dark Fantasy"],
        **overrides,
    }
    return await client.post("/api/v1/manga/", json=payload, headers=admin_header)


async def test_list_empty(client):
    r = await client.get("/api/v1/manga/")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["items"] == []


async def test_create_requires_admin(client, user_token, auth_header):
    r = await client.post(
        "/api/v1/manga/",
        json={"title": "Nope", "description": "No access"},
        headers=auth_header(user_token),
    )
    assert r.status_code == 403


async def test_create_manga_as_admin(client, admin_token, auth_header):
    r = await _create_manga(client, auth_header(admin_token))
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Berserk"
    assert {g["name"] for g in body["genres"]} == {"Action", "Dark Fantasy"}


async def test_create_duplicate_title_conflicts(client, admin_token, auth_header):
    h = auth_header(admin_token)
    assert (await _create_manga(client, h)).status_code == 201
    r = await _create_manga(client, h)
    assert r.status_code == 409


async def test_get_detail_and_list_after_create(client, admin_token, auth_header):
    create = await _create_manga(client, auth_header(admin_token))
    manga_id = create.json()["id"]

    detail = await client.get(f"/api/v1/manga/{manga_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == manga_id

    listed = await client.get("/api/v1/manga/")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


async def test_update_manga_as_admin(client, admin_token, auth_header):
    h = auth_header(admin_token)
    manga_id = (await _create_manga(client, h)).json()["id"]

    r = await client.patch(
        f"/api/v1/manga/{manga_id}",
        json={"author": "Kentaro Miura"},
        headers=h,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["author"] == "Kentaro Miura"


async def test_update_manga_ignores_direct_rating_change(client, admin_token, auth_header):
    h = auth_header(admin_token)
    manga_id = (await _create_manga(client, h)).json()["id"]

    # Rating is now derived from votes; admin PATCH cannot override it.
    r = await client.patch(f"/api/v1/manga/{manga_id}", json={"rating": 9.8}, headers=h)
    assert r.status_code == 200
    assert r.json()["rating"] == 0.0


async def test_delete_requires_admin(client, admin_token, user_token, auth_header):
    manga_id = (await _create_manga(client, auth_header(admin_token))).json()["id"]

    forbid = await client.delete(f"/api/v1/manga/{manga_id}", headers=auth_header(user_token))
    assert forbid.status_code == 403

    ok = await client.delete(f"/api/v1/manga/{manga_id}", headers=auth_header(admin_token))
    assert ok.status_code == 200

    missing = await client.get(f"/api/v1/manga/{manga_id}")
    assert missing.status_code == 404


async def test_nonexistent_manga_returns_404(client):
    r = await client.get("/api/v1/manga/9999")
    assert r.status_code == 404
