import React, { useCallback, useState } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import profileService, { type MyCoupon, type ProfileData } from '@/services/api/profile';
import { extractData, extractRows } from './accountUtils';

/**
 * ``<input type="date">`` wants "" for empty, the API wants null. Keeping the
 * two straight in one place stops an untouched field being sent as "" — which
 * DRF rejects as an invalid date rather than treating as "no change".
 */
const toApiDate = (value: string): string | null => (value.trim() ? value : null);

/** Today, as yyyy-mm-dd, for the `max` on the date inputs. */
const today = () => new Date().toISOString().slice(0, 10);

/**
 * Pull something readable out of a DRF error.
 *
 * Field errors arrive as `{date_of_birth: ["You must be at least 13..."]}` with
 * no `message` key, so reading only `message` showed the generic fallback and
 * the customer never learned why the save failed.
 */
const errorMessage = (err: any, fallback: string): string => {
  const data = err?.response?.data;
  if (!data) return fallback;
  if (typeof data.message === 'string' && data.message) return data.message;

  const source = data.errors && typeof data.errors === 'object' ? data.errors : data;
  for (const value of Object.values(source)) {
    if (typeof value === 'string' && value) return value;
    if (Array.isArray(value) && typeof value[0] === 'string') return value[0];
  }
  return fallback;
};

export const AccountProfilePage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [coupons, setCoupons] = useState<MyCoupon[]>([]);
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    phone: '',
    date_of_birth: '',
    anniversary_date: '',
  });
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });

  const loadProfile = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const response = await profileService.getProfile();
      const row = extractData<ProfileData>(response);
      setProfile(row);
      if (row) {
        setForm({
          first_name: row.first_name || '',
          last_name: row.last_name || '',
          phone: row.phone || '',
          date_of_birth: row.date_of_birth || '',
          anniversary_date: row.anniversary_date || '',
        });
      }
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Unable to load profile.');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCoupons = useCallback(async () => {
    try {
      const response = await profileService.getMyCoupons();
      // extractRows, not extractData: the payload is `{data: [...]}` and
      // extractData deliberately returns null for an array.
      setCoupons(extractRows<MyCoupon>(response));
    } catch {
      // A gift list that fails to load is not worth an error banner on a page
      // whose main job is the profile form.
      setCoupons([]);
    }
  }, []);

  React.useEffect(() => {
    void loadProfile();
    void loadCoupons();
  }, [loadProfile, loadCoupons]);

  const handleSaveProfile = async () => {
    try {
      setSaving(true);
      setError('');
      setSuccess('');
      const response = await profileService.updateProfile({
        ...form,
        date_of_birth: toApiDate(form.date_of_birth),
        anniversary_date: toApiDate(form.anniversary_date),
      });
      const row = extractData<ProfileData>(response);
      setProfile(row);
      if (row) localStorage.setItem('auth_user', JSON.stringify(row));
      setSuccess('Profile updated successfully.');
    } catch (err: any) {
      setError(errorMessage(err, 'Unable to update profile.'));
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async () => {
    if (!passwordForm.current_password || !passwordForm.new_password) {
      setError('Please enter current and new password.');
      return;
    }
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setError('New password and confirm password do not match.');
      return;
    }

    try {
      setPasswordSaving(true);
      setError('');
      setSuccess('');
      await profileService.changePassword({
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password,
      });
      setPasswordForm({
        current_password: '',
        new_password: '',
        confirm_password: '',
      });
      setSuccess('Password changed successfully.');
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Unable to change password.');
    } finally {
      setPasswordSaving(false);
    }
  };

  if (loading) {
    return (
      <Card className="rounded-3xl border-[#517b4b]/15 bg-white p-6 shadow-[0_12px_28px_rgba(81,123,75,0.1)]">
        <p className="text-sm text-muted-foreground">Loading profile...</p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card className="rounded-3xl border-[#517b4b]/15 bg-white p-6 shadow-[0_12px_28px_rgba(81,123,75,0.1)]">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-xl font-bold text-[#517b4b]">Account Details</h2>
          {profile?.is_email_verified ? (
            <Badge className="bg-emerald-50 text-emerald-700 border border-emerald-200">Email Verified</Badge>
          ) : (
            <Badge className="bg-amber-50 text-amber-700 border border-amber-200">Email Not Verified</Badge>
          )}
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Input placeholder="First Name" value={form.first_name} onChange={(e) => setForm((prev) => ({ ...prev, first_name: e.target.value }))} />
          <Input placeholder="Last Name" value={form.last_name} onChange={(e) => setForm((prev) => ({ ...prev, last_name: e.target.value }))} />
          <Input placeholder="Phone" value={form.phone} onChange={(e) => setForm((prev) => ({ ...prev, phone: e.target.value }))} />
          <Input placeholder="Email" value={profile?.email || ''} disabled />
        </div>

        {/* Occasions. Both optional and both clearable — a customer who changes
            their mind can empty the field and we stop. Labelled rather than
            placeholder-only because a bare date input tells you nothing about
            which date it wants. */}
        <div className="mt-5 rounded-2xl border border-[#517b4b]/15 bg-[#eafed6]/40 p-4">
          <h3 className="text-sm font-bold text-[#517b4b]">Your celebrations</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Optional. Tell us and we&apos;ll send a gift coupon a few days before — nothing else.
            Clear a date any time to stop.
          </p>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="block">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Birthday
              </span>
              <Input
                type="date"
                className="mt-1"
                max={today()}
                value={form.date_of_birth}
                onChange={(e) => setForm((prev) => ({ ...prev, date_of_birth: e.target.value }))}
              />
            </label>
            <label className="block">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Anniversary
              </span>
              <Input
                type="date"
                className="mt-1"
                max={today()}
                value={form.anniversary_date}
                onChange={(e) => setForm((prev) => ({ ...prev, anniversary_date: e.target.value }))}
              />
            </label>
          </div>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <Button className="rounded-xl bg-[#517b4b] text-white hover:bg-[#456a41]" disabled={saving} onClick={() => void handleSaveProfile()}>
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
        </div>
      </Card>

      {coupons.length > 0 && (
        <Card className="rounded-3xl border-[#517b4b]/15 bg-white p-6 shadow-[0_12px_28px_rgba(81,123,75,0.1)]">
          <h3 className="mb-1 text-lg font-bold text-[#517b4b]">Your gift coupons</h3>
          <p className="mb-3 text-xs text-muted-foreground">
            Tied to this account — apply the code at checkout.
          </p>
          <div className="space-y-2">
            {coupons.map((coupon) => (
              <div
                key={coupon.code}
                className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-dashed border-[#517b4b]/40 bg-[#eafed6]/40 px-4 py-3"
              >
                <div>
                  <span className="font-mono text-base font-bold tracking-wide text-[#2f5f2a]">
                    {coupon.code}
                  </span>
                  <span className="ml-2 text-xs capitalize text-muted-foreground">
                    {coupon.occasion || 'gift'}
                  </span>
                </div>
                <div className="text-right text-xs text-muted-foreground">
                  <div className="font-semibold text-foreground">
                    {coupon.type === 'percentage' ? `${coupon.value}% off` : `₹${coupon.value} off`}
                    {coupon.max_discount ? ` (up to ₹${coupon.max_discount})` : ''}
                  </div>
                  <div>Valid till {new Date(coupon.expires_at).toLocaleDateString()}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card className="rounded-3xl border-[#517b4b]/15 bg-white p-6 shadow-[0_12px_28px_rgba(81,123,75,0.1)]">
        <h3 className="mb-3 text-lg font-bold text-[#517b4b]">Change Password</h3>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <Input
            type="password"
            placeholder="Current Password"
            value={passwordForm.current_password}
            onChange={(e) => setPasswordForm((prev) => ({ ...prev, current_password: e.target.value }))}
          />
          <Input
            type="password"
            placeholder="New Password"
            value={passwordForm.new_password}
            onChange={(e) => setPasswordForm((prev) => ({ ...prev, new_password: e.target.value }))}
          />
          <Input
            type="password"
            placeholder="Confirm Password"
            value={passwordForm.confirm_password}
            onChange={(e) => setPasswordForm((prev) => ({ ...prev, confirm_password: e.target.value }))}
          />
        </div>
        <div className="mt-4 flex items-center gap-2">
          <Button variant="outline" className="rounded-xl" disabled={passwordSaving} onClick={() => void handleChangePassword()}>
            {passwordSaving ? 'Updating...' : 'Update Password'}
          </Button>
        </div>
      </Card>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {success ? <p className="text-sm text-emerald-700">{success}</p> : null}
    </div>
  );
};

