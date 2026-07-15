from app import app


def test_favicon_route_serves_the_svg_app_icon():
    response = app.test_client().get("/favicon.ico")

    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
