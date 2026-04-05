import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def reset_items() -> None:
    app.state.items = []
    yield
    app.state.items = []


client = TestClient(app)


def test_root_returns_message() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "AI-Powered CI/CD Pipeline"}


def test_list_items_starts_empty() -> None:
    response = client.get("/items")

    assert response.status_code == 200
    assert response.json() == []


def test_create_item_returns_201() -> None:
    response = client.post(
        "/items",
        json={"name": "Notebook", "description": "Work notes", "price": 12.5},
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "name": "Notebook",
        "description": "Work notes",
        "price": 12.5,
    }


def test_created_item_is_persisted() -> None:
    client.post("/items", json={"name": "Notebook", "price": 12.5})

    response = client.get("/items")

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "name": "Notebook", "description": None, "price": 12.5}
    ]


def test_second_item_gets_incremented_id() -> None:
    client.post("/items", json={"name": "Notebook", "price": 12.5})
    response = client.post("/items", json={"name": "Pen", "price": 2.0})

    assert response.status_code == 201
    assert response.json()["id"] == 2


def test_items_list_reflects_multiple_creates() -> None:
    client.post("/items", json={"name": "Notebook", "price": 12.5})
    client.post("/items", json={"name": "Pen", "price": 2.0})

    response = client.get("/items")

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["Notebook", "Pen"]


def test_duplicate_item_name_returns_400() -> None:
    client.post("/items", json={"name": "Notebook", "price": 12.5})
    response = client.post("/items", json={"name": "Notebook", "price": 14.0})

    assert response.status_code == 400
    assert response.json()["detail"] == "Item with this name already exists."


def test_missing_name_returns_422() -> None:
    response = client.post("/items", json={"price": 12.5})

    assert response.status_code == 422


def test_empty_name_returns_422() -> None:
    response = client.post(
        "/items",
        json={"name": "", "description": "Work notes", "price": 12.5},
    )

    assert response.status_code == 422


def test_whitespace_name_is_allowed() -> None:
    response = client.post("/items", json={"name": "  spaced  ", "price": 12.5})

    assert response.status_code == 201
    assert response.json()["name"] == "  spaced  "


def test_missing_price_returns_422() -> None:
    response = client.post("/items", json={"name": "Notebook"})

    assert response.status_code == 422


def test_negative_price_returns_422() -> None:
    response = client.post(
        "/items",
        json={"name": "Notebook", "price": -1},
    )

    assert response.status_code == 422


def test_openapi_includes_three_routes() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert set(paths) == {"/", "/health", "/items"}
    assert set(paths["/items"]) == {"get", "post"}


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
