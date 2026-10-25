"""Frozen selected momentum policy; read-only scenarios, never broker orders."""
import math

POLICY = dict(version='momentum-ma120-selected-r2', max_positions=20,
              hold_days=20, stop_pct=.12, ma_period=120, momentum_weeks=12,
              rebalance_weeks=1, daily_refill=False, stop_cooldown=0,
              momentum_rank=0., vol_rank_min=0., vol_rank_max=1.,
              rank_by='momentum_desc', lot_size=100, commission=.00025,
              stamp=.0005, slippage=.0005)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def market_gate(closes):
    window=closes[-120:]
    if len(window)<120 or any(not number(x) or x<=0 for x in window):
        return dict(ready=False,allow_open=False,close=None,ma=None)
    ma=sum(window)/120
    return dict(ready=True,allow_open=window[-1]>ma,close=window[-1],ma=ma)


def entry_size(equity, cash, native_price):
    if any(not number(x) for x in [equity,cash,native_price]) or equity<=0 or cash<0 or native_price<=0:
        raise ValueError('invalid_equity_cash_or_native_price')
    target=equity/20
    unit=native_price*(1+POLICY['slippage'])*(1+POLICY['commission'])
    shares=int(min(cash,target)/unit/100)*100
    return dict(shares=shares,target_amount=target,estimated_cost=shares*unit,
                reference_stop=native_price*(1+POLICY['slippage'])*.88,
                execution_ready=False,
                assumptions='Backtest proportional fees only; excludes broker minimums and actual fills.')


def holding_action(entry_price, native_price, quote_verified, elapsed_sessions, entered_today):
    if not number(entry_price) or entry_price<=0 or not quote_verified or not number(native_price) or native_price<=0:
        return dict(action='verify',reason='missing_verified_execution_prices')
    stop=entry_price*.88
    if entered_today:
        return dict(action='t1_blocked',stop_price=stop)
    if native_price<=stop:
        return dict(action='stop',stop_price=stop,execution_ready=False)
    if elapsed_sessions is None or not isinstance(elapsed_sessions,int) or elapsed_sessions<0:
        return dict(action='verify',reason='missing_entry_session_count',stop_price=stop)
    return dict(action='time_at_close' if elapsed_sessions>=21 else 'hold',stop_price=stop,execution_ready=False)
