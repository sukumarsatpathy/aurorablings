# Aurora Blings — Settings & Feature System

## Architecture

The system is divided into four main models, all aggressively cached in Redis to ensure zero database overhead on hot-path reads.

| Area | Model | Description |
|---|---|---|
| **Catalogue** | [Feature](file:///f:/Development/Django/aurorablings/backend/apps/features/models.py#81-126) | The immutable dictionary of features ([code](file:///f:/Development/Django/aurorablings/backend/apps/features/admin.py#90-91), [category](file:///f:/Development/Django/aurorablings/backend/apps/surcharge/services.py#87-90), [tier](file:///f:/Development/Django/aurorablings/backend/apps/features/admin.py#48-52), `config_schema`). |
| **Logic Gate** | [FeatureFlag](file:///f:/Development/Django/aurorablings/backend/apps/features/models.py#132-177) | The runtime switch. Tied 1:1 to a feature. Contains [is_enabled](file:///f:/Development/Django/aurorablings/backend/apps/features/serializers.py#24-29) and `rollout_percentage` (0-100). |
| **Integrations** | [ProviderConfig](file:///f:/Development/Django/aurorablings/backend/apps/features/models.py#183-243) | Stores provider credentials for features that require config (e.g. Stripe keys). Active exclusively per-feature. |
| **General Config** | [AppSetting](file:///f:/Development/Django/aurorablings/backend/apps/features/models.py#249-320) | Global key-value store (e.g. `currency = INR`, `max_cart_size = 20`) mapped by category. |

## Code-level Usage

### Checking a Feature (Python)

```python
from apps.features.services import is_feature_enabled, require_feature

# 1. Boolean check (handles caching and gradual rollout % mathematically)
if is_feature_enabled("payment_stripe", user_id=request.user.id):
    pass

# 2. Hard guard (raises FeatureDisabledError)
require_feature("advanced_analytics", user_id=request.user.id)
```

### View Decorator

```python
from apps.features.decorators import feature_required

# Fails with HTTP 503 if feature is disabled or user not in rollout
@feature_required("sms_notifications")
class SMSWebhookView(APIView):
    ...
```

### Retrieving Settings

```python
from apps.features.services import get_setting

# Returns the typed value cleanly (bool, int, list, str)
currency = get_setting("default_currency", default="USD")
```

## Caching Strategy ([apps/features/cache.py](file:///f:/Development/Django/aurorablings/backend/apps/features/cache.py))

Feature checks are extremely read-heavy. To prevent DB thrashing:
- **Feature Flags**: Cached for 5 mins as a `[is_enabled, rollout_pct]` tuple.
- **Provider Configs**: Cached for 10 mins.
- **App Settings**: Cached for 15 mins (individual keys).
- **Public Settings**: Cached as a batch for 30 mins to instantly serve the frontend `/public-settings/` endpoint.

*Cache Invalidation:* [save()](file:///f:/Development/Django/aurorablings/backend/apps/catalog/models.py#149-154) and [delete()](file:///f:/Development/Django/aurorablings/backend/core/models.py#84-88) methods on the respective Django models intercept writes and instantly delete the corresponding Redis key. This means updates made in the Django Admin apply instantly, while reads still cost 0 DB hits.

## Gradual Rollout

Every [FeatureFlag](file:///f:/Development/Django/aurorablings/backend/apps/features/models.py#132-177) has a `rollout_percentage` field:
- **0**: Completely off.
- **100**: Completely on.
- **1–99**: Gradual rollout. Traffic routing uses a deterministic user hash bucket: [(hash(str(user_id)) % 100) < rollout_pct](file:///f:/Development/Django/aurorablings/backend/core/viewsets.py#50-52).
  - *Note:* Unauthenticated users (no `user_id`) receive `False` during partial rollouts to ensure consistent UX per session.

## Provider Configuration (Marketplace)

[ProviderConfig](file:///f:/Development/Django/aurorablings/backend/apps/features/models.py#183-243) allows multiple backends targeting the same feature (e.g., Stripe vs. Cashfree). 

The `Feature.config_schema` enforces what is needed. The `services.set_provider_config(activate=True)` will ensure that only *one* config per feature is active at any time. The admin interface automatically hides fields marked as `"secret": true` in the JSON schema.

## Migration Command
```bash
python manage.py makemigrations features
python manage.py migrate
```
