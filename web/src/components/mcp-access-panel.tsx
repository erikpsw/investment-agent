"use client";

import { useState } from "react";
import {
  ChevronDown,
  Copy,
  ExternalLink,
  KeyRound,
  Loader2,
  ShieldCheck,
  Trash2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { CreatedPersonalAccessToken, PersonalAccessToken } from "@/lib/api";
import {
  CONNECTOR_SETTINGS_URLS,
  MCP_OAUTH_CLIENT_ID,
  MCP_SERVER_URL,
} from "@/lib/mcp-connectors";

interface McpAccessPanelProps {
  tokens: PersonalAccessToken[];
  createdToken: CreatedPersonalAccessToken | null;
  newTokenName: string;
  tokenLoading: boolean;
  onNewTokenNameChange: (value: string) => void;
  onCreateToken: () => void;
  onCopyToken: () => void;
  onCloseCreatedToken: () => void;
  onRevokeToken: (id: string) => void;
}

export function McpAccessPanel({
  tokens,
  createdToken,
  newTokenName,
  tokenLoading,
  onNewTokenNameChange,
  onCreateToken,
  onCopyToken,
  onCloseCreatedToken,
  onRevokeToken,
}: McpAccessPanelProps) {
  const [open, setOpen] = useState(true);
  const [tokenOpen, setTokenOpen] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [renderedAt] = useState(() => Date.now());

  const copyValue = async (label: string, value: string) => {
    await navigator.clipboard.writeText(value);
    setCopied(label);
    window.setTimeout(() => setCopied(null), 1600);
  };

  return (
    <Card>
      <Collapsible open={open} onOpenChange={setOpen}>
        <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
          <div>
            <CardTitle className="flex items-center gap-2">
              <KeyRound className="h-5 w-5" />远程 MCP 接入
            </CardTitle>
            <CardDescription>推荐使用 OAuth。Personal Access Token 仅作为不支持 OAuth 时的备用方案。</CardDescription>
          </div>
          <CollapsibleTrigger asChild>
            <Button type="button" variant="ghost" size="sm">
              {open ? "收起" : "展开"}
              <ChevronDown className={`ml-1 h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} />
            </Button>
          </CollapsibleTrigger>
        </CardHeader>

        <CollapsibleContent>
          <CardContent className="space-y-5">
            <section className="space-y-4 rounded-xl border border-primary/25 bg-primary/5 p-4">
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-primary/10 p-2 text-primary"><ShieldCheck className="h-5 w-5" /></div>
                <div>
                  <div className="font-medium">OAuth 推荐接入</div>
                  <p className="text-sm text-muted-foreground">登录 Auth0 后仅授权读取你的投资组合，无需保存长期 Token。</p>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-[150px_minmax(0,1fr)_auto] md:items-center">
                <div className="text-sm text-muted-foreground">MCP Server URL</div>
                <code className="break-all rounded bg-background px-3 py-2 text-xs sm:text-sm">{MCP_SERVER_URL}</code>
                <Button type="button" variant="outline" size="sm" onClick={() => copyValue("url", MCP_SERVER_URL)}>
                  <Copy />{copied === "url" ? "已复制" : "复制"}
                </Button>

                <div className="text-sm text-muted-foreground">OAuth Client ID</div>
                <code className="break-all rounded bg-background px-3 py-2 text-xs sm:text-sm">{MCP_OAUTH_CLIENT_ID}</code>
                <Button type="button" variant="outline" size="sm" onClick={() => copyValue("client", MCP_OAUTH_CLIENT_ID)}>
                  <Copy />{copied === "client" ? "已复制" : "复制"}
                </Button>
              </div>

              <div className="flex flex-wrap gap-2">
                <a
                  className={buttonVariants({ variant: "default" })}
                  href={CONNECTOR_SETTINGS_URLS.claude}
                  target="_blank"
                  rel="noreferrer"
                >
                  打开 Claude 连接器<ExternalLink />
                </a>
                <a
                  className={buttonVariants({ variant: "outline" })}
                  href={CONNECTOR_SETTINGS_URLS.chatgpt}
                  target="_blank"
                  rel="noreferrer"
                >
                  打开 ChatGPT Apps 设置<ExternalLink />
                </a>
              </div>
              <p className="text-xs leading-5 text-muted-foreground">
                在第三方设置页粘贴上面的 Server URL 和 Client ID；Client Secret 留空。ChatGPT 自定义 MCP App 需要工作区支持 Developer mode。
              </p>
            </section>

            <Collapsible open={tokenOpen} onOpenChange={setTokenOpen} className="rounded-xl border">
              <div className="flex items-center justify-between gap-3 p-4">
                <div>
                  <div className="font-medium">备用 Token 接入</div>
                  <p className="text-sm text-muted-foreground">适用于 Codex bearer token 配置或 OAuth 故障排查，有效期 90 天。</p>
                </div>
                <CollapsibleTrigger asChild>
                  <Button type="button" variant="ghost" size="sm">
                    {tokenOpen ? "收起" : "展开"}
                    <ChevronDown className={`ml-1 h-4 w-4 transition-transform ${tokenOpen ? "rotate-180" : ""}`} />
                  </Button>
                </CollapsibleTrigger>
              </div>
              <CollapsibleContent>
                <div className="space-y-4 border-t p-4">
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Input
                      value={newTokenName}
                      onChange={(event) => onNewTokenNameChange(event.target.value)}
                      maxLength={80}
                      placeholder="例如：Codex MCP"
                      className="sm:max-w-sm"
                    />
                    <Button variant="outline" onClick={onCreateToken} disabled={tokenLoading || !newTokenName.trim()}>
                      {tokenLoading ? <Loader2 className="animate-spin" /> : <KeyRound />}创建 90 天 Token
                    </Button>
                  </div>

                  {createdToken && (
                    <div className="space-y-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-4">
                      <div className="font-medium">完整 Token 仅显示这一次</div>
                      <Textarea value={createdToken.token} readOnly className="min-h-24 font-mono text-xs" />
                      <div className="flex flex-wrap gap-2">
                        <Button variant="outline" onClick={onCopyToken}><Copy />复制 Token</Button>
                        <Button variant="ghost" onClick={onCloseCreatedToken}>我已保存，关闭</Button>
                      </div>
                    </div>
                  )}

                  <div className="space-y-2">
                    <div className="text-sm font-medium">已创建的 Token</div>
                    {tokens.length === 0 ? (
                      <div className="rounded-lg border p-3 text-sm text-muted-foreground">还没有有效的 Personal Access Token</div>
                    ) : tokens.map((token) => {
                      const expired = new Date(token.expires_at).getTime() <= renderedAt;
                      return (
                        <div key={token.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3 text-sm">
                          <div>
                            <div className="flex items-center gap-2 font-medium">
                              {token.name}<Badge variant={expired ? "outline" : "secondary"}>{expired ? "已过期" : "有效"}</Badge>
                            </div>
                            <div className="mt-1 text-xs text-muted-foreground">
                              {token.token_prefix}... · 到期 {new Date(token.expires_at).toLocaleString("zh-CN")}
                              {token.last_used_at ? ` · 最近使用 ${new Date(token.last_used_at).toLocaleString("zh-CN")}` : " · 尚未使用"}
                            </div>
                          </div>
                          {!expired && (
                            <Button variant="outline" size="sm" onClick={() => onRevokeToken(token.id)} disabled={tokenLoading}>
                              <Trash2 />撤销
                            </Button>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  <div className="rounded-lg border bg-muted/40 p-4 text-sm leading-6">
                    <div className="font-medium">Codex Token 配置</div>
                    <code className="mt-2 block break-all">设置环境变量 ERIK_AI_ACCESS_TOKEN 为上面的 Token</code>
                    <code className="block break-all">codex mcp add erik_ai --url {MCP_SERVER_URL} --bearer-token-env-var ERIK_AI_ACCESS_TOKEN</code>
                    <div className="mt-2 text-muted-foreground">Token 可立即撤销。请勿提交到 Git 或发送给他人。</div>
                  </div>
                </div>
              </CollapsibleContent>
            </Collapsible>
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}
