import Icon from './Icon.jsx';

/**
 * A thin table wrapper.
 *
 * Columns declare their own rendering, so pages describe what a row means
 * instead of repeating markup. Wide tables scroll inside their own container
 * rather than pushing the page sideways.
 */
export default function Table({
  columns,
  rows,
  rowKey = (row) => row.id,
  onRowClick,
  sort,
  onSortChange,
  emptyMessage = 'No rows',
}) {
  return (
    <div className="table-wrap">
      <table className={`table${onRowClick ? ' table--clickable' : ''}`}>
        <thead>
          <tr>
            {columns.map((column) => {
              const sortable = Boolean(column.sortKey && onSortChange);
              // Both sides can be undefined on an unsorted table, and
              // `undefined === undefined` would mark every column active.
              const active = Boolean(column.sortKey) && sort?.key === column.sortKey;
              return (
                <th
                  key={column.key}
                  className={[column.align === 'right' && 'is-right', sortable && 'is-sortable']
                    .filter(Boolean)
                    .join(' ')}
                  style={column.width ? { width: column.width } : undefined}
                  onClick={
                    sortable
                      ? () =>
                          onSortChange({
                            key: column.sortKey,
                            direction: active && sort.direction === 'asc' ? 'desc' : 'asc',
                          })
                      : undefined
                  }
                  aria-sort={
                    active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : undefined
                  }
                >
                  {column.header}
                  {active ? (
                    <Icon
                      name={sort.direction === 'asc' ? 'arrowUp' : 'arrowDown'}
                      size={11}
                      className="table__sort"
                      style={{ display: 'inline' }}
                    />
                  ) : null}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="u-center u-muted" style={{ padding: '2rem' }}>
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr
                key={rowKey(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                // A clickable row must also be reachable without a mouse.
                tabIndex={onRowClick ? 0 : undefined}
                onKeyDown={
                  onRowClick
                    ? (event) => {
                        if (event.key === 'Enter') onRowClick(row);
                      }
                    : undefined
                }
              >
                {columns.map((column) => (
                  <td key={column.key} className={column.align === 'right' ? 'is-right' : undefined}>
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
