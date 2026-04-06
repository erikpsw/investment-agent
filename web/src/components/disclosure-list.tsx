"use client";

import { useState } from "react";
import { FileText, Download, ExternalLink, ChevronDown, ChevronUp, Loader2, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useDisclosure } from "@/hooks/use-quote";

interface DisclosureListProps {
  ticker: string;
  compactMode?: boolean;
  maxItems?: number;
}

export function DisclosureList({ ticker, compactMode = false, maxItems = 5 }: DisclosureListProps) {
  const { data: disclosure, isLoading, refetch, isFetching } = useDisclosure(ticker, "annual");
  const [expanded, setExpanded] = useState(false);

  if (isLoading) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="h-4 w-4" />
            财报 PDF
            <Loader2 className="h-4 w-4 animate-spin ml-auto" />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!disclosure || disclosure.documents.length === 0) {
    return null;
  }

  const hasPdfLinks = disclosure.documents.some(doc => doc.url.endsWith('.pdf'));
  const displayDocs = expanded ? disclosure.documents : disclosure.documents.slice(0, maxItems);

  if (compactMode) {
    return (
      <div className="space-y-1.5">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <FileText className="h-4 w-4" />
            财报 PDF
            {disclosure.cached && (
              <Badge variant="secondary" className="text-xs">缓存</Badge>
            )}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            {isFetching ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <RefreshCw className="h-3 w-3" />
            )}
          </Button>
        </div>
        
        {hasPdfLinks ? (
          <>
            {displayDocs.map((doc, index) => (
              <a
                key={index}
                href={doc.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-start gap-2 p-2 rounded-lg hover:bg-muted/50 transition-colors group text-sm"
              >
                <div className="mt-0.5">
                  {doc.url.endsWith('.pdf') ? (
                    <Download className="h-3.5 w-3.5 text-red-500" />
                  ) : (
                    <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate group-hover:text-primary text-xs">
                    {doc.title}
                  </p>
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span>{doc.date}</span>
                    {doc.size && (
                      <>
                        <span>·</span>
                        <span>{doc.size}</span>
                      </>
                    )}
                  </div>
                </div>
              </a>
            ))}
            {disclosure.documents.length > maxItems && (
              <Button
                variant="ghost"
                size="sm"
                className="w-full text-xs"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? (
                  <>
                    <ChevronUp className="h-3 w-3 mr-1" />
                    收起
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-3 w-3 mr-1" />
                    更多 ({disclosure.documents.length - maxItems})
                  </>
                )}
              </Button>
            )}
          </>
        ) : (
          disclosure.documents.map((doc, index) => (
            <a key={index} href={doc.url} target="_blank" rel="noopener noreferrer">
              <Button className="w-full justify-start text-xs h-8" variant="outline" size="sm">
                <FileText className="h-3 w-3 mr-1.5" />
                {doc.title}
                <ExternalLink className="h-3 w-3 ml-auto" />
              </Button>
            </a>
          ))
        )}
      </div>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="h-4 w-4" />
            财报 PDF
            {disclosure.cached && (
              <Badge variant="secondary" className="text-xs">缓存</Badge>
            )}
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            {isFetching ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <RefreshCw className="h-3 w-3" />
            )}
          </Button>
        </div>
        {disclosure.company_name && (
          <CardDescription>{disclosure.company_name}</CardDescription>
        )}
      </CardHeader>
      <CardContent>
        {hasPdfLinks ? (
          <ScrollArea className={expanded ? "h-[400px]" : "h-auto"}>
            <div className="space-y-1.5">
              {displayDocs.map((doc, index) => (
                <a
                  key={index}
                  href={doc.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-start gap-3 p-2 rounded-lg hover:bg-muted/50 transition-colors group"
                >
                  <div className="mt-0.5">
                    {doc.url.endsWith('.pdf') ? (
                      <Download className="h-4 w-4 text-red-500" />
                    ) : (
                      <ExternalLink className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate group-hover:text-primary">
                      {doc.title}
                    </p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span>{doc.date}</span>
                      {doc.size && (
                        <>
                          <span>·</span>
                          <span>{doc.size}</span>
                        </>
                      )}
                      {doc.category && (
                        <>
                          <span>·</span>
                          <Badge variant="outline" className="text-xs px-1 py-0">
                            {doc.category}
                          </Badge>
                        </>
                      )}
                    </div>
                  </div>
                </a>
              ))}
            </div>
          </ScrollArea>
        ) : (
          <div className="space-y-2">
            {disclosure.documents.map((doc, index) => (
              <a key={index} href={doc.url} target="_blank" rel="noopener noreferrer">
                <Button className="w-full justify-start" variant="outline">
                  <FileText className="h-4 w-4 mr-2" />
                  {doc.title}
                  <ExternalLink className="h-3 w-3 ml-auto" />
                </Button>
              </a>
            ))}
          </div>
        )}

        {disclosure.documents.length > maxItems && (
          <Button
            variant="ghost"
            className="w-full mt-2"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? (
              <>
                <ChevronUp className="h-4 w-4 mr-2" />
                收起
              </>
            ) : (
              <>
                <ChevronDown className="h-4 w-4 mr-2" />
                查看全部 ({disclosure.documents.length})
              </>
            )}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
