"""Product catalogue endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, Response, UploadFile, status

from app.deps import ManagerStore, Store
from app.errors import ValidationError
from app.models import product as product_model
from app.schemas.product import (
    CatalogueStats,
    ImportResult,
    ProductCreate,
    ProductOut,
    ProductPage,
    ProductUpdate,
    StockStatus,
)
from app.services import product_service

router = APIRouter(prefix="/products", tags=["products"])

MAX_IMPORT_BYTES = 5 * 1024 * 1024


@router.get("", response_model=ProductPage)
def list_products(
    context: Store,
    category: str | None = Query(default=None, description="Exact category match"),
    brand: str | None = Query(default=None),
    supplier_id: int | None = Query(default=None, gt=0),
    search: str | None = Query(default=None, description="Name, SKU, brand or exact barcode"),
    stock_status: StockStatus | None = Query(default=None),
    include_archived: bool = Query(default=False),
    sort: str = Query(default="name"),
    direction: str = Query(default="asc", pattern="^(asc|desc)$"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """A filtered, sorted page of the store's catalogue."""
    filters = {
        "category": category,
        "brand": brand,
        "supplier_id": supplier_id,
        "search": search,
        "stock_status": stock_status,
        "is_active": None if include_archived else True,
    }
    return {
        "items": product_model.list_products(
            context.store_id, sort=sort, direction=direction, limit=limit, offset=offset, **filters
        ),
        "total": product_model.count_products(context.store_id, **filters),
        "limit": limit,
        "offset": offset,
    }


@router.get("/categories", response_model=list[str])
def list_categories(context: Store) -> list[str]:
    """Distinct categories in use, for populating filters."""
    return product_model.list_categories(context.store_id)


@router.get("/brands", response_model=list[str])
def list_brands(context: Store) -> list[str]:
    return product_model.list_brands(context.store_id)


@router.get("/stats", response_model=CatalogueStats)
def catalogue_stats(context: Store) -> dict:
    """Counts and inventory valuation for the catalogue header."""
    return product_model.catalogue_stats(context.store_id)


@router.get("/export", response_class=Response)
def export_products(context: Store) -> Response:
    """Download the catalogue as CSV."""
    return Response(
        content=product_service.export_csv(context.store_id),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="products.csv"'},
    )


@router.post("/import", response_model=ImportResult)
async def import_products(context: ManagerStore, file: UploadFile) -> dict:
    """Import or update products from a CSV file. Rows fail independently."""
    raw = await file.read()
    if len(raw) > MAX_IMPORT_BYTES:
        raise ValidationError("CSV file is too large (limit 5 MB)")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("CSV file must be UTF-8 encoded") from exc

    return product_service.import_csv(context.store_id, content, context.user_id)


@router.get("/barcode/{barcode}", response_model=ProductOut)
def lookup_barcode(barcode: str, context: Store) -> dict:
    """Resolve a scanned (or typed) barcode to a sellable product."""
    return product_service.lookup_barcode(context.store_id, barcode)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, context: Store) -> dict:
    return product_service.get_product(context.store_id, product_id)


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, context: ManagerStore) -> dict:
    """Create a product. SKUs and barcodes are unique within a store."""
    return product_service.create_product(
        context.store_id, payload.model_dump(), context.user_id
    )


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(product_id: int, payload: ProductUpdate, context: ManagerStore) -> dict:
    return product_service.update_product(
        context.store_id, product_id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/{product_id}", response_model=ProductOut)
def archive_product(product_id: int, context: ManagerStore) -> dict:
    """Archive a product. Sales history references it, so it is never deleted."""
    return product_service.archive_product(context.store_id, product_id)
