import { useState } from 'react';
import type { FormEvent } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { MainLayout } from '@/components/layouts/MainLayout';
import { AuthLayout } from '@/components/layouts/AuthLayout';
import apiClient from '@/services/api/client';
import { useTurnstileConfig } from '@/hooks/useTurnstileConfig';
import { TurnstileWidget } from '@/components/security/TurnstileWidget';

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [turnstileToken, setTurnstileToken] = useState('');
  const [turnstileResetKey, setTurnstileResetKey] = useState(0);
  const { turnstileEnabled, turnstileSiteKey } = useTurnstileConfig();

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
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
      setTurnstileToken('');
      setTurnstileResetKey((prev) => prev + 1);
    } catch (error: unknown) {
      setTurnstileToken('');
      setTurnstileResetKey((prev) => prev + 1);
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
    <MainLayout>
      <AuthLayout>
        <div className="space-y-4">
          <h3 className="mb-2 text-center text-xl font-bold">Forgot Password</h3>
          <p className="text-center text-sm text-muted-foreground">
            Enter your account email and we will send you a password reset link.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              className="w-full rounded-xl border border-border p-3"
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
              className="w-full rounded-xl bg-primary p-3 font-bold text-primary-foreground disabled:opacity-60"
            >
              {isSubmitting ? 'Sending link...' : 'Send Reset Link'}
            </button>

            <p className="text-center text-sm text-muted-foreground">
              Remembered your password?{' '}
              <Link to="/login" className="font-medium text-primary">
                Back to login
              </Link>
            </p>
          </form>
        </div>
      </AuthLayout>
    </MainLayout>
  );
}
