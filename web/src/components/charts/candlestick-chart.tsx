"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  CandlestickData,
  HistogramData,
  LineData,
  Time,
  ColorType,
} from "lightweight-charts";
import { Skeleton } from "@/components/ui/skeleton";
import { useHistory } from "@/hooks/use-history";

interface CandlestickChartProps {
  ticker: string;
  period?: string;
  interval?: string;
  height?: number | string;
}

export function CandlestickChart({
  ticker,
  period = "1y",
  interval = "1d",
  height = "clamp(200px, 32dvh, 300px)",
}: CandlestickChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const ma5SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ma20SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  // Fetch preceding bars so MA20 is available at the visible range's start.
  const fetchPeriod = ({ "5d": "3mo", "1mo": "3mo", "3mo": "6mo", "6mo": "1y", "1y": "2y", "5y": "10y", "10y": "max" } as Record<string, string>)[period] || period;
  const { data, isLoading, error } = useHistory(ticker, { period: fetchPeriod, interval });
  const visibleCount = ({ "5d": 5, "1mo": 22, "3mo": 65, "6mo": 125, "1y": 250, "5y": 1260, "10y": 2520 } as Record<string, number>)[period];

  const [containerReady, setContainerReady] = useState(false);

  useEffect(() => {
    if (!chartContainerRef.current) return;
    
    const container = chartContainerRef.current;
    
    if (container.clientWidth === 0) {
      const observer = new ResizeObserver((entries) => {
        for (const entry of entries) {
          if (entry.contentRect.width > 0) {
            setContainerReady(true);
            observer.disconnect();
          }
        }
      });
      observer.observe(container);
      return () => observer.disconnect();
    } else {
      const frame = requestAnimationFrame(() => setContainerReady(true));
      return () => cancelAnimationFrame(frame);
    }
  }, []);

  useEffect(() => {
    if (!chartContainerRef.current || !containerReady) return;
    
    const container = chartContainerRef.current;
    const containerWidth = container.clientWidth;

    const chart = createChart(container, {
      width: containerWidth,
      height: container.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9ca3af",
      },
      grid: {
        vertLines: { color: "#e5e7eb20" },
        horzLines: { color: "#e5e7eb20" },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: "#e5e7eb40",
      },
      timeScale: {
        borderColor: "#e5e7eb40",
        timeVisible: true,
      },
    });

    chartRef.current = chart;

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });
    candlestickSeriesRef.current = candlestickSeries;

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: "#6366f1",
      priceFormat: {
        type: "volume",
      },
      priceScaleId: "",
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.85,
        bottom: 0,
      },
    });
    volumeSeriesRef.current = volumeSeries;

    const ma5Series = chart.addSeries(LineSeries, {
      color: "#f59e0b",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    ma5SeriesRef.current = ma5Series;

    const ma20Series = chart.addSeries(LineSeries, {
      color: "#3b82f6",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    ma20SeriesRef.current = ma20Series;

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth, height: chartContainerRef.current.clientHeight });
      }
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [height, containerReady]);

  useEffect(() => {
    if (!data?.bars || !candlestickSeriesRef.current) return;

    const candlestickData: CandlestickData<Time>[] = data.bars.map((bar) => ({
      time: bar.time as Time,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    }));

    const volumeData: HistogramData<Time>[] = data.bars.map((bar) => ({
      time: bar.time as Time,
      value: bar.volume,
      color: bar.close >= bar.open ? "#22c55e80" : "#ef444480",
    }));

    const closes = data.bars.map((bar) => bar.close);
    const ma5Data: LineData<Time>[] = [];
    const ma20Data: LineData<Time>[] = [];

    for (let i = 0; i < data.bars.length; i++) {
      if (i >= 4) {
        const sum5 = closes.slice(i - 4, i + 1).reduce((a, b) => a + b, 0);
        ma5Data.push({
          time: data.bars[i].time as Time,
          value: sum5 / 5,
        });
      }
      if (i >= 19) {
        const sum20 = closes.slice(i - 19, i + 1).reduce((a, b) => a + b, 0);
        ma20Data.push({
          time: data.bars[i].time as Time,
          value: sum20 / 20,
        });
      }
    }

    candlestickSeriesRef.current.setData(candlestickData);
    volumeSeriesRef.current?.setData(volumeData);
    ma5SeriesRef.current?.setData(ma5Data);
    ma20SeriesRef.current?.setData(ma20Data);

    let start = Math.max(0, data.bars.length - (visibleCount || data.bars.length));
    const years = ({ "1y": 1, "5y": 5, "10y": 10 } as Record<string, number>)[period];
    if (years && data.bars.length) {
      const cutoff = new Date(data.bars[data.bars.length - 1].time);
      cutoff.setUTCFullYear(cutoff.getUTCFullYear() - years);
      const date = cutoff.toISOString().slice(0, 10);
      const index = data.bars.findIndex(bar => bar.time >= date);
      start = Math.max(0, index);
    }
    if (data.bars.length > 1) chartRef.current?.timeScale().setVisibleLogicalRange({ from: start, to: data.bars.length - 1 });
    else if (data.bars.length === 1) chartRef.current?.timeScale().fitContent();
  }, [data, visibleCount, containerReady, period]);

  return (
    <div className="min-w-0 space-y-2">
      <div className="relative" data-testid="candlestick-plot" style={{ height }}>
        <div ref={chartContainerRef} className="w-full h-full" />
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80">
            <div className="space-y-2 w-full px-4">
              <Skeleton className="w-full h-[200px]" />
              <div className="flex justify-between">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-4 w-20" />
              </div>
            </div>
          </div>
        )}
        {!isLoading && !error && data && data.bars.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80 text-muted-foreground">
            <p>暂无走势数据</p>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center text-muted-foreground bg-background/80">
            <p>加载图表失败: {error.message}</p>
          </div>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <button type="button" className="min-h-11 rounded border px-3" onClick={() => chartRef.current?.timeScale().fitContent()}>查看全部已加载数据</button>
        <span>拖动查看 · 滚轮或双指缩放 · MA20 按日线计算</span>
        {data?.bars.length ? <span>已加载数据范围：{data.bars[0].time} 至 {data.bars[data.bars.length - 1].time}（{data.bars.length} 个交易日）</span> : null}
        <div className="flex items-center gap-1">
          <div className="w-3 h-0.5 bg-amber-500" />
          <span>MA5</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-0.5 bg-blue-500" />
          <span>MA20</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-green-500/50 rounded-sm" />
          <span>涨</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-red-500/50 rounded-sm" />
          <span>跌</span>
        </div>
      </div>
    </div>
  );
}
