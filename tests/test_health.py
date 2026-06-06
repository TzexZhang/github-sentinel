async def test_health_check_returns_ok(client):
    # 健康检查用于确认应用和路由注册正常。
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"code": 200, "data": {"status": "ok"}, "success": True}


async def test_runtime_status_returns_instance_id(client):
    response = await client.get("/api/runtime")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["instance_id"], str)
    assert payload["instance_id"]


async def test_dashboard_route_serves_gradio_ui(client):
    response = await client.get("/dashboard/")

    assert response.status_code == 200
    assert "Git Sentinel Dashboard" in response.text
