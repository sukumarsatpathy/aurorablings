import React from 'react';

interface UploadOverlayProps {
  visible: boolean;
  message?: string;
  /** 0-100 shows a progress bar; null/undefined shows only the spinner */
  percent?: number | null;
}

/**
 * Full-screen blocking overlay shown while files are uploading / being
 * processed on the server. Prevents double-submits and gives admins
 * clear feedback that work is in progress.
 */
export function UploadOverlay({ visible, message = 'Uploading...', percent = null }: UploadOverlayProps) {
  if (!visible) return null;

  const clamped = typeof percent === 'number' ? Math.min(100, Math.max(0, percent)) : null;

  return (
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/50"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="w-80 rounded-xl bg-white p-6 text-center shadow-2xl">
        <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-gray-200 border-t-gray-900" />
        <div className="text-sm font-medium text-gray-900">{message}</div>
        {clamped !== null ? (
          <>
            <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-gray-200">
              <div
                className="h-full rounded-full bg-gray-900 transition-all duration-200"
                style={{ width: `${clamped}%` }}
              />
            </div>
            <div className="mt-1 text-xs text-gray-500">{Math.round(clamped)}%</div>
          </>
        ) : null}
      </div>
    </div>
  );
}

export default UploadOverlay;
