import React, { useState, useEffect, useMemo } from 'react';
import { DataTable, StatusBadge } from '@/components/admin/AdminTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { 
  Plus, Search, Filter, MoreHorizontal, Edit, Trash2, Mail, Phone, 
  MapPin, Check, X, ShieldAlert 
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/DropdownMenu';
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalFooter,
} from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import customerService from '@/services/api/customers';
import customerAddressService from '@/services/api/customerAddresses';
import type { Customer, AddressData } from '@/types/customer';
import { cn } from '@/lib/utils';
import settingsService from '@/services/api/settings';
import notificationsAdminService from '@/services/api/adminNotifications';

type UiToast = {
  id: string;
  variant: 'success' | 'error' | 'info';
  message: string;
};

export const Customers: React.FC = () => {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [customerView, setCustomerView] = useState<'all' | 'blocked' | 'inactive'>('all');
  const [activeEmailProvider, setActiveEmailProvider] = useState<'smtp' | 'brevo'>('smtp');
  const [toasts, setToasts] = useState<UiToast[]>([]);
  
  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [formData, setFormData] = useState<any>({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    phone: '',
    role: 'customer',
    is_active: true,
  });

  // Address Modal State
  const [isAddressModalOpen, setIsAddressModalOpen] = useState(false);
  const [editingAddress, setEditingAddress] = useState<Partial<AddressData> | null>(null);
  const [customerToDeactivate, setCustomerToDeactivate] = useState<Customer | null>(null);
  const [isDeactivateModalOpen, setIsDeactivateModalOpen] = useState(false);
  const [addressToDelete, setAddressToDelete] = useState<string | null>(null);
  const [useForBothAddressTypes, setUseForBothAddressTypes] = useState(false);
  const [addressFormData, setAddressFormData] = useState<Partial<AddressData>>({
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
  });

  const fetchCustomers = async () => {
    try {
      setLoading(true);
      const response = await customerService.getAll({ search: searchTerm });
      // Backend envelope: { success, message, data: [...] }
      setCustomers(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      console.error('Failed to fetch customers:', error);
    } finally {
      setLoading(false);
    }
  };

  const pushToast = (variant: UiToast['variant'], message: string) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => [...prev, { id, variant, message }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 3200);
  };

  useEffect(() => {
    fetchCustomers();
  }, []);

  useEffect(() => {
    const loadProvider = async () => {
      try {
        // 1) Prefer the provider-status API (same source as Notifications Dashboard)
        const providerRes = await notificationsAdminService.getProviderStatus();
        const providerRows = Array.isArray(providerRes?.data)
          ? providerRes.data
          : Array.isArray(providerRes?.data?.data)
            ? providerRes.data.data
            : [];
        const activeProvider = providerRows.find((row: any) => row?.is_active === true);
        if (activeProvider?.provider_type) {
          const activeType = String(activeProvider.provider_type).toLowerCase();
          setActiveEmailProvider(activeType === 'brevo' ? 'brevo' : 'smtp');
          return;
        }

        // 2) Fallback to settings key notification.delivery.provider
        const settingsResponse = await settingsService.getAll({ category: 'notification' });
        const candidateArrays = [
          settingsResponse,
          settingsResponse?.data,
          settingsResponse?.data?.data,
          settingsResponse?.results,
          settingsResponse?.data?.results,
        ];
        const rows = candidateArrays.find((x) => Array.isArray(x)) || [];
        const delivery = (rows as any[]).find((row: any) => row?.key === 'notification.delivery');
        const typed = delivery?.typed_value;
        const value = delivery?.value;
        const parsed = typeof typed === 'object' && typed ? typed : (typeof value === 'string' ? JSON.parse(value) : {});
        const provider = String(parsed?.provider || 'smtp').toLowerCase();
        setActiveEmailProvider(provider === 'brevo' ? 'brevo' : 'smtp');
      } catch {
        setActiveEmailProvider('smtp');
      }
    };
    void loadProvider();
  }, []);

  // Password Strength Logic
  const passwordRequirements = useMemo(() => {
    const p = formData.password || '';
    return [
      { id: 'length', label: '8+ characters', met: p.length >= 8 },
      { id: 'upper', label: '1 uppercase letter', met: /[A-Z]/.test(p) },
      { id: 'digit', label: '1 digit', met: /[0-9]/.test(p) },
    ];
  }, [formData.password]);

  const passwordStrength = useMemo(() => {
    const metCount = passwordRequirements.filter(r => r.met).length;
    if (metCount === 0) return { score: 0, label: 'Weak', color: 'bg-destructive' };
    if (metCount === 1) return { score: 33, label: 'Fair', color: 'bg-orange-500' };
    if (metCount === 2) return { score: 66, label: 'Good', color: 'bg-yellow-500' };
    return { score: 100, label: 'Strong', color: 'bg-emerald-500' };
  }, [passwordRequirements]);

  // Table Columns
  const columns = [
    { 
      header: 'Customer', 
      accessorKey: 'full_name', 
      cell: (item: Customer) => (
        <div className="flex flex-col">
          <div className="font-bold text-foreground">{item.first_name} {item.last_name}</div>
          <div className="text-xs text-muted-foreground flex items-center gap-1">
            <Mail size={10} /> {item.email}
          </div>
        </div>
      )
    },
    { 
      header: 'Phone', 
      accessorKey: 'phone',
      cell: (item: Customer) => (
        <div className="text-xs flex items-center gap-1">
           {item.phone && <><Phone size={10} /> {item.phone}</>}
        </div>
      )
    },
    { 
      header: 'Addresses', 
      accessorKey: 'addresses', 
      cell: (item: Customer) => (
        <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
          <MapPin size={10} /> {item.addresses?.length || 0} saved
        </div>
      )
    },
    { 
      header: 'Role', 
      accessorKey: 'role', 
      cell: (item: Customer) => (
        <Badge variant="surface" className="text-[10px] capitalize">{item.role}</Badge>
      )
    },
    { 
      header: 'Status', 
      accessorKey: 'is_active',
      align: 'right' as const,
      cell: (item: Customer) => (
        <StatusBadge status={item.is_locked ? 'Blocked' : (item.is_active ? 'Active' : 'Inactive')} />
      )
    },
  ];

  const handleEdit = (item: Customer) => {
    setEditingCustomer(item);
    setFormData({
      first_name: item.first_name,
      last_name: item.last_name,
      email: item.email,
      phone: item.phone,
      role: item.role,
      is_active: item.is_active,
    });
    setIsModalOpen(true);
  };

  const handleAdd = () => {
    setEditingCustomer(null);
    setFormData({
      email: '',
      password: '',
      first_name: '',
      last_name: '',
      phone: '',
      role: 'customer',
    });
    setIsModalOpen(true);
  };

  const handleSave = async () => {
    try {
      if (editingCustomer) {
        await customerService.update(editingCustomer.id, formData);
      } else {
        await customerService.create(formData);
      }
      setIsModalOpen(false);
      fetchCustomers();
    } catch (error: any) {
      console.error("Save error:", error);
      const errorData = error.response?.data;
      const msg = errorData?.message || 
                  (errorData?.errors ? Object.values(errorData.errors).flat().join(', ') : null) ||
                  errorData?.detail || 
                  "Failed to save customer";
      alert(msg);
    }
  };

  // Address Handlers
  const handleAddAddress = () => {
    setEditingAddress(null);
    setUseForBothAddressTypes(false);
    setAddressFormData({
      address_type: 'shipping',
      is_default: false,
      full_name: `${formData.first_name} ${formData.last_name}`.trim(),
      line1: '',
      line2: '',
      city: '',
      state: '',
      postal_code: '',
      country: 'India',
      phone: formData.phone || '',
    });
    setIsAddressModalOpen(true);
  };

  const handleEditAddress = (addr: AddressData) => {
    setEditingAddress(addr);
    setUseForBothAddressTypes(false);
    setAddressFormData({ ...addr });
    setIsAddressModalOpen(true);
  };

  const handleSaveAddress = async () => {
    if (!editingCustomer) return;

    const basePayload: Partial<AddressData> = {
      is_default: !!addressFormData.is_default,
      full_name: addressFormData.full_name || '',
      line1: addressFormData.line1 || '',
      line2: addressFormData.line2 || '',
      city: addressFormData.city || '',
      state: addressFormData.state || '',
      postal_code: addressFormData.postal_code || '',
      country: addressFormData.country || 'India',
      phone: addressFormData.phone || '',
    };

    const refreshCustomer = async () => {
      const updated = await customerService.getById(editingCustomer.id);
      setCustomers(prev => prev.map(c => c.id === editingCustomer.id ? updated.data : c));
      setEditingCustomer(updated.data);
    };

    try {
      if (useForBothAddressTypes) {
        const targetTypes: Array<'shipping' | 'billing'> = ['shipping', 'billing'];

        for (const type of targetTypes) {
          const payload = { ...basePayload, address_type: type };
          const existing = editingCustomer.addresses?.find((a: AddressData) => a.address_type === type);

          if (existing?.id) {
            await customerAddressService.update(editingCustomer.id, existing.id, payload);
          } else {
            await customerAddressService.create(editingCustomer.id, payload as AddressData);
          }
        }
      } else if (editingAddress?.id) {
        await customerAddressService.update(
          editingCustomer.id,
          editingAddress.id,
          { ...basePayload, address_type: addressFormData.address_type }
        );
      } else {
        await customerAddressService.create(
          editingCustomer.id,
          { ...basePayload, address_type: addressFormData.address_type || 'shipping' } as AddressData
        );
      }

      setIsAddressModalOpen(false);
      await refreshCustomer();
    } catch (error: any) {
      alert("Failed to save address");
    }
  };

  const handleDeleteAddress = async (addressId: string) => {
    if (!editingCustomer) return;
    setAddressToDelete(addressId);
  };

  const confirmDeleteAddress = async () => {
    if (!editingCustomer || !addressToDelete) return;
    try {
      await customerAddressService.delete(editingCustomer.id, addressToDelete);
      const updated = await customerService.getById(editingCustomer.id);
      setCustomers(prev => prev.map(c => c.id === editingCustomer.id ? updated.data : c));
      setEditingCustomer(updated.data);
      setAddressToDelete(null);
    } catch (error) {
      alert("Failed to delete address");
    }
  };

  const openDeactivateModal = (item: Customer) => {
    setCustomerToDeactivate(item);
    setIsDeactivateModalOpen(true);
  };

  const handleSendWelcomeEmail = async (item: Customer) => {
    try {
      const response = await customerService.sendWelcomeEmail(item.id);
      pushToast('success', response?.message || `Welcome email sent to ${item.email}`);
    } catch (error: any) {
      const generic = error?.response?.data?.message || 'Failed to send welcome email.';
      const detail = error?.response?.data?.errors?.detail || '';
      pushToast('error', detail ? `${generic} (${detail})` : generic);
    }
  };

  const handleDeactivateCustomer = async () => {
    if (!customerToDeactivate) return;
    try {
      await customerService.delete(customerToDeactivate.id);
      setIsDeactivateModalOpen(false);
      setCustomerToDeactivate(null);
      fetchCustomers();
    } catch (error) {
      alert("Failed to deactivate customer");
    }
  };

  const handleUnblockCustomer = async (item: Customer) => {
    try {
      const response = await customerService.unblockCustomer(item.id);
      pushToast('success', response?.message || `Unlocked ${item.email}`);
      await fetchCustomers();
    } catch (error: any) {
      const message = error?.response?.data?.message || 'Failed to unlock customer.';
      pushToast('error', message);
    }
  };

  const actions = (item: Customer) => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[160px]">
        <div className="px-2 py-1.5 border-b border-border/60 mb-1">
          <Badge variant="surface" className="text-[9px] uppercase tracking-wider">
            Email: {activeEmailProvider === 'brevo' ? 'Brevo' : 'SMTP'}
          </Badge>
        </div>
        <DropdownMenuItem onClick={() => handleEdit(item)} className="flex items-center gap-2 cursor-pointer text-xs">
          <Edit size={14} /> Edit details
        </DropdownMenuItem>
        {item.is_locked ? (
          <DropdownMenuItem onClick={() => handleUnblockCustomer(item)} className="flex items-center gap-2 cursor-pointer text-xs text-emerald-700 focus:text-emerald-700">
            <Check size={14} /> Unblock account
          </DropdownMenuItem>
        ) : null}
          <DropdownMenuItem onClick={() => handleSendWelcomeEmail(item)} className="flex items-center gap-2 cursor-pointer text-xs">
            <Mail size={14} /> Send welcome email
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={() => openDeactivateModal(item)}
            className="flex items-center gap-2 cursor-pointer text-xs text-destructive focus:text-destructive"
        >
          <Trash2 size={14} /> Deactivate
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  const customerStats = useMemo(() => {
    const allRows = Array.isArray(customers) ? customers : [];
    return {
      all: allRows.length,
      blocked: allRows.filter((c) => Boolean(c.is_locked)).length,
      inactive: allRows.filter((c) => !c.is_active).length,
    };
  }, [customers]);

  const filteredCustomers = (Array.isArray(customers) ? customers : []).filter((c) => {
    const matchesSearch =
      `${c.first_name || ''} ${c.last_name || ''}`.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (c.email || '').toLowerCase().includes(searchTerm.toLowerCase());
    if (!matchesSearch) return false;

    if (customerView === 'blocked') return Boolean(c.is_locked);
    if (customerView === 'inactive') return !c.is_active;
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
         <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Customers</h1>
            <p className="text-xs text-muted-foreground mt-1">Manage user accounts, addresses, and status.</p>
         </div>
         <Button onClick={handleAdd} className="shrink-0 h-10 gap-2 font-bold px-4 rounded-xl shadow-sm">
            <Plus size={16} /> Add Customer
         </Button>
      </div>

      <div className="bg-white p-4 rounded-[14px] border border-border shadow-sm flex flex-col gap-3">
         <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
            <Input 
              placeholder="Search customers by name or email..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 h-10 shadow-none border-border/60 bg-muted/20"
            />
         </div>
         <div className="flex flex-wrap items-center gap-2">
            <Button
              variant={customerView === 'all' ? 'default' : 'outline'}
              className="h-9 px-3 text-xs"
              onClick={() => setCustomerView('all')}
            >
              All ({customerStats.all})
            </Button>
            <Button
              variant={customerView === 'blocked' ? 'default' : 'outline'}
              className="h-9 px-3 text-xs"
              onClick={() => setCustomerView('blocked')}
            >
              Blocked Users ({customerStats.blocked})
            </Button>
            <Button
              variant={customerView === 'inactive' ? 'default' : 'outline'}
              className="h-9 px-3 text-xs"
              onClick={() => setCustomerView('inactive')}
            >
              Inactive ({customerStats.inactive})
            </Button>
            <Button variant="outline" className="h-9 px-3 gap-2 text-muted-foreground border-border/60 text-xs">
              <Filter size={14} /> Filters
            </Button>
         </div>
      </div>

      {loading ? (
        <div className="text-center py-10 text-muted-foreground text-xs uppercase tracking-widest animate-pulse">
            Loading customers...
        </div>
      ) : (
        <DataTable 
          data={filteredCustomers} 
          columns={columns} 
          actions={actions}
          onRowClick={(item) => handleEdit(item)}
        />
      )}

      {/* Main CRUD Modal */}
      <Modal open={isModalOpen} onOpenChange={setIsModalOpen}>
        <ModalContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <ModalHeader>
            <ModalTitle>{editingCustomer ? 'Edit Customer' : 'Add New Customer'}</ModalTitle>
          </ModalHeader>
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 py-6">
            {/* CORE INFO SECTION */}
            <div className="space-y-6">
               <div className="space-y-4">
                  <h3 className="font-bold text-sm text-foreground border-b pb-2 flex items-center gap-2">
                     <Edit size={16} className="text-primary"/> Basic Information
                  </h3>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <label className="text-xs font-bold uppercase text-muted-foreground">First Name</label>
                      <Input 
                        value={formData.first_name}
                        onChange={e => setFormData({...formData, first_name: e.target.value})}
                        placeholder="John"
                        autoComplete="off"
                        className="h-10 border-border/60"
                      />
                    </div>
                    <div className="grid gap-2">
                      <label className="text-xs font-bold uppercase text-muted-foreground">Last Name</label>
                      <Input 
                        value={formData.last_name}
                        onChange={e => setFormData({...formData, last_name: e.target.value})}
                        placeholder="Doe"
                        autoComplete="off"
                        className="h-10 border-border/60"
                      />
                    </div>
                  </div>

                  <div className="grid gap-2">
                    <label className="text-xs font-bold uppercase text-muted-foreground">Email Address</label>
                    <Input 
                      value={formData.email}
                      onChange={e => setFormData({...formData, email: e.target.value})}
                      placeholder="customer@example.com"
                      autoComplete="off"
                      readOnly={!!editingCustomer}
                      className={cn("h-10 border-border/60", editingCustomer && "bg-muted/30 cursor-not-allowed")}
                    />
                  </div>

                  {!editingCustomer && (
                    <div className="grid gap-3">
                      <div className="flex items-center justify-between">
                         <label className="text-xs font-bold uppercase text-muted-foreground">Password</label>
                         <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded-full text-white", passwordStrength.color)}>
                            {passwordStrength.label}
                         </span>
                      </div>
                      <Input 
                        type="password"
                        value={formData.password}
                        onChange={e => setFormData({...formData, password: e.target.value})}
                        placeholder="Enter secure password"
                        className="h-10 border-border/60"
                      />
                      {/* Strength Meter Bar */}
                      <div className="h-1 w-full bg-muted rounded-full overflow-hidden">
                         <div 
                           className={cn("h-full transition-all duration-300", passwordStrength.color)} 
                           style={{ width: `${passwordStrength.score}%` }}
                         />
                      </div>
                      {/* Password Requirements */}
                      <div className="grid grid-cols-1 gap-1.5 mt-1">
                         {passwordRequirements.map(req => (
                           <div key={req.id} className="flex items-center gap-2 text-[10px]">
                              {req.met ? <Check size={12} className="text-emerald-500" /> : <X size={12} className="text-muted-foreground" />}
                              <span className={req.met ? "text-foreground font-medium" : "text-muted-foreground"}>{req.label}</span>
                           </div>
                         ))}
                      </div>
                    </div>
                  )}

                  <div className="grid gap-2">
                    <label className="text-xs font-bold uppercase text-muted-foreground">Contact Number</label>
                    <Input 
                      value={formData.phone}
                      onChange={e => setFormData({...formData, phone: e.target.value})}
                      placeholder="+91 XXXXX XXXXX"
                      autoComplete="off"
                      className="h-10 border-border/60"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <label className="text-xs font-bold uppercase text-muted-foreground">Account Role</label>
                      <select 
                        className="flex h-10 w-full rounded-md border border-border/60 bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20"
                        value={formData.role}
                        onChange={e => setFormData({...formData, role: e.target.value as any})}
                      >
                        <option value="customer">Customer</option>
                        <option value="staff">Staff</option>
                        <option value="admin">Admin</option>
                      </select>
                    </div>
                    {editingCustomer && (
                      <div className="grid gap-2">
                        <label className="text-xs font-bold uppercase text-muted-foreground">Status</label>
                        <select 
                          className="flex h-10 w-full rounded-md border border-border/60 bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20"
                          value={formData.is_active ? 'active' : 'inactive'}
                          onChange={e => setFormData({...formData, is_active: e.target.value === 'active'})}
                        >
                          <option value="active">Active</option>
                          <option value="inactive">Inactive</option>
                        </select>
                      </div>
                    )}
                  </div>
               </div>
            </div>

            {/* ADDRESS SECTION */}
            <div className="space-y-6">
               <div className="space-y-4">
                  <div className="flex items-center justify-between border-b pb-2">
                     <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
                        <MapPin size={16} className="text-primary"/> Address Book
                     </h3>
                     {editingCustomer && (
                        <Button variant="ghost" size="sm" onClick={handleAddAddress} className="h-7 text-xs px-2 text-primary font-bold">
                           <Plus size={14} className="mr-1"/> Add Address
                        </Button>
                     )}
                  </div>
                  
                  <div className="space-y-3">
                     {!editingCustomer ? (
                        <div className="bg-blue-50/50 border border-blue-100 p-4 rounded-xl text-center">
                           <ShieldAlert className="mx-auto text-blue-400 mb-2" size={24} />
                           <p className="text-xs text-blue-600 font-medium">Create the customer account first to manage their address book.</p>
                        </div>
                     ) : editingCustomer.addresses && editingCustomer.addresses.length > 0 ? (
                        editingCustomer.addresses.map((addr: AddressData) => (
                           <div key={addr.id} className="relative group bg-white border border-border p-4 rounded-xl shadow-sm hover:border-primary/40 transition-colors">
                              <div className="flex items-center justify-between mb-2">
                                 <Badge variant={addr.address_type === 'shipping' ? 'default' : 'outline'} className="text-[9px] uppercase tracking-wider h-5">
                                    {addr.address_type}
                                 </Badge>
                                 {addr.is_default && (
                                    <Badge variant="surface" className="text-[9px] uppercase tracking-wider h-5 bg-emerald-50 text-emerald-600 border-emerald-100">Default</Badge>
                                 )}
                              </div>
                              <p className="text-sm font-bold text-foreground">{addr.full_name}</p>
                              <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                                 {addr.line1}{addr.line2 ? `, ${addr.line2}` : ''}<br/>
                                 {addr.city}, {addr.state} - {addr.postal_code}<br/>
                                 {addr.country}
                              </p>
                              <div className="mt-3 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                 <Button variant="outline" size="sm" onClick={() => handleEditAddress(addr)} className="h-7 text-[10px] px-2">Edit</Button>
                                 <Button variant="ghost" size="sm" onClick={() => handleDeleteAddress(addr.id)} className="h-7 text-[10px] px-2 text-destructive">Delete</Button>
                              </div>
                           </div>
                        ))
                     ) : (
                        <div className="text-center p-8 text-muted-foreground text-xs bg-muted/20 rounded-xl border border-dashed border-border">
                           No addresses found for this customer.
                        </div>
                     )}
                  </div>
               </div>
            </div>
          </div>

          <ModalFooter className="border-t pt-4">
            <Button
              variant="outline"
              onClick={() => setIsModalOpen(false)}
              className="rounded-xl border-primary/40 bg-white text-primary transition-all duration-300 hover:-translate-y-0.5 hover:border-primary hover:bg-primary hover:text-primary-foreground hover:shadow-sm"
            >
              Cancel
            </Button>
            <Button
              variant="outline"
              onClick={handleSave}
              className="rounded-xl border-primary/40 bg-white px-6 font-bold text-primary transition-all duration-300 hover:-translate-y-0.5 hover:border-primary hover:bg-primary hover:text-primary-foreground hover:shadow-sm"
            >
               {editingCustomer ? 'Update Customer' : 'Create Customer'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Address Sub-Modal */}
      <Modal open={isAddressModalOpen} onOpenChange={setIsAddressModalOpen}>
         <ModalContent className="max-w-md">
            <ModalHeader>
               <ModalTitle>{editingAddress ? 'Edit Address' : 'Add New Address'}</ModalTitle>
            </ModalHeader>
            <div className="space-y-4 py-4">
               <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                     <label className="text-xs font-bold uppercase text-muted-foreground">Type</label>
                     <select 
                        className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                        value={addressFormData.address_type}
                        onChange={e => setAddressFormData({...addressFormData, address_type: e.target.value as any})}
                     >
                        <option value="shipping">Shipping</option>
                        <option value="billing">Billing</option>
                     </select>
                  </div>
                  <div className="grid gap-2">
                     <label className="text-xs font-bold uppercase text-muted-foreground">Set as Default</label>
                     <select 
                        className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                        value={addressFormData.is_default ? 'yes' : 'no'}
                        onChange={e => setAddressFormData({...addressFormData, is_default: e.target.value === 'yes'})}
                     >
                        <option value="no">No</option>
                        <option value="yes">Yes</option>
                     </select>
                  </div>
               </div>

               <label className="flex items-center gap-2 text-xs text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={useForBothAddressTypes}
                    onChange={(e) => setUseForBothAddressTypes(e.target.checked)}
                  />
                  Use this same address for both shipping and billing
               </label>
               
               <div className="grid gap-2">
                  <label className="text-xs font-bold uppercase text-muted-foreground">Full Name</label>
                  <Input value={addressFormData.full_name} onChange={e => setAddressFormData({...addressFormData, full_name: e.target.value})} placeholder="Recipient Name" />
               </div>

               <div className="grid gap-2">
                  <label className="text-xs font-bold uppercase text-muted-foreground">Address Line 1</label>
                  <Input value={addressFormData.line1} onChange={e => setAddressFormData({...addressFormData, line1: e.target.value})} placeholder="Street, building, etc." />
               </div>

               <div className="grid gap-2">
                  <label className="text-xs font-bold uppercase text-muted-foreground">Address Line 2 (Optional)</label>
                  <Input value={addressFormData.line2} onChange={e => setAddressFormData({...addressFormData, line2: e.target.value})} placeholder="Apartment, suite, etc." />
               </div>

               <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                     <label className="text-xs font-bold uppercase text-muted-foreground">City</label>
                     <Input value={addressFormData.city} onChange={e => setAddressFormData({...addressFormData, city: e.target.value})} />
                  </div>
                  <div className="grid gap-2">
                     <label className="text-xs font-bold uppercase text-muted-foreground">State</label>
                     <Input value={addressFormData.state} onChange={e => setAddressFormData({...addressFormData, state: e.target.value})} />
                  </div>
               </div>

               <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                     <label className="text-xs font-bold uppercase text-muted-foreground">Postal Code</label>
                     <Input value={addressFormData.postal_code} onChange={e => setAddressFormData({...addressFormData, postal_code: e.target.value})} />
                  </div>
                  <div className="grid gap-2">
                     <label className="text-xs font-bold uppercase text-muted-foreground">Country</label>
                     <Input value={addressFormData.country} onChange={e => setAddressFormData({...addressFormData, country: e.target.value})} />
                  </div>
               </div>

               <div className="grid gap-2">
                  <label className="text-xs font-bold uppercase text-muted-foreground">Phone Number</label>
                  <Input value={addressFormData.phone} onChange={e => setAddressFormData({...addressFormData, phone: e.target.value})} />
               </div>
            </div>
            <ModalFooter>
               <Button
                 variant="outline"
                 onClick={() => setIsAddressModalOpen(false)}
                 className="rounded-xl border-primary/40 bg-white text-primary transition-all duration-300 hover:-translate-y-0.5 hover:border-primary hover:bg-primary hover:text-primary-foreground hover:shadow-sm"
               >
                 Cancel
               </Button>
               <Button
                 variant="outline"
                 onClick={handleSaveAddress}
                 className="rounded-xl border-primary/40 bg-white text-primary transition-all duration-300 hover:-translate-y-0.5 hover:border-primary hover:bg-primary hover:text-primary-foreground hover:shadow-sm"
               >
                 Save Address
               </Button>
            </ModalFooter>
         </ModalContent>
      </Modal>

      {/* Deactivate Confirmation Modal */}
      <Modal
        open={isDeactivateModalOpen}
        onOpenChange={(open) => {
          setIsDeactivateModalOpen(open);
          if (!open) setCustomerToDeactivate(null);
        }}
      >
        <ModalContent className="max-w-md">
          <ModalHeader>
            <ModalTitle>Deactivate Customer</ModalTitle>
          </ModalHeader>
          <div className="space-y-3 py-2">
            <p className="text-sm text-muted-foreground">
              Are you sure you want to deactivate this account?
            </p>
            {customerToDeactivate && (
              <div className="rounded-xl border border-border bg-muted/30 p-3 text-sm">
                <div className="font-semibold text-foreground">
                  {customerToDeactivate.first_name} {customerToDeactivate.last_name}
                </div>
                <div className="text-xs text-muted-foreground mt-1">{customerToDeactivate.email}</div>
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              The user will lose access, but the record will remain for audit/history.
            </p>
          </div>
          <ModalFooter>
            <Button
              variant="outline"
              onClick={() => setIsDeactivateModalOpen(false)}
              className="rounded-xl border-primary/40 bg-white text-primary transition-all duration-300 hover:-translate-y-0.5 hover:border-primary hover:bg-primary hover:text-primary-foreground hover:shadow-sm"
            >
              Cancel
            </Button>
            <Button
              variant="outline"
              onClick={handleDeactivateCustomer}
              className="rounded-xl border-red-300 bg-white text-red-600 transition-all duration-300 hover:-translate-y-0.5 hover:border-red-600 hover:bg-red-600 hover:text-white hover:shadow-sm"
            >
              Deactivate Account
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <ConfirmDialog
        open={Boolean(addressToDelete)}
        onOpenChange={(open) => {
          if (!open) setAddressToDelete(null);
        }}
        title="Delete Address"
        description="This address will be removed from the customer profile."
        confirmLabel="Delete Address"
        variant="destructive"
        onConfirm={confirmDeleteAddress}
      />

      <div className="pointer-events-none fixed right-5 top-5 z-50 space-y-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={[
              'rounded-xl border bg-white px-4 py-3 text-sm shadow-lg',
              toast.variant === 'success' ? 'border-emerald-300 text-emerald-700' : '',
              toast.variant === 'error' ? 'border-destructive/40 text-destructive' : '',
              toast.variant === 'info' ? 'border-blue-300 text-blue-700' : '',
            ].join(' ')}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </div>
  );
};
