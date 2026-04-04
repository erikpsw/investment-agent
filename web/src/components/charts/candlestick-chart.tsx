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
  height?: number;
}

export function CandlestickChart({
  ticker,
  period = "1mo",
  interval = "1d",
  height = 400,
}: CandlestickChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const ma5SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ma20SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  const { data, isLoading, error } = useHistory(ticker, { period, interval });

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
      setContainerReady(true);
    }
  }, []);

  useEffect(() => {
    if (!chartContainerRef.current || !containerReady) return;
    
    const container = chartContainerRef.current;
    const containerWidth = container.clientWidth;

    const chart = createChart(container, {
      width: containerWidth,
      height,
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
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
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

    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return (
    <div className="space-y-2">
      <div className="relative" style={{ height }}>
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
        {error && (
          <div className="absolute inset-0 flex items-center justify-center text-muted-foreground bg-background/80">
            <p>加载图表失败: {error.message}</p>
          </div>
        )}
      </div>
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
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
