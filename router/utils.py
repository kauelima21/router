import datetime
import decimal
import json


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()

        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)

        return super(DecimalEncoder, self).default(o)


def json_dumps(obj: dict, sort_keys=False):
    return json.dumps(obj, cls=DecimalEncoder, sort_keys=sort_keys)
