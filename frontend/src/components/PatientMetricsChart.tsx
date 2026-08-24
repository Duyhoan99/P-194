'use client';

import React, { useCallback, useState, useEffect, useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from 'recharts';
import {
  Activity,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  AlertTriangle,
  ShieldCheck,
} from 'lucide-react';
import { patients } from '@/lib/api';

export interface MetricOption {
  code: string;
  label: string;
  fullName: string;
  unit: string;
  threshold: number;
  goodDirection: 'above' | 'below'; // 'above': >= threshold is GOOD (e.g. eGFR), 'below': <= threshold is GOOD (e.g. HbA1c, Glucose)
  thresholdLabel: string;
  goodText: string;
  warningText: string;
  description: string;
  altUnits?: {
    [unit: string]: { threshold: number; thresholdLabel: string };
  };
}

// LOINC configurations for clinical metrics with evidence-based thresholds
export const METRIC_OPTIONS: MetricOption[] = [
  {
    code: '4548-4',
    label: 'HbA1c',
    fullName: 'Hemoglobin A1c (Kiểm soát đường huyết 3 tháng)',
    unit: '%',
    threshold: 7.0,
    goodDirection: 'below',
    thresholdLabel: 'Ngưỡng mục tiêu: 7.0%',
    goodText: 'Kiểm soát tốt (≤ 7.0%)',
    warningText: 'Cảnh báo vượt ngưỡng (> 7.0%)',
    description: 'Khuyến cáo ADA & Bộ Y tế: Duy trì HbA1c ≤ 7.0% giúp giảm biến chứng mạch máu lớn và vi mạch.',
  },
  {
    code: '2339-0',
    label: 'Glucose',
    fullName: 'Đường huyết lúc đói (Fasting Glucose)',
    unit: 'mmol/L',
    threshold: 7.0,
    goodDirection: 'below',
    thresholdLabel: 'Ngưỡng đường huyết đói: 7.0 mmol/L',
    goodText: 'Bình thường / Ổn định (≤ 7.0 mmol/L)',
    warningText: 'Cảnh báo tăng đường huyết (> 7.0 mmol/L)',
    description: 'Chỉ số đường huyết tĩnh mạch lúc đói mục tiêu: ≤ 7.0 mmol/L (tương đương 126 mg/dL).',
    altUnits: {
      'mg/dL': { threshold: 126, thresholdLabel: 'Ngưỡng đường huyết: 126 mg/dL' },
      'mg/dl': { threshold: 126, thresholdLabel: 'Ngưỡng đường huyết: 126 mg/dL' },
    },
  },
  {
    code: '33914-3',
    label: 'eGFR',
    fullName: 'Độ lọc cầu thận ước tính (eGFR)',
    unit: 'mL/min/1.73m2',
    threshold: 60.0,
    goodDirection: 'above',
    thresholdLabel: 'Ngưỡng an toàn thận: ≥ 60 mL/min',
    goodText: 'Chức năng thận tốt (≥ 60 mL/min)',
    warningText: 'Cảnh báo suy giảm chức năng thận (< 60 mL/min)',
    description: 'eGFR ≥ 60 mL/min/1.73m2 là chức năng thận an toàn; dưới 60 cảnh báo bệnh thận mạn (CKD G3-G5).',
  },
  {
    code: '2160-0',
    label: 'Creatinine',
    fullName: 'Creatinine huyết thanh',
    unit: 'µmol/L',
    threshold: 106.0,
    goodDirection: 'below',
    thresholdLabel: 'Ngưỡng an toàn: 106 µmol/L',
    goodText: 'Lọc thận bình thường (≤ 106 µmol/L)',
    warningText: 'Cảnh báo tăng Creatinine (> 106 µmol/L)',
    description: 'Nồng độ Creatinine tăng cao cảnh báo khả năng thanh thải lọc cầu thận của bệnh nhân bị suy giảm.',
    altUnits: {
      'mg/dL': { threshold: 1.2, thresholdLabel: 'Ngưỡng an toàn: 1.2 mg/dL' },
      'mg/dl': { threshold: 1.2, thresholdLabel: 'Ngưỡng an toàn: 1.2 mg/dL' },
    },
  },
  {
    code: '8480-6',
    label: 'BP Systolic',
    fullName: 'Huyết áp tâm thu (Systolic Blood Pressure)',
    unit: 'mmHg',
    threshold: 130.0,
    goodDirection: 'below',
    thresholdLabel: 'Ngưỡng huyết áp mục tiêu: 130 mmHg',
    goodText: 'Huyết áp tối ưu (≤ 130 mmHg)',
    warningText: 'Cảnh báo tăng huyết áp (> 130 mmHg)',
    description: 'Mục tiêu huyết áp tâm thu khuyến cáo cho bệnh nhân ĐTĐ/tim mạch: duy trì ≤ 130 mmHg.',
  },
];

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('vi-VN', { month: 'short', year: '2-digit' });
  } catch {
    return dateStr;
  }
}

interface MetricPoint {
  date: string;
  value: number;
  raw: string;
  isGood: boolean;
  isWarning: boolean;
  delta: number;
}

export default function PatientMetricsChart({ patientId }: { patientId: string }) {
  const [selectedMetric, setSelectedMetric] = useState<MetricOption>(METRIC_OPTIONS[0]);
  const [data, setData] = useState<MetricPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [trendInfo, setTrendInfo] = useState<{ display: string; unit: string } | null>(null);

  // Active unit and active threshold (adapts if backend returns alternate unit)
  const activeUnit = trendInfo?.unit || selectedMetric.unit;
  const activeThreshold = useMemo(() => {
    if (selectedMetric.altUnits && trendInfo?.unit && selectedMetric.altUnits[trendInfo.unit]) {
      return selectedMetric.altUnits[trendInfo.unit].threshold;
    }
    return selectedMetric.threshold;
  }, [selectedMetric, trendInfo]);

  const loadMetric = useCallback((metric: MetricOption) => {
    setLoading(true);
    setError('');
    patients.getTrends(patientId, metric.code)
      .then((res) => {
        const returnedUnit = res.unit || metric.unit;
        let threshold = metric.threshold;
        if (metric.altUnits && metric.altUnits[returnedUnit]) {
          threshold = metric.altUnits[returnedUnit].threshold;
        }

        const points: MetricPoint[] = (res.points || []).map((p: any) => {
          const val = Number(p.value);
          const isGood = metric.goodDirection === 'above' ? val >= threshold : val <= threshold;
          const isWarning = !isGood;
          return {
            date: formatDate(p.observed_at),
            value: val,
            raw: p.observed_at,
            isGood,
            isWarning,
            delta: Number((val - threshold).toFixed(2)),
          };
        });

        setData(points);
        setTrendInfo({
          display: res.display || metric.label,
          unit: returnedUnit,
        });
      })
      .catch((err: any) => {
        setError(err.detail || 'Không thể tải dữ liệu chỉ số');
        setData([]);
      })
      .finally(() => setLoading(false));
  }, [patientId]);

  useEffect(() => {
    loadMetric(selectedMetric);
  }, [selectedMetric, loadMetric]);

  const handleMetricChange = (metric: MetricOption) => {
    setSelectedMetric(metric);
  };

  // Calculate trend direction
  const trendDirection = data.length >= 2
    ? data[data.length - 1].value > data[data.length - 2].value ? 'up' : 'down'
    : null;

  const latestPoint = data.length > 0 ? data[data.length - 1] : null;
  // Compute dynamic Y-axis domain symmetric around activeThreshold so the threshold line is vertically centered ("cắt đều trên và dưới")
  const yDomain = useMemo<[number, number]>(() => {
    if (data.length === 0) {
      const span = Math.max(activeThreshold * 0.25, 2);
      const lower = Math.max(0, Math.round((activeThreshold - span) * 10) / 10);
      const upper = Math.round((activeThreshold + span) * 10) / 10;
      return [lower, upper];
    }
    const values = data.map((d) => d.value);
    const maxDiff = Math.max(...values.map((v) => Math.abs(v - activeThreshold)));
    // Provide ample breathing space so points are nicely distributed
    const baseSpan = Math.max(maxDiff, activeThreshold * 0.15, 0.8);
    const halfSpan = baseSpan * 1.35;

    let lower = Math.round((activeThreshold - halfSpan) * 10) / 10;
    let upper = Math.round((activeThreshold + halfSpan) * 10) / 10;

    if (lower < 0) {
      lower = 0;
      upper = Math.round(activeThreshold * 2 * 10) / 10;
    }

    return [lower, upper];
  }, [data, activeThreshold]);

  // 1. Calculate exact Stroke gradient (for the line curve itself)
  const strokeGradStops = useMemo(() => {
    if (data.length === 0) {
      return { isSolidGreen: false, isSolidRed: false, offsetPct: '50%' };
    }
    const values = data.map((d) => d.value);
    const dataMin = Math.min(...values);
    const dataMax = Math.max(...values);
    const isAboveGood = selectedMetric.goodDirection === 'above';

    if (isAboveGood) {
      if (dataMin >= activeThreshold) {
        return { isSolidGreen: true, isSolidRed: false, offsetPct: '100%' };
      }
      if (dataMax < activeThreshold) {
        return { isSolidGreen: false, isSolidRed: true, offsetPct: '0%' };
      }
    } else {
      if (dataMax <= activeThreshold) {
        return { isSolidGreen: true, isSolidRed: false, offsetPct: '100%' };
      }
      if (dataMin > activeThreshold) {
        return { isSolidGreen: false, isSolidRed: true, offsetPct: '0%' };
      }
    }

    const strokeRange = dataMax - dataMin;
    const frac = strokeRange > 0 ? (dataMax - activeThreshold) / strokeRange : 0.5;
    const clamped = Math.max(0, Math.min(1, frac));
    return {
      isSolidGreen: false,
      isSolidRed: false,
      offsetPct: `${(clamped * 100).toFixed(2)}%`,
    };
  }, [data, activeThreshold, selectedMetric]);

  // 2. Calculate exact Area fill gradient (from dataMax down to domainMin)
  const areaGradStops = useMemo(() => {
    if (data.length === 0) {
      return { isSolidGreen: false, isSolidRed: false, offsetPct: '50%' };
    }
    const values = data.map((d) => d.value);
    const dataMax = Math.max(...values, activeThreshold);
    const [domainMin] = yDomain;
    const totalRange = dataMax - domainMin;
    const isAboveGood = selectedMetric.goodDirection === 'above';

    if (isAboveGood) {
      if (dataMax <= activeThreshold) {
        return { isSolidGreen: false, isSolidRed: true, offsetPct: '0%' };
      }
      if (Math.min(...values) >= activeThreshold) {
        return { isSolidGreen: true, isSolidRed: false, offsetPct: '100%' };
      }
    } else {
      if (dataMax <= activeThreshold) {
        return { isSolidGreen: true, isSolidRed: false, offsetPct: '100%' };
      }
      if (Math.min(...values) > activeThreshold) {
        return { isSolidGreen: false, isSolidRed: true, offsetPct: '0%' };
      }
    }

    const frac = totalRange > 0 ? (dataMax - activeThreshold) / totalRange : 0.5;
    const clamped = Math.max(0, Math.min(1, frac));
    return {
      isSolidGreen: false,
      isSolidRed: false,
      offsetPct: `${(clamped * 100).toFixed(2)}%`,
    };
  }, [data, activeThreshold, yDomain, selectedMetric]);

  // 5 evenly spaced ticks centered around activeThreshold
  const yTicks = useMemo(() => {
    const [lower, upper] = yDomain;
    const half = upper - activeThreshold;
    const step = half / 2;
    const t1 = Math.round(lower * 10) / 10;
    const t2 = Math.round((activeThreshold - step) * 10) / 10;
    const t3 = activeThreshold;
    const t4 = Math.round((activeThreshold + step) * 10) / 10;
    const t5 = Math.round(upper * 10) / 10;
    return [t1, t2, t3, t4, t5];
  }, [yDomain, activeThreshold]);

  return (
    <div className="clinical-card p-6 mb-6 relative overflow-hidden">
      {/* Ambient background glow */}
      <div className="absolute top-0 right-1/4 w-96 h-32 bg-cyan-500/5 blur-3xl pointer-events-none -z-10" />
      <div className="absolute bottom-0 left-1/4 w-96 h-32 bg-rose-500/5 blur-3xl pointer-events-none -z-10" />

      {/* Top Header */}
      <div className="flex flex-col 2xl:flex-row 2xl:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-500/10 flex items-center justify-center border border-cyan-500/20 shadow-[0_0_15px_rgba(34,211,238,0.2)] shrink-0">
            <Activity className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 font-extrabold">Diễn tiến Chỉ số &amp; Ngưỡng Lâm sàng</h3>
              {latestPoint ? (
                <span className={`text-[11px] px-2.5 py-0.5 rounded-full font-bold font-mono border ${
                  latestPoint.isGood
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-300 dark:border-emerald-800'
                    : 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/50 dark:text-rose-300 dark:border-rose-800'
                }`}>
                  {selectedMetric.label}: {latestPoint.value} {activeUnit}
                </span>
              ) : (
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-white/5 font-mono">
                  {selectedMetric.label}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-300 font-semibold mt-0.5">{selectedMetric.fullName}</p>
          </div>
        </div>

        {/* Right side controls: Metric pills & Latest Status */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Metric Selector Pills */}
          <div className="flex flex-wrap gap-1 clinical-subcard p-1 rounded-xl">
            {METRIC_OPTIONS.map((m) => {
              const isSelected = selectedMetric.code === m.code;
              return (
                <button
                  key={m.code}
                  onClick={() => handleMetricChange(m)}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-teal-600 text-white font-bold shadow-sm'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 font-medium'
                  }`}
                >
                  {m.label}
                </button>
              );
            })}
          </div>

          {/* Latest Measured Value Status Badge */}
          {latestPoint && (
            <div
              className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border font-semibold text-xs shadow-sm shrink-0 ${
                latestPoint.isGood
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.15)]'
                  : 'bg-rose-500/10 border-rose-500/30 text-rose-300 shadow-[0_0_12px_rgba(244,63,94,0.15)]'
              }`}
            >
              {latestPoint.isGood ? (
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              )}
              <div className="flex items-center gap-1.5 whitespace-nowrap">
                <span className="text-slate-300 font-normal">Gần nhất:</span>
                <span className="font-bold font-mono text-sm text-slate-100">
                  {latestPoint.value} {activeUnit}
                </span>
                {trendDirection === 'up' && <TrendingUp className="w-3.5 h-3.5 text-slate-300 ml-0.5" />}
                {trendDirection === 'down' && <TrendingDown className="w-3.5 h-3.5 text-slate-300 ml-0.5" />}
              </div>
              <span className="text-[10px] px-1.5 py-0.5 rounded-md font-bold uppercase tracking-wider bg-black/30">
                {latestPoint.isGood ? 'Tốt' : 'Cảnh báo'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Chart Canvas Area */}
      {loading ? (
        <div className="h-[290px] flex items-center justify-center text-slate-400">
          <RefreshCw className="w-5 h-5 animate-spin mr-2 text-cyan-400" />
          <span className="text-sm font-medium">Đang tải biểu đồ chỉ số...</span>
        </div>
      ) : error ? (
        <div className="h-[290px] flex flex-col items-center justify-center text-slate-400">
          <Activity className="w-8 h-8 text-slate-600 mb-2" />
          <span className="text-sm">{error}</span>
          <button
            onClick={() => loadMetric(selectedMetric)}
            className="mt-2 text-xs font-semibold text-cyan-400 hover:text-cyan-300 underline cursor-pointer"
          >
            Thử lại
          </button>
        </div>
      ) : data.length === 0 ? (
        <div className="h-[290px] flex flex-col items-center justify-center text-slate-400">
          <Activity className="w-8 h-8 text-slate-600 mb-2" />
          <span className="text-sm">Không có dữ liệu {selectedMetric.label} cho bệnh nhân này.</span>
        </div>
      ) : (
        <div className="h-[290px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 18, right: 24, left: -2, bottom: 5 }}>
              <defs>
                {/* 2-Color Split Stroke Gradient */}
                <linearGradient id="curveStrokeGrad" x1="0" y1="0" x2="0" y2="1">
                  {strokeGradStops.isSolidGreen ? (
                    <>
                      <stop offset="0%" stopColor="#10b981" />
                      <stop offset="100%" stopColor="#10b981" />
                    </>
                  ) : strokeGradStops.isSolidRed ? (
                    <>
                      <stop offset="0%" stopColor="#ef4444" />
                      <stop offset="100%" stopColor="#ef4444" />
                    </>
                  ) : selectedMetric.goodDirection === 'below' ? (
                    <>
                      <stop offset="0%" stopColor="#ef4444" />
                      <stop offset={strokeGradStops.offsetPct} stopColor="#ef4444" />
                      <stop offset={strokeGradStops.offsetPct} stopColor="#10b981" />
                      <stop offset="100%" stopColor="#10b981" />
                    </>
                  ) : (
                    <>
                      <stop offset="0%" stopColor="#10b981" />
                      <stop offset={strokeGradStops.offsetPct} stopColor="#10b981" />
                      <stop offset={strokeGradStops.offsetPct} stopColor="#ef4444" />
                      <stop offset="100%" stopColor="#ef4444" />
                    </>
                  )}
                </linearGradient>

                {/* 2-Color Split Area Fill Gradient */}
                <linearGradient id="areaSplitGrad" x1="0" y1="0" x2="0" y2="1">
                  {selectedMetric.goodDirection === 'below' ? (
                    areaGradStops.isSolidGreen ? (
                      <>
                        <stop offset="0%" stopColor="#10b981" stopOpacity={0.25} />
                        <stop offset="100%" stopColor="#10b981" stopOpacity={0.02} />
                      </>
                    ) : areaGradStops.isSolidRed ? (
                      <>
                        <stop offset="0%" stopColor="#ef4444" stopOpacity={0.25} />
                        <stop offset="100%" stopColor="#ef4444" stopOpacity={0.02} />
                      </>
                    ) : (
                      <>
                        <stop offset="0%" stopColor="#ef4444" stopOpacity={0.35} />
                        <stop offset={areaGradStops.offsetPct} stopColor="#ef4444" stopOpacity={0.12} />
                        <stop offset={areaGradStops.offsetPct} stopColor="#10b981" stopOpacity={0.12} />
                        <stop offset="100%" stopColor="#10b981" stopOpacity={0.02} />
                      </>
                    )
                  ) : (
                    areaGradStops.isSolidRed ? (
                      <>
                        <stop offset="0%" stopColor="#ef4444" stopOpacity={0.25} />
                        <stop offset="100%" stopColor="#ef4444" stopOpacity={0.02} />
                      </>
                    ) : (
                      <>
                        <stop offset="0%" stopColor="#10b981" stopOpacity={0.35} />
                        <stop offset={areaGradStops.offsetPct} stopColor="#10b981" stopOpacity={0.12} />
                        <stop offset={areaGradStops.offsetPct} stopColor="#ef4444" stopOpacity={0.12} />
                        <stop offset="100%" stopColor="#ef4444" stopOpacity={0.02} />
                      </>
                    )
                  )}
                </linearGradient>
              </defs>

              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-card)" vertical={false} />

              {/* X Axis */}
              <XAxis
                dataKey="date"
                stroke="var(--text-muted)"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: 'var(--border-card)' }}
              />

              {/* Y Axis: Ascending order with highlighted Threshold Tick */}
              <YAxis
                width={38}
                stroke="var(--text-muted)"
                tickLine={false}
                axisLine={false}
                domain={yDomain}
                ticks={yTicks}
                tick={(props: any) => {
                  const { x, y, payload } = props;
                  if (!payload || payload.value === undefined) return null;
                  const val = Number(payload.value);
                  const isThreshold = Math.abs(val - activeThreshold) < 0.05;

                  if (isThreshold) {
                    return (
                      <text
                        x={x - 4}
                        y={y + 4}
                        textAnchor="end"
                        fill="#ef4444"
                        fontSize={12}
                        fontWeight="700"
                        fontFamily="system-ui, -apple-system, sans-serif"
                      >
                        {val}
                      </text>
                    );
                  }

                  return (
                    <text
                      x={x - 4}
                      y={y + 4}
                      textAnchor="end"
                      fill="#64748b"
                      fontSize={11}
                      fontWeight="500"
                      fontFamily="system-ui, -apple-system, sans-serif"
                    >
                      {val}
                    </text>
                  );
                }}
              />

              {/* Top Shaded Zone: Above threshold */}
              <ReferenceArea
                y1={activeThreshold}
                y2={yDomain[1]}
                fill={selectedMetric.goodDirection === 'below' ? '#ef4444' : '#10b981'}
                fillOpacity={0.05}
              />

              {/* Bottom Shaded Zone: Below threshold */}
              <ReferenceArea
                y1={yDomain[0]}
                y2={activeThreshold}
                fill={selectedMetric.goodDirection === 'below' ? '#10b981' : '#ef4444'}
                fillOpacity={0.05}
              />

              {/* Central Horizontal Solid Red Threshold Reference Line */}
              <ReferenceLine
                y={activeThreshold}
                stroke="#ef4444"
                strokeWidth={2}
              />

              {/* Custom Interactive Tooltip */}
              <Tooltip
                content={({ active, payload }: any) => {
                  if (!active || !payload || !payload.length) return null;
                  const pt = payload[0].payload as MetricPoint;
                  const diff = (pt.value - activeThreshold).toFixed(1);
                  const diffSign = Number(diff) > 0 ? `+${diff}` : `${diff}`;
                  const isGood = pt.isGood;

                  return (
                    <div className="bg-slate-900/95 backdrop-blur-xl border border-white/10 rounded-xl p-3.5 shadow-2xl min-w-[230px]">
                      <div className="flex items-center justify-between gap-3 mb-2 pb-2 border-b border-white/10">
                        <span className="text-xs font-semibold text-slate-300">{pt.date}</span>
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1 ${
                            isGood
                              ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                              : 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
                          }`}
                        >
                          {isGood ? '● Đạt mục tiêu (Tốt)' : '▲ Vượt ngưỡng (Cảnh báo)'}
                        </span>
                      </div>

                      <div className="flex items-baseline justify-between mb-1.5">
                        <span className="text-xs text-slate-400">{selectedMetric.label}:</span>
                        <span className="text-base font-bold font-mono text-slate-900 dark:text-slate-100 font-extrabold">
                          {pt.value} <span className="text-xs font-normal text-slate-400">{activeUnit}</span>
                        </span>
                      </div>

                      <div className="flex items-center justify-between text-[11px] pt-1.5 border-t border-white/5 text-slate-400">
                        <span>So với ngưỡng ({activeThreshold}):</span>
                        <span className={`font-mono font-semibold ${isGood ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {diffSign} {activeUnit}
                        </span>
                      </div>

                      <div
                        className={`mt-2.5 text-[10.5px] rounded-lg px-2.5 py-1.5 border ${
                          isGood
                            ? 'bg-emerald-950/30 border-emerald-500/20 text-emerald-300/90'
                            : 'bg-rose-950/30 border-rose-500/20 text-rose-300/90'
                        }`}
                      >
                        {isGood
                          ? `Chỉ số đạt mục tiêu kiểm soát an toàn (${selectedMetric.goodText})`
                          : `Chỉ số cảnh báo vượt ngưỡng khuyến cáo (${selectedMetric.warningText})`}
                      </div>
                    </div>
                  );
                }}
              />

              {/* Area & Trend Curve: Split 2 colors based on clinical condition */}
              <Area
                type="monotone"
                dataKey="value"
                stroke="url(#curveStrokeGrad)"
                strokeWidth={2.8}
                fillOpacity={1}
                fill="url(#areaSplitGrad)"
                dot={(props: any) => {
                  const { cx, cy, payload } = props;
                  if (!payload || cx === undefined || cy === undefined) return <React.Fragment key={`dot-${cx}-${cy}`} />;
                  const isGood = payload.isGood;
                  const dotColor = isGood ? '#10b981' : '#ef4444';
                  return (
                    <g key={`point-${payload.date}-${cx}-${cy}`}>
                      <circle
                        cx={cx}
                        cy={cy}
                        r={7}
                        fill="transparent"
                        stroke={dotColor}
                        strokeWidth={2}
                        strokeOpacity={0.4}
                      />
                      <circle
                        cx={cx}
                        cy={cy}
                        r={4.5}
                        fill={dotColor}
                        stroke="#0f172a"
                        strokeWidth={2}
                      />
                    </g>
                  );
                }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Footer Legend & Information */}
      {data.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-4 mt-3 pt-3 border-t border-white/5 text-[11px]">
          <div className="flex flex-wrap items-center gap-5">
            {/* Threshold Line Legend */}
            <div className="flex items-center gap-2">
              <div className="w-6 border-t-2 border-red-500" />
              <span className="text-red-400 font-semibold">
                Đường ngưỡng tham chiếu ({activeThreshold} {activeUnit})
              </span>
            </div>

            {/* Safe / Good Indicator Legend */}
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
              <span className="text-emerald-400 font-medium">Đạt mục tiêu (Tốt)</span>
            </div>

            {/* Warning Indicator Legend */}
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-rose-500" />
              <span className="text-rose-400 font-medium">Vượt ngưỡng (Cảnh báo)</span>
            </div>
          </div>

          <div className="flex items-center gap-2 text-slate-500 font-mono text-[10.5px]">
            <span>{data.length} lần đo</span>
            <span>•</span>
            <span>{selectedMetric.description.slice(0, 48)}...</span>
          </div>
        </div>
      )}
    </div>
  );
}
