import React, { useEffect, useMemo, useState } from 'react';
import { Eye, Filter, MoreHorizontal, RefreshCw, Search, Star, ThumbsDown, ThumbsUp } from 'lucide-react';

import { DataTable, StatusBadge } from '@/components/admin/AdminTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/DropdownMenu';
import {
  Modal,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalTitle,
} from '@/components/ui/Modal';
import reviewsService, { type AdminReview } from '@/services/api/reviews';

const REVIEW_STATUSES = ['pending', 'approved', 'rejected', 'hidden'] as const;

export const Reviews: React.FC = () => {
  const [reviews, setReviews] = useState<AdminReview[]>([]);
  const [loading, setLoading] = useState(true);

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [ratingFilter, setRatingFilter] = useState<string>('');
  const [verifiedFilter, setVerifiedFilter] = useState<string>('');
  const [featuredFilter, setFeaturedFilter] = useState<string>('');

  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [selectedReview, setSelectedReview] = useState<AdminReview | null>(null);
  const [noteText, setNoteText] = useState('');
  const [moderating, setModerating] = useState(false);

  const loadReviews = async () => {
    try {
      setLoading(true);
      const response = await reviewsService.listAdminReviews({
        page,
        page_size: 20,
        status: statusFilter || undefined,
        rating: ratingFilter ? Number(ratingFilter) : undefined,
        verified_purchase: verifiedFilter ? verifiedFilter === 'true' : undefined,
        featured: featuredFilter ? featuredFilter === 'true' : undefined,
        search: search.trim() || undefined,
      });

      setReviews(Array.isArray(response.data) ? response.data : []);
      const pages = Number(response.meta?.total_pages || 1);
      setTotalPages(pages > 0 ? pages : 1);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReviews();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  const applyFilters = () => {
    setPage(1);
    setTimeout(() => {
      loadReviews();
    }, 0);
  };

  const clearFilters = () => {
    setSearch('');
    setStatusFilter('');
    setRatingFilter('');
    setVerifiedFilter('');
    setFeaturedFilter('');
    setPage(1);
    setTimeout(() => {
      loadReviews();
    }, 0);
  };

  const openReview = (review: AdminReview) => {
    setSelectedReview(review);
    setNoteText(review.admin_notes || '');
  };

  const refreshSelectedReviewInList = (updated: AdminReview) => {
    setReviews((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    setSelectedReview(updated);
  };

  const runModeration = async (action: 'approve' | 'reject' | 'hide' | 'feature') => {
    if (!selectedReview) return;

    try {
      setModerating(true);
      let updated: AdminReview;

      if (action === 'approve') {
        updated = await reviewsService.approveReview(selectedReview.id, {
          admin_notes: noteText,
          is_featured: selectedReview.is_featured,
        });
      } else if (action === 'reject') {
        updated = await reviewsService.rejectReview(selectedReview.id, {
          admin_notes: noteText,
        });
      } else if (action === 'hide') {
        updated = await reviewsService.hideReview(selectedReview.id, {
          admin_notes: noteText,
        });
      } else {
        updated = await reviewsService.featureReview(selectedReview.id, {
          admin_notes: noteText,
          is_featured: !selectedReview.is_featured,
        });
      }

      refreshSelectedReviewInList(updated);
    } catch (error) {
      console.error('Moderation failed', error);
      alert('Moderation request failed. Please try again.');
    } finally {
      setModerating(false);
    }
  };

  const columns = useMemo(
    () => [
      {
        header: 'Product',
        accessorKey: 'product_name',
        cell: (item: AdminReview) => (
          <div className="flex flex-col">
            <span className="font-semibold">{item.product_name}</span>
            <span className="text-xs text-muted-foreground">{item.user_email}</span>
          </div>
        ),
      },
      {
        header: 'Rating',
        accessorKey: 'rating',
        cell: (item: AdminReview) => (
          <div className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-700">
            <Star size={12} className="fill-current" />
            {item.rating}
          </div>
        ),
        align: 'center' as const,
      },
      {
        header: 'Status',
        accessorKey: 'status',
        cell: (item: AdminReview) => <StatusBadge status={item.status} type="generic" />,
      },
      {
        header: 'Flags',
        accessorKey: 'is_verified_purchase',
        cell: (item: AdminReview) => (
          <div className="flex items-center gap-2">
            {item.is_verified_purchase ? <Badge variant="surface" className="text-[10px]">Verified</Badge> : null}
            {item.is_featured ? <Badge className="text-[10px]">Featured</Badge> : null}
            {item.is_edited ? <Badge variant="outline" className="text-[10px]">Edited</Badge> : null}
          </div>
        ),
      },
      {
        header: 'Votes',
        accessorKey: 'helpful_count',
        cell: (item: AdminReview) => (
          <div className="text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1"><ThumbsUp size={12} />{item.helpful_count}</span>
            <span className="mx-2">|</span>
            <span className="inline-flex items-center gap-1"><ThumbsDown size={12} />{item.unhelpful_count}</span>
          </div>
        ),
      },
      {
        header: 'Posted',
        accessorKey: 'created_at',
        className: 'text-xs text-muted-foreground',
        cell: (item: AdminReview) => new Date(item.created_at).toLocaleDateString(),
      },
    ],
    []
  );

  const actions = (item: AdminReview) => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[170px]">
        <DropdownMenuItem onClick={() => openReview(item)} className="cursor-pointer text-xs">
          <Eye size={14} className="mr-2" /> View & Moderate
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Reviews</h1>
          <p className="mt-1 text-xs text-muted-foreground">Moderate buyer reviews, manage visibility, and feature top feedback.</p>
        </div>
        <Button variant="outline" onClick={loadReviews} className="h-10 gap-2 rounded-xl border-border/60 bg-white">
          <RefreshCw size={16} /> Refresh
        </Button>
      </div>

      <div className="rounded-[14px] border border-border bg-white p-4 shadow-sm">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-6">
          <div className="relative md:col-span-2">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
            <Input
              className="h-10 border-border/60 bg-muted/20 pl-9"
              placeholder="Search by product, user, title, comment"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <select className="h-10 rounded-md border border-border/60 bg-white px-3 text-sm" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All Status</option>
            {REVIEW_STATUSES.map((status) => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>

          <select className="h-10 rounded-md border border-border/60 bg-white px-3 text-sm" value={ratingFilter} onChange={(e) => setRatingFilter(e.target.value)}>
            <option value="">All Ratings</option>
            {[5, 4, 3, 2, 1].map((rating) => (
              <option key={rating} value={String(rating)}>{rating} stars</option>
            ))}
          </select>

          <select className="h-10 rounded-md border border-border/60 bg-white px-3 text-sm" value={verifiedFilter} onChange={(e) => setVerifiedFilter(e.target.value)}>
            <option value="">All Verification</option>
            <option value="true">Verified only</option>
            <option value="false">Not verified</option>
          </select>

          <select className="h-10 rounded-md border border-border/60 bg-white px-3 text-sm" value={featuredFilter} onChange={(e) => setFeaturedFilter(e.target.value)}>
            <option value="">All Featured States</option>
            <option value="true">Featured only</option>
            <option value="false">Not featured</option>
          </select>
        </div>

        <div className="mt-3 flex items-center gap-2">
          <Button onClick={applyFilters} className="h-9 gap-2">
            <Filter size={14} /> Apply
          </Button>
          <Button variant="outline" onClick={clearFilters} className="h-9 border-border/60">Clear</Button>
        </div>
      </div>

      {loading ? (
        <div className="rounded-[14px] border border-border bg-white p-8 text-center text-sm text-muted-foreground">Loading reviews...</div>
      ) : (
        <DataTable data={reviews} columns={columns} actions={actions} onRowClick={(item) => openReview(item as AdminReview)} />
      )}

      <div className="flex items-center justify-end gap-2">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>Previous</Button>
        <span className="text-xs text-muted-foreground">Page {page} of {totalPages}</span>
        <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((prev) => prev + 1)}>Next</Button>
      </div>

      <Modal open={Boolean(selectedReview)} onOpenChange={(open) => { if (!open) setSelectedReview(null); }}>
        <ModalContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
          <ModalHeader>
            <ModalTitle>Review Moderation</ModalTitle>
          </ModalHeader>

          {selectedReview ? (
            <div className="space-y-4 py-2 text-sm">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div><span className="font-semibold">Product:</span> {selectedReview.product_name}</div>
                <div><span className="font-semibold">User:</span> {selectedReview.user_email}</div>
                <div><span className="font-semibold">Rating:</span> {selectedReview.rating}/5</div>
                <div><span className="font-semibold">Status:</span> {selectedReview.status}</div>
                <div><span className="font-semibold">Verified Purchase:</span> {selectedReview.is_verified_purchase ? 'Yes' : 'No'}</div>
                <div><span className="font-semibold">Featured:</span> {selectedReview.is_featured ? 'Yes' : 'No'}</div>
              </div>

              {selectedReview.title ? (
                <div className="rounded-xl border border-border/70 bg-muted/20 p-3">
                  <p className="text-xs font-bold uppercase text-muted-foreground">Title</p>
                  <p className="mt-1">{selectedReview.title}</p>
                </div>
              ) : null}

              <div className="rounded-xl border border-border/70 bg-muted/20 p-3">
                <p className="text-xs font-bold uppercase text-muted-foreground">Comment</p>
                <p className="mt-1 whitespace-pre-wrap">{selectedReview.comment}</p>
              </div>

              {selectedReview.media?.length ? (
                <div>
                  <p className="mb-2 text-xs font-bold uppercase text-muted-foreground">Images</p>
                  <div className="grid grid-cols-3 gap-2 md:grid-cols-5">
                    {selectedReview.media.map((media) => (
                      <img key={media.id} src={media.image} alt="Review" className="h-20 w-full rounded-lg object-cover" />
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="grid gap-2">
                <label className="text-xs font-bold uppercase text-muted-foreground">Admin Notes</label>
                <textarea
                  rows={3}
                  className="w-full rounded-xl border border-border/60 bg-background px-4 py-2 text-sm"
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                />
              </div>
            </div>
          ) : null}

          <ModalFooter className="flex-wrap gap-2 sm:justify-between sm:space-x-0">
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => runModeration('approve')} disabled={moderating}>Approve</Button>
              <Button variant="outline" onClick={() => runModeration('reject')} disabled={moderating}>Reject</Button>
              <Button variant="outline" onClick={() => runModeration('hide')} disabled={moderating}>Hide</Button>
              <Button variant="outline" onClick={() => runModeration('feature')} disabled={moderating}>
                {selectedReview?.is_featured ? 'Unfeature' : 'Feature'}
              </Button>
            </div>
            <Button variant="outline" onClick={() => setSelectedReview(null)} disabled={moderating}>Close</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </div>
  );
};
