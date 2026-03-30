import React from 'react';
import { Link, Navigate } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';

export const UserDashboardPage: React.FC = () => {
  const token = localStorage.getItem('auth_token');
  const rawUser = localStorage.getItem('auth_user');

  if (!token) {
    return <Navigate to="/login?next=/dashboard" replace />;
  }

  let displayName = 'Customer';
  try {
    const user = rawUser ? JSON.parse(rawUser) : null;
    const first = String(user?.first_name || '').trim();
    const last = String(user?.last_name || '').trim();
    displayName = `${first} ${last}`.trim() || String(user?.email || 'Customer');
  } catch {
    displayName = 'Customer';
  }

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('auth_user');
    window.dispatchEvent(new CustomEvent('aurora:auth-changed'));
    window.dispatchEvent(new CustomEvent('aurora:cart-updated'));
    window.location.href = '/';
  };

  return (
    <div className="pt-32 pb-24">
      <div className="container mx-auto px-4 max-w-4xl space-y-6">
        <Card className="p-8 rounded-3xl border bg-white/90">
          <h1 className="text-3xl font-bold">Welcome, {displayName}</h1>
          <p className="text-muted-foreground mt-2">Manage your shopping activity from your dashboard.</p>
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="p-5 rounded-2xl">
            <h2 className="font-semibold mb-2">My Cart</h2>
            <p className="text-sm text-muted-foreground mb-4">Review items and update quantities.</p>
            <Link to="/cart"><Button className="rounded-xl w-full">Open Cart</Button></Link>
          </Card>

          <Card className="p-5 rounded-2xl">
            <h2 className="font-semibold mb-2">Checkout</h2>
            <p className="text-sm text-muted-foreground mb-4">Complete your pending purchase securely.</p>
            <Link to="/checkout"><Button className="rounded-xl w-full" variant="outline">Go to Checkout</Button></Link>
          </Card>

          <Card className="p-5 rounded-2xl">
            <h2 className="font-semibold mb-2">Sign Out</h2>
            <p className="text-sm text-muted-foreground mb-4">Log out of your account on this device.</p>
            <Button className="rounded-xl w-full" variant="outline" onClick={handleLogout}>Logout</Button>
          </Card>
        </div>
      </div>
    </div>
  );
};
