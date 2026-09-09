import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Login from '../pages/auth/Login.jsx';
import { renderWithProviders } from './helpers.jsx';
import * as api from '../services/api.js';

vi.mock('../services/api.js', async () => {
  const actual = await vi.importActual('../services/api.js');
  return {
    ...actual,
    login: vi.fn(),
    getMe: vi.fn(),
    setUnauthorizedHandler: vi.fn(),
  };
});

const session = {
  access_token: 'test-token',
  token_type: 'bearer',
  user: { id: 1, email: 'owner@example.com', full_name: 'Test Owner', is_active: true },
  stores: [{ id: 1, name: 'Test Store', role: 'OWNER', onboarding_completed: true }],
};

describe('Login', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('sends the typed credentials to the API', async () => {
    api.login.mockResolvedValue(session);
    renderWithProviders(<Login />);

    await userEvent.type(screen.getByLabelText(/email/i), 'owner@example.com');
    await userEvent.type(screen.getByLabelText(/password/i), 'secret-password');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() =>
      expect(api.login).toHaveBeenCalledWith({
        email: 'owner@example.com',
        password: 'secret-password',
      }),
    );
  });

  it('stores the token so the session survives a reload', async () => {
    api.login.mockResolvedValue(session);
    renderWithProviders(<Login />);

    await userEvent.type(screen.getByLabelText(/email/i), 'owner@example.com');
    await userEvent.type(screen.getByLabelText(/password/i), 'secret-password');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => expect(localStorage.getItem('kiranaiq.token')).toBe('test-token'));
    expect(localStorage.getItem('kiranaiq.store')).toBe('1');
  });

  it('shows the API error message and stays on the form', async () => {
    api.login.mockRejectedValue(new Error('Incorrect email or password'));
    renderWithProviders(<Login />);

    await userEvent.type(screen.getByLabelText(/email/i), 'owner@example.com');
    await userEvent.type(screen.getByLabelText(/password/i), 'wrong');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password');
    expect(screen.getByRole('button', { name: /sign in/i })).toBeEnabled();
  });

  it('never puts the password in the DOM as readable text', async () => {
    api.login.mockResolvedValue(session);
    renderWithProviders(<Login />);

    const password = screen.getByLabelText(/password/i);
    await userEvent.type(password, 'secret-password');
    expect(password).toHaveAttribute('type', 'password');
  });
});
