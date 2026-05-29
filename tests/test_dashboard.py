async def test_dashboard_home_renders_lightweight_ui(client):
    response = await client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "GitHub Sentinel Dashboard" in response.text
    assert "仓库地址" in response.text
    assert "访问令牌（可选）" in response.text
    assert "订阅间隔（秒）" in response.text
    assert "已加密存储" in response.text
    assert "删除订阅" in response.text
    assert "报告时间范围" in response.text
    assert "最近 24 小时" in response.text
    assert "deleteSubscription" in response.text
    assert "reportWindowSelect" in response.text
    assert "/api/subscriptions" in response.text
    assert "/api/reports" in response.text
