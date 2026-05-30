async def test_dashboard_home_renders_lightweight_ui(client):
    response = await client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "GitHub Sentinel Dashboard" in response.text
    assert "仓库地址" in response.text
    assert "访问令牌（可选）" in response.text
    assert "订阅间隔（秒）" in response.text
    assert "查看报告" in response.text
    assert "生成报告" in response.text
    assert "按订阅间隔抓取" in response.text
    assert "删除订阅" in response.text
    assert "content_markdown" in response.text
    assert "markdown" in response.text
    assert 'id="reportStartDateInput"' in response.text
    assert 'id="reportEndDateInput"' in response.text
    assert "data-select-subscription-id" in response.text
    assert "data-generate-report-id" in response.text
    assert "/api/subscriptions" in response.text
