import {Header} from "@/components/header";
import {MomentumDecisionChart} from "@/components/momentum-decision-chart";
export default async function DecisionPage({params,searchParams}:{params:Promise<{ticker:string}>;searchParams:Promise<{scope?:string}>}){
 const {ticker}=await params;
 const query=await searchParams;const scope=query.scope==='mainboard'?'mainboard':'reference793';
 return <><Header/><main className="mx-auto w-full max-w-7xl p-4 lg:p-8"><MomentumDecisionChart ticker={ticker} scope={scope}/></main></>;
}
