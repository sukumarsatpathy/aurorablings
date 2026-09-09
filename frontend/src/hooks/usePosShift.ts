import { useCallback, useEffect, useState } from 'react';

import posService, { type PosShift, type PosTerminal } from '@/services/api/pos';

const TERMINAL_KEY = 'pos_terminal_id';

/**
 * The shift is the counter's session: nothing can be sold or paid for without
 * one, so this is loaded before the till renders anything else.
 *
 * The chosen terminal is remembered on the device because a stall tablet is the
 * same terminal every day, and asking again each morning is friction with no
 * payoff. The shift itself is never cached — it lives on the server, where the
 * one-open-shift-per-terminal rule is enforced.
 */
export function usePosShift() {
  const [terminals, setTerminals] = useState<PosTerminal[]>([]);
  const [terminalId, setTerminalId] = useState<string>(() => localStorage.getItem(TERMINAL_KEY) || '');
  const [shift, setShift] = useState<PosShift | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const chooseTerminal = useCallback((id: string) => {
    localStorage.setItem(TERMINAL_KEY, id);
    setTerminalId(id);
  }, []);

  const refresh = useCallback(async () => {
    setError('');
    try {
      const current = await posService.currentShift(terminalId || undefined);
      setShift(current);
    } catch {
      setError('Could not reach the counter service.');
    } finally {
      setLoading(false);
    }
  }, [terminalId]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const list = await posService.terminals();
        if (active) setTerminals(list);
      } catch {
        if (active) setError('Could not load terminals.');
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const openShift = useCallback(
    async (openingFloat: string) => {
      if (!terminalId) throw new Error('Choose a terminal first.');
      const opened = await posService.openShift(terminalId, openingFloat);
      setShift(opened);
      return opened;
    },
    [terminalId],
  );

  return {
    terminals,
    terminalId,
    chooseTerminal,
    shift,
    loading,
    error,
    refresh,
    openShift,
    setShift,
  };
}
