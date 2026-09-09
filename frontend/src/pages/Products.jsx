import { useState } from 'react';

import DataTable from '../components/DataTable.jsx';
import { ErrorState, Loading } from '../components/States.jsx';
import { useApi } from '../hooks/useApi.js';
import { getCategories, getProducts } from '../services/api.js';

export default function Products() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');

  const categories = useApi(getCategories);
  const products = useApi(() => getProducts({ search, category }), [search, category]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Products</h1>
          <p className="muted">{products.data ? `${products.data.length} shown` : 'Catalogue'}</p>
        </div>
        <div className="filters">
          <input
            className="input"
            type="search"
            placeholder="Search name or SKU…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <select className="input" value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="">All categories</option>
            {(categories.data ?? []).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {products.loading && <Loading />}
      {products.error && <ErrorState error={products.error} onRetry={products.reload} />}

      {products.data && (
        <section className="panel">
          <DataTable
            rows={products.data}
            empty="No products match those filters."
            columns={[
              { key: 'sku', label: 'SKU' },
              { key: 'name', label: 'Product' },
              { key: 'category', label: 'Category' },
              { key: 'unit_price', label: 'Price', align: 'right', render: (row) => `₹${row.unit_price}` },
              { key: 'current_stock', label: 'Stock', align: 'right' },
              { key: 'reorder_level', label: 'Reorder level', align: 'right' },
              { key: 'lead_time_days', label: 'Lead time', align: 'right', render: (row) => `${row.lead_time_days}d` },
            ]}
          />
        </section>
      )}
    </>
  );
}
