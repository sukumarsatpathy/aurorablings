import React, { useCallback, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { useAddressAutoFill } from '@/hooks/useAddressAutoFill';
import profileService, { type AddressData, type ProfileData } from '@/services/api/profile';
import { extractData, extractRows } from './accountUtils';

type AddressFormState = AddressData;

const emptyForm: AddressFormState = {
  address_type: 'shipping',
  is_default: false,
  full_name: '',
  line1: '',
  line2: '',
  city: '',
  state: '',
  postal_code: '',
  country: 'India',
  phone: '',
};

export const AccountAddressPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [addresses, setAddresses] = useState<AddressData[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<AddressFormState>(emptyForm);
  const [useAccountContact, setUseAccountContact] = useState(true);
  const [formArea, setFormArea] = useState('');
  const [error, setError] = useState('');

  const preferredAddress = useMemo(() => {
    if (!addresses.length) return null;
    return (
      addresses.find((row) => row.is_default && row.address_type === 'shipping') ||
      addresses.find((row) => row.is_default) ||
      addresses[0]
    );
  }, [addresses]);

  const buildCreateForm = useCallback((preferred?: AddressData | null, currentProfile?: ProfileData | null): AddressFormState => {
    const fullNameFromProfile = `${currentProfile?.first_name || ''} ${currentProfile?.last_name || ''}`.trim();
    return {
      address_type: preferred?.address_type || 'shipping',
      is_default: false,
      full_name: preferred?.full_name || fullNameFromProfile,
      line1: preferred?.line1 || '',
      line2: preferred?.line2 || '',
      city: preferred?.city || '',
      state: preferred?.state || '',
      postal_code: preferred?.postal_code || '',
      country: preferred?.country || 'India',
      phone: preferred?.phone || currentProfile?.phone || '',
    };
  }, []);

  const accountFullName = useMemo(
    () => `${profile?.first_name || ''} ${profile?.last_name || ''}`.trim(),
    [profile?.first_name, profile?.last_name]
  );
  const accountPhone = useMemo(() => String(profile?.phone || '').trim(), [profile?.phone]);

  const loadAddresses = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const [addressesResponse, profileResponse] = await Promise.all([
        profileService.getAddresses(),
        profileService.getProfile(),
      ]);
      const rows = extractRows<AddressData>(addressesResponse);
      const profileData = extractData<ProfileData>(profileResponse);
      setAddresses(rows);
      setProfile(profileData);
      if (!editingId && !formOpen) {
        const preferred =
          rows.find((row) => row.is_default && row.address_type === 'shipping') ||
          rows.find((row) => row.is_default) ||
          rows[0] ||
          null;
        setForm(buildCreateForm(preferred, profileData));
      }
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Unable to load addresses.');
    } finally {
      setLoading(false);
    }
  }, [buildCreateForm, editingId, formOpen]);

  React.useEffect(() => {
    void loadAddresses();
  }, [loadAddresses]);

  const onResolved = useCallback((payload: { city: string; state: string; area: string; pincode: string }, source: 'pincode' | 'gps') => {
    setForm((prev) => ({
      ...prev,
      city: payload.city || prev.city,
      state: payload.state || prev.state,
      postal_code: source === 'gps' && prev.postal_code ? prev.postal_code : (payload.pincode || prev.postal_code),
      line2: prev.line2 || payload.area || prev.line2,
    }));
    if (payload.area) setFormArea(payload.area);
  }, []);

  const autoFill = useAddressAutoFill({
    pincode: form.postal_code,
    onResolved,
    enabled: formOpen,
  });

  const resetForm = () => {
    setEditingId(null);
    setForm(buildCreateForm(preferredAddress, profile));
    setUseAccountContact(true);
    setFormArea('');
    setFormOpen(false);
  };

  const beginCreate = () => {
    setEditingId(null);
    setForm(buildCreateForm(preferredAddress, profile));
    setUseAccountContact(true);
    setFormArea('');
    setFormOpen(true);
    setError('');
  };

  const beginEdit = (address: AddressData) => {
    setEditingId(String(address.id || ''));
    setForm({
      address_type: address.address_type,
      is_default: Boolean(address.is_default),
      full_name: address.full_name || '',
      line1: address.line1 || '',
      line2: address.line2 || '',
      city: address.city || '',
      state: address.state || '',
      postal_code: address.postal_code || '',
      country: address.country || 'India',
      phone: address.phone || '',
    });
    const sameAsAccount =
      (address.full_name || '').trim() === accountFullName &&
      (address.phone || '').trim() === accountPhone;
    setUseAccountContact(sameAsAccount);
    setFormArea('');
    setFormOpen(true);
    setError('');
  };

  const handleUseAccountContactChange = (checked: boolean) => {
    setUseAccountContact(checked);
    if (checked) {
      setForm((prev) => ({
        ...prev,
        full_name: accountFullName || prev.full_name,
        phone: accountPhone || prev.phone,
      }));
      return;
    }
    setForm((prev) => ({
      ...prev,
      full_name: '',
      phone: '',
    }));
  };

  React.useEffect(() => {
    if (!formOpen) return;
    if (!useAccountContact) return;
    setForm((prev) => ({
      ...prev,
      full_name: accountFullName || prev.full_name,
      phone: accountPhone || prev.phone,
    }));
  }, [accountFullName, accountPhone, formOpen, useAccountContact]);

  const handleSave = async () => {
    if (!form.full_name.trim() || !form.line1.trim() || !form.city.trim() || !form.state.trim() || !form.postal_code.trim()) {
      setError('Please complete full name, line 1, city, state, and pincode.');
      return;
    }
    if (String(form.postal_code || '').replace(/\D/g, '').length !== 6) {
      setError('Please enter a valid 6-digit pincode.');
      return;
    }

    try {
      setSaving(true);
      setError('');
      const payload: AddressData = {
        ...form,
        line2: form.line2 || formArea || '',
        postal_code: String(form.postal_code || '').replace(/\D/g, '').slice(0, 6),
      };
      if (editingId) {
        await profileService.updateAddress(editingId, payload);
      } else {
        await profileService.createAddress(payload);
      }
      await loadAddresses();
      resetForm();
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Unable to save address.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (addressId: string) => {
    if (!window.confirm('Delete this address?')) return;
    try {
      setError('');
      await profileService.deleteAddress(addressId);
      await loadAddresses();
      if (editingId === addressId) resetForm();
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Unable to delete address.');
    }
  };

  const addressCountLabel = useMemo(() => `${addresses.length} saved`, [addresses.length]);

  return (
    <div className="space-y-6">
      <Card className="rounded-3xl border-[#517b4b]/15 bg-white p-6 shadow-[0_12px_28px_rgba(81,123,75,0.1)]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-[#517b4b]">Address Book</h2>
            <p className="text-sm text-muted-foreground">Manage delivery addresses with pincode auto-fill.</p>
          </div>
          <div className="flex items-center gap-2">
            <Badge className="bg-[#517b4b]/10 text-[#517b4b]">{addressCountLabel}</Badge>
            <Button className="rounded-xl bg-[#517b4b] text-white hover:bg-[#456a41]" onClick={beginCreate}>
              Add Address
            </Button>
          </div>
        </div>
      </Card>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      {formOpen ? (
        <Card className="rounded-3xl border-[#517b4b]/15 bg-white p-6 shadow-[0_12px_28px_rgba(81,123,75,0.1)]">
          <h3 className="mb-4 text-lg font-bold text-[#517b4b]">{editingId ? 'Edit Address' : 'Add Address'}</h3>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <select
              className="h-10 rounded-xl border border-input bg-transparent px-3 text-sm"
              value={form.address_type}
              onChange={(e) => setForm((prev) => ({ ...prev, address_type: e.target.value as 'shipping' | 'billing' }))}
            >
              <option value="shipping">Shipping</option>
              <option value="billing">Billing</option>
            </select>
            <label className="inline-flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_default}
                onChange={(e) => setForm((prev) => ({ ...prev, is_default: e.target.checked }))}
              />
              Set as default
            </label>
            <label className="md:col-span-2 inline-flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={useAccountContact}
                onChange={(e) => handleUseAccountContactChange(e.target.checked)}
              />
              Use my account name & phone
            </label>
            <p className="md:col-span-2 -mt-1 text-xs text-muted-foreground">
              Ordering for someone else? Turn this off to enter recipient name and phone.
            </p>
            <Input
              placeholder="Full Name"
              value={form.full_name}
              disabled={useAccountContact}
              onChange={(e) => setForm((prev) => ({ ...prev, full_name: e.target.value }))}
            />
            <Input
              placeholder="Phone"
              value={form.phone}
              disabled={useAccountContact}
              onChange={(e) => setForm((prev) => ({ ...prev, phone: e.target.value }))}
            />
            <div className="md:col-span-2">
              <Input placeholder="Address Line 1" value={form.line1} onChange={(e) => setForm((prev) => ({ ...prev, line1: e.target.value }))} />
            </div>
            <div className="md:col-span-2">
              <Input placeholder="Address Line 2 / Landmark" value={form.line2} onChange={(e) => setForm((prev) => ({ ...prev, line2: e.target.value }))} />
            </div>
            <Input
              placeholder="Pincode"
              value={form.postal_code}
              onChange={(e) => setForm((prev) => ({ ...prev, postal_code: e.target.value.replace(/\D/g, '').slice(0, 6) }))}
            />
            <Input placeholder="City" value={form.city} onChange={(e) => setForm((prev) => ({ ...prev, city: e.target.value }))} />
            {autoFill.result.areas.length > 1 ? (
              <select
                className="md:col-span-2 h-10 rounded-xl border border-input bg-transparent px-3 text-sm"
                value={formArea}
                onChange={(e) => {
                  setFormArea(e.target.value);
                  setForm((prev) => ({ ...prev, line2: prev.line2 || e.target.value }));
                }}
              >
                <option value="">Select area</option>
                {autoFill.result.areas.map((area) => (
                  <option key={area} value={area}>{area}</option>
                ))}
              </select>
            ) : null}
            <Input placeholder="State" value={form.state} onChange={(e) => setForm((prev) => ({ ...prev, state: e.target.value }))} />
            <Input placeholder="Country" value={form.country} onChange={(e) => setForm((prev) => ({ ...prev, country: e.target.value }))} />
          </div>
          <div className="mt-3 space-y-1 text-xs text-muted-foreground">
            {autoFill.isLoading ? <p>Detecting location from pincode...</p> : null}
            {autoFill.error ? <p className="text-amber-700">{autoFill.error}</p> : null}
            {autoFill.locationLabel ? <p className="text-emerald-700">{autoFill.locationLabel}</p> : null}
            <button
              type="button"
              className="text-primary underline underline-offset-4 disabled:text-muted-foreground"
              onClick={() => void autoFill.detectFromGps()}
              disabled={autoFill.isGpsLoading}
            >
              {autoFill.isGpsLoading ? 'Detecting via GPS...' : 'Use current location'}
            </button>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button className="rounded-xl bg-[#517b4b] text-white hover:bg-[#456a41]" disabled={saving} onClick={() => void handleSave()}>
              {saving ? 'Saving...' : 'Save Address'}
            </Button>
            <Button variant="outline" className="rounded-xl" onClick={resetForm}>Cancel</Button>
          </div>
        </Card>
      ) : null}

      <Card className="rounded-3xl border-[#517b4b]/15 bg-white p-6 shadow-[0_12px_28px_rgba(81,123,75,0.1)]">
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading addresses...</p>
        ) : addresses.length === 0 ? (
          <p className="text-sm text-muted-foreground">No address saved yet.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {addresses.map((address) => (
              <div key={address.id} className="rounded-2xl border border-border/70 bg-muted/20 p-4">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <p className="font-semibold">{address.full_name}</p>
                  <div className="flex items-center gap-1">
                    <Badge variant="outline">{address.address_type}</Badge>
                    {address.is_default ? <Badge className="bg-[#517b4b]/10 text-[#517b4b]">Default</Badge> : null}
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">
                  {address.line1}{address.line2 ? `, ${address.line2}` : ''}, {address.city}, {address.state} - {address.postal_code}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">{address.country} • {address.phone}</p>
                <div className="mt-3 flex gap-2">
                  <Button size="sm" variant="outline" className="rounded-xl" onClick={() => beginEdit(address)}>
                    Edit
                  </Button>
                  {address.id ? (
                    <Button size="sm" variant="outline" className="rounded-xl text-red-600" onClick={() => void handleDelete(String(address.id))}>
                      Delete
                    </Button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};
