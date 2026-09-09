import Button from './Button.jsx';
import Icon from './Icon.jsx';
import { number } from '../../lib/format.js';

/** Offset pagination. Hidden entirely when everything fits on one page. */
export default function Pagination({ total, limit, offset, onChange, noun = 'rows' }) {
  if (total <= limit) return null;

  const page = Math.floor(offset / limit) + 1;
  const pages = Math.ceil(total / limit);
  const first = offset + 1;
  const last = Math.min(offset + limit, total);

  return (
    <div className="pagination">
      <span>
        {number(first)}–{number(last)} of {number(total)} {noun}
      </span>
      <div className="u-row">
        <Button
          size="sm"
          disabled={page <= 1}
          onClick={() => onChange(Math.max(offset - limit, 0))}
          aria-label="Previous page"
        >
          <Icon name="chevronLeft" size={13} />
        </Button>
        <span className="u-xs u-nowrap">
          Page {page} of {pages}
        </span>
        <Button
          size="sm"
          disabled={page >= pages}
          onClick={() => onChange(offset + limit)}
          aria-label="Next page"
        >
          <Icon name="chevronRight" size={13} />
        </Button>
      </div>
    </div>
  );
}
