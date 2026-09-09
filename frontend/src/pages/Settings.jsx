import { useEffect, useState } from 'react';

import PageHeader from '../components/layout/PageHeader.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import Modal, { ConfirmDialog } from '../components/ui/Modal.jsx';
import Table from '../components/ui/Table.jsx';
import Badge from '../components/ui/Badge.jsx';
import { SelectField, TextField } from '../components/ui/Field.jsx';
import { AsyncSection, CardSkeleton } from '../components/ui/States.jsx';
import { useAuth, useCan } from '../context/AuthContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { useApi } from '../hooks/useApi.js';
import * as api from '../services/api.js';
import { date, initials } from '../lib/format.js';

const TABS = [
  { id: 'store', label: 'Store profile' },
  { id: 'inventory', label: 'Inventory & forecasting' },
  { id: 'invoicing', label: 'Tax & invoicing' },
  { id: 'team', label: 'Team' },
  { id: 'profile', label: 'Your account' },
];

const BUSINESS_TYPES = [
  'KIRANA', 'GROCERY', 'MINI_SUPERMARKET', 'PHARMACY', 'CONVENIENCE_STORE', 'OTHER',
];

export default function Settings() {
  const [tab, setTab] = useState('store');

  return (
    <div className="page">
      <PageHeader title="Settings" subtitle="Your store, its policy, and who can use it." />

      <div className="tabs" style={{ marginBottom: 'var(--s5)' }}>
        {TABS.map((option) => (
          <button
            key={option.id}
            type="button"
            className={`tab${tab === option.id ? ' tab--active' : ''}`}
            onClick={() => setTab(option.id)}
          >
            {option.label}
          </button>
        ))}
      </div>

      {tab === 'store' ? <StoreTab /> : null}
      {tab === 'inventory' ? <PolicyTab /> : null}
      {tab === 'invoicing' ? <InvoicingTab /> : null}
      {tab === 'team' ? <TeamTab /> : null}
      {tab === 'profile' ? <ProfileTab /> : null}
    </div>
  );
}

function StoreTab() {
  const { store, refreshSession } = useAuth();
  const canManage = useCan('MANAGER');
  const toast = useToast();

  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (store) {
      setForm({
        name: store.name || '',
        owner_name: store.owner_name || '',
        phone: store.phone || '',
        email: store.email || '',
        address: store.address || '',
        city: store.city || '',
        state: store.state || '',
        pin_code: store.pin_code || '',
        gst_number: store.gst_number || '',
        business_type: store.business_type || 'KIRANA',
      });
    }
  }, [store]);

  if (!form) return <CardSkeleton height={300} />;

  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = Object.fromEntries(
        Object.entries(form).map(([key, value]) => [key, value === '' ? null : value]),
      );
      await api.updateStore(store.id, { ...payload, name: form.name });
      await refreshSession();
      toast.success('Store details saved');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <Card
        title="Store profile"
        subtitle="These details appear on your receipts and invoices."
        footer={
          canManage ? (
            <div className="u-row" style={{ justifyContent: 'flex-end' }}>
              <Button type="submit" variant="primary" loading={saving} onClick={submit}>
                Save changes
              </Button>
            </div>
          ) : null
        }
      >
        {error ? (
          <div className="alert alert--error" role="alert" style={{ marginBottom: 'var(--s4)' }}>
            {error}
          </div>
        ) : null}
        {store?.is_demo ? (
          <div className="alert alert--info" style={{ marginBottom: 'var(--s4)' }}>
            This is the demo store. Its data is generated, not real — useful for exploring, not for
            running a shop.
          </div>
        ) : null}

        <fieldset disabled={!canManage} style={{ border: 'none', padding: 0, margin: 0 }}>
          <div className="form-grid">
            <TextField label="Store name" required value={form.name} onChange={set('name')} />
            <TextField label="Owner name" value={form.owner_name} onChange={set('owner_name')} />
            <TextField label="Phone" type="tel" value={form.phone} onChange={set('phone')} />
            <TextField label="Email" type="email" optional value={form.email} onChange={set('email')} />
            <SelectField
              label="Business type"
              value={form.business_type}
              onChange={set('business_type')}
              options={BUSINESS_TYPES.map((value) => ({
                value,
                label: value.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()),
              }))}
            />
            <TextField label="GST number" optional value={form.gst_number} onChange={set('gst_number')} />
            <TextField
              label="Address"
              optional
              className="form-grid__full"
              value={form.address}
              onChange={set('address')}
            />
            <TextField label="City" value={form.city} onChange={set('city')} />
            <TextField label="State" value={form.state} onChange={set('state')} />
            <TextField label="PIN code" value={form.pin_code} onChange={set('pin_code')} />
          </div>
        </fieldset>
      </Card>
    </form>
  );
}

/**
 * Inventory and forecasting policy.
 *
 * These thresholds change what the model calls critical, and how much it tells
 * you to order — so they are an owner-level decision, enforced as such by the API.
 */
function PolicyTab() {
  const canOwn = useCan('OWNER');
  const toast = useToast();
  const settings = useApi(() => api.getStoreSettings(), []);

  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (settings.data) setForm(settings.data);
  }, [settings.data]);

  if (settings.loading || !form) return <CardSkeleton height={320} />;

  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    try {
      await api.updateStoreSettings({
        low_stock_threshold: Number(form.low_stock_threshold),
        default_lead_time_days: Number(form.default_lead_time_days),
        critical_cover_days: form.critical_cover_days,
        medium_cover_buffer_days: form.medium_cover_buffer_days,
        overstock_cover_days: form.overstock_cover_days,
        safety_days: Number(form.safety_days),
        service_level_z: form.service_level_z,
      });
      toast.success('Policy saved — recommendations will use the new thresholds');
      settings.reload();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <Card
        title="Inventory and forecasting policy"
        subtitle="What counts as urgent, and how much buffer to hold. Applies to this store only."
        footer={
          canOwn ? (
            <div className="u-row" style={{ justifyContent: 'flex-end' }}>
              <Button type="submit" variant="primary" loading={saving} onClick={submit}>
                Save policy
              </Button>
            </div>
          ) : null
        }
      >
        {!canOwn ? (
          <div className="alert alert--info" style={{ marginBottom: 'var(--s4)' }}>
            Only owners can change these thresholds — they affect every reorder recommendation.
          </div>
        ) : null}

        <fieldset disabled={!canOwn} style={{ border: 'none', padding: 0, margin: 0 }}>
          <div className="form-grid">
            <TextField
              label="Low-stock threshold"
              type="number" min="0"
              hint="Default reorder level for new products."
              value={form.low_stock_threshold}
              onChange={set('low_stock_threshold')}
            />
            <TextField
              label="Default lead time (days)"
              type="number" min="0"
              hint="Used when a product has no supplier."
              value={form.default_lead_time_days}
              onChange={set('default_lead_time_days')}
            />
            <TextField
              label="Critical cover (days)"
              type="number" min="0" step="0.5"
              hint="At or below this many days of stock, a product is Critical."
              value={form.critical_cover_days}
              onChange={set('critical_cover_days')}
            />
            <TextField
              label="Medium buffer (days)"
              type="number" min="0" step="0.5"
              hint="Cover within lead time plus this is Medium risk."
              value={form.medium_cover_buffer_days}
              onChange={set('medium_cover_buffer_days')}
            />
            <TextField
              label="Overstock threshold (days)"
              type="number" min="0" step="1"
              hint="Cover beyond this is flagged as capital tied up."
              value={form.overstock_cover_days}
              onChange={set('overstock_cover_days')}
            />
            <TextField
              label="Safety days"
              type="number" min="0"
              hint="Extra days of demand held beyond the lead time."
              value={form.safety_days}
              onChange={set('safety_days')}
            />
            <TextField
              label="Service level (z)"
              type="number" min="0" max="5" step="0.01"
              hint="1.28 ≈ 90% service level, 1.65 ≈ 95%. Higher means more safety stock."
              value={form.service_level_z}
              onChange={set('service_level_z')}
            />
          </div>
        </fieldset>
      </Card>
    </form>
  );
}

function InvoicingTab() {
  const canOwn = useCan('OWNER');
  const toast = useToast();
  const settings = useApi(() => api.getStoreSettings(), []);

  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (settings.data) setForm(settings.data);
  }, [settings.data]);

  if (settings.loading || !form) return <CardSkeleton height={260} />;

  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    try {
      await api.updateStoreSettings({
        invoice_prefix: form.invoice_prefix,
        purchase_order_prefix: form.purchase_order_prefix,
        default_tax_rate: form.default_tax_rate,
        financial_year_start_month: Number(form.financial_year_start_month),
        timezone: form.timezone,
      });
      toast.success('Invoicing settings saved');
      settings.reload();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <Card
        title="Tax and invoicing"
        footer={
          canOwn ? (
            <div className="u-row" style={{ justifyContent: 'flex-end' }}>
              <Button type="submit" variant="primary" loading={saving} onClick={submit}>
                Save
              </Button>
            </div>
          ) : null
        }
      >
        <fieldset disabled={!canOwn} style={{ border: 'none', padding: 0, margin: 0 }}>
          <div className="form-grid">
            <TextField
              label="Invoice prefix"
              hint="Invoices are numbered PREFIX-00001. Existing numbers are unchanged."
              value={form.invoice_prefix}
              onChange={set('invoice_prefix')}
            />
            <TextField
              label="Purchase order prefix"
              value={form.purchase_order_prefix}
              onChange={set('purchase_order_prefix')}
            />
            <TextField
              label="Default tax rate (%)"
              type="number" min="0" max="100" step="0.01"
              hint="Applied to new products unless overridden."
              value={form.default_tax_rate}
              onChange={set('default_tax_rate')}
            />
            <SelectField
              label="Financial year starts"
              value={form.financial_year_start_month}
              onChange={set('financial_year_start_month')}
              options={[
                { value: 4, label: 'April (India)' },
                { value: 1, label: 'January' },
                { value: 7, label: 'July' },
                { value: 10, label: 'October' },
              ]}
            />
            <TextField label="Timezone" value={form.timezone} onChange={set('timezone')} />
          </div>
        </fieldset>
      </Card>
    </form>
  );
}

function TeamTab() {
  const { store, user } = useAuth();
  const canOwn = useCan('OWNER');
  const toast = useToast();

  const members = useApi(() => api.listMembers(store.id), [store?.id]);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [removing, setRemoving] = useState(null);
  const [busy, setBusy] = useState(false);

  async function changeRole(member, role) {
    try {
      await api.updateMemberRole(store.id, member.user_id, role);
      toast.success(`${member.full_name} is now ${role.toLowerCase()}`);
      members.reload();
    } catch (error) {
      toast.error(error.message);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await api.removeMember(store.id, removing.user_id);
      toast.success(`${removing.full_name} removed`);
      setRemoving(null);
      members.reload();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Card
        title="Team members"
        subtitle="Roles are enforced by the server, not just hidden in the interface."
        flush
        actions={
          canOwn ? (
            <Button size="sm" variant="primary" icon="plus" onClick={() => setInviteOpen(true)}>
              Add member
            </Button>
          ) : null
        }
      >
        <AsyncSection
          loading={members.loading}
          error={members.error}
          onRetry={members.reload}
          skeleton={<CardSkeleton height={180} />}
        >
          <Table
            columns={[
              {
                key: 'person',
                header: 'Member',
                render: (row) => (
                  <div className="u-row">
                    <span className="avatar">{initials(row.full_name)}</span>
                    <div>
                      <div className="table__primary">
                        {row.full_name}
                        {row.user_id === user?.id ? (
                          <span className="u-xs u-subtle"> · you</span>
                        ) : null}
                      </div>
                      <div className="table__secondary">{row.email}</div>
                    </div>
                  </div>
                ),
              },
              {
                key: 'role',
                header: 'Role',
                render: (row) =>
                  canOwn && row.user_id !== user?.id ? (
                    <select
                      className="select"
                      style={{ width: 130 }}
                      value={row.role}
                      onChange={(event) => changeRole(row, event.target.value)}
                      aria-label={`Role for ${row.full_name}`}
                    >
                      {['OWNER', 'MANAGER', 'CASHIER'].map((role) => (
                        <option key={role} value={role}>
                          {role[0] + role.slice(1).toLowerCase()}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <Badge tone={row.role === 'OWNER' ? 'accent' : 'neutral'}>
                      {row.role[0] + row.role.slice(1).toLowerCase()}
                    </Badge>
                  ),
              },
              {
                key: 'since',
                header: 'Member since',
                render: (row) => <span className="u-small u-muted">{date(row.created_at)}</span>,
              },
              {
                key: 'actions',
                header: '',
                align: 'right',
                render: (row) =>
                  canOwn && row.user_id !== user?.id ? (
                    <Button size="sm" variant="ghost" onClick={() => setRemoving(row)}>
                      Remove
                    </Button>
                  ) : null,
              },
            ]}
            rows={members.data || []}
          />
        </AsyncSection>
      </Card>

      <Card title="What each role can do" className="u-mt4">
        <div className="grid grid--3">
          {[
            ['Owner', 'Everything, including store policy, team management and settings.'],
            ['Manager', 'Products, inventory, suppliers, purchasing, analytics and the till.'],
            ['Cashier', 'The till, sales history and product lookup.'],
          ].map(([role, description]) => (
            <div key={role}>
              <div className="u-strong u-small">{role}</div>
              <p className="u-xs u-muted" style={{ marginTop: 3 }}>
                {description}
              </p>
            </div>
          ))}
        </div>
      </Card>

      <InviteModal
        open={inviteOpen}
        storeId={store?.id}
        onClose={() => setInviteOpen(false)}
        onSaved={() => {
          setInviteOpen(false);
          members.reload();
        }}
      />

      <ConfirmDialog
        open={removing !== null}
        onClose={() => setRemoving(null)}
        onConfirm={remove}
        loading={busy}
        destructive
        title={`Remove ${removing?.full_name}?`}
        confirmLabel="Remove"
        message="They lose access to this store immediately. Their account and any sales they recorded are kept."
      />
    </>
  );
}

function InviteModal({ open, storeId, onClose, onSaved }) {
  const toast = useToast();
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('CASHIER');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.addMember(storeId, { email, role });
      toast.success('Member added');
      setEmail('');
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="narrow"
      title="Add a team member"
      subtitle="They need a Kirana-IQ account first."
      footer={
        <>
          <Button onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} loading={saving}>
            Add member
          </Button>
        </>
      }
    >
      <form onSubmit={submit} className="u-col u-gap4">
        {error ? (
          <div className="alert alert--error" role="alert">
            {error}
          </div>
        ) : null}
        <TextField
          label="Their email"
          type="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <SelectField
          label="Role"
          value={role}
          onChange={(event) => setRole(event.target.value)}
          options={[
            { value: 'CASHIER', label: 'Cashier — till and sales history' },
            { value: 'MANAGER', label: 'Manager — plus catalogue and purchasing' },
            { value: 'OWNER', label: 'Owner — full access' },
          ]}
        />
      </form>
    </Modal>
  );
}

function ProfileTab() {
  const { user, setUser } = useAuth();
  const toast = useToast();

  const [profile, setProfile] = useState({ full_name: '', phone: '' });
  const [passwords, setPasswords] = useState({ current_password: '', new_password: '' });
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState(null);

  useEffect(() => {
    if (user) setProfile({ full_name: user.full_name || '', phone: user.phone || '' });
  }, [user]);

  async function saveProfile(event) {
    event.preventDefault();
    setSavingProfile(true);
    try {
      const updated = await api.updateProfile({
        full_name: profile.full_name,
        phone: profile.phone || null,
      });
      setUser(updated);
      toast.success('Profile updated');
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSavingProfile(false);
    }
  }

  async function savePassword(event) {
    event.preventDefault();
    setSavingPassword(true);
    setPasswordError(null);
    try {
      await api.changePassword(passwords);
      toast.success('Password changed');
      setPasswords({ current_password: '', new_password: '' });
    } catch (error) {
      setPasswordError(error.message);
    } finally {
      setSavingPassword(false);
    }
  }

  return (
    <div className="grid grid--2">
      <form onSubmit={saveProfile}>
        <Card
          title="Your profile"
          footer={
            <div className="u-row" style={{ justifyContent: 'flex-end' }}>
              <Button type="submit" variant="primary" loading={savingProfile} onClick={saveProfile}>
                Save
              </Button>
            </div>
          }
        >
          <div className="u-col u-gap4">
            <TextField label="Email" value={user?.email || ''} disabled hint="Email cannot be changed." />
            <TextField
              label="Full name"
              required
              value={profile.full_name}
              onChange={(event) => setProfile({ ...profile, full_name: event.target.value })}
            />
            <TextField
              label="Phone"
              type="tel"
              optional
              value={profile.phone}
              onChange={(event) => setProfile({ ...profile, phone: event.target.value })}
            />
          </div>
        </Card>
      </form>

      <form onSubmit={savePassword}>
        <Card
          title="Change password"
          footer={
            <div className="u-row" style={{ justifyContent: 'flex-end' }}>
              <Button
                type="submit"
                variant="primary"
                loading={savingPassword}
                onClick={savePassword}
                disabled={!passwords.current_password || passwords.new_password.length < 8}
              >
                Change password
              </Button>
            </div>
          }
        >
          <div className="u-col u-gap4">
            {passwordError ? (
              <div className="alert alert--error" role="alert">
                {passwordError}
              </div>
            ) : null}
            <TextField
              label="Current password"
              type="password"
              autoComplete="current-password"
              value={passwords.current_password}
              onChange={(event) =>
                setPasswords({ ...passwords, current_password: event.target.value })
              }
            />
            <TextField
              label="New password"
              type="password"
              autoComplete="new-password"
              minLength={8}
              hint="At least 8 characters."
              value={passwords.new_password}
              onChange={(event) => setPasswords({ ...passwords, new_password: event.target.value })}
            />
          </div>
        </Card>
      </form>
    </div>
  );
}
