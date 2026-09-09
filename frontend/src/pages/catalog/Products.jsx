import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import ProductForm from './ProductForm.jsx';
import PageHeader from '../../components/layout/PageHeader.jsx';
import Button from '../../components/ui/Button.jsx';
import Card from '../../components/ui/Card.jsx';
import Icon from '../../components/ui/Icon.jsx';
import Pagination from '../../components/ui/Pagination.jsx';
import Table from '../../components/ui/Table.jsx';
import { StockBadge } from '../../components/ui/Badge.jsx';
import { AsyncSection, EmptyState, TableSkeleton } from '../../components/ui/States.jsx';
import { useCan } from '../../context/AuthContext.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import { useApi } from '../../hooks/useApi.js';
import { useDebounce } from '../../hooks/useDebounce.js';
import * as api from '../../services/api.js';
import { currency, number } from '../../lib/format.js';

const LIMIT = 25;

export default function Products() {
  const navigate = useNavigate();
  const toast = useToast();
  const canManage = useCan('MANAGER');
  const fileInput = useRef(null);

  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [stockStatus, setStockStatus] = useState('');
  const [includeArchived, setIncludeArchived] = useState(false);
  const [sort, setSort] = useState({ key: 'name', direction: 'asc' });
  const [offset, setOffset] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [importing, setImporting] = useState(false);

  const debouncedSearch = useDebounce(search, 300);

  const products = useApi(
    () =>
      api.listProducts({
        search: debouncedSearch || undefined,
        category: category || undefined,
        stock_status: stockStatus || undefined,
        include_archived: includeArchived || undefined,
        sort: sort.key,
        direction: sort.direction,
        limit: LIMIT,
        offset,
      }),
    [debouncedSearch, category, stockStatus, includeArchived, sort.key, sort.direction, offset],
  );
  const categories = useApi(() => api.getProductCategories(), []);
  const stats = useApi(() => api.getCatalogueStats(), [formOpen]);

  const rows = products.data?.items || [];
  const filtered = Boolean(debouncedSearch || category || stockStatus);

  async function onImport(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    setImporting(true);
    try {
      const result = await api.importProducts(file);
      const summary = `${result.created} created, ${result.updated} updated`;
      if (result.failed) {
        toast.error(`${summary}, ${result.failed} row(s) failed. First: ${result.errors[0]?.error}`);
      } else {
        toast.success(`Import complete — ${summary}`);
      }
      products.reload();
      categories.reload();
      stats.reload();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setImporting(false);
      if (fileInput.current) fileInput.current.value = '';
    }
  }

  const columns = [
    {
      key: 'name',
      header: 'Product',
      sortKey: 'name',
      render: (row) => (
        <div>
          <div className="table__primary">
            {row.name}
            {!row.is_active ? <span className="u-xs u-subtle"> · archived</span> : null}
          </div>
          <div className="table__secondary u-mono">
            {row.sku}
            {row.barcode ? ` · ${row.barcode}` : ''}
          </div>
        </div>
      ),
    },
    {
      key: 'category',
      header: 'Category',
      sortKey: 'category',
      render: (row) => (
        <div>
          <div className="u-small">{row.category}</div>
          {row.brand ? <div className="table__secondary">{row.brand}</div> : null}
        </div>
      ),
    },
    {
      key: 'price',
      header: 'Price',
      sortKey: 'price',
      align: 'right',
      render: (row) => (
        <div>
          <div className="u-num">{currency(row.selling_price)}</div>
          <div className="table__secondary u-num">cost {currency(row.cost_price)}</div>
        </div>
      ),
    },
    {
      key: 'margin',
      header: 'Margin',
      align: 'right',
      render: (row) => {
        const selling = Number(row.selling_price);
        const cost = Number(row.cost_price);
        // Margin against a zero cost is not 100%, it is unknown.
        if (!selling || !cost) return <span className="u-subtle">—</span>;
        const margin = ((selling - cost) / selling) * 100;
        return <span className="u-num u-small">{margin.toFixed(0)}%</span>;
      },
    },
    {
      key: 'stock',
      header: 'Stock',
      sortKey: 'stock',
      align: 'right',
      render: (row) => (
        <div>
          <div className="u-num u-strong">
            {number(row.current_stock)} <span className="u-subtle u-xs">{row.unit}</span>
          </div>
          <div className="table__secondary">reorder at {number(row.reorder_level)}</div>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => (
        <StockBadge
          status={
            row.current_stock <= 0
              ? 'OUT_OF_STOCK'
              : row.current_stock <= row.reorder_level
                ? 'LOW'
                : 'OK'
          }
        />
      ),
    },
  ];

  return (
    <div className="page">
      <PageHeader
        title="Products"
        subtitle="Your catalogue, prices and stock levels."
        actions={
          canManage ? (
            <>
              <input
                ref={fileInput}
                type="file"
                accept=".csv,text/csv"
                onChange={onImport}
                className="u-visually-hidden"
              />
              <Button icon="upload" loading={importing} onClick={() => fileInput.current?.click()}>
                Import CSV
              </Button>
              <Button icon="download" onClick={() => api.exportProducts()}>
                Export
              </Button>
              <Button variant="primary" icon="plus" onClick={() => setFormOpen(true)}>
                Add product
              </Button>
            </>
          ) : null
        }
      />

      {stats.data ? (
        <div className="grid grid--kpi" style={{ marginBottom: 'var(--s5)' }}>
          <div className="stat">
            <span className="stat__label">Active products</span>
            <span className="stat__value stat__value--sm">{number(stats.data.total)}</span>
          </div>
          <div className={`stat${stats.data.low_stock ? ' stat--warn' : ''}`}>
            <span className="stat__label">Low stock</span>
            <span className="stat__value stat__value--sm">{number(stats.data.low_stock)}</span>
          </div>
          <div className={`stat${stats.data.out_of_stock ? ' stat--alert' : ''}`}>
            <span className="stat__label">Out of stock</span>
            <span className="stat__value stat__value--sm">{number(stats.data.out_of_stock)}</span>
          </div>
          <div className="stat">
            <span className="stat__label">Inventory value</span>
            <span className="stat__value stat__value--sm">
              {currency(stats.data.inventory_cost_value, { compact: true })}
            </span>
            <span className="stat__meta">at cost price</span>
          </div>
        </div>
      ) : null}

      <Card flush>
        <div className="toolbar">
          <div className="search-input">
            <Icon name="search" size={14} />
            <input
              className="input"
              placeholder="Name, SKU, brand or barcode"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setOffset(0);
              }}
              aria-label="Search products"
            />
          </div>

          <select
            className="select"
            style={{ width: 160 }}
            value={category}
            onChange={(event) => {
              setCategory(event.target.value);
              setOffset(0);
            }}
            aria-label="Category"
          >
            <option value="">All categories</option>
            {(categories.data || []).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>

          <select
            className="select"
            style={{ width: 150 }}
            value={stockStatus}
            onChange={(event) => {
              setStockStatus(event.target.value);
              setOffset(0);
            }}
            aria-label="Stock status"
          >
            <option value="">All stock</option>
            <option value="in">In stock</option>
            <option value="low">Low stock</option>
            <option value="out">Out of stock</option>
          </select>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={(event) => setIncludeArchived(event.target.checked)}
            />
            Show archived
          </label>

          <div className="toolbar__spacer" />
          <span className="u-xs u-muted">{number(products.data?.total || 0)} products</span>
        </div>

        <AsyncSection
          loading={products.loading}
          error={products.error}
          onRetry={products.reload}
          isEmpty={rows.length === 0}
          skeleton={<TableSkeleton columns={6} />}
          empty={
            <EmptyState
              icon="products"
              title={filtered ? 'No products match' : 'No products yet'}
              message={
                filtered
                  ? 'Try a different search, or clear the filters to see everything.'
                  : 'Add your first product or import your catalogue from a CSV file.'
              }
              actions={
                filtered ? (
                  <Button
                    onClick={() => {
                      setSearch('');
                      setCategory('');
                      setStockStatus('');
                    }}
                  >
                    Clear filters
                  </Button>
                ) : canManage ? (
                  <>
                    <Button variant="primary" icon="plus" onClick={() => setFormOpen(true)}>
                      Add product
                    </Button>
                    <Button icon="upload" onClick={() => fileInput.current?.click()}>
                      Import CSV
                    </Button>
                  </>
                ) : null
              }
            />
          }
        >
          <>
            <Table
              columns={columns}
              rows={rows}
              sort={sort}
              onSortChange={(next) => {
                setSort(next);
                setOffset(0);
              }}
              onRowClick={(row) => navigate(`/app/products/${row.id}`)}
            />
            <Pagination
              total={products.data?.total || 0}
              limit={LIMIT}
              offset={offset}
              onChange={setOffset}
              noun="products"
            />
          </>
        </AsyncSection>
      </Card>

      <ProductForm
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSaved={() => {
          setFormOpen(false);
          products.reload();
          categories.reload();
          stats.reload();
        }}
      />
    </div>
  );
}
