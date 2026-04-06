import { createOpenAI } from "@ai-sdk/openai";
import { streamText, createUIMessageStreamResponse, UIMessage } from "ai";

const openai = createOpenAI({
  baseURL: process.env.OPENAI_COMPAT_BASE_URL || "https://api-inference.modelscope.cn/v1",
  apiKey: process.env.OPENAI_COMPAT_API_KEY || "",
});

interface StockContext {
  ticker?: string;
  name?: string | null;
  price?: number | null;
  changePercent?: number | null;
  peRatio?: number | null;
  marketCap?: number | null;
  analysis?: string | null;
  keyMetrics?: Record<string, unknown> | null;
}

function extractTextFromParts(parts: UIMessage["parts"]): string {
  if (!parts) return "";
  return parts
    .filter((p): p is { type: "text"; text: string } => p.type === "text")
    .map((p) => p.text)
    .join("");
}

export async function POST(req: Request) {
  const { messages, stockContext } = (await req.json()) as {
    messages: UIMessage[];
    stockContext?: StockContext;
  };

  const formatKeyMetrics = (metrics: Record<string, unknown> | null | undefined): string => {
    if (!metrics) return "";
    const entries = Object.entries(metrics)
      .filter(([, v]) => v !== null && v !== undefined)
      .map(([k, v]) => `- ${k}: ${v}`)
      .join("\n");
    return entries ? `\n关键财务指标：\n${entries}` : "";
  };

  const systemPrompt = `你是一位专业的投资分析师助手，擅长分析股票、财务报表和市场趋势。请用简体中文回答。

${stockContext ? `当前分析的股票/财报信息：
- 股票代码: ${stockContext.ticker}
- 公司/财报名称: ${stockContext.name || "未知"}
${stockContext.price ? `- 当前价格: ${stockContext.price}` : ""}
${stockContext.changePercent !== null && stockContext.changePercent !== undefined ? `- 涨跌幅: ${stockContext.changePercent}%` : ""}
${stockContext.peRatio ? `- 市盈率: ${stockContext.peRatio}` : ""}
${stockContext.marketCap ? `- 市值: ${stockContext.marketCap}` : ""}
${formatKeyMetrics(stockContext.keyMetrics)}
${stockContext.analysis ? `\n已有的分析结论：\n${stockContext.analysis.substring(0, 2000)}` : ""}
` : ""}

请提供专业、客观的分析建议。注意：
1. 所有分析仅供参考，不构成投资建议
2. 投资有风险，决策需谨慎
3. 请基于事实和数据进行分析
4. 如果信息不足，请明确说明
5. 请使用简体中文回答`;

  // Convert UIMessages to simple format for streamText
  const simpleMessages = messages.map((m) => ({
    role: m.role as "user" | "assistant" | "system",
    content: extractTextFromParts(m.parts),
  }));

  const result = streamText({
    model: openai(process.env.OPENAI_COMPAT_MODEL || "Qwen/Qwen3-8B"),
    system: systemPrompt,
    messages: simpleMessages,
  });

  return createUIMessageStreamResponse({
    stream: result.toUIMessageStream(),
  });
}
