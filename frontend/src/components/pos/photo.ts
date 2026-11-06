/**
 * Shrink a phone photo before it leaves the tablet.
 *
 * A modern phone camera produces 4–8 MB images; a stall runs on 4G. The server
 * re-encodes to WebP anyway, so sending more than ~1200px is wasted upload time
 * with a customer waiting. Falls back to the original file if the browser
 * cannot decode it (e.g. HEIC on some Androids) — the server still accepts it.
 */
export async function shrinkPhoto(file: File, maxSide = 1200, quality = 0.82): Promise<Blob> {
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
    const width = Math.round(bitmap.width * scale);
    const height = Math.round(bitmap.height * scale);
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) return file;
    ctx.drawImage(bitmap, 0, 0, width, height);
    bitmap.close?.();
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality));
    return blob && blob.size < file.size ? blob : file;
  } catch {
    return file;
  }
}

export const apiError = (err: unknown, fallback: string): string => {
  const data = (err as { response?: { data?: Record<string, unknown> } })?.response?.data;
  if (!data) return fallback;
  if (typeof data.detail === 'string') return data.detail;
  if (typeof data.message === 'string') return data.message;
  // DRF field errors: { amount: ["..."] }
  const first = Object.values(data).find((v) => Array.isArray(v) && typeof v[0] === 'string') as string[] | undefined;
  return first?.[0] || fallback;
};
