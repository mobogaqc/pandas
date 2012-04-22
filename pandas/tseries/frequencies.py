import re

from pandas.tseries.offsets import DateOffset
import pandas.tseries.offsets as offsets


def get_freq_code(freqstr):
    """

    Parameters
    ----------

    Returns
    -------
    """
    if isinstance(freqstr, DateOffset):
        freqstr = (get_offset_name(freqstr), freqstr.n)

    if isinstance(freqstr, tuple):
        if (isinstance(freqstr[0], (int, long)) and
            isinstance(freqstr[1], (int, long))):
            #e.g., freqstr = (2000, 1)
            return freqstr
        else:
            #e.g., freqstr = ('T', 5)
            try:
                code = _period_str_to_code(freqstr[0])
                stride = freqstr[1]
            except:
                code = _period_str_to_code(freqstr[1])
                stride = freqstr[0]
            return code, stride

    if isinstance(freqstr, (int, long)):
        return (freqstr, 1)

    base, stride = _base_and_stride(freqstr)
    code = _period_str_to_code(base)

    return code, stride


def _get_freq_str(base, mult):
    code = _reverse_period_code_map.get(base)
    if code is None:
        return _unknown_freq
    if mult == 1:
        return code
    return str(mult) + code


_unknown_freq = 'Unknown'


#-------------------------------------------------------------------------------
# Offset names ("time rules") and related functions


from pandas.tseries.offsets import (Day, BDay, Hour, Minute, Second, Milli,
                                    Micro, MonthEnd, MonthBegin, BMonthBegin,
                                    BMonthEnd, YearBegin, YearEnd, BYearBegin,
                                    BYearEnd, QuarterBegin, QuarterEnd,
                                    BQuarterBegin, BQuarterEnd)

_offset_map = {
    'D'     : Day(),
    'B'     : BDay(),
    'H'     : Hour(),
    'T'     : Minute(),
    'S'     : Second(),
    'L'     : Milli(),
    'U'     : Micro(),
    None    : None,

    # Monthly - Calendar
    'M'      : MonthEnd(),
    'MS'     : MonthBegin(),

    # Monthly - Business
    'BM'     : BMonthEnd(),
    'BMS'    : BMonthBegin(),

    # Annual - Calendar
    'A-JAN' : YearEnd(month=1),
    'A-FEB' : YearEnd(month=2),
    'A-MAR' : YearEnd(month=3),
    'A-APR' : YearEnd(month=4),
    'A-MAY' : YearEnd(month=5),
    'A-JUN' : YearEnd(month=6),
    'A-JUL' : YearEnd(month=7),
    'A-AUG' : YearEnd(month=8),
    'A-SEP' : YearEnd(month=9),
    'A-OCT' : YearEnd(month=10),
    'A-NOV' : YearEnd(month=11),
    'A-DEC' : YearEnd(month=12),
    'A'     : YearEnd(month=12),

    # Annual - Calendar (start)
    'AS-JAN' : YearBegin(month=1),
    'AS'     : YearBegin(month=1),
    'AS-FEB' : YearBegin(month=2),
    'AS-MAR' : YearBegin(month=3),
    'AS-APR' : YearBegin(month=4),
    'AS-MAY' : YearBegin(month=5),
    'AS-JUN' : YearBegin(month=6),
    'AS-JUL' : YearBegin(month=7),
    'AS-AUG' : YearBegin(month=8),
    'AS-SEP' : YearBegin(month=9),
    'AS-OCT' : YearBegin(month=10),
    'AS-NOV' : YearBegin(month=11),
    'AS-DEC' : YearBegin(month=12),

    # Annual - Business
    'BA-JAN' : BYearEnd(month=1),
    'BA-FEB' : BYearEnd(month=2),
    'BA-MAR' : BYearEnd(month=3),
    'BA-APR' : BYearEnd(month=4),
    'BA-MAY' : BYearEnd(month=5),
    'BA-JUN' : BYearEnd(month=6),
    'BA-JUL' : BYearEnd(month=7),
    'BA-AUG' : BYearEnd(month=8),
    'BA-SEP' : BYearEnd(month=9),
    'BA-OCT' : BYearEnd(month=10),
    'BA-NOV' : BYearEnd(month=11),
    'BA-DEC' : BYearEnd(month=12),
    'BA'     : BYearEnd(month=12),

    # Annual - Business (Start)
    'BAS-JAN' : BYearBegin(month=1),
    'BAS'     : BYearBegin(month=1),
    'BAS-FEB' : BYearBegin(month=2),
    'BAS-MAR' : BYearBegin(month=3),
    'BAS-APR' : BYearBegin(month=4),
    'BAS-MAY' : BYearBegin(month=5),
    'BAS-JUN' : BYearBegin(month=6),
    'BAS-JUL' : BYearBegin(month=7),
    'BAS-AUG' : BYearBegin(month=8),
    'BAS-SEP' : BYearBegin(month=9),
    'BAS-OCT' : BYearBegin(month=10),
    'BAS-NOV' : BYearBegin(month=11),
    'BAS-DEC' : BYearBegin(month=12),

    # Quarterly - Calendar
    # 'Q'     : QuarterEnd(startingMonth=3),
    'Q-JAN' : QuarterEnd(startingMonth=1),
    'Q-FEB' : QuarterEnd(startingMonth=2),
    'Q-MAR' : QuarterEnd(startingMonth=3),
    'Q-APR' : QuarterEnd(startingMonth=4),
    'Q-MAY' : QuarterEnd(startingMonth=5),
    'Q-JUN' : QuarterEnd(startingMonth=6),
    'Q-JUL' : QuarterEnd(startingMonth=7),
    'Q-AUG' : QuarterEnd(startingMonth=8),
    'Q-SEP' : QuarterEnd(startingMonth=9),
    'Q-OCT' : QuarterEnd(startingMonth=10),
    'Q-NOV' : QuarterEnd(startingMonth=11),
    'Q-DEC' : QuarterEnd(startingMonth=12),

    # Quarterly - Calendar (Start)
    # 'QS'     : QuarterBegin(startingMonth=1),
    'QS-JAN' : QuarterBegin(startingMonth=1),
    'QS-FEB' : QuarterBegin(startingMonth=2),
    'QS-MAR' : QuarterBegin(startingMonth=3),
    'QS-APR' : QuarterBegin(startingMonth=4),
    'QS-MAY' : QuarterBegin(startingMonth=5),
    'QS-JUN' : QuarterBegin(startingMonth=6),
    'QS-JUL' : QuarterBegin(startingMonth=7),
    'QS-AUG' : QuarterBegin(startingMonth=8),
    'QS-SEP' : QuarterBegin(startingMonth=9),
    'QS-OCT' : QuarterBegin(startingMonth=10),
    'QS-NOV' : QuarterBegin(startingMonth=11),
    'QS-DEC' : QuarterBegin(startingMonth=12),

    # Quarterly - Business
    'BQ-JAN' : BQuarterEnd(startingMonth=1),
    'BQ-FEB' : BQuarterEnd(startingMonth=2),
    'BQ-MAR' : BQuarterEnd(startingMonth=3),

    # 'BQ'     : BQuarterEnd(startingMonth=3),
    'BQ-APR' : BQuarterEnd(startingMonth=4),
    'BQ-MAY' : BQuarterEnd(startingMonth=5),
    'BQ-JUN' : BQuarterEnd(startingMonth=6),
    'BQ-JUL' : BQuarterEnd(startingMonth=7),
    'BQ-AUG' : BQuarterEnd(startingMonth=8),
    'BQ-SEP' : BQuarterEnd(startingMonth=9),
    'BQ-OCT' : BQuarterEnd(startingMonth=10),
    'BQ-NOV' : BQuarterEnd(startingMonth=11),
    'BQ-DEC' : BQuarterEnd(startingMonth=12),

    # Quarterly - Business (Start)
    'BQS-JAN' : BQuarterBegin(startingMonth=1),
    'BQS'     : BQuarterBegin(startingMonth=1),
    'BQS-FEB' : BQuarterBegin(startingMonth=2),
    'BQS-MAR' : BQuarterBegin(startingMonth=3),
    'BQS-APR' : BQuarterBegin(startingMonth=4),
    'BQS-MAY' : BQuarterBegin(startingMonth=5),
    'BQS-JUN' : BQuarterBegin(startingMonth=6),
    'BQS-JUL' : BQuarterBegin(startingMonth=7),
    'BQS-AUG' : BQuarterBegin(startingMonth=8),
    'BQS-SEP' : BQuarterBegin(startingMonth=9),
    'BQS-OCT' : BQuarterBegin(startingMonth=10),
    'BQS-NOV' : BQuarterBegin(startingMonth=11),
    'BQS-DEC' : BQuarterBegin(startingMonth=12),

    # Weekly
    'W-MON' : offsets.Week(weekday=0),
    'W-TUE' : offsets.Week(weekday=1),
    'W-WED' : offsets.Week(weekday=2),
    'W-THU' : offsets.Week(weekday=3),
    'W-FRI' : offsets.Week(weekday=4),
    'W-SAT' : offsets.Week(weekday=5),
    'W-SUN' : offsets.Week(weekday=6),
}

_rule_aliases = {
    # Legacy rules that will continue to map to their original values
    # essentially for the rest of time

    'WEEKDAY': 'B',
    'EOM': 'BM',

    'W@MON': 'W-MON',
    'W@TUE': 'W-TUE',
    'W@WED': 'W-WED',
    'W@THU': 'W-THU',
    'W@FRI': 'W-FRI',
    'W@SAT': 'W-SAT',
    'W@SUN': 'W-SUN',

    'Q@JAN': 'BQ-JAN',
    'Q@FEB': 'BQ-FEB',
    'Q@MAR': 'BQ-MAR',

    'A@JAN' : 'BA-JAN',
    'A@FEB' : 'BA-FEB',
    'A@MAR' : 'BA-MAR',
    'A@APR' : 'BA-APR',
    'A@MAY' : 'BA-MAY',
    'A@JUN' : 'BA-JUN',
    'A@JUL' : 'BA-JUL',
    'A@AUG' : 'BA-AUG',
    'A@SEP' : 'BA-SEP',
    'A@OCT' : 'BA-OCT',
    'A@NOV' : 'BA-NOV',
    'A@DEC' : 'BA-DEC',

    # lite aliases
    'Min': 'T',
    'min': 'T',
    'ms': 'L',
    'us': 'U'
}

for i, weekday in enumerate(['MON', 'TUE', 'WED', 'THU', 'FRI']):
    for iweek in xrange(4):
        name = 'WOM-%d%s' % (iweek + 1, weekday)
        _offset_map[name] = offsets.WeekOfMonth(week=iweek, weekday=i)
        _rule_aliases[name.replace('-', '@')] = name

_legacy_reverse_map = dict((v, k) for k, v in _rule_aliases.iteritems())

# for helping out with pretty-printing and name-lookups

_offset_names = {}
for name, offset in _offset_map.iteritems():
    if offset is None:
        continue
    offset.name = name
    _offset_names[offset] = name


def inferTimeRule(index):
    if len(index) < 3:
        raise Exception('Need at least three dates to infer time rule!')

    first, second, third = index[:3]
    items = _offset_map.iteritems()

    for rule, offset in items:
        if offset is None:
            continue
        if (first + offset) == second and (second + offset) == third:
            return rule

    raise Exception('Could not infer time rule from data!')


def to_offset(freqstr):
    """
    Return DateOffset object from string representation

    Example
    -------
    to_offset('5Min') -> Minute(5)
    """
    if freqstr is None:
        return None

    if isinstance(freqstr, DateOffset):
        return freqstr

    if isinstance(freqstr, tuple):
        name = freqstr[0]
        stride = freqstr[1]
        if isinstance(stride, basestring):
            name, stride = stride, name
        name, _ = _base_and_stride(name)
    else:
        name, stride = _base_and_stride(freqstr)

    offset = get_offset(name)

    return offset * stride


opattern = re.compile(r'(\d*)\s*(\S+)')

def _base_and_stride(freqstr):
    """
    Return base freq and stride info from string representation

    Example
    -------
    _freq_and_stride('5Min') -> 'Min', 5
    """
    groups = opattern.match(freqstr)

    if groups.lastindex != 2:
        raise ValueError("Could not evaluate %s" % freqstr)

    stride = groups.group(1)

    if len(stride):
        stride = int(stride)
    else:
        stride = 1

    base = groups.group(2)

    return (base, stride)


_dont_uppercase = ['MS', 'ms']


def get_offset(name):
    """
    Return DateOffset object associated with rule name

    Example
    -------
    get_offset('EOM') --> BMonthEnd(1)
    """
    if name not in _dont_uppercase:
        name = name.upper()

        if name in _rule_aliases:
            name = _rule_aliases[name]
        elif name.lower() in _rule_aliases:
            name = _rule_aliases[name.lower()]
    else:
        if name in _rule_aliases:
            name = _rule_aliases[name]

    offset = _offset_map.get(name)

    if offset is not None:
        return offset
    else:
        raise Exception('Bad rule name requested: %s!' % name)


getOffset = get_offset


def hasOffsetName(offset):
    return offset in _offset_names

def get_offset_name(offset):
    """
    Return rule name associated with a DateOffset object

    Example
    -------
    get_offset_name(BMonthEnd(1)) --> 'EOM'
    """
    name = _offset_names.get(offset)

    if name is not None:
        return name
    else:
        raise Exception('Bad rule given: %s!' % offset)

def get_legacy_offset_name(offset):
    """
    Return the pre pandas 0.8.0 name for the date offset
    """
    name = _offset_names.get(offset)
    return _legacy_reverse_map.get(name, name)

get_offset_name = get_offset_name

def get_standard_freq(freq):
    """
    Return the standardized frequency string
    """
    if freq is None:
        return None

    if isinstance(freq, DateOffset):
        return get_offset_name(freq)

    code, stride = get_freq_code(freq)
    return _get_freq_str(code, stride)

#----------------------------------------------------------------------
# Period codes

# period frequency constants corresponding to scikits timeseries
# originals
_period_code_map = {
    # Annual freqs with various fiscal year ends.
    # eg, 2005 for A-FEB runs Mar 1, 2004 to Feb 28, 2005
    "A"     : 1000,  # Annual
    "A-DEC" : 1000,  # Annual - December year end
    "A-JAN" : 1001,  # Annual - January year end
    "A-FEB" : 1002,  # Annual - February year end
    "A-MAR" : 1003,  # Annual - March year end
    "A-APR" : 1004,  # Annual - April year end
    "A-MAY" : 1005,  # Annual - May year end
    "A-JUN" : 1006,  # Annual - June year end
    "A-JUL" : 1007,  # Annual - July year end
    "A-AUG" : 1008,  # Annual - August year end
    "A-SEP" : 1009,  # Annual - September year end
    "A-OCT" : 1010,  # Annual - October year end
    "A-NOV" : 1011,  # Annual - November year end

    # Quarterly frequencies with various fiscal year ends.
    # eg, Q42005 for Q-OCT runs Aug 1, 2005 to Oct 31, 2005
    "Q"     : 2000,    # Quarterly - December year end (default quarterly)
    "Q-DEC" : 2000 ,    # Quarterly - December year end
    "Q-JAN" : 2001,    # Quarterly - January year end
    "Q-FEB" : 2002,    # Quarterly - February year end
    "Q-MAR" : 2003,    # Quarterly - March year end
    "Q-APR" : 2004,    # Quarterly - April year end
    "Q-MAY" : 2005,    # Quarterly - May year end
    "Q-JUN" : 2006,    # Quarterly - June year end
    "Q-JUL" : 2007,    # Quarterly - July year end
    "Q-AUG" : 2008,    # Quarterly - August year end
    "Q-SEP" : 2009,    # Quarterly - September year end
    "Q-OCT" : 2010,    # Quarterly - October year end
    "Q-NOV" : 2011,    # Quarterly - November year end

    "M"     : 3000,   # Monthly

    "W"     : 4000,    # Weekly
    "W-SUN" : 4000,    # Weekly - Sunday end of week
    "W-MON" : 4001,    # Weekly - Monday end of week
    "W-TUE" : 4002,    # Weekly - Tuesday end of week
    "W-WED" : 4003,    # Weekly - Wednesday end of week
    "W-THU" : 4004,    # Weekly - Thursday end of week
    "W-FRI" : 4005,    # Weekly - Friday end of week
    "W-SAT" : 4006,    # Weekly - Saturday end of week

    "B"      : 5000,   # Business days
    "D"      : 6000,   # Daily
    "H"      : 7000,   # Hourly
    "T"      : 8000,   # Minutely
    "S"      : 9000,   # Secondly
    None     : -10000  # Undefined
}

def _period_alias_dictionary():
    """
    Build freq alias dictionary to support freqs from original c_dates.c file
    of the scikits.timeseries library.
    """
    alias_dict = {}

    M_aliases = ["M", "MTH", "MONTH", "MONTHLY"]
    B_aliases = ["B", "BUS", "BUSINESS", "BUSINESSLY", 'WEEKDAY']
    D_aliases = ["D", "DAY", "DLY", "DAILY"]
    H_aliases = ["H", "HR", "HOUR", "HRLY", "HOURLY"]
    T_aliases = ["T", "MIN", "MINUTE", "MINUTELY"]
    S_aliases = ["S", "SEC", "SECOND", "SECONDLY"]
    U_aliases = ["U", "UND", "UNDEF", "UNDEFINED"]

    for k in M_aliases:
        alias_dict[k] = 'M'

    for k in B_aliases:
        alias_dict[k] = 'B'

    for k in D_aliases:
        alias_dict[k] = 'D'

    for k in H_aliases:
        alias_dict[k] = 'H'

    for k in T_aliases:
        alias_dict[k] = 'Min'

    for k in S_aliases:
        alias_dict[k] = 'S'

    for k in U_aliases:
        alias_dict[k] = None

    A_prefixes = ["A", "Y", "ANN", "ANNUAL", "ANNUALLY", "YR", "YEAR",
                  "YEARLY"]

    Q_prefixes = ["Q", "QTR", "QUARTER", "QUARTERLY", "Q-E",
                  "QTR-E", "QUARTER-E", "QUARTERLY-E"]

    month_names = [
        [ "DEC", "DECEMBER" ],
        [ "JAN", "JANUARY" ],
        [ "FEB", "FEBRUARY" ],
        [ "MAR", "MARCH" ],
        [ "APR", "APRIL" ],
        [ "MAY", "MAY" ],
        [ "JUN", "JUNE" ],
        [ "JUL", "JULY" ],
        [ "AUG", "AUGUST" ],
        [ "SEP", "SEPTEMBER" ],
        [ "OCT", "OCTOBER" ],
        [ "NOV", "NOVEMBER" ] ]

    seps = ["@", "-"]

    for k in A_prefixes:
        alias_dict[k] = 'A'
        for m_tup in month_names:
            for sep in seps:
                m1, m2 = m_tup
                alias_dict[k + sep + m1] = 'A-' + m1
                alias_dict[k + sep + m2] = 'A-' + m1

    for k in Q_prefixes:
        alias_dict[k] = 'Q'
        for m_tup in month_names:
            for sep in seps:
                m1, m2 = m_tup
                alias_dict[k + sep + m1] = 'Q-' + m1
                alias_dict[k + sep + m2] = 'Q-' + m1

    W_prefixes = ["W", "WK", "WEEK", "WEEKLY"]

    day_names = [
        [ "SUN", "SUNDAY" ],
        [ "MON", "MONDAY" ],
        [ "TUE", "TUESDAY" ],
        [ "WED", "WEDNESDAY" ],
        [ "THU", "THURSDAY" ],
        [ "FRI", "FRIDAY" ],
        [ "SAT", "SATURDAY" ] ]

    for k in W_prefixes:
        alias_dict[k] = 'W'
        for d_tup in day_names:
            for sep in ["@", "-"]:
                d1, d2 = d_tup
                alias_dict[k + sep + d1] = 'W-' + d1
                alias_dict[k + sep + d2] = 'W-' + d1

    return alias_dict

_reverse_period_code_map = {}
for k, v in _period_code_map.iteritems():
    _reverse_period_code_map[v] = k

_reso_period_map = {
    "year"    : "A",
    "quarter" : "Q",
    "month"   : "M",
    "day"     : "D",
    "hour"    : "H",
    "minute"  : "T",
    "second"  : "S",
}

def _infer_period_group(freqstr):
    return _period_group(_reso_period_map[freqstr])

def _period_group(freqstr):
    base, mult = get_freq_code(freqstr)
    return base // 1000 * 1000

_period_alias_dict = _period_alias_dictionary()

def _period_str_to_code(freqstr):
    # hack
    freqstr = _rule_aliases.get(freqstr, freqstr)
    freqstr = _rule_aliases.get(freqstr.lower(), freqstr)

    try:
        freqstr = freqstr.upper()
        return _period_code_map[freqstr]
    except:
        alias = _period_alias_dict[freqstr]
        try:
            return _period_code_map[alias]
        except:
            raise "Could not interpret frequency %s" % freqstr
