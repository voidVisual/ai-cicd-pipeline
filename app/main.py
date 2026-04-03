from typing import List, Optional

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field


app = FastAPI(title="AI-Powered CI/CD Pipeline")
app.state.items = []


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=300)
    price: float = Field(gt=0)


class Item(ItemCreate):
    id: int


@app.get("/")
def read_root() -> dict:
    return {"message": "AI-Powered CI/CD Pipeline"}


@app.get("/items", response_model=List[Item])
def list_items() -> List[Item]:
    return app.state.items


@app.post("/items", response_model=Item, status_code=status.HTTP_201_CREATED)
def create_item(item: ItemCreate) -> Item:
    for existing_item in app.state.items:
        if existing_item["name"] == item.name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item with this name already exists.",
            )

    item_id = len(app.state.items) + 1
    created_item = Item(id=item_id, **item.model_dump())
    app.state.items.append(created_item.model_dump())
    return created_item
