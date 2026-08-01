def test_security_headers_present(client):
    resp = client.get("/api/health")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    csp = resp.headers.get("Content-Security-Policy") or ""
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
