export type CustomerRole = 'admin' | 'staff' | 'customer';

export interface AddressData {
  id: string;
  address_type: 'shipping' | 'billing';
  is_default: boolean;
  full_name: string;
  line1: string;
  line2?: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  phone: string;
}

export interface Customer {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  role: CustomerRole;
  is_active: boolean;
  date_joined: string;
  failed_login_attempts: number;
  last_failed_login?: string | null;
  locked_until?: string | null;
  is_locked?: boolean;
  is_email_verified: boolean;
  addresses: AddressData[];
}

export interface CustomerCreateData {
  email: string;
  password?: string;
  first_name: string;
  last_name: string;
  phone?: string;
  role?: CustomerRole;
}

export interface CustomerUpdateData {
  first_name?: string;
  last_name?: string;
  phone?: string;
  role?: CustomerRole;
  is_active?: boolean;
  is_email_verified?: boolean;
}
