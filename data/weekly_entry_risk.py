"""Price-only entry checks; passing never grants execution permission."""
import math


def check_entry_risk(preview, reference):
    result = dict(price_risk_passed=False, execution_ready=False, gap_atr=None,
                  stop_distance_atr=None, gap_limit_atr=0.5, stop_limit_atr=2.5, reasons=[])
    if (preview.get('mapping_status') != 'compatible'
            or reference.get('price_basis') != 'unadjusted'
            or reference.get('date') != preview.get('signal_at')
            or not preview.get('executable_from')
            or reference.get('date', '') >= preview['executable_from']):
        result['reasons'] = ['invalid_price_reference']
        return result
    values = [reference.get('close'), reference.get('atr14'),
              preview.get('native_open'), preview.get('native_stop')]
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in values):
        result['reasons'] = ['invalid_price_reference']
        return result
    close, atr, opening, stop = values
    if opening <= stop:
        result['reasons'] = ['entry_at_or_below_stop']
        return result
    result['gap_atr'] = abs(opening - close) / atr
    result['stop_distance_atr'] = (opening - stop) / atr
    if result['gap_atr'] > 0.5:
        result['reasons'].append('gap_exceeds_0.5_atr')
    if result['stop_distance_atr'] > 2.5:
        result['reasons'].append('stop_distance_exceeds_2.5_atr')
    result['price_risk_passed'] = not result['reasons']
    return result
