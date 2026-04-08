import apiClient from './client';

export type ReviewSort = 'newest' | 'highest_rating' | 'lowest_rating' | 'most_helpful' | 'featured_first';
export type ReviewVoteType = 'helpful' | 'unhelpful';

export interface ReviewMedia {
  id: string;
  image: string;
  sort_order: number;
  created_at: string;
}

export interface ProductReview {
  id: string;
  rating: number;
  title: string;
  comment: string;
  is_verified_purchase: boolean;
  is_featured: boolean;
  helpful_count: number;
  unhelpful_count: number;
  created_at: string;
  updated_at: string;
  reviewer_name: string;
  media: ReviewMedia[];
}

export interface ReviewSummary {
  average_rating: number;
  total_reviews: number;
  rating_breakdown: Record<string, number>;
  has_reviewed: boolean;
  my_review_id: string | null;
  can_review: boolean;
  eligibility_reason: string;
}

export interface MyReview {
  id: string;
  product: string;
  product_name: string;
  rating: number;
  title: string;
  comment: string;
  status: string;
  is_verified_purchase: boolean;
  is_featured: boolean;
  is_edited: boolean;
  helpful_count: number;
  unhelpful_count: number;
  created_at: string;
  updated_at: string;
  media: ReviewMedia[];
}

export interface ReviewListPayload {
  data: ProductReview[];
  meta?: {
    total_count: number;
    total_pages: number;
    page: number;
    page_size: number;
    next: string | null;
    previous: string | null;
  };
}

export interface AdminReview {
  id: string;
  product: string;
  product_name: string;
  user: string;
  user_email: string;
  rating: number;
  title: string;
  comment: string;
  status: 'pending' | 'approved' | 'rejected' | 'hidden';
  is_verified_purchase: boolean;
  is_featured: boolean;
  is_edited: boolean;
  is_soft_deleted: boolean;
  helpful_count: number;
  unhelpful_count: number;
  moderated_at: string | null;
  moderated_by: string | null;
  moderated_by_email?: string | null;
  admin_notes: string;
  created_at: string;
  updated_at: string;
  media: ReviewMedia[];
}

const reviewsService = {
  async listProductReviews(productId: string, params?: { sort?: ReviewSort; page?: number; page_size?: number }): Promise<ReviewListPayload> {
    const response = await apiClient.get(`/v1/reviews/products/${productId}/reviews/`, { params });
    return {
      data: response.data?.data || [],
      meta: response.data?.meta,
    };
  },

  async getReviewSummary(productId: string): Promise<ReviewSummary> {
    const response = await apiClient.get(`/v1/reviews/products/${productId}/review-summary/`);
    return response.data?.data;
  },

  async createReview(productId: string, payload: { rating: number; title?: string; comment: string; images?: File[]; turnstile_token?: string }): Promise<MyReview> {
    const form = new FormData();
    form.append('rating', String(payload.rating));
    if (payload.title) form.append('title', payload.title);
    form.append('comment', payload.comment);
    if (payload.turnstile_token) form.append('turnstile_token', payload.turnstile_token);
    (payload.images || []).forEach((image) => form.append('images', image));

    const response = await apiClient.post(`/v1/reviews/products/${productId}/reviews/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data?.data;
  },

  async updateReview(reviewId: string, payload: { rating: number; title?: string; comment: string; images?: File[]; turnstile_token?: string }): Promise<MyReview> {
    const form = new FormData();
    form.append('rating', String(payload.rating));
    if (payload.title) form.append('title', payload.title);
    form.append('comment', payload.comment);
    if (payload.turnstile_token) form.append('turnstile_token', payload.turnstile_token);
    (payload.images || []).forEach((image) => form.append('images', image));

    const response = await apiClient.patch(`/v1/reviews/reviews/${reviewId}/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data?.data;
  },

  async deleteReview(reviewId: string): Promise<void> {
    await apiClient.delete(`/v1/reviews/reviews/${reviewId}/`);
  },

  async voteReview(reviewId: string, voteType: ReviewVoteType): Promise<{ review_id: string; helpful_count: number; unhelpful_count: number }> {
    const response = await apiClient.post(`/v1/reviews/reviews/${reviewId}/vote/`, { vote_type: voteType });
    return response.data?.data;
  },

  async listMyReviews(params?: { page?: number; page_size?: number }): Promise<{ data: MyReview[]; meta?: any }> {
    const response = await apiClient.get('/v1/reviews/me/reviews/', { params });
    return {
      data: response.data?.data || [],
      meta: response.data?.meta,
    };
  },

  async listAdminReviews(params?: {
    page?: number;
    page_size?: number;
    status?: string;
    product?: string;
    rating?: number;
    verified_purchase?: boolean;
    featured?: boolean;
    search?: string;
  }): Promise<{ data: AdminReview[]; meta?: any }> {
    const response = await apiClient.get('/v1/reviews/admin/reviews/', { params });
    return {
      data: response.data?.data || [],
      meta: response.data?.meta,
    };
  },

  async approveReview(reviewId: string, payload?: { admin_notes?: string; is_featured?: boolean }): Promise<AdminReview> {
    const response = await apiClient.post(`/v1/reviews/admin/reviews/${reviewId}/approve/`, payload || {});
    return response.data?.data;
  },

  async rejectReview(reviewId: string, payload?: { admin_notes?: string }): Promise<AdminReview> {
    const response = await apiClient.post(`/v1/reviews/admin/reviews/${reviewId}/reject/`, payload || {});
    return response.data?.data;
  },

  async hideReview(reviewId: string, payload?: { admin_notes?: string }): Promise<AdminReview> {
    const response = await apiClient.post(`/v1/reviews/admin/reviews/${reviewId}/hide/`, payload || {});
    return response.data?.data;
  },

  async featureReview(reviewId: string, payload?: { admin_notes?: string; is_featured?: boolean }): Promise<AdminReview> {
    const response = await apiClient.post(`/v1/reviews/admin/reviews/${reviewId}/feature/`, payload || {});
    return response.data?.data;
  },
};

export default reviewsService;
