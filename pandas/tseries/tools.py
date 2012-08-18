from datetime import datetime, timedelta
import re
import sys

import numpy as np

import pandas.lib as lib
import pandas.core.common as com

try:
    import dateutil
    from dateutil.parser import parse
    from dateutil.relativedelta import relativedelta

    # raise exception if dateutil 2.0 install on 2.x platform
    if (sys.version_info[0] == 2 and
        dateutil.__version__ == '2.0'):  # pragma: no cover
        raise Exception('dateutil 2.0 incompatible with Python 2.x, you must '
                        'install version 1.5 or 2.1+!')
except ImportError: # pragma: no cover
    print 'Please install python-dateutil via easy_install or some method!'
    raise # otherwise a 2nd import won't show the message


def _infer_tzinfo(start, end):
    def _infer(a, b):
        tz = a.tzinfo
        if b and b.tzinfo:
            assert(tz.zone == b.tzinfo.zone)
        return tz
    tz = None
    if start is not None:
        tz = _infer(start, end)
    elif end is not None:
        tz = _infer(end, start)
    return tz


def _maybe_get_tz(tz):
    if isinstance(tz, (str, unicode)):
        import pytz
        tz = pytz.timezone(tz)
    return tz


def to_datetime(arg, errors='ignore', dayfirst=False, utc=None, box=True):
    """
    Convert argument to datetime

    Parameters
    ----------
    arg : string, datetime, array of strings (with possible NAs)
    errors : {'ignore', 'raise'}, default 'ignore'
        Errors are ignored by default (values left untouched)
    utc : boolean, default None
        Return UTC DatetimeIndex if True (converting any tz-aware
        datetime.datetime objects as well)

    Returns
    -------
    ret : datetime if parsing succeeded
    """
    from pandas.core.series import Series
    from pandas.tseries.index import DatetimeIndex

    def _convert_f(arg):
        arg = com._ensure_object(arg)

        try:
            result = lib.array_to_datetime(arg, raise_=errors == 'raise',
                                           utc=utc, dayfirst=dayfirst)
            if com.is_datetime64_dtype(result) and box:
                result = DatetimeIndex(result, tz='utc' if utc else None)
            return result
        except ValueError, e:
            try:
                values, tz = lib.datetime_to_datetime64(arg)
                return DatetimeIndex(values, tz=tz)
            except (ValueError, TypeError):
                raise e

    if arg is None:
        return arg
    elif isinstance(arg, datetime):
        return arg
    elif isinstance(arg, Series):
        values = _convert_f(arg.values)
        return Series(values, index=arg.index, name=arg.name)
    elif isinstance(arg, (np.ndarray, list)):
        if isinstance(arg, list):
            arg = np.array(arg, dtype='O')
        result = _convert_f(arg)
        return result
    try:
        if not arg:
            return arg
        return parse(arg, dayfirst=dayfirst)
    except Exception:
        if errors == 'raise':
            raise
        return arg


class DateParseError(ValueError):
    pass



# patterns for quarters like '4Q2005', '05Q1'
qpat1full = re.compile(r'(\d)Q(\d\d\d\d)')
qpat2full = re.compile(r'(\d\d\d\d)Q(\d)')
qpat1 = re.compile(r'(\d)Q(\d\d)')
qpat2 = re.compile(r'(\d\d)Q(\d)')
ypat = re.compile(r'(\d\d\d\d)$')

def parse_time_string(arg, freq=None):
    """
    Try hard to parse datetime string, leveraging dateutil plus some extra
    goodies like quarter recognition.

    Parameters
    ----------
    arg : basestring
    freq : str or DateOffset, default None
        Helps with interpreting time string if supplied

    Returns
    -------
    datetime, datetime/dateutil.parser._result, str
    """
    from pandas.core.format import print_config
    from pandas.tseries.offsets import DateOffset
    from pandas.tseries.frequencies import (_get_rule_month, _month_numbers,
                                            _get_freq_str)

    if not isinstance(arg, basestring):
        return arg

    arg = arg.upper()

    default = datetime(1,1,1).replace(hour=0, minute=0,
                                      second=0, microsecond=0)

    # special handling for possibilities eg, 2Q2005, 2Q05, 2005Q1, 05Q1
    if len(arg) in [4, 6]:
        m = ypat.match(arg)
        if m:
            ret = default.replace(year=int(m.group(1)))
            return ret, ret, 'year'

        add_century = False
        if len(arg) == 4:
            add_century = True
            qpats = [(qpat1, 1), (qpat2, 0)]
        else:
            qpats = [(qpat1full, 1), (qpat2full, 0)]

        for pat, yfirst in qpats:
            qparse = pat.match(arg)
            if qparse is not None:
                if yfirst:
                    yi, qi = 1, 2
                else:
                    yi, qi = 2, 1
                q = int(qparse.group(yi))
                y_str = qparse.group(qi)
                y = int(y_str)
                if add_century:
                    y += 2000

                if freq is not None:
                    # hack attack, #1228
                    mnum = _month_numbers[_get_rule_month(freq)] + 1
                    month = (mnum + (q - 1) * 3) % 12 + 1
                    if month > mnum:
                        y -= 1
                else:
                    month = (q - 1) * 3 + 1

                ret = default.replace(year=y, month=month)
                return ret, ret, 'quarter'

        is_mo_str = freq is not None and freq == 'M'
        is_mo_off = getattr(freq, 'rule_code', None) == 'M'
        is_monthly = is_mo_str or is_mo_off
        if len(arg) == 6 and is_monthly:
            try:
                ret = _try_parse_monthly(arg)
                if ret is not None:
                    return ret, ret, 'month'
            except Exception:
                pass

    # montly f7u12
    mresult = _attempt_monthly(arg)
    if mresult:
        return mresult

    dayfirst = print_config.date_dayfirst
    yearfirst = print_config.date_yearfirst

    try:
        parsed = parse(arg, dayfirst=dayfirst, yearfirst=yearfirst)
    except Exception, e:
        raise DateParseError(e)

    if parsed is None:
        raise DateParseError("Could not parse %s" % arg)

    repl = {}
    reso = 'year'
    stopped = False
    for attr in ["year", "month", "day", "hour",
                 "minute", "second", "microsecond"]:
        can_be_zero = ['hour', 'minute', 'second', 'microsecond']
        value = getattr(parsed, attr)
        if value is not None and value != 0: # or attr in can_be_zero):
            repl[attr] = value
            if not stopped:
                reso = attr
        else:
            stopped = True
            break
    ret = default.replace(**repl)
    return ret, parsed, reso  # datetime, resolution

def _attempt_monthly(val):
    pats = ['%Y-%m', '%m-%Y', '%b %Y', '%b-%Y']
    for pat in pats:
        try:
            ret = datetime.strptime(val, pat)
            return ret, ret, 'month'
        except Exception:
            pass


def _try_parse_monthly(arg):
    base = 2000
    add_base = False
    default = datetime(1, 1, 1).replace(hour=0, minute=0, second=0,
                                        microsecond=0)

    if len(arg) == 4:
        add_base = True
        y = int(arg[:2])
        m = int(arg[2:4])
    elif len(arg) >= 6: # 201201
        y = int(arg[:4])
        m = int(arg[4:6])
    if add_base:
        y += base
    ret = default.replace(year=y, month=m)
    return ret

def normalize_date(dt):
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def format(dt):
    """Returns date in YYYYMMDD format."""
    return dt.strftime('%Y%m%d')

OLE_TIME_ZERO = datetime(1899, 12, 30, 0, 0, 0)

def ole2datetime(oledt):
    """function for converting excel date to normal date format"""
    val = float(oledt)

    # Excel has a bug where it thinks the date 2/29/1900 exists
    # we just reject any date before 3/1/1900.
    if val < 61:
        raise Exception("Value is outside of acceptable range: %s " % val)

    return OLE_TIME_ZERO + timedelta(days=val)

