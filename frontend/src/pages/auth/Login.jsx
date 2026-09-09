import { useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';

import AuthShell from './AuthShell.jsx';
import Button from '../../components/ui/Button.jsx';
import { TextField } from '../../components/ui/Field.jsx';
import { useAuth } from '../../context/AuthContext.jsx';

export default function Login() {
  const { signIn, isAuthenticated, loading: sessionLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  if (!sessionLoading && isAuthenticated) {
    return <Navigate to={location.state?.from || '/app'} replace />;
  }

  async function onSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const session = await signIn(form);
      // A user with no store has nothing to look at; send them to the wizard.
      navigate(session.stores?.length ? location.state?.from || '/app' : '/onboarding', {
        replace: true,
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Sign in"
      lead="Welcome back. Open your store and pick up where you left off."
      footer={
        <>
          New to Kirana-IQ? <Link to="/register">Create an account</Link>
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
          label="Email"
          type="email"
          autoComplete="email"
          required
          autoFocus
          value={form.email}
          onChange={(event) => setForm({ ...form, email: event.target.value })}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={form.password}
          onChange={(event) => setForm({ ...form, password: event.target.value })}
        />

        <div className="u-row-between">
          <Link to="/forgot-password" className="u-small">
            Forgot your password?
          </Link>
        </div>

        <Button type="submit" variant="primary" size="lg" block loading={submitting}>
          Sign in
        </Button>
      </form>

      <div className="demo-hint">
        <strong>Demo store</strong> — sign in with <code>demo@demo.kirana-iq.com</code> /{' '}
        <code>demo12345</code> to explore a store with a year of sales already loaded.
      </div>
    </AuthShell>
  );
}
