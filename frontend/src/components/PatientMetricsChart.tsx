'use client';

import React, { useState, useEffect, useMemo } from 'react';
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
  CheckCircle2,
  ShieldCheck,
  Target,
  Info,
  ArrowUp,
  ArrowDown,
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

  const loadMetric = (metric: MetricOption) => {
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
  };

  useEffect(() => {
    loadMetric(selectedMetric);
  }, [patientId, selectedMetric]);

  const handleMetricChange = (metric: MetricOption) => {
    setSelectedMetric(metric);
  };

  // Calculate trend direction
  const trendDirection = data.length >= 2
    ? data[data.length - 1].value > data[data.length - 2].value ? 'up' : 'down'
    : null;

  const latestPoint = data.length > 0 ? data[data.length - 1] : null;
  const hasWarningPoints = data.some((d) => d.isWarning);

  // Compute dynamic Y-axis domain so the threshold is cleanly visible inside the chart
  const yDomain = useMemo<[number, number]>(() => {
    if (data.length === 0) {
      return [Math.max(0, activeThreshold * 0.8), activeThreshold * 1.2];
    }
    const values = data.map((d) => d.value);
    const minVal = Math.min(...values, activeThreshold);
    const maxVal = Math.max(...values, activeThreshold);
    const span = maxVal - minVal;
    const padding = span > 0 ? span * 0.25 : Math.max(activeThreshold * 0.15, 1);

    const lower = Math.max(0, Math.floor((minVal - padding) * 10) / 10);
    const upper = Math.ceil((maxVal + padding) * 10) / 10;
    return [lower, upper];
  }, [data, activeThreshold]);

  return (
    <div className="bg-slate-900/50 backdrop-blur-xl border border-white/10 rounded-2xl p-6 shadow-2xl mb-6 relative overflow-hidden">
      {/* Ambient background glow */}
      <div className="absolute top-0 right-1/4 w-96 h-32 bg-cyan-500/5 blur-3xl pointer-events-none -z-10" />
      <div className="absolute bottom-0 left-1/4 w-96 h-32 bg-amber-500/5 blur-3xl pointer-events-none -z-10" />

      {/* Top Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-500/10 flex items-center justify-center border border-cyan-500/20 shadow-[0_0_15px_rgba(34,211,238,0.2)]">
            <Activity className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-slate-100">Diễn tiến Chỉ số & Ngưỡng Lâm sàng</h3>
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-white/5 font-mono">
                {selectedMetric.label}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">{selectedMetric.fullName}</p>
          </div>
        </div>

        {/* Right side controls: Metric pills & Latest Status */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Metric Selector Pills */}
          <div className="flex gap-1 bg-slate-950/60 p-1 rounded-xl border border-white/5 shadow-inner">
            {METRIC_OPTIONS.map((m) => {
              const isSelected = selectedMetric.code === m.code;
              return (
                <button
                  key={m.code}
                  onClick={() => handleMetricChange(m)}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-gradient-to-r from-cyan-500/20 to-blue-500/20 text-cyan-300 border border-cyan-500/30 shadow-[0_0_10px_rgba(6,182,212,0.15)]'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'
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
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl border font-semibold text-xs shadow-sm ${
                latestPoint.isGood
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.15)]'
                  : 'bg-amber-500/10 border-amber-500/30 text-amber-300 shadow-[0_0_12px_rgba(245,158,11,0.15)]'
              }`}
            >
              {latestPoint.isGood ? (
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
              )}
              <div className="flex items-center gap-1.5">
                <span className="text-slate-300 font-normal">Gần nhất:</span>
                <span className="font-bold font-mono text-sm">
                  {latestPoint.value} {activeUnit}
                </span>
                {trendDirection === 'up' && <TrendingUp className="w-3.5 h-3.5 text-slate-300 ml-0.5" />}
                {trendDirection === 'down' && <TrendingDown className="w-3.5 h-3.5 text-slate-300 ml-0.5" />}
              </div>
              <span className="text-[10px] px-1.5 py-0.5 rounded-md font-medium uppercase tracking-wider bg-black/20">
                {latestPoint.isGood ? 'Tốt' : 'Cảnh báo'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Threshold Explanation & Zone Visual Banner */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5 mb-4 rounded-xl bg-slate-950/40 border border-white/5 text-xs text-slate-300">
        <div className="flex items-center gap-2">
          <Target className="w-4 h-4 text-cyan-400 shrink-0" />
          <span className="text-slate-400">Ngưỡng chuẩn:</span>
          <span className="font-bold text-slate-100 font-mono">
            {activeThreshold} {activeUnit}
          </span>
        </div>

        {/* Dynamic Zone Orientation Indicators */}
        <div className="flex items-center gap-4 text-[11px]">
          {selectedMetric.goodDirection === 'above' ? (
            <>
              <div className="flex items-center gap-1.5 text-emerald-400">
                <ArrowUp className="w-3.5 h-3.5" />
                <span className="font-medium">Phía trên (≥ {activeThreshold}):</span>
                <span className="text-emerald-300/90 font-semibold">Tình trạng TỐT</span>
              </div>
              <div className="w-px h-3 bg-white/10" />
              <div className="flex items-center gap-1.5 text-amber-400">
                <ArrowDown className="w-3.5 h-3.5" />
                <span className="font-medium">Phía dưới (&lt; {activeThreshold}):</span>
                <span className="text-amber-300/90 font-semibold">Tình trạng CẢNH BÁO</span>
              </div>
            </>
          ) : (
            <>
              <div className="flex items-center gap-1.5 text-emerald-400">
                <ArrowDown className="w-3.5 h-3.5" />
                <span className="font-medium">Phía dưới (≤ {activeThreshold}):</span>
                <span className="text-emerald-300/90 font-semibold">Tình trạng TỐT (Mục tiêu)</span>
              </div>
              <div className="w-px h-3 bg-white/10" />
              <div className="flex items-center gap-1.5 text-amber-400">
                <ArrowUp className="w-3.5 h-3.5" />
                <span className="font-medium">Phía trên (&gt; {activeThreshold}):</span>
                <span className="text-amber-300/90 font-semibold">Tình trạng CẢNH BÁO</span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Chart Canvas Area */}
      {loading ? (
        <div className="h-[250px] flex items-center justify-center text-slate-400">
          <RefreshCw className="w-5 h-5 animate-spin mr-2 text-cyan-400" />
          <span className="text-sm">Đang tải biểu đồ chỉ số...</span>
        </div>
      ) : error ? (
        <div className="h-[250px] flex flex-col items-center justify-center text-slate-400">
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
        <div className="h-[250px] flex flex-col items-center justify-center text-slate-400">
          <Activity className="w-8 h-8 text-slate-600 mb-2" />
          <span className="text-sm">Không có dữ liệu {selectedMetric.label} cho bệnh nhân này.</span>
        </div>
      ) : (
        <div className="h-[260px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 18, right: 24, left: -10, bottom: 5 }}>
              <defs>
                {/* Visual Area Gradient */}
                <linearGradient id="metricAreaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={hasWarningPoints ? '#f59e0b' : '#22d3ee'} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={hasWarningPoints ? '#f59e0b' : '#22d3ee'} stopOpacity={0.02} />
                </linearGradient>

                {/* Glow filter for the reference threshold line */}
                <filter id="thresholdGlow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="2" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>

              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />

              <XAxis
                dataKey="date"
                stroke="#64748b"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
              />

              <YAxis
                stroke="#64748b"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                domain={yDomain}
                tickFormatter={(v) => `${v}`}
              />

              {/* Shaded Zone Visuals for Good vs Warning areas */}
              {selectedMetric.goodDirection === 'above' ? (
                <>
                  <ReferenceArea
                    y1={activeThreshold}
                    y2={yDomain[1]}
                    fill="#10b981"
                    fillOpacity={0.04}
                  />
                  <ReferenceArea
                    y1={yDomain[0]}
                    y2={activeThreshold}
                    fill="#f59e0b"
                    fillOpacity={0.04}
                  />
                </>
              ) : (
                <>
                  <ReferenceArea
                    y1={yDomain[0]}
                    y2={activeThreshold}
                    fill="#10b981"
                    fillOpacity={0.04}
                  />
                  <ReferenceArea
                    y1={activeThreshold}
                    y2={yDomain[1]}
                    fill="#f59e0b"
                    fillOpacity={0.04}
                  />
                </>
              )}

              {/* Central Horizontal Threshold Reference Line */}
              <ReferenceLine
                y={activeThreshold}
                stroke="#38bdf8"
                strokeDasharray="6 4"
                strokeWidth={2}
                filter="url(#thresholdGlow)"
                label={(props: any) => {
                  const { viewBox } = props;
                  if (!viewBox) return null;
                  const { x, y, width } = viewBox;
                  const badgeWidth = 175;
                  const badgeX = Math.max(x + 10, x + width - badgeWidth - 10);
                  const badgeY = Math.max(8, y - 13);

                  return (
                    <g key="threshold-badge" transform={`translate(${badgeX}, ${badgeY})`}>
                      <rect
                        width={badgeWidth}
                        height={24}
                        rx={6}
                        fill="rgba(15, 23, 42, 0.9)"
                        stroke="rgba(56, 189, 248, 0.6)"
                        strokeWidth={1.2}
                      />
                      <circle cx={14} cy={12} r={4} fill="#38bdf8" />
                      <text
                        x={24}
                        y={16}
                        fill="#38bdf8"
                        fontSize={10.5}
                        fontWeight="700"
                        letterSpacing="0.3px"
                        fontFamily="system-ui, sans-serif"
                      >
                        NGƯỠNG: {activeThreshold} {activeUnit}
                      </text>
                    </g>
                  );
                }}
              />

              {/* Custom Interactive Tooltip */}
              <Tooltip
                content={({ active, payload }: any) => {
                  if (!active || !payload || !payload.length) return null;
                  const pt = payload[0].payload as MetricPoint;
                  const diff = (pt.value - activeThreshold).toFixed(1);
                  const diffSign = Number(diff) > 0 ? `+${diff}` : `${diff}`;

                  return (
                    <div className="bg-slate-900/95 backdrop-blur-xl border border-white/10 rounded-xl p-3.5 shadow-2xl min-w-[230px]">
                      <div className="flex items-center justify-between gap-3 mb-2 pb-2 border-b border-white/10">
                        <span className="text-xs font-semibold text-slate-300">{pt.date}</span>
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1 ${
                            pt.isGood
                              ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                              : 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                          }`}
                        >
                          {pt.isGood ? '✓ Tình trạng tốt' : '⚠️ Tình trạng cảnh báo'}
                        </span>
                      </div>

                      <div className="flex items-baseline justify-between mb-1.5">
                        <span className="text-xs text-slate-400">{selectedMetric.label}:</span>
                        <span className="text-base font-bold font-mono text-slate-100">
                          {pt.value} <span className="text-xs font-normal text-slate-400">{activeUnit}</span>
                        </span>
                      </div>

                      <div className="flex items-center justify-between text-[11px] pt-1.5 border-t border-white/5 text-slate-400">
                        <span>So với ngưỡng ({activeThreshold}):</span>
                        <span className={`font-mono font-semibold ${pt.isGood ? 'text-emerald-400' : 'text-amber-400'}`}>
                          {diffSign} {activeUnit}
                        </span>
                      </div>

                      <div
                        className={`mt-2.5 text-[10.5px] rounded-lg px-2.5 py-1.5 border ${
                          pt.isGood
                            ? 'bg-emerald-950/30 border-emerald-500/20 text-emerald-300/90'
                            : 'bg-amber-950/30 border-amber-500/20 text-amber-300/90'
                        }`}
                      >
                        {pt.isGood ? selectedMetric.goodText : selectedMetric.warningText}
                      </div>
                    </div>
                  );
                }}
              />

              {/* Area & Trend Curve */}
              <Area
                type="monotone"
                dataKey="value"
                stroke={hasWarningPoints ? '#f59e0b' : '#22d3ee'}
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#metricAreaGrad)"
                dot={(props: any) => {
                  const { cx, cy, payload } = props;
                  if (!payload || cx === undefined || cy === undefined) return <React.Fragment key={`dot-${cx}-${cy}`} />;
                  const isGood = payload.isGood;
                  return (
                    <g key={`point-${payload.date}-${cx}-${cy}`}>
                      <circle
                        cx={cx}
                        cy={cy}
                        r={6}
                        fill="transparent"
                        stroke={isGood ? '#10b981' : '#f59e0b'}
                        strokeWidth={1.5}
                        strokeOpacity={0.4}
                      />
                      <circle
                        cx={cx}
                        cy={cy}
                        r={4}
                        fill={isGood ? '#10b981' : '#f59e0b'}
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
              <div className="w-6 border-t-2 border-dashed border-sky-400" />
              <span className="text-slate-300 font-medium">
                Dòng ngưỡng tham chiếu ({activeThreshold} {activeUnit})
              </span>
            </div>

            {/* Good Indicator Legend */}
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.7)]" />
              <span className="text-emerald-400 font-medium">Tình trạng tốt</span>
            </div>

            {/* Warning Indicator Legend */}
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.7)]" />
              <span className="text-amber-400 font-medium">Tình trạng cảnh báo</span>
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
