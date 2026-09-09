import { useState } from 'react';

import PageHeader from '../../components/layout/PageHeader.jsx';
import Button from '../../components/ui/Button.jsx';
import Card from '../../components/ui/Card.jsx';
import Icon from '../../components/ui/Icon.jsx';
import { AsyncSection, CardSkeleton } from '../../components/ui/States.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import { useApi } from '../../hooks/useApi.js';
import * as api from '../../services/api.js';

const PERIODS = [
  { id: 'today', label: 'Today' },
  { id: '7d', label: 'Last 7 days' },
  { id: '30d', label: 'Last 30 days' },
  { id: '90d', label: 'Last 90 days' },
  { id: '365d', label: 'Last year' },
];

const ICONS = {
  'daily-sales': 'sales',
  invoices: 'sales',
  'product-sales': 'products',
  inventory: 'inventory',
  'low-stock': 'warning',
  profit: 'money',
  tax: 'reports',
  purchases: 'purchases',
  expenses: 'expenses',
};

export default function Reports() {
  const toast = useToast();
  const [period, setPeriod] = useState('30d');
  const [custom, setCustom] = useState({ start_date: '', end_date: '' });
  const [downloading, setDownloading] = useState(null);

  const reports = useApi(() => api.listReports(), []);

  async function download(report) {
    setDownloading(report.id);
    try {
      const params =
        period === 'custom' && custom.start_date && custom.end_date ? custom : { period };
      await api.downloadReport(report.id, params);
      toast.success(`${report.label} downloaded`);
    } catch (error) {
      toast.error(error.message);
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="page">
      <PageHeader
        title="Reports"
        subtitle="Download your numbers as CSV, for accounting or your own spreadsheets."
        actions={
          <div className="u-row">
            <select
              className="select"
              style={{ width: 170 }}
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
              aria-label="Reporting period"
            >
              {PERIODS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
              <option value="custom">Custom range</option>
            </select>
            {period === 'custom' ? (
              <>
                <input
                  type="date"
                  className="input"
                  style={{ width: 150 }}
                  value={custom.start_date}
                  onChange={(event) => setCustom({ ...custom, start_date: event.target.value })}
                  aria-label="From date"
                />
                <input
                  type="date"
                  className="input"
                  style={{ width: 150 }}
                  value={custom.end_date}
                  onChange={(event) => setCustom({ ...custom, end_date: event.target.value })}
                  aria-label="To date"
                />
              </>
            ) : null}
          </div>
        }
      />

      <AsyncSection
        loading={reports.loading}
        error={reports.error}
        onRetry={reports.reload}
        skeleton={
          <div className="grid grid--3">
            {Array.from({ length: 6 }).map((_, index) => (
              <CardSkeleton key={index} height={130} />
            ))}
          </div>
        }
      >
        <div className="grid grid--3">
          {(reports.data || []).map((report) => (
            <Card key={report.id}>
              <div className="u-col" style={{ gap: 'var(--s3)' }}>
                <div className="feature__icon" style={{ marginBottom: 0 }}>
                  <Icon name={ICONS[report.id] || 'reports'} size={16} />
                </div>
                <div>
                  <h3 className="card__title">{report.label}</h3>
                  <p className="u-small u-muted" style={{ marginTop: 4 }}>
                    {report.description}
                  </p>
                </div>
                <Button
                  icon="download"
                  block
                  loading={downloading === report.id}
                  disabled={period === 'custom' && (!custom.start_date || !custom.end_date)}
                  onClick={() => download(report)}
                >
                  Download CSV
                </Button>
              </div>
            </Card>
          ))}
        </div>
      </AsyncSection>
    </div>
  );
}
