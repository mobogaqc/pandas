# cython: profile=False
cimport numpy as np
import numpy as np

from numpy cimport int32_t, int64_t, import_array, ndarray
from cpython cimport *

# this is our datetime.pxd
from datetime cimport *
from util cimport is_integer_object, is_datetime64_object

from datetime import timedelta
from dateutil.parser import parse as parse_date
cimport util

from khash cimport *
import cython

# initialize numpy
import_array()
#import_ufunc()

# import datetime C API
PyDateTime_IMPORT

# in numpy 1.7, will prob need the following:
# numpy_pydatetime_import

cdef bint numpy_16 = np.__version__ < '1.7'

ctypedef enum time_res:
    r_min = 0
    r_microsecond
    r_second
    r_minute
    r_hour
    r_day
    r_month
    r_year
    r_max = 98
    r_invalid = 99

try:
    basestring
except NameError: # py3
    basestring = str

def ints_to_pydatetime(ndarray[int64_t] arr, tz=None):
    cdef:
        Py_ssize_t i, n = len(arr)
        pandas_datetimestruct dts
        ndarray[object] result = np.empty(n, dtype=object)

    if tz is not None:
        if tz is pytz.utc:
            for i in range(n):
                pandas_datetime_to_datetimestruct(arr[i], PANDAS_FR_ns, &dts)
                result[i] = datetime(dts.year, dts.month, dts.day, dts.hour,
                                     dts.min, dts.sec, dts.us, tz)
        else:
            trans = _get_transitions(tz)
            deltas = _get_deltas(tz)
            for i in range(n):
                # Adjust datetime64 timestamp, recompute datetimestruct
                pos = trans.searchsorted(arr[i]) - 1
                inf = tz._transition_info[pos]

                pandas_datetime_to_datetimestruct(arr[i] + deltas[pos],
                                                  PANDAS_FR_ns, &dts)
                result[i] = datetime(dts.year, dts.month, dts.day, dts.hour,
                                     dts.min, dts.sec, dts.us,
                                     tz._tzinfos[inf])
    else:
        for i in range(n):
            pandas_datetime_to_datetimestruct(arr[i], PANDAS_FR_ns, &dts)
            result[i] = datetime(dts.year, dts.month, dts.day, dts.hour,
                                 dts.min, dts.sec, dts.us)

    return result


# Python front end to C extension type _Timestamp
# This serves as the box for datetime64
class Timestamp(_Timestamp):

    def __new__(cls, object ts_input, object offset=None, tz=None):
        cdef _TSObject ts
        cdef _Timestamp ts_base

        if isinstance(ts_input, float):
            # to do, do we want to support this, ie with fractional seconds?
            raise TypeError("Cannot convert a float to datetime")

        if isinstance(ts_input, basestring):
            try:
                ts_input = parse_date(ts_input)
            except Exception:
                pass

        ts = convert_to_tsobject(ts_input, tz)

        if ts.value == NPY_NAT:
            return NaT

        # make datetime happy
        ts_base = _Timestamp.__new__(cls, ts.dts.year, ts.dts.month,
                                     ts.dts.day, ts.dts.hour, ts.dts.min,
                                     ts.dts.sec, ts.dts.us, ts.tzinfo)

        # fill out rest of data
        ts_base.value = ts.value
        ts_base.offset = offset
        ts_base.nanosecond = ts.dts.ps / 1000

        return ts_base

    @property
    def tz(self):
        """
        Alias for tzinfo
        """
        return self.tzinfo

    @property
    def freq(self):
        return self.offset

    def __setstate__(self, state):
        self.value = state[0]
        self.offset = state[1]
        self.tzinfo = state[2]

    def __reduce__(self):
        object_state = self.value, self.offset, self.tzinfo
        return (Timestamp, object_state)

    def to_period(self, freq=None):
        """
        Return an period of which this timestamp is an observation.
        """
        from pandas.tseries.period import Period

        if freq is None:
            freq = self.freq

        return Period(self, freq=freq)

    @property
    def dayofweek(self):
        return self.weekday()

    @property
    def dayofyear(self):
        return self.day

    @property
    def week(self):
        return self._get_field('woy')

    weekofyear = week

    @property
    def quarter(self):
        return self._get_field('q')

    @property
    def freqstr(self):
        return getattr(self.offset, 'freqstr', self.offset)

    @property
    def asm8(self):
        return np.int64(self.value).view('M8[ns]')

    def tz_convert(self, tz):
        if isinstance(tz, basestring):
            import pytz
            tz = pytz.timezone(tz)

        conv = tz.normalize(self)
        return Timestamp(conv)

    def replace(self, **kwds):
        return Timestamp(datetime.replace(self, **kwds),
                         offset=self.offset)

    def to_pydatetime(self, warn=True):
        """
        If warn=True, issue warning if nanoseconds is nonzero
        """
        cdef:
            pandas_datetimestruct dts
            _TSObject ts

        if self.nanosecond != 0 and warn:
            print 'Warning: discarding nonzero nanoseconds'
        ts = convert_to_tsobject(self, self.tzinfo)

        return datetime(ts.dts.year, ts.dts.month, ts.dts.day,
                        ts.dts.hour, ts.dts.min, ts.dts.sec,
                        ts.dts.us, ts.tzinfo)


class NaTType(_NaT):

    def __new__(cls):
        cdef _NaT base

        base = _NaT.__new__(cls, 1, 1, 1)
        mangle_nat(base)
        base.value = NPY_NAT

        return base

    def __repr__(self):
        return 'NaT'

    def weekday(self):
        return -1

    def toordinal(self):
        return -1

fields = ['year', 'quarter', 'month', 'day', 'hour',
          'minute', 'second', 'microsecond', 'nanosecond',
          'week', 'dayofyear']
for field in fields:
    prop = property(fget=lambda self: -1)
    setattr(NaTType, field, prop)


NaT = NaTType()

iNaT = util.get_nat()


cdef inline bint is_timestamp(object o):
    return isinstance(o, Timestamp)

def is_timestamp_array(ndarray[object] values):
    cdef int i, n = len(values)
    if n == 0:
        return False
    for i in range(n):
        if not is_timestamp(values[i]):
            return False
    return True

#----------------------------------------------------------------------
# Frequency inference

def unique_deltas(ndarray[int64_t] arr):
    cdef:
        Py_ssize_t i, n = len(arr)
        int64_t val
        khiter_t k
        kh_int64_t *table
        int ret = 0
        list uniques = []

    table = kh_init_int64()
    kh_resize_int64(table, 10)
    for i in range(n - 1):
        val = arr[i + 1] - arr[i]
        k = kh_get_int64(table, val)
        if k == table.n_buckets:
            kh_put_int64(table, val, &ret)
            uniques.append(val)
    kh_destroy_int64(table)

    result = np.array(uniques, dtype=np.int64)
    result.sort()
    return result


cdef inline bint _is_multiple(int64_t us, int64_t mult):
    return us % mult == 0


def apply_offset(ndarray[object] values, object offset):
    cdef:
        Py_ssize_t i, n = len(values)
        ndarray[int64_t] new_values
        object boxed

    result = np.empty(n, dtype='M8[ns]')
    new_values = result.view('i8')
    pass


# This is PITA. Because we inherit from datetime, which has very specific
# construction requirements, we need to do object instantiation in python
# (see Timestamp class above). This will serve as a C extension type that
# shadows the python class, where we do any heavy lifting.
cdef class _Timestamp(datetime):
    cdef readonly:
        int64_t value, nanosecond
        object offset       # frequency reference

    def __hash__(self):
        if self.nanosecond:
            return hash(self.value)
        else:
            return datetime.__hash__(self)

    def __richcmp__(_Timestamp self, object other, int op):
        cdef _Timestamp ots

        if isinstance(other, _Timestamp):
            ots = other
        elif isinstance(other, datetime):
            ots = Timestamp(other)
        else:
            if op == 2:
                return False
            elif op == 3:
                return True
            else:
                raise TypeError('Cannot compare Timestamp with %s' % str(other))

        if op == 2: # ==
            return self.value == ots.value
        elif op == 3: # !=
            return self.value != ots.value
        elif op == 0: # <
            return self.value < ots.value
        elif op == 1: # <=
            return self.value <= ots.value
        elif op == 4: # >
            return self.value > ots.value
        elif op == 5: # >=
            return self.value >= ots.value

    def __add__(self, other):
        if is_integer_object(other):
            if self.offset is None:
                msg = ("Cannot add integral value to Timestamp "
                       "without offset.")
                raise ValueError(msg)
            else:
                return Timestamp((self.offset.__mul__(other)).apply(self))
        else:
            if isinstance(other, timedelta) or hasattr(other, 'delta'):
                nanos = _delta_to_nanoseconds(other)
                return Timestamp(self.value + nanos)
            else:
                result = datetime.__add__(self, other)
                if isinstance(result, datetime):
                    result = Timestamp(result)
                    result.nanosecond = self.nanosecond
                return result

    def __sub__(self, other):
        if is_integer_object(other):
            return self.__add__(-other)
        else:
            return datetime.__sub__(self, other)

    cpdef _get_field(self, field):
        out = fast_field_accessor(np.array([self.value], dtype=np.int64),
                                  field)
        return out[0]


cdef class _NaT(_Timestamp):

    def __richcmp__(_NaT self, object other, int op):
        # if not isinstance(other, (_NaT, _Timestamp)):
        #     raise TypeError('Cannot compare %s with NaT' % type(other))

        if op == 2: # ==
            return False
        elif op == 3: # !=
            return True
        elif op == 0: # <
            return False
        elif op == 1: # <=
            return False
        elif op == 4: # >
            return False
        elif op == 5: # >=
            return False




def _delta_to_nanoseconds(delta):
    try:
        delta = delta.delta
    except:
        pass
    return (delta.days * 24 * 60 * 60 * 1000000
            + delta.seconds * 1000000
            + delta.microseconds) * 1000


# lightweight C object to hold datetime & int64 pair
cdef class _TSObject:
    cdef:
        pandas_datetimestruct dts      # pandas_datetimestruct
        int64_t value               # numpy dt64
        object tzinfo

    property value:
        def __get__(self):
            return self.value

# helper to extract datetime and int64 from several different possibilities
cpdef convert_to_tsobject(object ts, object tz=None):
    """
    Extract datetime and int64 from any of:
        - np.int64
        - np.datetime64
        - python int or long object
        - iso8601 string object
        - python datetime object
        - another timestamp object
    """
    cdef:
        _TSObject obj
        bint utc_convert = 1

    obj = _TSObject()

    if is_datetime64_object(ts):
        obj.value = _get_datetime64_nanos(ts)
        pandas_datetime_to_datetimestruct(obj.value, PANDAS_FR_ns, &obj.dts)
    elif is_integer_object(ts):
        obj.value = ts
        pandas_datetime_to_datetimestruct(ts, PANDAS_FR_ns, &obj.dts)
    elif util.is_string_object(ts):
        _string_to_dts(ts, &obj.dts)
        obj.value = pandas_datetimestruct_to_datetime(PANDAS_FR_ns, &obj.dts)
    elif PyDateTime_Check(ts):
        obj.value = _pydatetime_to_dts(ts, &obj.dts)
        obj.tzinfo = ts.tzinfo
        if obj.tzinfo is not None:
            obj.value -= _delta_to_nanoseconds(obj.tzinfo._utcoffset)
    elif PyDate_Check(ts):
        obj.value  = _date_to_datetime64(ts, &obj.dts)
    else:
        raise ValueError("Could not construct Timestamp from argument %s" %
                         type(ts))

    if tz is not None:
        if tz is pytz.utc:
            obj.tzinfo = tz
        else:
            # Adjust datetime64 timestamp, recompute datetimestruct
            trans = _get_transitions(tz)
            deltas = _get_deltas(tz)
            pos = trans.searchsorted(obj.value) - 1
            inf = tz._transition_info[pos]

            pandas_datetime_to_datetimestruct(obj.value + deltas[pos],
                                              PANDAS_FR_ns, &obj.dts)
            obj.tzinfo = tz._tzinfos[inf]

    return obj

# elif isinstance(ts, _Timestamp):
#     tmp = ts
#     obj.value = (<_Timestamp> ts).value
#     obj.dtval =
# elif isinstance(ts, object):
#     # If all else fails
#     obj.value = _dtlike_to_datetime64(ts, &obj.dts)
#     obj.dtval = _dts_to_pydatetime(&obj.dts)

cdef inline object _datetime64_to_datetime(int64_t val):
    cdef pandas_datetimestruct dts
    pandas_datetime_to_datetimestruct(val, PANDAS_FR_ns, &dts)
    return _dts_to_pydatetime(&dts)

cdef inline object _dts_to_pydatetime(pandas_datetimestruct *dts):
    return <object> PyDateTime_FromDateAndTime(dts.year, dts.month,
                                               dts.day, dts.hour,
                                               dts.min, dts.sec, dts.us)

cdef inline int64_t _pydatetime_to_dts(object val, pandas_datetimestruct *dts):
    dts.year = PyDateTime_GET_YEAR(val)
    dts.month = PyDateTime_GET_MONTH(val)
    dts.day = PyDateTime_GET_DAY(val)
    dts.hour = PyDateTime_DATE_GET_HOUR(val)
    dts.min = PyDateTime_DATE_GET_MINUTE(val)
    dts.sec = PyDateTime_DATE_GET_SECOND(val)
    dts.us = PyDateTime_DATE_GET_MICROSECOND(val)
    dts.ps = dts.as = 0
    return pandas_datetimestruct_to_datetime(PANDAS_FR_ns, dts)

cdef inline int64_t _dtlike_to_datetime64(object val,
                                          pandas_datetimestruct *dts):
    dts.year = val.year
    dts.month = val.month
    dts.day = val.day
    dts.hour = val.hour
    dts.min = val.minute
    dts.sec = val.second
    dts.us = val.microsecond
    dts.ps = dts.as = 0
    return pandas_datetimestruct_to_datetime(PANDAS_FR_ns, dts)

cdef inline int64_t _date_to_datetime64(object val,
                                        pandas_datetimestruct *dts):
    dts.year = PyDateTime_GET_YEAR(val)
    dts.month = PyDateTime_GET_MONTH(val)
    dts.day = PyDateTime_GET_DAY(val)
    dts.hour = dts.min = dts.sec = dts.us = 0
    dts.ps = dts.as = 0
    return pandas_datetimestruct_to_datetime(PANDAS_FR_ns, dts)


cdef inline int _string_to_dts(object val, pandas_datetimestruct* dts) except -1:
    cdef:
        npy_bool islocal, special
        PANDAS_DATETIMEUNIT out_bestunit

    if PyUnicode_Check(val):
        val = PyUnicode_AsASCIIString(val);
    parse_iso_8601_datetime(val, len(val), PANDAS_FR_ns, NPY_UNSAFE_CASTING,
                            dts, &islocal, &out_bestunit, &special)
    return 0

cdef conversion_factor(time_res res1, time_res res2):
    cdef:
        time_res min_res, max_res
        int64_t factor

    min_res = min(res1, res2)
    max_res = max(res1, res2)
    factor = 1

    if min_res == max_res:
        return factor

    while min_res < max_res:
        if min_res < r_microsecond:
            raise "Cannot convert from less than us"
        elif min_res == r_microsecond:
            factor *= 1000000
            min_res = r_second
        elif min_res == r_second:
            factor *= 60
            min_res = r_minute
        elif min_res == r_minute:
            factor *= 60
            min_res = r_hour
        elif min_res == r_hour:
            factor *= 24
            min_res = r_day
        else:
            raise "Cannot convert to month or year"

    return factor

# Logic to generate ranges
# -----------------------------------------------------------------------------

cdef inline int64_t weekend_adjustment(int64_t dow, int bkwd):
    if dow > 4:                         # sat or sun?
        if bkwd:                        # roll back 1 or 2 days
            return (4 - dow)
        else:                           # roll forward 2 or 1 days
            return (7 - dow)
    return 0

cdef int64_t us_in_day = conversion_factor(r_microsecond, r_day)

cdef class _Offset:
    """
    Base class to generate timestamps. Set the anchor, and then move offsets
    with next & prev. Retrieve timestamp with ts attribute.
    """
    cdef:
        int64_t t, dow, biz, dayoffset
        object start
        _TSObject ts

    def __cinit__(self):
        self.t=0
        self.dow=0
        self.biz=0
        self.dayoffset=0

    cpdef anchor(self, object start=None):
        if start is not None:
            self.start = start
        self.ts = convert_to_tsobject(self.start)
        self._setup()

    cdef _setup(self):
        pass

    cpdef next(self):
        pass

    cpdef prev(self):
        pass

    cdef int64_t _ts(self):
        """
        Access the current timestamp value, with a possible weekday
        adjustment.
        """
        cdef int64_t adj

        if self.biz != 0:
            adj = weekend_adjustment(self.dow, self.biz < 0)
            return self.t + us_in_day * adj
        else:
            return self.t

    cdef int64_t _get_anchor(self):
        """
        Retrieve an anchor relating to current offset we're on.
        """
        return self.t - self.dayoffset * us_in_day

    property ts:
        def __get__(self):
            return self._ts()

cdef class YearOffset(_Offset):
    """
    Generate annual timestamps from provided start time; apply dayoffset to
    each timestamp. If biz > 0, we choose the next business day at each time;
    previous if < 0.

    Parameters
    ----------
    dayoffset : int
    biz : int
    """
    cdef:
        int64_t y, ly

    def __init__(self, int64_t dayoffset=0, int64_t biz=0, object anchor=None):
        self.dayoffset = dayoffset
        self.biz = biz

        if anchor is not None:
            self.anchor(anchor)

    cdef _setup(self):
        cdef _TSObject ts = self.ts

        self.t = ts.value + self.dayoffset * us_in_day
        self.y = ts.dts.year

        self.ly = (ts.dts.month > 2 or
                   ts.dts.month == 2 and ts.dts.day == 29)

        if self.biz != 0:
            self.dow = (ts_dayofweek(ts) + self.dayoffset) % 7

    cpdef next(self):
        cdef int64_t days

        days = 365 + is_leapyear(self.y + self.ly)

        self.t += days * us_in_day
        self.y += 1

        if self.biz != 0:
            self.dow = (self.dow + days) % 7

    cpdef prev(self):
        cdef int64_t days

        days = 365 + is_leapyear(self.y - (1-self.ly))

        self.t -= days * us_in_day
        self.y -= 1

        if self.biz != 0:
            self.dow = (self.dow - days) % 7

cdef class MonthOffset(_Offset):
    """
    Generate monthly timestamps from provided start time, and apply dayoffset
    to each timestamp.  Stride to construct strided timestamps (eg quarterly).
    If biz > 0, we choose the next business day at each time; previous if < 0.

    Parameters
    ----------
    dayoffset : int
    stride : int, > 0
    biz : int
    """
    cdef:
        Py_ssize_t stride, ly, m
        int64_t y

    def __init__(self, int64_t dayoffset=0, Py_ssize_t stride=1,
                 int64_t biz=0, object anchor=None):
        self.dayoffset = dayoffset
        self.stride = stride
        self.biz = biz

        if stride <= 0:
            raise ValueError("Stride must be positive")

        if anchor is not None:
            self.anchor(anchor)

    cdef _setup(self):
        cdef _TSObject ts = self.ts

        self.t = ts.value + (self.dayoffset * us_in_day)

        # for day counting
        self.m  = ts.dts.month - 1
        self.y  = ts.dts.year
        self.ly = is_leapyear(self.y)

        if self.biz != 0:
            self.dow = (ts_dayofweek(ts) + self.dayoffset) % 7

    cpdef next(self):
        cdef:
            int64_t tmp, days
            Py_ssize_t j

        days = 0
        for j in range(0, self.stride):
            if self.m >= 12:
                self.m -= 12
                self.y += 1
                self.ly = is_leapyear(self.y)
            days += _days_per_month_table[self.ly][self.m]
            self.m += 1

        self.t += days * us_in_day

        if self.biz != 0:
            self.dow = (self.dow + days) % 7

    cpdef prev(self):
        cdef:
            int64_t tmp, days
            Py_ssize_t j

        days = 0
        for j in range(0, self.stride):
            self.m -= 1
            if self.m < 0:
                self.m += 12
                self.y -= 1
                self.ly = is_leapyear(self.y)
            days += _days_per_month_table[self.ly][self.m]

        self.t -= days * us_in_day

        if self.biz != 0:
            self.dow = (self.dow - days) % 7

cdef class DayOfMonthOffset(_Offset):
    """
    Generate relative monthly timestamps from month & year of provided start
    time. For example, fridays of the third week of each month (week=3, day=4);
    or, thursdays of the last week of each month (week=-1, day=3).

    Parameters
    ----------
    week : int
    day : int, 0 to 6
    """
    cdef:
        Py_ssize_t ly, m
        int64_t y, day, week

    def __init__(self, int64_t week=0, int64_t day=0, object anchor=None):
        self.week = week
        self.day = day

        if self.day < 0 or self.day > 6:
            raise ValueError("Day offset must be 0 to 6")

        if anchor is not None:
            self.anchor(anchor)

    cdef _setup(self):
        cdef _TSObject ts = self.ts

        # rewind to beginning of month
        self.t = ts.value - (ts.dts.day - 1) * us_in_day
        self.dow = dayofweek(ts.dts.year, ts.dts.month, 1)

        # for day counting
        self.m = ts.dts.month - 1
        self.y = ts.dts.year
        self.ly = is_leapyear(self.y)

    cpdef next(self):
        cdef:
            int64_t tmp, days

        days = _days_per_month_table[self.ly][self.m]
        self.t += days * us_in_day
        self.dow = (self.dow + days) % 7

        self.m += 1
        if self.m >= 12:
            self.m -= 12
            self.y += 1
            self.ly = is_leapyear(self.y)

    cpdef prev(self):
        cdef:
            int64_t tmp, days

        days = _days_per_month_table[self.ly][(self.m - 1) % 12]
        self.t -= days * us_in_day
        self.dow = (self.dow - days) % 7

        self.m -= 1
        if self.m < 0:
            self.m += 12
            self.y -= 1
            self.ly = is_leapyear(self.y)

    cdef int64_t _ts(self):
        """
        Overwrite default adjustment
        """
        cdef int64_t adj = (self.week * 7) + (self.day - self.dow) % 7
        return self.t + us_in_day * adj

cdef class DayOffset(_Offset):
    """
    Generate daily timestamps beginning with first valid time >= start time. If
    biz != 0, we skip weekends. Stride, to construct weekly timestamps.

    Parameters
    ----------
    stride : int, > 0
    biz : boolean
    """
    cdef:
        Py_ssize_t stride

    def __init__(self, int64_t stride=1, int64_t biz=0, object anchor=None):
        self.stride = stride
        self.biz = biz

        if self.stride <= 0:
            raise ValueError("Stride must be positive")

        if anchor is not None:
            self.anchor(anchor)

    cdef _setup(self):
        cdef _TSObject ts = self.ts
        self.t = ts.value
        if self.biz != 0:
            self.dow = ts_dayofweek(ts)

    cpdef next(self):
        self.t += (self.stride * us_in_day)
        if self.biz != 0:
            self.dow = (self.dow + self.stride) % 7
            if self.dow >= 5:
                self.t += (7 - self.dow) * us_in_day
                self.dow = 0

    cpdef prev(self):
        self.t -= (self.stride * us_in_day)
        if self.biz != 0:
            self.dow = (self.dow - self.stride) % 7
            if self.dow >= 5:
                self.t += (4 - self.dow) * us_in_day
                self.dow = 4


def array_to_datetime(ndarray[object] values, raise_=False, dayfirst=False):
    cdef:
        Py_ssize_t i, n = len(values)
        object val
        ndarray[int64_t] iresult
        ndarray[object] oresult
        pandas_datetimestruct dts

    from dateutil.parser import parse

    try:
        result = np.empty(n, dtype='M8[ns]')
        iresult = result.view('i8')
        for i in range(n):
            val = values[i]
            if util._checknull(val):
                iresult[i] = iNaT
            elif PyDateTime_Check(val):
                result[i] = val
            elif PyDate_Check(val):
                iresult[i] = _date_to_datetime64(val, &dts)
            elif util.is_datetime64_object(val):
                iresult[i] = _get_datetime64_nanos(val)
            elif util.is_integer_object(val):
                iresult[i] = val
            else:
                if len(val) == 0:
                    iresult[i] = iNaT
                    continue
                try:
                    result[i] = parse(val, dayfirst=dayfirst)
                except Exception:
                    raise TypeError
        return result
    except TypeError:
        oresult = np.empty(n, dtype=object)

        for i in range(n):
            val = values[i]
            if util._checknull(val):
                oresult[i] = val
            else:
                if len(val) == 0:
                    # TODO: ??
                    oresult[i] = 'NaT'
                    continue
                try:
                    oresult[i] = parse(val, dayfirst=dayfirst)
                except Exception:
                    if raise_:
                        raise
                    return values
                    # oresult[i] = val

        return oresult

cdef inline _get_datetime64_nanos(object val):
    cdef:
        pandas_datetimestruct dts
        PANDAS_DATETIMEUNIT unit
        npy_datetime ival

    unit = get_datetime64_unit(val)
    if numpy_16:
        if unit == 3:
            raise ValueError('NumPy 1.6.1 business freq not supported')

        if unit > 3:
            unit = <PANDAS_DATETIMEUNIT> ((<int>unit) - 1)

    ival = get_datetime64_value(val)

    if unit != PANDAS_FR_ns:
        pandas_datetime_to_datetimestruct(ival, unit, &dts)
        return pandas_datetimestruct_to_datetime(PANDAS_FR_ns, &dts)
    else:
        return ival


def cast_to_nanoseconds(ndarray arr):
    cdef:
        Py_ssize_t i, n = arr.size
        ndarray[int64_t] ivalues, iresult
        PANDAS_DATETIMEUNIT unit
        pandas_datetimestruct dts

    shape = (<object> arr).shape

    ivalues = arr.view(np.int64).ravel()

    result = np.empty(shape, dtype='M8[ns]')
    iresult = result.ravel().view(np.int64)

    unit = get_datetime64_unit(arr.flat[0])
    if numpy_16:
        if unit == 3:
            raise ValueError('NumPy 1.6.1 business freq not supported')

        if unit > 3:
            unit = <PANDAS_DATETIMEUNIT> ((<int>unit) - 1)

    for i in range(n):
        pandas_datetime_to_datetimestruct(ivalues[i], unit, &dts)
        iresult[i] = pandas_datetimestruct_to_datetime(PANDAS_FR_ns, &dts)

    return result

#----------------------------------------------------------------------
# Conversion routines


def pydt_to_i8(object pydt):
    '''
    Convert to int64 representation compatible with numpy datetime64; converts
    to UTC
    '''
    cdef:
        _TSObject ts

    ts = convert_to_tsobject(pydt)

    return ts.value

def i8_to_pydt(int64_t i8, object tzinfo = None):
    '''
    Inverse of pydt_to_i8
    '''
    return Timestamp(i8)

#----------------------------------------------------------------------
# time zone conversion helpers

try:
    import pytz
    have_pytz = True
except:
    have_pytz = False

def tz_convert(ndarray[int64_t] vals, object tz1, object tz2):
    cdef:
        ndarray[int64_t] utc_dates, result, trans, deltas
        Py_ssize_t i, pos, n = len(vals)
        int64_t v, offset

    if not have_pytz:
        import pytz

    # Convert to UTC

    if tz1.zone != 'UTC':
        utc_dates = np.empty(n, dtype=np.int64)
        deltas = _get_deltas(tz1)
        trans = _get_transitions(tz1)
        pos = trans.searchsorted(vals[0]) - 1
        if pos < 0:
            raise ValueError('First time before start of DST info')

        offset = deltas[pos]
        for i in range(n):
            v = vals[i]
            if v >= trans[pos + 1]:
                pos += 1
                offset = deltas[pos]
            utc_dates[i] = v - offset
    else:
        utc_dates = vals

    if tz2.zone == 'UTC':
        return utc_dates

    # Convert UTC to other timezone

    result = np.empty(n, dtype=np.int64)
    trans = _get_transitions(tz2)
    deltas = _get_deltas(tz2)
    pos = trans.searchsorted(utc_dates[0]) - 1
    if pos < 0:
        raise ValueError('First time before start of DST info')

    offset = deltas[pos]
    for i in range(n):
        v = utc_dates[i]
        if v >= trans[pos + 1]:
            pos += 1
            offset = deltas[pos]
        result[i] = v + offset

    return result

def tz_convert_single(int64_t val, object tz1, object tz2):
    cdef:
        ndarray[int64_t] trans, deltas
        Py_ssize_t pos
        int64_t v, offset, utc_date


    if not have_pytz:
        import pytz

    # Convert to UTC

    if tz1.zone != 'UTC':
        deltas = _get_deltas(tz1)
        trans = _get_transitions(tz1)
        pos = trans.searchsorted(val) - 1
        if pos < 0:
            raise ValueError('First time before start of DST info')
        offset = deltas[pos]
        utc_date = val - offset
    else:
        utc_date = val

    if tz2.zone == 'UTC':
        return utc_date

    # Convert UTC to other timezone
    trans = _get_transitions(tz2)
    deltas = _get_deltas(tz2)
    pos = trans.searchsorted(utc_date) - 1
    if pos < 0:
        raise ValueError('First time before start of DST info')

    offset = deltas[pos]
    return utc_date + offset


trans_cache = {}
utc_offset_cache = {}

def _get_transitions(tz):
    """
    Get UTC times of DST transitions
    """
    if tz not in trans_cache:
        arr = np.array(tz._utc_transition_times, dtype='M8[ns]')
        trans_cache[tz] = arr.view('i8')
    return trans_cache[tz]

def _get_deltas(tz):
    """
    Get UTC offsets in microseconds corresponding to DST transitions
    """
    if tz not in utc_offset_cache:
        utc_offset_cache[tz] = _unbox_utcoffsets(tz._transition_info)
    return utc_offset_cache[tz]

cdef double total_seconds(object td): # Python 2.6 compat
    return ((td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) //
            10**6)

cpdef ndarray _unbox_utcoffsets(object transinfo):
    cdef:
        Py_ssize_t i, sz
        ndarray[int64_t] arr

    sz = len(transinfo)
    arr = np.empty(sz, dtype='i8')

    for i in range(sz):
        arr[i] = int(total_seconds(transinfo[i][0])) * 1000000000

    return arr


def tz_localize_check(ndarray[int64_t] vals, object tz):
    """
    Localize tzinfo-naive DateRange to given time zone (using pytz). If
    there are ambiguities in the values, raise AmbiguousTimeError.

    Returns
    -------
    localized : DatetimeIndex
    """
    cdef:
        ndarray[int64_t] trans, deltas
        Py_ssize_t i, pos, n = len(vals)
        int64_t v, dst_start, dst_end

    if not have_pytz:
        raise Exception("Could not find pytz module")

    if tz == pytz.utc or tz is None:
        return

    trans = _get_transitions(tz)
    deltas = _get_deltas(tz)

    pos = np.searchsorted(trans, vals[0])
    dst_start = trans[pos] + deltas[pos - 1]
    dst_end = trans[pos] + deltas[pos]

    for i in range(n):
        v = vals[i]
        if v >= trans[pos + 1]:
            pos += 1
            dst_start = trans[pos] + deltas[pos - 1]
            dst_end = trans[pos] + deltas[pos]

        if dst_start > dst_end:
            dst_end, dst_start = dst_start, dst_end

        if dst_start <= v and v <= dst_end:
            msg = "Cannot localize, ambiguous time %s found" % Timestamp(v)
            raise pytz.AmbiguousTimeError(msg)


# Accessors
#----------------------------------------------------------------------

def build_field_sarray(ndarray[int64_t] dtindex):
    '''
    Datetime as int64 representation to a structured array of fields
    '''
    cdef:
        Py_ssize_t i, count = 0
        int isleap
        pandas_datetimestruct dts
        ndarray[int32_t] years, months, days, hours, minutes, seconds, mus

    count = len(dtindex)

    sa_dtype = [('Y', 'i4'), # year
                ('M', 'i4'), # month
                ('D', 'i4'), # day
                ('h', 'i4'), # hour
                ('m', 'i4'), # min
                ('s', 'i4'), # second
                ('u', 'i4')] # microsecond

    out = np.empty(count, dtype=sa_dtype)

    years = out['Y']
    months = out['M']
    days = out['D']
    hours = out['h']
    minutes = out['m']
    seconds = out['s']
    mus = out['u']

    for i in range(count):
        pandas_datetime_to_datetimestruct(dtindex[i], PANDAS_FR_ns, &dts)
        years[i] = dts.year
        months[i] = dts.month
        days[i] = dts.day
        hours[i] = dts.hour
        minutes[i] = dts.min
        seconds[i] = dts.sec
        mus[i] = dts.us

    return out

@cython.wraparound(False)
def fast_field_accessor(ndarray[int64_t] dtindex, object field):
    '''
    Given a int64-based datetime index, extract the year, month, etc.,
    field and return an array of these values.
    '''
    cdef:
        _TSObject ts
        Py_ssize_t i, count = 0
        ndarray[int32_t] out
        ndarray[int32_t, ndim=2] _month_offset
        int isleap
        pandas_datetimestruct dts

    _month_offset = np.array(
        [[ 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365 ],
         [ 0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335, 366 ]],
         dtype=np.int32 )

    count = len(dtindex)
    out = np.empty(count, dtype='i4')

    if field == 'Y':
        for i in range(count):
            if dtindex[i] == NPY_NAT: out[i] = -1; continue

            pandas_datetime_to_datetimestruct(dtindex[i], PANDAS_FR_ns, &dts)
            out[i] = dts.year
        return out

    elif field == 'M':
        for i in range(count):
            if dtindex[i] == NPY_NAT: out[i] = -1; continue

            pandas_datetime_to_datetimestruct(dtindex[i], PANDAS_FR_ns, &dts)
            out[i] = dts.month
        return out

    elif field == 'D':
        for i in range(count):
            if dtindex[i] == NPY_NAT: out[i] = -1; continue

            pandas_datetime_to_datetimestruct(dtindex[i], PANDAS_FR_ns, &dts)
            out[i] = dts.day
        return out

    elif field == 'h':
        for i in range(count):
            if dtindex[i] == NPY_NAT: out[i] = -1; continue

            pandas_datetime_to_datetimestruct(dtindex[i], PANDAS_FR_ns, &dts)
            out[i] = dts.hour
        return out

    elif field == 'm':
        for i in range(count):
            if dtindex[i] == NPY_NAT: out[i] = -1; continue

            pandas_datetime_to_datetimestruct(dtindex[i], PANDAS_FR_ns, &dts)
            out[i] = dts.min
        return out

    elif field == 's':
        for i in range(count):
            if dtindex[i] == NPY_NAT: out[i] = -1; continue

            pandas_datetime_to_datetimestruct(dtindex[i], PANDAS_FR_ns, &dts)
            out[i] = dts.sec
        return out

    elif field == 'us':
        for i in range(count):
            if dtindex[i] == NPY_NAT: out[i] = -1; continue

            pandas_datetime_to_datetimestruct(dtindex[i], PANDAS_FR_ns, &dts)
            out[i] = dts.us
        return out
    elif field == 'ns':
        for i in range(count):
            if dtindex[i] == NPY_NAT: out[i] = -1; continue

            pandas_datetime_to_datetimestruct(dtindex[i], PANDAS_FR_ns, &dts)
            out[i] = dts.ps / 1000
        return out
    elif field == 'doy':
        for i in range(count):
            if dtindex[i] == NPY_NAT: out[i] = -1; continue

            pandas_datetime_to_datetimestruct(dtindex[i], PANDAS_FR_ns, &dts)
            isleap = is_leapyear(dts.year)
            out[i] = _month_offset[isleap, dts.month-1] + dts.day
        return out

    elif field == 'dow':
        for i in range(count):
            if dtindex[i] == NPY_NAT: out[i] = -1; continue

            ts = convert_to_tsobject(dtindex[i])
            out[i] = ts_dayofweek(ts)
        return out

    elif field == 'woy':
        for i in range(count):
            if dtindex[i] == NPY_NAT: out[i] = -1; continue

            pandas_datetime_to_datetimestruct(dtindex[i], PANDAS_FR_ns, &dts)
            isleap = is_leapyear(dts.year)
            out[i] = _month_offset[isleap, dts.month - 1] + dts.day
            out[i] = ((out[i] - 1) / 7) + 1
        return out

    elif field == 'q':
        for i in range(count):
            if dtindex[i] == NPY_NAT: out[i] = -1; continue

            pandas_datetime_to_datetimestruct(dtindex[i], PANDAS_FR_ns, &dts)
            out[i] = dts.month
            out[i] = ((out[i] - 1) / 3) + 1
        return out

    raise ValueError("Field %s not supported" % field)


cdef inline int m8_weekday(int64_t val):
    ts = convert_to_tsobject(val)
    return ts_dayofweek(ts)

cdef int64_t DAY_NS = 86400000000000LL

def values_at_time(ndarray[int64_t] stamps, int64_t time):
    cdef:
        Py_ssize_t i, j, count, n = len(stamps)
        ndarray[int64_t] indexer, times
        int64_t last, cur

    # Assumes stamps is sorted

    if len(stamps) == 0:
        return np.empty(0, dtype=np.int64)

    # is this OK?
    # days = stamps // DAY_NS
    times = stamps % DAY_NS

    # Nanosecond resolution
    count = 0
    for i in range(n):
        if times[i] == time:
            count += 1

    indexer = np.empty(count, dtype=np.int64)

    j = 0
    # last = days[0]
    for i in range(n):
        if times[i] == time:
            indexer[j] = i
            j += 1

    return indexer

def values_between_time(ndarray[int64_t] stamps, int64_t stime, int64_t etime,
                        bint include_start, bint include_end):
    cdef:
        Py_ssize_t i, j, count, n = len(stamps)
        ndarray[int64_t] indexer, times
        int64_t last, cur

    # Assumes stamps is sorted

    if len(stamps) == 0:
        return np.empty(0, dtype=np.int64)

    # is this OK?
    # days = stamps // DAY_NS
    times = stamps % DAY_NS

    # Nanosecond resolution
    count = 0
    if include_start and include_end:
        for i in range(n):
            cur = times[i]
            if cur >= stime and cur <= etime:
                count += 1
    elif include_start:
        for i in range(n):
            cur = times[i]
            if cur >= stime and cur < etime:
                count += 1
    elif include_end:
        for i in range(n):
            cur = times[i]
            if cur > stime and cur <= etime:
                count += 1
    else:
        for i in range(n):
            cur = times[i]
            if cur > stime and cur < etime:
                count += 1

    indexer = np.empty(count, dtype=np.int64)

    j = 0
    # last = days[0]
    if include_start and include_end:
        for i in range(n):
            cur = times[i]
            if cur >= stime and cur <= etime:
                indexer[j] = i
                j += 1
    elif include_start:
        for i in range(n):
            cur = times[i]
            if cur >= stime and cur < etime:
                indexer[j] = i
                j += 1
    elif include_end:
        for i in range(n):
            cur = times[i]
            if cur > stime and cur <= etime:
                indexer[j] = i
                j += 1
    else:
        for i in range(n):
            cur = times[i]
            if cur > stime and cur < etime:
                indexer[j] = i
                j += 1

    return indexer

def date_normalize(ndarray[int64_t] stamps):
    cdef:
        Py_ssize_t i, n = len(stamps)
        ndarray[int64_t] result = np.empty(n, dtype=np.int64)
        pandas_datetimestruct dts

    for i in range(n):
        pandas_datetime_to_datetimestruct(stamps[i], PANDAS_FR_ns, &dts)
        dts.hour = 0
        dts.min = 0
        dts.sec = 0
        dts.us = 0
        result[i] = pandas_datetimestruct_to_datetime(PANDAS_FR_ns, &dts)

    return result

def dates_normalized(ndarray[int64_t] stamps):
    cdef:
        Py_ssize_t i, n = len(stamps)
        pandas_datetimestruct dts

    for i in range(n):
        pandas_datetime_to_datetimestruct(stamps[i], PANDAS_FR_ns, &dts)
        if (dts.hour + dts.min + dts.sec + dts.us) > 0:
            return False

    return True

# Some general helper functions
#----------------------------------------------------------------------

def isleapyear(int64_t year):
    return is_leapyear(year)

def monthrange(int64_t year, int64_t month):
    cdef:
        int64_t days
        int64_t day_of_week

    if month < 1 or month > 12:
        raise ValueError("bad month number 0; must be 1-12")

    days = _days_per_month_table[is_leapyear(year)][month-1]

    return (dayofweek(year, month, 1), days)

cdef inline int64_t ts_dayofweek(_TSObject ts):
    return dayofweek(ts.dts.year, ts.dts.month, ts.dts.day)

