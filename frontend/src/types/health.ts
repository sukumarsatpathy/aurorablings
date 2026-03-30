export type HealthStatus = 'healthy' | 'warning' | 'degraded' | 'down';

export interface HealthTrendPoint {
  timestamp: string;
  latency: number;
  failures: number;
}

export interface HealthSummaryMetric {
  status: HealthStatus;
  description: string;
}

export interface HealthSummaryData {
  updatedAt: string;
  overallStatus: HealthStatus;
  overallDescription: string;
  serverHealth: HealthSummaryMetric;
  apiHealth: HealthSummaryMetric;
  paymentHealth: HealthSummaryMetric;
}

export interface HealthDetailCardData {
  id: string;
  name: string;
  status: HealthStatus;
  metricLabel: string;
  metricValue: string;
  message: string;
  statusCode?: string;
  metadata?: Record<string, unknown>;
}

export interface HealthAlert {
  id: string;
  status: Extract<HealthStatus, 'warning' | 'degraded' | 'down'>;
  title: string;
  message: string;
  timestamp: string;
}

export interface DetailedHealthData {
  server: HealthDetailCardData[];
  api: HealthDetailCardData[];
  payment: HealthDetailCardData[];
  trends: HealthTrendPoint[];
}

export interface HealthDashboardData {
  summary: HealthSummaryData;
  detailed: DetailedHealthData;
  alerts: HealthAlert[];
}
