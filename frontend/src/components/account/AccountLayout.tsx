import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Home, ListOrdered, LogOut, MapPinHouse, UserCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  { to: '/account', label: 'Dashboard', icon: Home, end: true },
  { to: '/account/orders', label: 'Orders', icon: ListOrdered },
  { to: '/account/address', label: 'Address', icon: MapPinHouse },
  { to: '/account/profile', label: 'Profile', icon: UserCircle2 },
  { to: '/account/logout', label: 'Logout', icon: LogOut },
];

export const AccountLayout: React.FC = () => {
  return (
    <div className="container mx-auto max-w-6xl px-4 py-6 md:py-8">
      <div className="mb-6 rounded-2xl border border-[#517b4b]/20 bg-white/85 p-3 shadow-[0_14px_32px_rgba(81,123,75,0.12)] backdrop-blur">
        <div className="mb-2 px-1">
          <h1 className="text-2xl font-bold tracking-tight text-[#517b4b]">My Account</h1>
          <p className="text-sm text-muted-foreground">Manage your orders, addresses, and profile details.</p>
        </div>
        <nav className="overflow-x-auto">
          <div className="flex min-w-max items-center gap-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    cn(
                      'inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-semibold transition-colors',
                      isActive
                        ? 'border-[#517b4b] bg-[#517b4b] text-white'
                        : 'border-border/70 bg-white text-foreground hover:border-[#517b4b]/30 hover:text-[#517b4b]'
                    )
                  }
                >
                  <Icon size={16} />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </div>
        </nav>
      </div>
      <div className="mt-8 md:mt-10">
        <Outlet />
      </div>
    </div>
  );
};
