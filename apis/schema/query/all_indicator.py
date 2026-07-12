import inspect

import graphene
import ta

from apis.schema.utils import user_authenticate


class IndicatorType(graphene.ObjectType):
    name = graphene.String()
    params = graphene.List(graphene.String)
    type = graphene.String()


def _compute_all_indicators():
    """Introspect the `ta` library once at import time — the input is static,
    so recomputing per request was pure waste. The filtering below (including
    the mutate-while-iterating loop) is preserved verbatim so the output list
    is byte-identical to what the per-request version produced."""
    result_indicators = []
    indicators = []

    indicator_s = [attr for attr in dir(ta.momentum) if not attr.startswith('__') and not attr.startswith('pd') and not attr.startswith('_ema')]
    for indicator in indicator_s:
        ta_indicator = {
            "type": "momentum",
            "name": indicator
        }
        indicators.append(ta_indicator)

    indicator_s = [attr for attr in dir(ta.volume) if not attr.startswith('__') and not attr.startswith('pd') and not attr.startswith('_ema')]
    for indicator in indicator_s:
        ta_indicator = {
            "type": "volume",
            "name": indicator
        }
        indicators.append(ta_indicator)

    indicator_s = [attr for attr in dir(ta.trend) if not attr.startswith('__') and not attr.startswith('pd') and not attr.startswith('_ema')]
    for indicator in indicator_s:
        ta_indicator = {
            "type": "trend",
            "name": indicator
        }
        indicators.append(ta_indicator)

    indicator_s = [attr for attr in dir(ta.volatility) if not attr.startswith('__') and not attr.startswith('pd') and not attr.startswith('_ema')]
    for indicator in indicator_s:
        ta_indicator = {
            "type": "volatility",
            "name": indicator
        }
        indicators.append(ta_indicator)

    final_indicators = []

    for indicator in indicators:

        if indicator['name'] == 'np' or str(indicator['name']) == 'tp' or indicator['name'].find("Mixin") != -1:
            indicators.remove(indicator)
        elif not(str(indicator['name'])[0].islower()):
            indicators.remove(indicator)
        else:
            final_indicators.append(indicator)

    for indicator in final_indicators:
        indicator_function = getattr(getattr(ta, indicator['type']), indicator['name'])
        if callable(indicator_function):
            signature = inspect.signature(indicator_function)
            param_names = [param.name for param in signature.parameters.values()]
            to_remove = ["close", "open", "high", "low", "volume", "fillna"]
            filtered_params = [param for param in param_names if param not in to_remove]

            result_indicator = {
                "name": indicator['name'],
                "params": filtered_params,
                "type": indicator['type']
            }
            result_indicators.append(result_indicator)

    return result_indicators


ALL_INDICATORS = _compute_all_indicators()
TOTAL_COUNT = len(inspect.getmembers(ta.momentum))


class AllIndicator(graphene.ObjectType):
    all_indicator = graphene.List(IndicatorType)
    total_count = graphene.Int()


    def resolve_total_count(self, info):
        return TOTAL_COUNT
    def resolve_all_indicator(self, info):
        return ALL_INDICATORS
