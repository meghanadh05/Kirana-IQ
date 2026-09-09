import { useState } from 'react';
import { Link } from 'react-router-dom';

import AuthShell from './AuthShell.jsx';
import Button from '../../components/ui/Button.jsx';
import { TextField } from '../../components/ui/Field.jsx';
import { forgotPassword } from '../../services/api.js';

/**
 * Password reset request.
 *
 * The confirmation is identical whether or not the address is registered — the
 * backend behaves the same way, so the page cannot be used to discover which
 * emails have accounts.
 */
export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    try {
      await forgotPassword(email);
      setSent(true);
    } catch {
      // A failure here would also leak information; the message is unchanged.
      setSent(true);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Reset your password"
      lead="Enter the email on your account and we will send reset instructions."
      footer={<Link to="/login">Back to sign in</Link>}
    >
      {sent ? (
        <div className="alert alert--info u-mt6" role="status">
          If an account exists for <strong>{email}</strong>, reset instructions are on their way.
          Check your inbox and spam folder.
        </div>
      ) : (
        <form onSubmit={onSubmit} className="auth__fields" noValidate>
          <TextField
            label="Email"
            type="email"
            autoComplete="email"
            required
            autoFocus
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <Button type="submit" variant="primary" size="lg" block loading={submitting}>
            Send reset instructions
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
