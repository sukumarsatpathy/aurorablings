import { useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import axios from 'axios';
import { Link, useSearchParams } from 'react-router-dom';
import { MainLayout } from '@/components/layouts/MainLayout';
import { AuthLayout } from '@/components/layouts/AuthLayout';
import apiClient from '@/services/api/client';

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = useMemo(() => searchParams.get('token') || '', [searchParams]);

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');

    if (!token) {
      setErrorMessage('Reset token is missing or invalid.');
      return;
    }
    if (password !== confirmPassword) {
      setErrorMessage('Passwords do not match.');
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await apiClient.post('/v1/auth/password/reset/confirm/', {
        token,
        new_password: password,
      });
      setSuccessMessage(response.data?.message || 'Password reset successfully. You can now sign in.');
      setPassword('');
      setConfirmPassword('');
    } catch (error: unknown) {
      if (axios.isAxiosError(error)) {
        const apiMessage = (error.response?.data as { message?: string } | undefined)?.message;
        setErrorMessage(apiMessage || 'Unable to reset password. The link may be expired.');
      } else if (error instanceof Error) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage('Unable to reset password. The link may be expired.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <MainLayout>
      <AuthLayout>
        <div className="space-y-4">
          <h3 className="mb-2 text-center text-xl font-bold">Reset Password</h3>
          <p className="text-center text-sm text-muted-foreground">
            Set a new password for your account.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="New Password"
              className="w-full rounded-xl border border-border p-3"
              autoComplete="new-password"
              minLength={8}
              required
            />
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm New Password"
              className="w-full rounded-xl border border-border p-3"
              autoComplete="new-password"
              minLength={8}
              required
            />

            {errorMessage ? <p className="text-sm text-red-600">{errorMessage}</p> : null}
            {successMessage ? <p className="text-sm text-green-700">{successMessage}</p> : null}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-xl bg-primary p-3 font-bold text-primary-foreground disabled:opacity-60"
            >
              {isSubmitting ? 'Resetting...' : 'Reset Password'}
            </button>

            <p className="text-center text-sm text-muted-foreground">
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
