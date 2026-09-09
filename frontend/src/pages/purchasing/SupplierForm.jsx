import { useEffect, useState } from 'react';

import Button from '../../components/ui/Button.jsx';
import Modal from '../../components/ui/Modal.jsx';
import { TextAreaField, TextField } from '../../components/ui/Field.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import * as api from '../../services/api.js';

const BLANK = {
  name: '', contact_person: '', phone: '', email: '', address: '',
  gst_number: '', default_lead_time_days: 3, notes: '',
};

export default function SupplierForm({ open, onClose, onSaved, supplier = null }) {
  const toast = useToast();
  const editing = Boolean(supplier);

  const [form, setForm] = useState(BLANK);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setForm(
      supplier
        ? Object.fromEntries(Object.keys(BLANK).map((key) => [key, supplier[key] ?? BLANK[key]]))
        : BLANK,
    );
  }, [open, supplier]);

  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);

    const payload = {
      name: form.name.trim(),
      contact_person: form.contact_person.trim() || null,
      phone: form.phone.trim() || null,
      email: form.email.trim() || null,
      address: form.address.trim() || null,
      gst_number: form.gst_number.trim() || null,
      default_lead_time_days: Number(form.default_lead_time_days || 0),
      notes: form.notes.trim() || null,
    };

    try {
      if (editing) {
        await api.updateSupplier(supplier.id, payload);
        toast.success(`${payload.name} updated`);
      } else {
        await api.createSupplier(payload);
        toast.success(`${payload.name} added`);
      }
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
      title={editing ? `Edit ${supplier.name}` : 'Add a supplier'}
      footer={
        <>
          <Button onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} loading={saving}>
            {editing ? 'Save changes' : 'Add supplier'}
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

        <div className="form-grid">
          <TextField
            label="Supplier name"
            required
            className="form-grid__full"
            value={form.name}
            onChange={set('name')}
          />
          <TextField label="Contact person" optional value={form.contact_person} onChange={set('contact_person')} />
          <TextField label="Phone" type="tel" optional value={form.phone} onChange={set('phone')} />
          <TextField label="Email" type="email" optional value={form.email} onChange={set('email')} />
          <TextField
            label="Lead time (days)"
            type="number"
            min="0"
            hint="How long deliveries take. Drives reorder urgency."
            value={form.default_lead_time_days}
            onChange={set('default_lead_time_days')}
          />
          <TextField label="GST number" optional value={form.gst_number} onChange={set('gst_number')} />
          <TextField label="Address" optional value={form.address} onChange={set('address')} />
          <TextAreaField
            label="Notes"
            optional
            className="form-grid__full"
            value={form.notes}
            onChange={set('notes')}
          />
        </div>
      </form>
    </Modal>
  );
}
