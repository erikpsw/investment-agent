import * as OpenCC from "opencc-js";

const converter = OpenCC.Converter({ from: "hk", to: "cn" });

export function toSimplified(text: string): string {
  if (!text) return text;
  return converter(text);
}

export function toSimplifiedIfNeeded(text: string): string {
  if (!text) return text;
  
  const hasTraditional = /[\u4e00-\u9fff]/.test(text) && 
    /[報導製製據經營業務資訊財務處發佈於為與進統計據區間對於據報導說據統計據調查據分析據研據顯示據估計據報告據了解據悉據報據知情]/.test(text);
  
  if (hasTraditional) {
    return converter(text);
  }
  return text;
}
