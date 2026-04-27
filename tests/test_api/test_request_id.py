async def test_request_id_echoed_when_provided(client):
    r = await client.get("/health", headers={"X-Request-ID": "trace-abc-123"})
    assert r.headers.get("X-Request-ID") == "trace-abc-123"


async def test_request_id_generated_when_missing(client):
    r = await client.get("/health")
    rid = r.headers.get("X-Request-ID")
    assert rid is not None
    assert len(rid) >= 16
