import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Monitor, Pencil, Plus, Trash2 } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Input } from '@/components/ui/Input';
import {
  Modal,
  ModalContent,
  ModalDescription,
  ModalFooter,
  ModalHeader,
  ModalTitle,
} from '@/components/ui/Modal';
import posService, { type PosTerminal, type PosTerminalWrite } from '@/services/api/pos';

interface Props {
  /** Admin-only in practice: staff get a read-only table, the server agrees. */
  canEdit: boolean;
  onToast: (variant: 'success' | 'error' | 'info', message: string) => void;
}

type FormState = { code: string; name: string; location: string; is_active: boolean };

const EMPTY_FORM: FormState = { code: '', name: '', location: '', is_active: true };

const errorMessage = (error: any, fallback: string): string => {
  const data = error?.response?.data;
  if (!data) return fallback;
  if (typeof data === 'string') return data;
  if (typeof data.detail === 'string') return data.detail;
  // DRF field errors: {"code": ["A terminal with this code already exists."]}
  const firstField = Object.values(data).find((v) => Array.isArray(v) && v.length);
  if (Array.isArray(firstField)) return String(firstField[0]);
  return fallback;
};

export const POSTerminalsSettings: React.FC<Props> = ({ canEdit, onToast }) => {
  const [terminals, setTerminals] = useState<PosTerminal[]>([]);
  const [loading, setLoading] = useState(true);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<PosTerminal | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const [pendingDelete, setPendingDelete] = useState<PosTerminal | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [togglingId, setTogglingId] = useState<string>('');

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setTerminals(await posService.allTerminals());
    } catch (error: any) {
      onToast('error', errorMessage(error, 'Failed to load POS terminals.'));
    } finally {
      setLoading(false);
    }
  }, [onToast]);

  useEffect(() => {
    void load();
  }, [load]);

  const activeCount = useMemo(() => terminals.filter((t) => t.is_active).length, [terminals]);

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormOpen(true);
  };

  const openEdit = (terminal: PosTerminal) => {
    setEditing(terminal);
    setForm({
      code: terminal.code,
      name: terminal.name,
      location: terminal.location || '',
      is_active: terminal.is_active,
    });
    setFormOpen(true);
  };

  const submit = async () => {
    const payload: PosTerminalWrite = {
      code: form.code.trim().toUpperCase(),
      name: form.name.trim(),
      location: form.location.trim(),
      is_active: form.is_active,
    };
    if (!payload.code || !payload.name) {
      onToast('error', 'Code and name are both required.');
      return;
    }

    try {
      setSaving(true);
      if (editing) {
        await posService.updateTerminal(editing.id, payload);
        onToast('success', `${payload.code} updated.`);
      } else {
        await posService.createTerminal(payload);
        onToast('success', `${payload.code} added.`);
      }
      setFormOpen(false);
      await load();
    } catch (error: any) {
      onToast('error', errorMessage(error, 'Could not save the terminal.'));
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (terminal: PosTerminal) => {
    try {
      setTogglingId(terminal.id);
      await posService.updateTerminal(terminal.id, { is_active: !terminal.is_active });
      onToast('success', `${terminal.code} ${terminal.is_active ? 'deactivated' : 'activated'}.`);
      await load();
    } catch (error: any) {
      // The server refuses to deactivate a terminal with an open shift (409).
      onToast('error', errorMessage(error, 'Could not change the terminal.'));
    } finally {
      setTogglingId('');
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    try {
      setDeleting(true);
      await posService.deleteTerminal(pendingDelete.id);
      onToast('success', `${pendingDelete.code} deleted.`);
      setPendingDelete(null);
      await load();
    } catch (error: any) {
      // 409 when the terminal has traded — the message tells them to deactivate.
      onToast('error', errorMessage(error, 'Could not delete the terminal.'));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-foreground">POS Terminals</h2>
          <p className="text-xs text-muted-foreground">
            The counters that can take money — a stall table, the shop till, a staff phone.
            Staff pick one of these when they open a shift.
          </p>
        </div>
        {canEdit ? (
          <Button onClick={openCreate} className="gap-2">
            <Plus size={16} />
            Add terminal
          </Button>
        ) : null}
      </div>

      {loading ? (
        <Card className="rounded-2xl border border-border/70 bg-white p-8 text-center text-sm text-muted-foreground">
          Loading terminals...
        </Card>
      ) : terminals.length === 0 ? (
        <Card className="rounded-2xl border border-border/70 bg-white p-8 text-center">
          <Monitor className="mx-auto mb-3 text-muted-foreground" size={22} />
          <p className="text-sm font-medium text-foreground">No terminals yet</p>
          <p className="mx-auto mt-1 max-w-sm text-xs text-muted-foreground">
            The counter can't open a shift until one exists. Add one per till — the code is
            printed on receipts, so make it something you'd recognise on paper.
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {terminals.map((terminal) => (
            <Card
              key={terminal.id}
              className="rounded-2xl border border-border/70 bg-white p-4"
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-foreground">{terminal.name}</p>
                    <Badge variant="outline" className="font-mono">{terminal.code}</Badge>
                    {terminal.is_active ? (
                      <Badge variant="surface">Active</Badge>
                    ) : (
                      <Badge variant="secondary">Inactive</Badge>
                    )}
                    {terminal.has_open_shift ? (
                      <Badge variant="default">Shift open</Badge>
                    ) : null}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {terminal.location || 'No location set'}
                    {typeof terminal.shift_count === 'number' ? (
                      <>
                        {' · '}
                        {terminal.shift_count} shift{terminal.shift_count === 1 ? '' : 's'}
                      </>
                    ) : null}
                    {typeof terminal.order_count === 'number' ? (
                      <>
                        {' · '}
                        {terminal.order_count} sale{terminal.order_count === 1 ? '' : 's'}
                      </>
                    ) : null}
                  </p>
                </div>

                {canEdit ? (
                  <div className="flex shrink-0 items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={togglingId === terminal.id}
                      onClick={() => toggleActive(terminal)}
                    >
                      {togglingId === terminal.id ? (
                        <Loader2 className="animate-spin" size={14} />
                      ) : terminal.is_active ? (
                        'Deactivate'
                      ) : (
                        'Activate'
                      )}
                    </Button>
                    <Button variant="outline" size="sm" className="gap-1" onClick={() => openEdit(terminal)}>
                      <Pencil size={14} />
                      Edit
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={() => setPendingDelete(terminal)}
                      aria-label={`Delete ${terminal.code}`}
                    >
                      <Trash2 size={14} />
                    </Button>
                  </div>
                ) : null}
              </div>
            </Card>
          ))}
        </div>
      )}

      {terminals.length > 0 && activeCount === 0 ? (
        <p className="text-xs text-amber-700">
          Every terminal is inactive, so no one can open a shift or ring up a sale.
        </p>
      ) : null}

      <Modal open={formOpen} onOpenChange={setFormOpen}>
        <ModalContent className="max-w-md">
          <ModalHeader>
            <ModalTitle>{editing ? `Edit ${editing.code}` : 'Add a terminal'}</ModalTitle>
            <ModalDescription>
              The code is printed on receipts and shown in shift reports.
            </ModalDescription>
          </ModalHeader>

          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-foreground" htmlFor="terminal-code">
                Code
              </label>
              <Input
                id="terminal-code"
                value={form.code}
                placeholder="STALL-01"
                autoCapitalize="characters"
                onChange={(e) => setForm((prev) => ({ ...prev, code: e.target.value.toUpperCase() }))}
              />
              <p className="text-[11px] text-muted-foreground">
                Letters, digits, dot, dash or underscore. Must be unique.
              </p>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-foreground" htmlFor="terminal-name">
                Name
              </label>
              <Input
                id="terminal-name"
                value={form.name}
                placeholder="Stall table"
                onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-foreground" htmlFor="terminal-location">
                Location <span className="text-muted-foreground">(optional)</span>
              </label>
              <Input
                id="terminal-location"
                value={form.location}
                placeholder="Bhubaneswar exhibition"
                onChange={(e) => setForm((prev) => ({ ...prev, location: e.target.value }))}
              />
            </div>

            <label className="flex items-center gap-2 pt-1 text-sm text-foreground">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border"
                checked={form.is_active}
                onChange={(e) => setForm((prev) => ({ ...prev, is_active: e.target.checked }))}
              />
              Active — staff can open a shift on it
            </label>
          </div>

          <ModalFooter>
            <Button variant="outline" onClick={() => setFormOpen(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={saving}>
              {saving ? 'Saving...' : editing ? 'Save changes' : 'Add terminal'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null);
        }}
        title={pendingDelete ? `Delete ${pendingDelete.code}?` : 'Delete terminal?'}
        description={
          pendingDelete && ((pendingDelete.shift_count || 0) > 0 || (pendingDelete.order_count || 0) > 0)
            ? 'This terminal has trading history, so it can’t be deleted — deactivate it instead and its shifts and sales stay attached to it.'
            : 'This terminal has never been used, so deleting it removes it completely.'
        }
        confirmLabel="Delete"
        variant="destructive"
        loading={deleting}
        onConfirm={confirmDelete}
      />
    </div>
  );
};

export default POSTerminalsSettings;
