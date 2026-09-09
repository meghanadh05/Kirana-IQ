"""Product catalogue rules: validation, opening stock and CSV import/export.

Stock never changes here except through the ledger. A product created with an
opening stock of 40 gets an OPENING_STOCK movement for those 40 units, so the
answer to "where did this stock come from?" is never "it was just there".
"""

from __future__ import annotations

import csv
import io
import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from psycopg.errors import UniqueViolation

from app.database import transaction
from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import category as category_model
from app.models import inventory as inventory_model
from app.models import product as product_model

logger = logging.getLogger(__name__)

UNITS = ("piece", "kg", "gram", "litre", "ml", "packet", "box")

CSV_COLUMNS = [
    "sku", "barcode", "name", "description", "category", "brand", "unit",
    "selling_price", "cost_price", "tax_rate", "current_stock", "reorder_level",
    "lead_time_days",
]


def _validate(data: dict[str, Any]) -> None:
    if data.get("unit") and data["unit"] not in UNITS:
        raise ValidationError(f"unit must be one of {list(UNITS)}")
    # Selling below cost is legal but almost always a typo, so it is surfaced
    # rather than silently accepted.
    selling = data.get("selling_price")
    cost = data.get("cost_price")
    if selling is not None and cost is not None and Decimal(str(cost)) > Decimal(str(selling)):
        logger.info("Product %s has cost above selling price", data.get("sku"))


def _duplicate_error(exc: UniqueViolation, data: dict[str, Any]) -> ConflictError:
    message = str(exc)
    if "barcode" in message:
        return ConflictError(f"Barcode '{data.get('barcode')}' is already used in this store")
    return ConflictError(f"SKU '{data.get('sku')}' already exists in this store")


def create_product(store_id: int, payload: dict[str, Any], user_id: int) -> dict[str, Any]:
    """Create a product and, when it starts with stock, open its ledger."""
    _validate(payload)
    opening_stock = int(payload.pop("current_stock", 0) or 0)

    data = {
        **payload,
        "store_id": store_id,
        # Stock starts at zero and arrives through a ledger movement below, so
        # the opening quantity is recorded rather than assumed.
        "current_stock": 0,
        # An empty barcode must be NULL, not '': the unique index treats every
        # empty string as the same barcode, so the second product would fail.
        "barcode": payload.get("barcode") or None,
    }

    try:
        product = product_model.create_product(data)
    except UniqueViolation as exc:
        raise _duplicate_error(exc, data) from exc

    category_model.ensure(store_id, product["category"])

    if opening_stock > 0:
        with transaction() as conn:
            inventory_model.apply_movement(
                conn,
                store_id=store_id,
                product_id=product["id"],
                quantity_change=opening_stock,
                transaction_type="OPENING_STOCK",
                reference_type="PRODUCT",
                reference_id=product["id"],
                notes="Opening stock entered when the product was created",
                created_by=user_id,
            )
        product = product_model.get_product(product["id"], store_id)

    return product


def update_product(store_id: int, product_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    if product_model.get_product(product_id, store_id) is None:
        raise NotFoundError(f"Product {product_id} not found")

    _validate(payload)
    if "barcode" in payload:
        payload["barcode"] = payload["barcode"] or None

    try:
        product = product_model.update_product(product_id, store_id, payload)
    except UniqueViolation as exc:
        raise _duplicate_error(exc, payload) from exc

    if product and payload.get("category"):
        category_model.ensure(store_id, product["category"])
    return product


def archive_product(store_id: int, product_id: int) -> dict[str, Any]:
    if product_model.get_product(product_id, store_id) is None:
        raise NotFoundError(f"Product {product_id} not found")
    product_model.archive_product(product_id, store_id)
    return product_model.get_product(product_id, store_id)


def get_product(store_id: int, product_id: int) -> dict[str, Any]:
    product = product_model.get_product(product_id, store_id)
    if product is None:
        raise NotFoundError(f"Product {product_id} not found")
    return product


def lookup_barcode(store_id: int, barcode: str) -> dict[str, Any]:
    """The POS scan path: exact barcode, then exact SKU as a fallback.

    Keyboard-wedge scanners type the code and press Enter, so a manually typed
    SKU arrives through exactly the same channel and should work too.
    """
    product = product_model.get_product_by_barcode(barcode, store_id)
    if product is None:
        product = product_model.get_product_by_sku(barcode, store_id)
    if product is None:
        raise NotFoundError(f"No product matches '{barcode}'")
    if not product["is_active"]:
        raise ValidationError(f"{product['name']} is archived and cannot be sold")
    return product


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------


def export_csv(store_id: int) -> str:
    rows = product_model.list_products(store_id, is_active=None, limit=10000)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column) for column in CSV_COLUMNS})
    return buffer.getvalue()


def _decimal(value: str | None, field: str, default: str = "0") -> Decimal:
    try:
        parsed = Decimal((value or default).strip() or default)
    except (InvalidOperation, AttributeError) as exc:
        raise ValidationError(f"{field} must be a number, got '{value}'") from exc
    if parsed < 0:
        raise ValidationError(f"{field} cannot be negative")
    return parsed


def _integer(value: str | None, field: str, default: str = "0") -> int:
    try:
        parsed = int(float((value or default).strip() or default))
    except (ValueError, AttributeError) as exc:
        raise ValidationError(f"{field} must be a whole number, got '{value}'") from exc
    if parsed < 0:
        raise ValidationError(f"{field} cannot be negative")
    return parsed


def import_csv(store_id: int, content: str, user_id: int) -> dict[str, Any]:
    """Import a catalogue. Rows are independent: one bad row is reported, not fatal.

    An all-or-nothing import would make a 500-row file unusable because of a
    single typo, and the shop owner cannot see which row broke it.
    """
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise ValidationError("The CSV file is empty")

    headers = {name.strip().lower() for name in reader.fieldnames}
    for required in ("sku", "name", "category", "selling_price"):
        if required not in headers:
            raise ValidationError(
                f"Missing required column '{required}'. "
                f"Expected columns: {', '.join(CSV_COLUMNS)}"
            )

    created, updated = 0, 0
    errors: list[dict[str, Any]] = []

    for line_number, raw in enumerate(reader, start=2):
        row = {(key or "").strip().lower(): (value or "").strip() for key, value in raw.items()}
        if not row.get("sku"):
            continue

        try:
            payload = {
                "sku": row["sku"],
                "barcode": row.get("barcode") or None,
                "name": row.get("name") or row["sku"],
                "description": row.get("description") or None,
                "category": row.get("category") or "Uncategorised",
                "brand": row.get("brand") or None,
                "unit": row.get("unit") or "piece",
                "selling_price": _decimal(row.get("selling_price"), "selling_price"),
                "cost_price": _decimal(row.get("cost_price"), "cost_price"),
                "tax_rate": _decimal(row.get("tax_rate"), "tax_rate"),
                "current_stock": _integer(row.get("current_stock"), "current_stock"),
                "reorder_level": _integer(row.get("reorder_level"), "reorder_level"),
                "lead_time_days": _integer(row.get("lead_time_days"), "lead_time_days", "3"),
                "supplier_id": None,
                "is_active": True,
            }
            _validate(payload)

            existing = product_model.get_product_by_sku(payload["sku"], store_id)
            if existing:
                stock = payload.pop("current_stock")
                product_model.update_product(existing["id"], store_id, payload)
                _reconcile_stock(store_id, existing, stock, user_id)
                category_model.ensure(store_id, payload["category"])
                updated += 1
            else:
                create_product(store_id, payload, user_id)
                created += 1
        except (ValidationError, ConflictError) as exc:
            errors.append({"row": line_number, "sku": row.get("sku"), "error": exc.detail})
        except Exception as exc:  # noqa: BLE001 - one bad row must not stop the import
            logger.exception("Import failed on row %s", line_number)
            errors.append({"row": line_number, "sku": row.get("sku"), "error": str(exc)})

    return {"created": created, "updated": updated, "failed": len(errors), "errors": errors[:50]}


def _reconcile_stock(
    store_id: int, existing: dict[str, Any], target_stock: int, user_id: int
) -> None:
    """Move an imported product's stock to the file's figure, through the ledger."""
    difference = target_stock - int(existing["current_stock"])
    if difference == 0:
        return
    with transaction() as conn:
        inventory_model.apply_movement(
            conn,
            store_id=store_id,
            product_id=existing["id"],
            quantity_change=difference,
            transaction_type="MANUAL_ADJUSTMENT",
            reference_type="CSV_IMPORT",
            notes="Stock set by catalogue import",
            created_by=user_id,
        )
