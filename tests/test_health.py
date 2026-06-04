async def test_health_check_returns_ok(client):
    # 健康检查用于确认应用和路由注册正常。
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"code": 200, "data": {"status": "ok"}, "success": True}


async def test_dashboard_route_serves_gradio_ui(client):
    response = await client.get("/dashboard/")

    assert response.status_code == 200
    assert "GitHub Sentinel Dashboard" in response.text
