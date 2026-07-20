export type UploadProgressHandler = (percent: number) => void;

/**
 * Converts an axios onUploadProgress event into a 0-100 percent callback.
 * Returns undefined when no handler is given so axios config stays clean.
 */
export const toUploadProgress = (onProgress?: UploadProgressHandler) =>
  onProgress
    ? (event: { loaded: number; total?: number }) => {
        if (event.total) {
          onProgress(Math.round((event.loaded / event.total) * 100));
        }
      }
    : undefined;
