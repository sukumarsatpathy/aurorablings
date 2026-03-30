import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import profileService from '@/services/api/profile';

export const AccountLogoutPage: React.FC = () => {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);

  const handleLogout = async () => {
    try {
      setBusy(true);
      const refresh = localStorage.getItem('refresh_token');
      if (refresh) {
        await profileService.logout(refresh);
      }
    } catch {
      // continue client-side logout even if server token revoke fails
    } finally {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('auth_user');
      window.dispatchEvent(new CustomEvent('aurora:auth-changed'));
      window.dispatchEvent(new CustomEvent('aurora:cart-updated'));
      setBusy(false);
      navigate('/login?next=/account', { replace: true });
    }
  };

  return (
    <Card className="rounded-3xl border-[#517b4b]/15 bg-white p-8 shadow-[0_12px_28px_rgba(81,123,75,0.1)]">
      <h2 className="text-2xl font-bold text-[#517b4b]">Logout</h2>
      <p className="mt-2 text-sm text-muted-foreground">
        You are about to sign out from your account on this device.
      </p>
      <div className="mt-5 flex items-center gap-2">
        <Button className="rounded-xl bg-[#517b4b] text-white hover:bg-[#456a41]" onClick={() => void handleLogout()} disabled={busy}>
          {busy ? 'Signing out...' : 'Sign Out'}
        </Button>
        <Button variant="outline" className="rounded-xl" onClick={() => navigate('/account')}>
          Cancel
        </Button>
      </div>
    </Card>
  );
};

