import React from 'react';
import { PaymentGatewayCard } from './PaymentGatewayCard';
import type { PluginSettingBundle } from './types';

interface Props {
  bundle: PluginSettingBundle;
  value: Record<string, unknown>;
  saving: boolean;
  canEdit: boolean;
  onChange: (next: Record<string, unknown>) => void;
  onSave: () => void;
}

export const PhonePeForm: React.FC<Props> = (props) => {
  return <PaymentGatewayCard {...props} />;
};
