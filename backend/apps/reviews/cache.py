PUBLIC_REVIEW_SUMMARY_TTL = 60 * 10
PUBLIC_REVIEW_LIST_TTL = 60 * 5


SORT_OPTIONS = (
    "newest",
    "highest_rating",
    "lowest_rating",
    "most_helpful",
    "featured_first",
)


def public_review_summary_key(product_id: str) -> str:
    return f"reviews:summary:{product_id}"


def public_review_list_key(*, product_id: str, sort_by: str, page: int, page_size: int) -> str:
    return f"reviews:list:{product_id}:{sort_by}:p{page}:s{page_size}"
