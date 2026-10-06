"""Frozen prospective research. No optimization or automatic parameter promotion."""
from datetime import date
import hashlib
import json
from pathlib import Path
from investment.data.formula_backtest import prepare,simulate
from investment.data.formula_scoring import WEIGHTS

ROOT=Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(",",":")).encode()).hexdigest()


def verify_engine(protocol):
    for name,expected in protocol["engine_source_hashes"].items():
        path=ROOT/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError("Frozen engine changed; create a separate protocol")


def seal_protocol(report,cutoff,*,created_on=None):
    created_on=created_on or date.today().isoformat()
    if date.fromisoformat(cutoff).isoformat()!=cutoff or cutoff<created_on:
        raise ValueError("Prospective cutoff cannot precede creation")
    fold=report["folds"][-1]
    if fold["train_end"]>=cutoff or max(f["test_end"] for f in report["folds"])>cutoff:
        raise ValueError("Cutoff precedes inspected validation")
    eligible=[t for t in fold["training_trials"] if t["eligible"]]
    if not eligible or fold["candidate_weights"]!=max(eligible,key=lambda t:t["objective"])["weights"]:
        raise ValueError("Weights do not match training selection")
    risks=[t for t in fold["risk_training_trials"] if t["eligible"]]
    risk=fold["candidate_risk_parameters"]
    if not risks or risk!=max(risks,key=lambda t:t["objective"])["parameters"]:
        raise ValueError("Risk does not match training selection")
    symbols=report["sampling"]["selected"]
    if len(symbols)<8 or len(set(symbols))!=len(symbols):
        raise ValueError("Need full frozen requested sample")
    hashes=dict(report["engine_source_hashes"])
    for name in ["data/formula_holdout.py","data/formula_backtest.py","data/formula_scoring.py","data/formula_risk.py","data/formula_execution.py"]:
        actual=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
        if name in hashes and hashes[name]!=actual:raise ValueError("Training report engine changed; rebuild first")
        hashes[name]=actual
    protocol={"version":"prospective-v1","applied":False,"market":report["market"],"created_on":created_on,"cutoff":cutoff,"minimum_sessions":80,"requested_universe":symbols,"training_available_universe":report["universe"],"training_cutoff":fold["train_end"],"candidate_weights":fold["candidate_weights"],"baseline_weights":dict(WEIGHTS["balanced"]),"risk_parameters":risk,"research_settings":report["research_settings"],"one_way_cost":.0015,"holding_sessions":20,"top_n":3,"cost_stress":[.003,.005],"source_report_fingerprint":digest(report),"engine_source_hashes":hashes,"parameter_selection":"frozen_no_reselection","limitations":["固定请求样本，包含原历史下载失败的证券；不得事后换样本", "只评估截止日期之后的数据；历史滚动结果不是独立留出验证", "价格复权、公司行动、时点财务及港股历史每手仍需单独核验，不自动应用参数"]}
    protocol["seal"]=digest(protocol)
    return protocol


def evaluate_protocol(protocol,series):
    body={k:v for k,v in protocol.items() if k!="seal"}
    if digest(body)!=protocol.get("seal"):raise ValueError("Protocol seal mismatch")
    verify_engine(protocol)
    expected=set(protocol["requested_universe"])
    if set(series)-expected:raise ValueError("Unexpected securities outside frozen sample")
    missing=sorted(expected-set(series))
    if missing or any(len(bars)<61 for bars in series.values()):
        return {"status":"insufficient_data","applied":False,"protocol_seal":protocol["seal"],"missing_securities":missing,"message":"冻结请求样本或历史预热数据不完整，未计算收益"}
    all_dates=sorted({row["date"] for bars in series.values() for row in bars})
    future_dates=[day for day in all_dates if day>protocol["cutoff"]]
    if len(future_dates)<protocol["minimum_sessions"]:
        return {"status":"insufficient_data","applied":False,"protocol_seal":protocol["seal"],"available_future_sessions":len(future_dates),"required_sessions":protocol["minimum_sessions"],"message":"留出数据不足，不生成收益或重新选参"}
    boundary=future_dates[protocol["minimum_sessions"]-1]
    series={ticker:[row for row in bars if row["date"]<=boundary] for ticker,bars in series.items()}
    warmup_missing=[]
    for ticker,bars in series.items():
        prior=[row for row in bars if row["date"]<=protocol["cutoff"]]
        if len(prior)<61 or (date.fromisoformat(future_dates[0])-date.fromisoformat(prior[-1]["date"])).days>7:
            warmup_missing.append(ticker)
    if warmup_missing:
        return {"status":"insufficient_data","applied":False,"protocol_seal":protocol["seal"],"warmup_missing_securities":sorted(warmup_missing),"message":"首次留出交易日前缺少完整且近期的历史预热，不缩小样本计算收益"}
    settings=protocol["research_settings"]
    for bars in series.values():
        for row in bars:
            if row.get("volume_reference_enabled",False) is not bool(settings.get("volume_reference",False)):
                raise ValueError("Frozen volume feature settings changed")
            if row.get("reference_research_enabled",False) is not bool(settings.get("historical_reference",False)):
                raise ValueError("Frozen historical-reference feature settings changed")
    dates,_,_=prepare(series)
    start=dates.index(future_dates[0]); end=start+protocol["minimum_sessions"]
    # Features are point-in-time inputs; datasets must preserve their provider
    # and filing-date provenance. The seal freezes the model, not vendor truth.
    common={"one_way_cost":protocol["one_way_cost"],"holding":protocol["holding_sessions"],"top_n":protocol["top_n"],"execution":protocol["research_settings"].get("execution")}
    candidate=protocol["candidate_weights"]; baseline=protocol["baseline_weights"]; risk=protocol["risk_parameters"]
    variants={"candidate":(candidate,{}),"baseline":(baseline,{}),"benchmark":(baseline,{"benchmark":True}),"protected":(baseline,{"use_risk":True}),"risk_tuned":(candidate,{"use_risk":True,"risk_parameters":risk}),"capped_control":(candidate,{"use_risk":True,"risk_parameters":risk,"risk_exits":False})}
    results={name:simulate(series,start,end,weights,**common,**options) for name,(weights,options) in variants.items()}
    stress=[{"one_way_cost":cost,**simulate(series,start,end,candidate,**{**common,"one_way_cost":cost},use_risk=True,risk_parameters=risk)} for cost in protocol["cost_stress"]]
    complete=all(r["missing_quote_days"]==0 and not r.get("risk_unverifiable_days") and not r.get("risk_missing_entries") for r in results.values())
    return {"status":"prospective_research","applied":False,"protocol_seal":protocol["seal"],"parameter_selection":protocol["parameter_selection"],"candidate_weights":candidate,"risk_parameters":risk,"test_start":dates[start],"test_end":dates[end-1],"sessions_evaluated":end-start,"complete_quote_and_risk_data":complete,"evaluation_input_fingerprint":digest(series),"out_of_sample":results,"cost_stress":stress,"limitations":protocol["limitations"]}
