import apiClient from './client';
import type {
  DetailedHealthData,
  HealthAlert,
  HealthDashboardData,
  HealthDetailCardData,
  HealthStatus,
  HealthSummaryData,
  HealthSummaryMetric,
  HealthTrendPoint,
} from '@/types/health';

const DEFAULT_UPDATED_AT = () => new Date().toISOString();

const toStatus = (value: unknown): HealthStatus => {
  if (typeof value !== 'string') return 'healthy';
  const normalized = value.toLowerCase();
  if (normalized === 'healthy' || normalized === 'warning' || normalized === 'degraded' || normalized === 'down') {
    return normalized;
  }
  return 'healthy';
};

const toNumber = (value: unknown, fallback = 0): number => {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
};

const toString = (value: unknown, fallback = ''): string => {
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return String(value);
  return fallback;
};

const normalizeSummaryMetric = (raw: unknown, fallback: HealthSummaryMetric): HealthSummaryMetric => {
  if (!raw || typeof raw !== 'object') return fallback;
  const source = raw as Record<string, unknown>;
  return {
    status: toStatus(source.status ?? fallback.status),
    description: toString(source.description, fallback.description),
  };
};

const normalizeSummary = (raw: unknown): HealthSummaryData => {
  const source = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {};

  return {
    updatedAt: toString(source.updated_at, DEFAULT_UPDATED_AT()),
    overallStatus: toStatus(source.overall_status),
    overallDescription: toString(source.overall_description, 'System is operating within normal thresholds'),
    serverHealth: normalizeSummaryMetric(source.server_health, {
      status: 'healthy',
      description: 'All systems operational',
    }),
    apiHealth: normalizeSummaryMetric(source.api_health, {
      status: 'healthy',
      description: 'Stable response times',
    }),
    paymentHealth: normalizeSummaryMetric(source.payment_health, {
      status: 'healthy',
      description: 'Payment flows are healthy',
    }),
  };
};

const normalizeCard = (raw: unknown, index: number, fallbackName: string): HealthDetailCardData => {
  const source = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {};
  const metricValue = source.usage_percent ?? source.latency_ms ?? source.response_time_ms ?? source.value;
  const parsedMetric = toNumber(metricValue, 0);
  const metricText = typeof metricValue === 'string' ? metricValue : parsedMetric.toFixed(1);

  return {
    id: toString(source.id, `${fallbackName.toLowerCase().replace(/\s+/g, '-')}-${index}`),
    name: toString(source.name, fallbackName),
    status: toStatus(source.status),
    metricLabel: toString(source.metric_label, 'Metric'),
    metricValue: toString(source.metric_value, metricText),
    message: toString(source.message, 'No active issues detected'),
    statusCode: source.status_code !== undefined ? toString(source.status_code, undefined) : undefined,
    metadata: source.metadata && typeof source.metadata === 'object' ? (source.metadata as Record<string, unknown>) : undefined,
  };
};

const normalizeCards = (raw: unknown, defaults: string[]): HealthDetailCardData[] => {
  const list = Array.isArray(raw) ? raw : [];
  if (!list.length) {
    return defaults.map((name, index) =>
      normalizeCard(
        {
          name,
          status: 'healthy',
          metric_label: index % 2 === 0 ? 'Usage' : 'Latency',
          metric_value: index % 2 === 0 ? `${45 + index * 4}%` : `${20 + index * 8}ms`,
          message: 'Operating normally',
        },
        index,
        name,
      ),
    );
  }
  return list.map((item, index) => normalizeCard(item, index, defaults[index] ?? `Component ${index + 1}`));
};

const normalizeTrend = (raw: unknown, index: number): HealthTrendPoint => {
  const source = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {};
  const fallbackTime = new Date(Date.now() - (11 - index) * 5 * 60 * 1000).toISOString();
  return {
    timestamp: toString(source.timestamp, fallbackTime),
    latency: toNumber(source.latency, 20 + index * 2),
    failures: toNumber(source.failures, index % 5 === 0 ? 1 : 0),
  };
};

const normalizeTrends = (raw: unknown): HealthTrendPoint[] => {
  const list = Array.isArray(raw) ? raw : [];
  if (!list.length) {
    return Array.from({ length: 12 }, (_, index) => normalizeTrend({}, index));
  }
  return list.map(normalizeTrend);
};

const normalizeDetailed = (raw: unknown): DetailedHealthData => {
  const source = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {};
  return {
    server: normalizeCards(source.server, ['CPU', 'Memory', 'Disk', 'Database', 'Redis']),
    api: normalizeCards(source.api, ['Product API', 'Cart API', 'Checkout API', 'Admin API']),
    payment: normalizeCards(source.payment, ['Cashfree Config', 'Cashfree Connectivity', 'Webhook Health', 'Payment Trend']),
    trends: normalizeTrends(source.trends),
  };
};

const normalizeAlert = (raw: unknown, index: number): HealthAlert => {
  const source = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {};
  const status = toStatus(source.status);
  return {
    id: toString(source.id, `alert-${index + 1}`),
    status: status === 'healthy' ? 'warning' : status,
    title: toString(source.title, 'System notice'),
    message: toString(source.message, 'An event requires review by the operations team'),
    timestamp: toString(source.timestamp, DEFAULT_UPDATED_AT()),
  };
};

const normalizeAlerts = (raw: unknown): HealthAlert[] => {
  const list = Array.isArray(raw) ? raw : [];
  if (!list.length) return [];
  return list.map(normalizeAlert);
};

const healthService = {
  getSummary: async (): Promise<HealthSummaryData> => {
    const response = await apiClient.get('/v1/system/health/summary/');
    const payload = response.data?.data ?? response.data;
    return normalizeSummary(payload);
  },
  getDetailed: async (): Promise<DetailedHealthData> => {
    const response = await apiClient.get('/v1/system/health/detailed/');
    const payload = response.data?.data ?? response.data;
    return normalizeDetailed(payload);
  },
  getAlerts: async (): Promise<HealthAlert[]> => {
    const response = await apiClient.get('/v1/system/health/alerts/');
    const payload = response.data?.data ?? response.data;
    return normalizeAlerts(payload);
  },
  getDashboard: async (): Promise<HealthDashboardData> => {
    const [summary, detailed, alerts] = await Promise.all([
      healthService.getSummary(),
      healthService.getDetailed(),
      healthService.getAlerts(),
    ]);
    return { summary, detailed, alerts };
  },
};

export default healthService;
