/** One place for counter formatting, so a receipt never reads ₹2000 beside ₹2798.00. */
export const money = (value: string | number) =>
  `₹${Number(value).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

export const asNumber = (value: string | number) => Number(value || 0);
