import inspect

import graphene
import ta

from apis.schema.utils import user_authenticate


class IndicatorType(graphene.ObjectType):
    name = graphene.String()
    params = graphene.List(graphene.String)
    type = graphene.String()


class AllIndicator(graphene.ObjectType):
    all_indicator = graphene.List(IndicatorType)
    total_count = graphene.Int()


    def resolve_total_count(self, info):
        return len(inspect.getmembers(ta.momentum))
    def resolve_all_indicator(self, info):
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

        print("len of the indicators", len(final_indicators))

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



