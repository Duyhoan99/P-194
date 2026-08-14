'use client';

import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, ReferenceLine } from 'recharts';
import { Activity, RefreshCw, TrendingDown, TrendingUp, AlertTriangle } from 'lucide-react';
import { patients } from '@/lib/api';

// Common LOINC codes for clinical metrics
const METRIC_OPTIONS = [
  { code: '4548-4', label: 'HbA1c', unit: '%', warnHigh: 7.0, critHigh: 9.0 },
  { code: '2339-0', label: 'Glucose', unit: 'mg/dL', warnHigh: 126, critHigh: 200 },
  { code: '2160-0', label: 'Creatinine', unit: 'mg/dL', warnHigh: 1.3, critHigh: 2.0 },
  { code: '33914-3', label: 'eGFR', unit: 'mL/min', warnLow: 60, critLow: 30 },
  { code: '8480-6', label: 'BP Systolic', unit: 'mmHg', warnHigh: 140, critHigh: 180 },
];

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('vi-VN', { month: 'short', year: '2-digit' });
  } catch {
    return dateStr;
  }
}

interface MetricData {
  date: string;
  value: number;
  raw: string;
  isAbnormal: boolean;
}

export default function PatientMetricsChart({ patientId }: { patientId: string }) {
  const [selectedMetric, setSelectedMetric] = useState(METRIC_OPTIONS[0]);
  const [data, setData] = useState<MetricData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [trendInfo, setTrendInfo] = useState<{ display: string; unit: string } | null>(null);

  const loadMetric = (metric: typeof METRIC_OPTIONS[0]) => {
    setLoading(true);
    setError('');
    patients.getTrends(patientId, metric.code)
      .then((res) => {
        const points = (res.points || []).map((p: any) => {
          const val = p.value;
          const isAbnormal = 
            (metric.warnHigh !== undefined && val > metric.warnHigh) ||
            ((metric as any).warnLow !== undefined && val < (metric as any).warnLow);
          return {
            date: formatDate(p.observed_at),
            value: val,
            raw: p.observed_at,
            isAbnormal,
          };
        });
        setData(points);
        setTrendInfo({ display: res.display || metric.label, unit: res.unit || metric.unit });
      })
      .catch((err: any) => {
        setError(err.detail || 'Unable to load trend data');
        setData([]);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadMetric(selectedMetric);
  }, [patientId, selectedMetric]);

  const handleMetricChange = (metric: typeof METRIC_OPTIONS[0]) => {
    setSelectedMetric(metric);
  };

  // Calculate trend direction
  const trendDirection = data.length >= 2
    ? data[data.length - 1].value > data[data.length - 2].value ? 'up' : 'down'
    : null;

  const latestValue = data.length > 0 ? data[data.length - 1].value : null;
  const hasAbnormal = data.some(d => d.isAbnormal);

  return (
    <div className="bg-slate-900/40 backdrop-blur-xl border border-white/5 rounded-2xl p-6 shadow-2xl mb-6">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-cyan-500/10 flex items-center justify-center border border-cyan-500/20 shadow-[0_0_12px_rgba(34,211,238,0.15)]">
            <Activity className="w-4.5 h-4.5 text-cyan-400" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-100">Vitals & Metrics Trend</h3>
            {trendInfo && (
              <span className="text-xs text-slate-500">{trendInfo.display} ({trendInfo.unit})</span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Metric selector pills */}
          <div className="flex gap-1 bg-slate-800/50 rounded-lg p-0.5 border border-white/5">
            {METRIC_OPTIONS.map((m) => (
              <button
                key={m.code}
                onClick={() => handleMetricChange(m)}
                className={`px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider rounded-md transition-all ${
                  selectedMetric.code === m.code
                    ? 'bg-cyan-900/50 text-cyan-300 shadow-sm'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>

          {/* Latest value */}
          {latestValue !== null && (
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm font-bold ${
              hasAbnormal
                ? 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
            }`}>
              {hasAbnormal && <AlertTriangle className="w-3.5 h-3.5" />}
              {latestValue.toFixed(1)} {selectedMetric.unit}
              {trendDirection === 'up' && <TrendingUp className="w-3.5 h-3.5 ml-1" />}
              {trendDirection === 'down' && <TrendingDown className="w-3.5 h-3.5 ml-1" />}
            </div>
          )}
        </div>
      </div>

      {loading ? (
        <div className="h-[220px] flex items-center justify-center text-slate-500">
          <RefreshCw className="w-5 h-5 animate-spin mr-2" />
          <span className="text-sm">Loading metrics...</span>
        </div>
      ) : error ? (
        <div className="h-[220px] flex flex-col items-center justify-center text-slate-500">
          <Activity className="w-8 h-8 text-slate-600 mb-2" />
          <span className="text-sm">{error}</span>
          <button onClick={() => loadMetric(selectedMetric)} className="mt-2 text-xs text-cyan-500 hover:text-cyan-400">Retry</button>
        </div>
      ) : data.length === 0 ? (
        <div className="h-[220px] flex flex-col items-center justify-center text-slate-500">
          <Activity className="w-8 h-8 text-slate-600 mb-2" />
          <span className="text-sm">No {selectedMetric.label} data available for this patient.</span>
        </div>
      ) : (
        <div className="h-[220px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="metricGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={hasAbnormal ? '#f59e0b' : '#22d3ee'} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={hasAbnormal ? '#f59e0b' : '#22d3ee'} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis dataKey="date" stroke="#64748b" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="#64748b" fontSize={11} tickLine={false} axisLine={false} domain={['auto', 'auto']} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(15, 23, 42, 0.95)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '12px',
                  backdropFilter: 'blur(10px)',
                  fontSize: '12px',
                }}
                itemStyle={{ color: '#e2e8f0' }}
                formatter={(value: any) => [`${Number(value).toFixed(2)} ${selectedMetric.unit}`, selectedMetric.label]}
              />
              {selectedMetric.warnHigh && (
                <ReferenceLine y={selectedMetric.warnHigh} stroke="rgba(245,158,11,0.4)" strokeDasharray="6 3" label="" />
              )}
              {(selectedMetric as any).warnLow && (
                <ReferenceLine y={(selectedMetric as any).warnLow} stroke="rgba(245,158,11,0.4)" strokeDasharray="6 3" label="" />
              )}
              <Area
                type="monotone"
                dataKey="value"
                stroke={hasAbnormal ? '#f59e0b' : '#22d3ee'}
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#metricGradient)"
                dot={(props: any) => {
                  const { cx, cy, payload } = props;
                  if (!payload) return <></>;
                  return (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={payload.isAbnormal ? 5 : 3}
                      fill={payload.isAbnormal ? '#f59e0b' : '#22d3ee'}
                      stroke={payload.isAbnormal ? '#92400e' : '#164e63'}
                      strokeWidth={2}
                    />
                  );
                }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Legend */}
      {data.length > 0 && (
        <div className="flex items-center gap-6 mt-3 pt-3 border-t border-white/5">
          <div className="flex items-center gap-2">
            <div className={`w-2.5 h-2.5 rounded-full ${hasAbnormal ? 'bg-amber-400' : 'bg-cyan-400'} shadow-[0_0_8px_rgba(34,211,238,0.6)]`} />
            <span className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold">{selectedMetric.label}</span>
          </div>
          {selectedMetric.warnHigh && (
            <div className="flex items-center gap-2">
              <div className="w-6 border-t-2 border-dashed border-amber-500/40" />
              <span className="text-[10px] text-slate-500 uppercase tracking-widest">Warning threshold</span>
            </div>
          )}
          <span className="text-[10px] text-slate-600 ml-auto">{data.length} data points</span>
        </div>
      )}
    </div>
  );
}
