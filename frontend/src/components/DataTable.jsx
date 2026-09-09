import { Empty } from './States.jsx';

/**
 * Minimal table renderer.
 *
 * `columns` is [{ key, label, align, render }]. `render` receives the whole row,
 * so cells can show badges or derived values.
 */
export default function DataTable({ columns, rows, empty = 'No rows.', rowKey = (row) => row.id }) {
  if (!rows?.length) return <Empty label={empty} />;

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} className={column.align === 'right' ? 'right' : undefined}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td key={column.key} className={column.align === 'right' ? 'right' : undefined}>
                  {column.render ? column.render(row) : row[column.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
