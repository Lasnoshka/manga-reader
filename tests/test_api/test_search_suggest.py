async def _create(client, admin_header, title, author=None):
    r = await client.post(
        "/api/v1/manga/",
        json={
            "title": title,
            "description": "desc",
            "author": author,
        },
        headers=admin_header,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_suggest_exact_substring(client, admin_token, auth_header):
    h = auth_header(admin_token)
    await _create(client, h, "Berserk", author="Kentaro Miura")
    await _create(client, h, "Naruto", author="Masashi Kishimoto")
    await _create(client, h, "Vinland Saga", author="Makoto Yukimura")

    r = await client.get("/api/v1/search/suggest?q=berserk")
    assert r.status_code == 200
    body = r.json()
    assert any(item["title"] == "Berserk" for item in body)


async def test_suggest_corrects_single_typo(client, admin_token, auth_header):
    h = auth_header(admin_token)
    await _create(client, h, "Berserk", author="Kentaro Miura")
    await _create(client, h, "Naruto", author="Masashi Kishimoto")

    r = await client.get("/api/v1/search/suggest?q=berzerk")
    assert r.status_code == 200
    body = r.json()
    titles = [item["title"] for item in body]
    assert "Berserk" in titles


async def test_suggest_handles_author_typo(client, admin_token, auth_header):
    h = auth_header(admin_token)
    await _create(client, h, "Vinland Saga", author="Makoto Yukimura")
    await _create(client, h, "Naruto", author="Masashi Kishimoto")

    r = await client.get("/api/v1/search/suggest?q=yukimura")
    body = r.json()
    titles = [item["title"] for item in body]
    assert "Vinland Saga" in titles


async def test_suggest_respects_limit(client, admin_token, auth_header):
    h = auth_header(admin_token)
    for i in range(8):
        await _create(client, h, f"Demon Slayer Vol {i}")

    r = await client.get("/api/v1/search/suggest?q=demon&limit=3")
    body = r.json()
    assert len(body) <= 3


async def test_suggest_empty_query_rejected(client):
    r = await client.get("/api/v1/search/suggest?q=")
    assert r.status_code == 422


async def test_search_finds_with_typo(client, admin_token, auth_header):
    h = auth_header(admin_token)
    await _create(client, h, "Attack on Titan")
    await _create(client, h, "Tokyo Ghoul")

    r = await client.get("/api/v1/search?q=atak%20on%20titan")
    assert r.status_code == 200
    titles = [item["title"] for item in r.json()]
    assert "Attack on Titan" in titles
