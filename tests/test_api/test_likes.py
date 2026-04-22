async def _create_manga(client, admin_header):
    r = await client.post(
        "/api/v1/manga/",
        json={"title": "Vinland Saga", "description": "Viking saga."},
        headers=admin_header,
    )
    return r.json()["id"]


async def test_like_requires_auth(client, admin_token, auth_header):
    manga_id = await _create_manga(client, auth_header(admin_token))
    r = await client.post(f"/api/v1/manga/{manga_id}/like/")
    assert r.status_code == 401


async def test_like_toggle_flow(client, admin_token, user_token, auth_header):
    manga_id = await _create_manga(client, auth_header(admin_token))
    headers = auth_header(user_token)

    initial = await client.get(f"/api/v1/manga/{manga_id}/like/", headers=headers)
    assert initial.status_code == 200
    assert initial.json() == {"manga_id": manga_id, "likes_count": 0, "liked": False}

    liked = await client.post(f"/api/v1/manga/{manga_id}/like/", headers=headers)
    assert liked.status_code == 201
    assert liked.json() == {"manga_id": manga_id, "likes_count": 1, "liked": True}

    # повторный лайк идемпотентен
    again = await client.post(f"/api/v1/manga/{manga_id}/like/", headers=headers)
    assert again.json()["likes_count"] == 1

    unliked = await client.delete(f"/api/v1/manga/{manga_id}/like/", headers=headers)
    assert unliked.status_code == 200
    assert unliked.json() == {"manga_id": manga_id, "likes_count": 0, "liked": False}


async def test_like_nonexistent_manga_returns_404(client, user_token, auth_header):
    r = await client.post("/api/v1/manga/9999/like/", headers=auth_header(user_token))
    assert r.status_code == 404
