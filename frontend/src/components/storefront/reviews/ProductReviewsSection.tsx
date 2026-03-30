import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { MessageSquare, ThumbsDown, ThumbsUp, Star, Sparkles, ShieldCheck } from 'lucide-react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal, ModalContent, ModalFooter, ModalHeader, ModalTitle } from '@/components/ui/Modal';
import { Skeleton } from '@/components/ui/Skeleton';
import { useMyReview } from '@/hooks/useMyReview';
import { useProductReviews } from '@/hooks/useProductReviews';
import { useReviewSummary } from '@/hooks/useReviewSummary';
import { useTurnstileConfig } from '@/hooks/useTurnstileConfig';
import { TurnstileWidget } from '@/components/security/TurnstileWidget';
import reviewsService, { type ReviewSort, type ProductReview } from '@/services/api/reviews';

const SORT_OPTIONS: Array<{ value: ReviewSort; label: string }> = [
  { value: 'featured_first', label: 'Featured First' },
  { value: 'newest', label: 'Newest' },
  { value: 'highest_rating', label: 'Highest Rating' },
  { value: 'lowest_rating', label: 'Lowest Rating' },
  { value: 'most_helpful', label: 'Most Helpful' },
];
const MAX_REVIEW_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;

function StarRow({ rating, size = 16 }: { rating: number; size?: number }) {
  return (
    <div className="flex items-center gap-1">
      {Array.from({ length: 5 }).map((_, idx) => (
        <Star
          key={idx}
          size={size}
          className={idx < rating ? 'text-amber-500' : 'text-muted-foreground/40'}
          fill={idx < rating ? 'currentColor' : 'none'}
        />
      ))}
    </div>
  );
}

function ReviewFormModal({
  open,
  onOpenChange,
  productId,
  reviewId,
  defaultRating,
  defaultTitle,
  defaultComment,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  productId: string;
  reviewId?: string | null;
  defaultRating?: number;
  defaultTitle?: string;
  defaultComment?: string;
}) {
  const queryClient = useQueryClient();

  const [rating, setRating] = useState(defaultRating || 5);
  const [title, setTitle] = useState(defaultTitle || '');
  const [comment, setComment] = useState(defaultComment || '');
  const [images, setImages] = useState<File[]>([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [turnstileToken, setTurnstileToken] = useState('');
  const [turnstileResetKey, setTurnstileResetKey] = useState(0);
  const { turnstileEnabled, turnstileSiteKey } = useTurnstileConfig();

  const mutation = useMutation({
    mutationFn: async () => {
      if (reviewId) {
        return reviewsService.updateReview(reviewId, { rating, title, comment, images });
      }
      return reviewsService.createReview(productId, { rating, title, comment, images, turnstile_token: turnstileToken });
    },
    onSuccess: () => {
      setMessage('Thanks. Your review has been submitted for approval.');
      setError('');
      setImages([]);
      setTurnstileToken('');
      setTurnstileResetKey((prev) => prev + 1);
      queryClient.invalidateQueries({ queryKey: ['review-summary', productId] });
      queryClient.invalidateQueries({ queryKey: ['product-reviews', productId] });
      queryClient.invalidateQueries({ queryKey: ['my-reviews'] });
    },
    onError: (err: any) => {
      setError(err?.response?.data?.message || 'Unable to submit review right now.');
      if (!reviewId && turnstileEnabled) {
        setTurnstileToken('');
        setTurnstileResetKey((prev) => prev + 1);
      }
    },
  });

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage('');
    setError('');
    if (!reviewId && turnstileEnabled && !turnstileToken) {
      setError('Please complete CAPTCHA verification.');
      return;
    }
    mutation.mutate();
  };

  return (
    <Modal open={open} onOpenChange={onOpenChange}>
      <ModalContent className="max-w-xl">
        <ModalHeader>
          <ModalTitle>{reviewId ? 'Edit Your Review' : 'Write a Review'}</ModalTitle>
        </ModalHeader>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Rating</label>
            <div className="flex items-center gap-2">
              {Array.from({ length: 5 }).map((_, idx) => {
                const starValue = idx + 1;
                return (
                  <button
                    type="button"
                    key={starValue}
                    className="rounded-full p-1"
                    onClick={() => setRating(starValue)}
                  >
                    <Star
                      size={20}
                      className={starValue <= rating ? 'text-amber-500' : 'text-muted-foreground/40'}
                      fill={starValue <= rating ? 'currentColor' : 'none'}
                    />
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Title</label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Optional review title" maxLength={255} />
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Comment</label>
            <textarea
              className="min-h-28 w-full rounded-xl border border-input bg-transparent px-4 py-3 text-sm"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              maxLength={2000}
              required
            />
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Images (optional)</label>
            <Input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              multiple
              onChange={(e) => {
                setError('');
                const next = Array.from(e.target.files || [])
                  .filter((file) => file.size <= MAX_REVIEW_IMAGE_SIZE_BYTES)
                  .slice(0, 5);
                if ((e.target.files || []).length !== next.length) {
                  setError('Only JPG, PNG, WEBP images up to 5 MB are allowed.');
                }
                setImages(next);
              }}
            />
          </div>

          {!reviewId ? (
            <TurnstileWidget
              enabled={turnstileEnabled}
              siteKey={turnstileSiteKey}
              resetKey={turnstileResetKey}
              onTokenChange={setTurnstileToken}
            />
          ) : null}

          {message ? <p className="text-sm text-green-700">{message}</p> : null}
          {error ? <p className="text-sm text-red-600">{error}</p> : null}

          <ModalFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Close
            </Button>
            <Button type="submit" disabled={mutation.isPending || comment.trim().length === 0}>
              {mutation.isPending ? 'Submitting...' : reviewId ? 'Update Review' : 'Submit Review'}
            </Button>
          </ModalFooter>
        </form>
      </ModalContent>
    </Modal>
  );
}

function ReviewCard({ review, onVote }: { review: ProductReview; onVote: (reviewId: string, vote: 'helpful' | 'unhelpful') => void }) {
  return (
    <article className="rounded-2xl border border-border bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <p className="text-sm font-semibold">{review.reviewer_name}</p>
          <div className="flex flex-wrap items-center gap-2">
            <StarRow rating={review.rating} size={14} />
            <span className="text-xs text-muted-foreground">{new Date(review.created_at).toLocaleDateString()}</span>
            {review.is_verified_purchase ? (
              <Badge variant="surface" className="gap-1 text-[10px] uppercase tracking-wide"><ShieldCheck size={12} />Verified Purchase</Badge>
            ) : null}
            {review.is_featured ? (
              <Badge className="gap-1 text-[10px] uppercase tracking-wide"><Sparkles size={12} />Featured</Badge>
            ) : null}
          </div>
        </div>
      </div>

      {review.title ? <h4 className="mt-3 text-sm font-bold">{review.title}</h4> : null}
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{review.comment}</p>

      {review.media?.length ? (
        <div className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-5">
          {review.media.map((media) => (
            <img key={media.id} src={media.image} alt="Review" className="h-20 w-full rounded-lg object-cover" loading="lazy" />
          ))}
        </div>
      ) : null}

      <div className="mt-4 flex items-center gap-2 text-xs">
        <Button variant="outline" size="sm" className="gap-2" onClick={() => onVote(review.id, 'helpful')}>
          <ThumbsUp size={14} /> Helpful ({review.helpful_count})
        </Button>
        <Button variant="outline" size="sm" className="gap-2" onClick={() => onVote(review.id, 'unhelpful')}>
          <ThumbsDown size={14} /> Unhelpful ({review.unhelpful_count})
        </Button>
      </div>
    </article>
  );
}

export function ProductReviewsSection({ productId }: { productId: string }) {
  const queryClient = useQueryClient();
  const [sort, setSort] = useState<ReviewSort>('featured_first');
  const [page, setPage] = useState(1);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const token = localStorage.getItem('auth_token');

  const { data: summary, isLoading: summaryLoading, isError: summaryError } = useReviewSummary(productId);
  const { data: reviewsPayload, isLoading: reviewsLoading, isError: reviewsError } = useProductReviews(productId, sort, page, 10);
  const { myReview } = useMyReview(productId);
  const hasExistingReview = Boolean(myReview || summary?.has_reviewed);

  const voteMutation = useMutation({
    mutationFn: ({ reviewId, vote }: { reviewId: string; vote: 'helpful' | 'unhelpful' }) => reviewsService.voteReview(reviewId, vote),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['product-reviews', productId] });
    },
  });

  const ratingBars = useMemo(() => {
    const breakdown = summary?.rating_breakdown || {};
    const total = summary?.total_reviews || 0;
    return [5, 4, 3, 2, 1].map((star) => {
      const count = Number(breakdown[String(star)] || 0);
      const percentage = total > 0 ? (count / total) * 100 : 0;
      return { star, count, percentage };
    });
  }, [summary?.rating_breakdown, summary?.total_reviews]);

  const reviews = reviewsPayload?.data || [];

  return (
    <section className="mt-16 space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="flex items-center gap-2 text-2xl font-bold"><MessageSquare size={22} />Customer Reviews</h3>
          <p className="mt-1 text-sm text-muted-foreground">Real experiences from Aurora Blings customers.</p>
        </div>

        {!token ? (
          <Button asChild variant="outline"><Link to={`/login?next=${encodeURIComponent(`/product/${productId}`)}`}>Login to write a review</Link></Button>
        ) : (
          <Button onClick={() => setIsModalOpen(true)}>{hasExistingReview ? 'Edit Your Review' : 'Write a Review'}</Button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 rounded-2xl border border-border bg-white p-6 shadow-sm lg:grid-cols-3">
        {summaryLoading ? (
          <>
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full lg:col-span-2" />
          </>
        ) : summaryError ? (
          <p className="text-sm text-red-600 lg:col-span-3">Unable to load review summary right now.</p>
        ) : (
          <>
            <div className="space-y-2">
              <p className="text-4xl font-bold text-primary">{(summary?.average_rating || 0).toFixed(1)}</p>
              <StarRow rating={Math.round(summary?.average_rating || 0)} />
              <p className="text-xs uppercase tracking-wide text-muted-foreground">{summary?.total_reviews || 0} total reviews</p>
            </div>

            <div className="space-y-2 lg:col-span-2">
              {ratingBars.map((bar) => (
                <div key={bar.star} className="flex items-center gap-3 text-xs">
                  <span className="w-8 font-semibold">{bar.star}★</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                    <div className="h-full rounded-full bg-amber-500" style={{ width: `${bar.percentage}%` }} />
                  </div>
                  <span className="w-8 text-right text-muted-foreground">{bar.count}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs text-muted-foreground">Showing {reviews.length} review(s)</div>
        <select
          value={sort}
          onChange={(e) => {
            setSort(e.target.value as ReviewSort);
            setPage(1);
          }}
          className="h-10 rounded-xl border border-input bg-white px-3 text-sm"
        >
          {SORT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      </div>

      {reviewsLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-36 w-full" />
          <Skeleton className="h-36 w-full" />
        </div>
      ) : reviewsError ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          We couldn't load reviews right now. Please try again.
        </div>
      ) : reviews.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-muted/20 p-8 text-center text-sm text-muted-foreground">
          No approved reviews yet. Be the first to share your experience.
        </div>
      ) : (
        <div className="space-y-4">
          {reviews.map((review) => (
            <ReviewCard key={review.id} review={review} onVote={(reviewId, vote) => voteMutation.mutate({ reviewId, vote })} />
          ))}
        </div>
      )}

      {reviewsPayload?.meta ? (
        <div className="flex items-center justify-end gap-2">
          <Button variant="outline" size="sm" onClick={() => setPage((prev) => Math.max(1, prev - 1))} disabled={page <= 1}>
            Previous
          </Button>
          <span className="text-xs text-muted-foreground">Page {reviewsPayload.meta.page} of {reviewsPayload.meta.total_pages}</span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((prev) => prev + 1)}
            disabled={page >= reviewsPayload.meta.total_pages}
          >
            Next
          </Button>
        </div>
      ) : null}

      {token ? (
        <ReviewFormModal
          open={isModalOpen}
          onOpenChange={setIsModalOpen}
          productId={productId}
          reviewId={myReview?.id || summary?.my_review_id || undefined}
          defaultRating={myReview?.rating}
          defaultTitle={myReview?.title}
          defaultComment={myReview?.comment}
        />
      ) : null}
    </section>
  );
}
