import pytest_asyncio


async def _create_manga(client, admin_header):
    r = await client.post(
        "/api/v1/manga/",
        json={"title": "Chainsaw Man", "description": "Devil hunter."},
        headers=admin_header,
    )
    return r.json()["id"]


@pytest_asyncio.fixture
async def second_user_token(client, session_factory):
    r = await client.post("/api/v1/auth/register", json={
        "username": "carol",
        "email": "carol@example.com",
        "password": "tr0ub4dor&3",
    })
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


async def test_rating_requires_auth_for_write(client, admin_token, auth_header):
    manga_id = await _create_manga(client, auth_header(admin_token))
    r = await client.put(f"/api/v1/manga/{manga_id}/rating/", json={"score": 8})
    assert r.status_code == 401


async def test_rating_status_anonymous(client, admin_token, auth_header):
    manga_id = await _create_manga(client, auth_header(admin_token))
    r = await client.get(f"/api/v1/manga/{manga_id}/rating/")
    assert r.status_code == 200
    body = r.json()
    assert body == {"manga_id": manga_id, "average": 0.0, "count": 0, "my_score": None}


async def test_upsert_then_replace(client, admin_token, user_token, auth_header):
    manga_id = await _create_manga(client, auth_header(admin_token))
    h = auth_header(user_token)

    first = await client.put(f"/api/v1/manga/{manga_id}/rating/", json={"score": 9}, headers=h)
    assert first.status_code == 200
    body = first.json()
    assert body["average"] == 9.0
    assert body["count"] == 1
    assert body["my_score"] == 9

    second = await client.put(f"/api/v1/manga/{manga_id}/rating/", json={"score": 5}, headers=h)
    assert second.status_code == 200
    assert second.json() == {
        "manga_id": manga_id,
        "average": 5.0,
        "count": 1,
        "my_score": 5,
    }


async def test_average_across_two_users(
    client, admin_token, user_token, second_user_token, auth_header
):
    manga_id = await _create_manga(client, auth_header(admin_token))
    await client.put(f"/api/v1/manga/{manga_id}/rating/", json={"score": 8},
                     headers=auth_header(user_token))
    await client.put(f"/api/v1/manga/{manga_id}/rating/", json={"score": 6},
                     headers=auth_header(second_user_token))

    r = await client.get(f"/api/v1/manga/{manga_id}/rating/")
    body = r.json()
    assert body["count"] == 2
    assert body["average"] == 7.0


async def test_delete_rating_removes_my_vote(client, admin_token, user_token, auth_header):
    manga_id = await _create_manga(client, auth_header(admin_token))
    h = auth_header(user_token)

    await client.put(f"/api/v1/manga/{manga_id}/rating/", json={"score": 7}, headers=h)
    r = await client.delete(f"/api/v1/manga/{manga_id}/rating/", headers=h)
    assert r.status_code == 200
    assert r.json() == {"manga_id": manga_id, "average": 0.0, "count": 0, "my_score": None}


async def test_score_must_be_in_range(client, admin_token, user_token, auth_header):
    manga_id = await _create_manga(client, auth_header(admin_token))
    h = auth_header(user_token)

    too_low = await client.put(f"/api/v1/manga/{manga_id}/rating/", json={"score": 0}, headers=h)
    assert too_low.status_code == 422
    too_high = await client.put(f"/api/v1/manga/{manga_id}/rating/", json={"score": 11}, headers=h)
    assert too_high.status_code == 422


async def test_rating_for_missing_manga_returns_404(client, user_token, auth_header):
    r = await client.put(
        "/api/v1/manga/99999/rating/", json={"score": 5}, headers=auth_header(user_token)
    )
    assert r.status_code == 404
