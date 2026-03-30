import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Modal, ModalContent, ModalFooter, ModalHeader, ModalTitle } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';

const DEFAULT_SESSION_TIMEOUT_MS = 10 * 60 * 1000; // 10 minutes inactivity
const DEFAULT_WARNING_MS = 2 * 60 * 1000; // show modal 2 minutes before logout
const SESSION_TIMEOUT_EVENT = 'aurora:session-timeout-update';
const SESSION_TIMEOUT_EXTEND_EVENT = 'aurora:session-timeout-extend';
const SESSION_TIMEOUT_LOGOUT_EVENT = 'aurora:session-timeout-logout';

const readMs = (value: string | undefined, fallback: number) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
};

const formatCountdown = (seconds: number) => {
  const mins = Math.floor(seconds / 60)
    .toString()
    .padStart(2, '0');
  const secs = (seconds % 60).toString().padStart(2, '0');
  return `${mins}:${secs}`;
};

interface SessionTimeoutManagerProps {
  preferredTitle?: string;
}

export const SessionTimeoutManager: React.FC<SessionTimeoutManagerProps> = ({ preferredTitle }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const sessionTimeoutMs = useMemo(
    () => readMs(import.meta.env.VITE_SESSION_TIMEOUT_MS, DEFAULT_SESSION_TIMEOUT_MS),
    []
  );
  const warningMs = useMemo(
    () => Math.min(readMs(import.meta.env.VITE_SESSION_WARNING_MS, DEFAULT_WARNING_MS), sessionTimeoutMs - 5000),
    [sessionTimeoutMs]
  );

  const [warningOpen, setWarningOpen] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(Math.ceil(warningMs / 1000));

  const warningTimerRef = useRef<number | null>(null);
  const logoutTimerRef = useRef<number | null>(null);
  const heartbeatRef = useRef<number | null>(null);
  const titleBlinkRef = useRef<number | null>(null);
  const logoutAtRef = useRef<number>(0);
  const defaultTitleRef = useRef<string>('');

  const isAuthenticated = useCallback(() => {
    return Boolean(localStorage.getItem('auth_token'));
  }, []);

  const clearTimer = (id: number | null) => {
    if (id) {
      window.clearTimeout(id);
      window.clearInterval(id);
    }
  };

  const clearAllTimers = useCallback(() => {
    clearTimer(warningTimerRef.current);
    clearTimer(logoutTimerRef.current);
    clearTimer(heartbeatRef.current);
    clearTimer(titleBlinkRef.current);
    warningTimerRef.current = null;
    logoutTimerRef.current = null;
    heartbeatRef.current = null;
    titleBlinkRef.current = null;
    document.title = defaultTitleRef.current;
  }, []);

  const forceLogout = useCallback(() => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('auth_user');
    clearAllTimers();
    setWarningOpen(false);

    const next = `${location.pathname}${location.search}`;
    navigate(`/login?next=${encodeURIComponent(next)}`, { replace: true });
  }, [clearAllTimers, location.pathname, location.search, navigate]);

  const startWarningCountdown = useCallback(() => {
    setWarningOpen(true);
  }, []);

  const scheduleSession = useCallback(() => {
    clearAllTimers();

    if (!isAuthenticated() || location.pathname === '/login') {
      return;
    }

    setWarningOpen(false);
    setSecondsLeft(Math.ceil(sessionTimeoutMs / 1000));

    logoutAtRef.current = Date.now() + sessionTimeoutMs;

    clearTimer(heartbeatRef.current);
    heartbeatRef.current = window.setInterval(() => {
      const remainingMs = Math.max(0, logoutAtRef.current - Date.now());
      const remainingSeconds = Math.ceil(remainingMs / 1000);
      setSecondsLeft(remainingSeconds);
      if (remainingSeconds <= 0) {
        clearTimer(heartbeatRef.current);
        heartbeatRef.current = null;
      }
    }, 1000);

    warningTimerRef.current = window.setTimeout(() => {
      startWarningCountdown();
    }, Math.max(0, sessionTimeoutMs - warningMs));

    logoutTimerRef.current = window.setTimeout(() => {
      forceLogout();
    }, sessionTimeoutMs);
  }, [clearAllTimers, forceLogout, isAuthenticated, location.pathname, sessionTimeoutMs, startWarningCountdown, warningMs]);

  const handleStayLoggedIn = useCallback(() => {
    scheduleSession();
  }, [scheduleSession]);

  useEffect(() => {
    defaultTitleRef.current = preferredTitle?.trim() || document.title;
  }, [preferredTitle]);

  useEffect(() => {
    scheduleSession();
    return () => clearAllTimers();
  }, [scheduleSession, clearAllTimers]);

  useEffect(() => {
    if (!isAuthenticated() || warningOpen) {
      return;
    }

    const onActivity = () => {
      scheduleSession();
    };

    const events: Array<keyof WindowEventMap> = ['mousedown', 'keydown', 'scroll', 'touchstart'];
    events.forEach((evt) => window.addEventListener(evt, onActivity, { passive: true }));

    return () => {
      events.forEach((evt) => window.removeEventListener(evt, onActivity));
    };
  }, [isAuthenticated, scheduleSession, warningOpen]);

  useEffect(() => {
    const emit = () => {
      window.dispatchEvent(
        new CustomEvent(SESSION_TIMEOUT_EVENT, {
          detail: {
            warningOpen,
            secondsLeft,
          },
        })
      );
    };

    emit();
  }, [warningOpen, secondsLeft]);

  useEffect(() => {
    const onExtend = () => handleStayLoggedIn();
    const onLogout = () => forceLogout();

    window.addEventListener(SESSION_TIMEOUT_EXTEND_EVENT, onExtend);
    window.addEventListener(SESSION_TIMEOUT_LOGOUT_EVENT, onLogout);

    return () => {
      window.removeEventListener(SESSION_TIMEOUT_EXTEND_EVENT, onExtend);
      window.removeEventListener(SESSION_TIMEOUT_LOGOUT_EVENT, onLogout);
    };
  }, [forceLogout, handleStayLoggedIn]);

  useEffect(() => {
    if (!warningOpen) {
      clearTimer(titleBlinkRef.current);
      titleBlinkRef.current = null;
      document.title = defaultTitleRef.current;
      return;
    }

    const updateTitle = () => {
      if (!document.hidden) {
        document.title = defaultTitleRef.current;
        clearTimer(titleBlinkRef.current);
        titleBlinkRef.current = null;
        return;
      }

      let showAlert = false;
      clearTimer(titleBlinkRef.current);
      titleBlinkRef.current = window.setInterval(() => {
        showAlert = !showAlert;
        document.title = showAlert
          ? `Session expiring in ${formatCountdown(secondsLeft)}`
          : defaultTitleRef.current;
      }, 900);
    };

    const onVisibilityChange = () => {
      updateTitle();
    };

    updateTitle();
    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange);
      clearTimer(titleBlinkRef.current);
      titleBlinkRef.current = null;
      document.title = defaultTitleRef.current;
    };
  }, [secondsLeft, warningOpen]);

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === 'auth_token' && !event.newValue) {
        clearAllTimers();
        setWarningOpen(false);
      }
    };

    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [clearAllTimers]);

  if (!isAuthenticated() || location.pathname === '/login') {
    return null;
  }

  return (
    <Modal
      open={warningOpen}
      onOpenChange={(open) => {
        // Prevent dismissing the warning without action.
        if (!open) return;
        setWarningOpen(open);
      }}
    >
      <ModalContent className="max-w-md">
        <ModalHeader>
          <ModalTitle>Session Expiring Soon</ModalTitle>
        </ModalHeader>
        <div className="space-y-3 py-2">
          <p className="text-sm text-muted-foreground">
            You will be logged out in <span className="font-bold text-foreground">{formatCountdown(secondsLeft)}</span> due to inactivity.
          </p>
          <p className="text-xs text-muted-foreground">
            Click below to remain logged in.
          </p>
        </div>
        <ModalFooter>
          <Button
            variant="outline"
            onClick={forceLogout}
            className="rounded-xl border-red-300 bg-white text-red-600 transition-all duration-300 hover:-translate-y-0.5 hover:border-red-600 hover:bg-red-600 hover:text-white"
          >
            Logout Now
          </Button>
          <Button
            variant="outline"
            onClick={handleStayLoggedIn}
            className="rounded-xl border-primary/40 bg-white text-primary transition-all duration-300 hover:-translate-y-0.5 hover:border-primary hover:bg-primary hover:text-primary-foreground"
          >
            Remain Logged In
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};
