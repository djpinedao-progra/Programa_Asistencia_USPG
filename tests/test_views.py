import pytest


@pytest.mark.parametrize(
    "asset, mimetype",
    [
        ("css/base.css", "text/css"),
        ("css/layout.css", "text/css"),
        ("css/components.css", "text/css"),
        ("css/screens.css", "text/css"),
        ("js/attendance-course.js", "text/javascript"),
        ("js/password-feedback.js", "text/javascript"),
        ("js/live-session.js", "text/javascript"),
        ("js/notice-filter.js", "text/javascript"),
        ("js/qr-scanner.js", "text/javascript"),
        ("js/classroom-schedule.js", "text/javascript"),
        ("img/uspg-official.png", "image/png"),
    ],
)
def test_view_assets_are_served_from_static_url(app, asset, mimetype):
    response = app.test_client().get(f"/static/{asset}")
    try:
        assert response.status_code == 200
        assert response.mimetype == mimetype
    finally:
        response.close()
