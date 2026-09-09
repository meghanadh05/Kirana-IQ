import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';

import AuthShell from './AuthShell.jsx';
import Button from '../../components/ui/Button.jsx';
import { TextField } from '../../components/ui/Field.jsx';
import { useAuth } from '../../context/AuthContext.jsx';

export default function Register() {
  const { signUp, isAuthenticated, loading: sessionLoading } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({ full_name: '', email: '', password: '', phone: '' });
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  if (!sessionLoading && isAuthenticated) return <Navigate to="/app" replace />;

  const tooShort = form.password.length > 0 && form.password.length < 8;

  async function onSubmit(event) {
    event.preventDefault();
    if (tooShort) return;

    setSubmitting(true);
    setError(null);
    try {
      await signUp({ ...form, phone: form.phone || null });
      navigate('/onboarding', { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Create your account"
      lead="Set up your store in a few minutes. No card required."
      footer={
        <>
          Already have an account? <Link to="/login">Sign in</Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="auth__fields" noValidate>
        {error ? (
          <div className="alert alert--error" role="alert">
            {error}
          </div>
        ) : null}

        <TextField
          label="Your name"
          autoComplete="name"
          required
          autoFocus
          value={form.full_name}
          onChange={(event) => setForm({ ...form, full_name: event.target.value })}
        />
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={form.email}
          onChange={(event) => setForm({ ...form, email: event.target.value })}
        />
        <TextField
          label="Phone"
          type="tel"
          optional
          autoComplete="tel"
          value={form.phone}
          onChange={(event) => setForm({ ...form, phone: event.target.value })}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          hint="At least 8 characters."
          error={tooShort ? 'Password must be at least 8 characters.' : null}
          value={form.password}
          onChange={(event) => setForm({ ...form, password: event.target.value })}
        />

        <Button type="submit" variant="primary" size="lg" block loading={submitting}>
          Create account
        </Button>
      </form>
    </AuthShell>
  );
}
