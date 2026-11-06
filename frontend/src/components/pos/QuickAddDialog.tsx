import { useEffect, useRef, useState } from 'react';

import { quickItemService, type QuickItem } from '@/services/api/pos';

import { apiError, shrinkPhoto } from './photo';

interface Props {
  /** Pre-fills the name with whatever was typed in the search box. */
  initialName?: string;
  onClose: () => void;
  /** Called with the saved item; the counter adds one to the cart. */
  onSaved: (item: QuickItem) => void;
}

/**
 * Sell a piece that has no barcode.
 *
 * Photo, name, price, how many are on hand — then it goes straight into the
 * cart. It is saved as a counter-only quick item, never a catalogue product, so
 * nothing appears on the website. The price is stored on the server; the sale
 * itself still sends only the item and a quantity.
 */
export function QuickAddDialog({ initialName = '', onClose, onSaved }: Props) {
  const [name, setName] = useState(initialName);
  const [price, setPrice] = useState('');
  const [quantity, setQuantity] = useState('1');
  const [photo, setPhoto] = useState<Blob | null>(null);
  const [preview, setPreview] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  const pick = async (file: File | undefined) => {
    if (!file) return;
    const small = await shrinkPhoto(file);
    setPhoto(small);
    setPreview((old) => {
      if (old) URL.revokeObjectURL(old);
      return URL.createObjectURL(small);
    });
  };

  const priceNum = Number(price);
  const qtyNum = Number(quantity);
  const canSave =
    name.trim().length > 0 && priceNum > 0 && Number.isInteger(qtyNum) && qtyNum >= 1 && !busy;

  const save = async () => {
    if (!canSave) return;
    setBusy(true);
    setError('');
    try {
      const item = await quickItemService.create({
        name: name.trim(),
        price: priceNum.toFixed(2),
        quantity: qtyNum,
        image: photo,
      });
      onSaved(item);
    } catch (err) {
      setError(apiError(err, 'Could not save the item.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-40 grid place-items-center overflow-y-auto bg-black/50 p-4">
      <form
        className="w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-xl"
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        <h3 className="text-base font-semibold">Quick add · item without barcode</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Counter only — this does not create a product on the website.
        </p>

        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={(e) => {
            void pick(e.target.files?.[0]);
            e.target.value = '';
          }}
        />
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="mt-4 flex aspect-[4/3] w-full items-center justify-center overflow-hidden rounded-lg border-2 border-dashed border-border bg-muted/40 text-sm font-semibold text-muted-foreground hover:border-primary"
        >
          {preview ? (
            <img src={preview} alt="Item" className="h-full w-full object-cover" />
          ) : (
            <span className="flex flex-col items-center gap-2">
              <svg aria-hidden="true" viewBox="0 0 24 24" className="h-8 w-8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
                <circle cx="12" cy="13" r="3.5" />
              </svg>
              Take a photo
            </span>
          )}
        </button>
        {preview && (
          <button
            type="button"
            className="mt-1 text-xs font-semibold text-muted-foreground underline"
            onClick={() => fileRef.current?.click()}
          >
            Retake photo
          </button>
        )}

        <label className="mt-4 block text-xs font-semibold text-muted-foreground">
          Product name
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={150}
            placeholder="e.g. Red stone jhumka"
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-base text-foreground outline-none focus:border-primary md:text-sm"
            autoFocus={!initialName}
          />
        </label>

        <div className="mt-3 grid grid-cols-2 gap-3">
          <label className="block text-xs font-semibold text-muted-foreground">
            Price (₹)
            <input
              value={price}
              onChange={(e) => setPrice(e.target.value.replace(/[^\d.]/g, ''))}
              inputMode="decimal"
              placeholder="0"
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-base tabular-nums text-foreground outline-none focus:border-primary md:text-sm"
              autoFocus={Boolean(initialName)}
            />
          </label>
          <label className="block text-xs font-semibold text-muted-foreground">
            Qty on hand
            <input
              value={quantity}
              onChange={(e) => setQuantity(e.target.value.replace(/\D/g, ''))}
              inputMode="numeric"
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-base tabular-nums text-foreground outline-none focus:border-primary md:text-sm"
            />
          </label>
        </div>
        <p className="mt-1 text-[11px] text-muted-foreground">
          How many pieces you have. One is added to this sale; change it in the cart.
        </p>

        {error && (
          <p className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
        )}

        <div className="mt-4 flex gap-2">
          <button
            type="button"
            className="flex-1 rounded-lg border border-border px-4 py-2.5 text-sm font-semibold"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!canSave}
            className="flex-1 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
          >
            {busy ? 'Saving…' : 'Save & add to cart'}
          </button>
        </div>
      </form>
    </div>
  );
}
