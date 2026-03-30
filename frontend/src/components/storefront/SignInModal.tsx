import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import apiClient from '@/services/api/client';
import { Modal, ModalContent } from '@/components/ui/Modal';
import { useTurnstileConfig } from '@/hooks/useTurnstileConfig';
import { TurnstileWidget } from '@/components/security/TurnstileWidget';

const normalizeRole = (role?: string) => String(role || '').trim().toLowerCase();

const defaultRouteByRole = (role?: string) => {
  const normalized = normalizeRole(role);
  if (normalized === 'admin' || normalized === 'staff') return '/admin/dashboard';
  return '/account';
};

interface SignInModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  nextPath?: string;
  initialMode?: 'login' | 'register' | 'forgot';
}

export const SignInModal: React.FC<SignInModalProps> = ({
  open,
  onOpenChange,
  nextPath = '',
  initialMode = 'login',
}) => {
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'register' | 'forgot'>(initialMode);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [phone, setPhone] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [turnstileToken, setTurnstileToken] = useState('');
  const [turnstileResetKey, setTurnstileResetKey] = useState(0);
  const { turnstileEnabled, turnstileSiteKey } = useTurnstileConfig();

  useEffect(() => {
    if (!open) return;
    setMode(initialMode);
    setErrorMessage('');
    setSuccessMessage('');
    setTurnstileToken('');
    setTurnstileResetKey((prev) => prev + 1);
  }, [open, initialMode]);

  useEffect(() => {
    setErrorMessage('');
    setTurnstileToken('');
    setTurnstileResetKey((prev) => prev + 1);
  }, [mode]);

  const handleLogin = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrorMessage('');
    if (turnstileEnabled && !turnstileToken) {
      setErrorMessage('Please complete CAPTCHA verification.');
      return;
    }
    setIsSubmitting(true);

    try {
      const response = await apiClient.post('/v1/auth/login/', { email, password, turnstile_token: turnstileToken });
      const payload = response.data?.data;
      const access = payload?.access as string | undefined;
      const refresh = payload?.refresh as string | undefined;
      const user = payload?.user;

      if (!access) {
        throw new Error('Access token missing in login response.');
      }

      localStorage.setItem('auth_token', access);
      if (refresh) {
        localStorage.setItem('refresh_token', refresh);
      }
      if (user) {
        localStorage.setItem('auth_user', JSON.stringify(user));
      }
      window.dispatchEvent(new CustomEvent('aurora:auth-changed'));

      onOpenChange(false);
      navigate(nextPath || defaultRouteByRole(user?.role), { replace: true });
    } catch (error: unknown) {
      if (turnstileEnabled) {
        setTurnstileToken('');
        setTurnstileResetKey((prev) => prev + 1);
      }
      if (axios.isAxiosError(error)) {
        const apiMessage = (error.response?.data as { message?: string } | undefined)?.message;
        setErrorMessage(apiMessage || 'Login failed. Please check your credentials.');
      } else if (error instanceof Error) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage('Login failed. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRegister = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrorMessage('');
    if (turnstileEnabled && !turnstileToken) {
      setErrorMessage('Please complete CAPTCHA verification.');
      return;
    }
    setIsSubmitting(true);

    try {
      await apiClient.post('/v1/auth/register/', {
        first_name: firstName,
        last_name: lastName,
        email,
        phone,
        password,
        turnstile_token: turnstileToken,
      });
      if (turnstileEnabled) {
        setSuccessMessage('Account created successfully. Please sign in to continue.');
        setPassword('');
        setMode('login');
        setTurnstileToken('');
        setTurnstileResetKey((prev) => prev + 1);
        return;
      }

      const response = await apiClient.post('/v1/auth/login/', { email, password, turnstile_token: turnstileToken });
      const payload = response.data?.data;
      const access = payload?.access as string | undefined;
      const refresh = payload?.refresh as string | undefined;
      const user = payload?.user;

      if (!access) {
        throw new Error('Account created, but auto-login failed.');
      }

      localStorage.setItem('auth_token', access);
      if (refresh) {
        localStorage.setItem('refresh_token', refresh);
      }
      if (user) {
        localStorage.setItem('auth_user', JSON.stringify(user));
      }
      window.dispatchEvent(new CustomEvent('aurora:auth-changed'));
      alert('Account created successfully! Please check your email.');

      onOpenChange(false);
      navigate(nextPath || defaultRouteByRole(user?.role || 'customer'), { replace: true });
    } catch (error: unknown) {
      if (turnstileEnabled) {
        setTurnstileToken('');
        setTurnstileResetKey((prev) => prev + 1);
      }
      if (axios.isAxiosError(error)) {
        const data = error.response?.data as { message?: string } | undefined;
        setErrorMessage(data?.message || 'Unable to register right now.');
      } else if (error instanceof Error) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage('Unable to register right now.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleForgotPassword = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');
    if (turnstileEnabled && !turnstileToken) {
      setErrorMessage('Please complete CAPTCHA verification.');
      return;
    }
    setIsSubmitting(true);

    try {
      const response = await apiClient.post('/v1/auth/password/reset/', { email, turnstile_token: turnstileToken });
      const message = response.data?.message || 'If an account exists for this email, a reset link has been sent.';
      setSuccessMessage(message);
      if (turnstileEnabled) {
        setTurnstileToken('');
        setTurnstileResetKey((prev) => prev + 1);
      }
    } catch (error: unknown) {
      if (turnstileEnabled) {
        setTurnstileToken('');
        setTurnstileResetKey((prev) => prev + 1);
      }
      if (axios.isAxiosError(error)) {
        const apiMessage = (error.response?.data as { message?: string } | undefined)?.message;
        setErrorMessage(apiMessage || 'Unable to send reset link right now. Please try again.');
      } else if (error instanceof Error) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage('Unable to send reset link right now. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal open={open} onOpenChange={onOpenChange}>
      <ModalContent className="max-w-md p-0 overflow-hidden">
        <div className="p-7 sm:p-8">
          <div className="space-y-4">
            <h3 className="text-xl font-bold text-center text-foreground">
              {mode === 'login' ? 'Sign In' : mode === 'register' ? 'Create Account' : 'Forgot Password'}
            </h3>

            {mode === 'login' ? (
              <form onSubmit={handleLogin} className="space-y-4">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Email"
                  className="w-full p-3 rounded-xl border border-border"
                  autoComplete="email"
                  required
                />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Password"
                  className="w-full p-3 rounded-xl border border-border"
                  autoComplete="current-password"
                  required
                />
                <div className="text-right">
                  <button
                    type="button"
                    className="text-sm font-medium text-primary"
                    onClick={() => setMode('forgot')}
                  >
                    Forgot password?
                  </button>
                </div>
                {errorMessage ? <p className="text-sm text-red-600">{errorMessage}</p> : null}
                <TurnstileWidget
                  enabled={turnstileEnabled}
                  siteKey={turnstileSiteKey}
                  resetKey={turnstileResetKey}
                  onTokenChange={setTurnstileToken}
                />
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full bg-primary text-primary-foreground p-3 rounded-xl font-bold disabled:opacity-60"
                >
                  {isSubmitting ? 'Signing in...' : 'Login'}
                </button>
                <p className="text-sm text-center text-muted-foreground">
                  New customer?{' '}
                  <button type="button" className="text-primary font-medium" onClick={() => setMode('register')}>
                    Create an account
                  </button>
                </p>
              </form>
            ) : null}

            {mode === 'register' ? (
              <form onSubmit={handleRegister} className="space-y-4">
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="First Name"
                  className="w-full p-3 rounded-xl border border-border"
                  required
                />
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="Last Name"
                  className="w-full p-3 rounded-xl border border-border"
                  required
                />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Email"
                  className="w-full p-3 rounded-xl border border-border"
                  autoComplete="email"
                  required
                />
                <input
                  type="text"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="Phone"
                  className="w-full p-3 rounded-xl border border-border"
                  required
                />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Password"
                  className="w-full p-3 rounded-xl border border-border"
                  autoComplete="new-password"
                  required
                />
                {errorMessage ? <p className="text-sm text-red-600">{errorMessage}</p> : null}
                {successMessage ? <p className="text-sm text-green-700">{successMessage}</p> : null}
                <TurnstileWidget
                  enabled={turnstileEnabled}
                  siteKey={turnstileSiteKey}
                  resetKey={turnstileResetKey}
                  onTokenChange={setTurnstileToken}
                />
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full bg-primary text-primary-foreground p-3 rounded-xl font-bold disabled:opacity-60"
                >
                  {isSubmitting ? 'Creating account...' : 'Register'}
                </button>
                <p className="text-sm text-center text-muted-foreground">
                  Already have an account?{' '}
                  <button type="button" className="text-primary font-medium" onClick={() => setMode('login')}>
                    Sign in
                  </button>
                </p>
              </form>
            ) : null}

            {mode === 'forgot' ? (
              <form onSubmit={handleForgotPassword} className="space-y-4">
                <p className="text-center text-sm text-muted-foreground">
                  Enter your account email and we will send you a password reset link.
                </p>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Email"
                  className="w-full p-3 rounded-xl border border-border"
                  autoComplete="email"
                  required
                />
                {errorMessage ? <p className="text-sm text-red-600">{errorMessage}</p> : null}
                {successMessage ? <p className="text-sm text-green-700">{successMessage}</p> : null}
                <TurnstileWidget
                  enabled={turnstileEnabled}
                  siteKey={turnstileSiteKey}
                  resetKey={turnstileResetKey}
                  onTokenChange={setTurnstileToken}
                />
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full bg-primary text-primary-foreground p-3 rounded-xl font-bold disabled:opacity-60"
                >
                  {isSubmitting ? 'Sending link...' : 'Send Reset Link'}
                </button>
                <p className="text-sm text-center text-muted-foreground">
                  <button type="button" className="text-primary font-medium" onClick={() => setMode('login')}>
                    Back to login
                  </button>
                </p>
              </form>
            ) : null}
          </div>
        </div>
      </ModalContent>
    </Modal>
  );
};
