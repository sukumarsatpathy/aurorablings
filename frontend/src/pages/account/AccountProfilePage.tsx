import React, { useCallback, useState } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import profileService, { type ProfileData } from '@/services/api/profile';
import { extractData } from './accountUtils';

export const AccountProfilePage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    phone: '',
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
        });
      }
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Unable to load profile.');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void loadProfile();
  }, [loadProfile]);

  const handleSaveProfile = async () => {
    try {
      setSaving(true);
      setError('');
      setSuccess('');
      const response = await profileService.updateProfile(form);
      const row = extractData<ProfileData>(response);
      setProfile(row);
      if (row) localStorage.setItem('auth_user', JSON.stringify(row));
      setSuccess('Profile updated successfully.');
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Unable to update profile.');
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
        <div className="mt-4 flex items-center gap-2">
          <Button className="rounded-xl bg-[#517b4b] text-white hover:bg-[#456a41]" disabled={saving} onClick={() => void handleSaveProfile()}>
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
        </div>
      </Card>

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

