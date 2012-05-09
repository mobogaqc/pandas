"""
Adapted from scikits.timeseries by Pierre GF Gerard-Marchant & Matt Knox
"""

#!!! TODO: Use the fact that axis can have units to simplify the process


from matplotlib import pylab
from matplotlib.ticker import Formatter, Locator
from matplotlib.transforms import nonsingular

import numpy as np

from pandas.tseries.offsets import DateOffset
import pandas.tseries.frequencies as frequencies
from pandas.tseries.frequencies import FreqGroup

from pandas.tseries.period import Period, PeriodIndex
from pandas.tseries.index import DatetimeIndex
from pandas.core.series import Series

import warnings

#----------------------------------------------------------------------
# Generic documentation

_doc_parameters = dict(
figsize="""figsize : {None, tuple}
        Size of the figure, as a tuple (width, height) in inches.
        If None, defaults to rc figure.figsize.""",
dpi="""dpi : {None, int}, optional
        Resolution in dots per inches.
        If None, defaults to rc figure.dpi.""",
facecolor="""facecolor : {None, string}, optional
        Background color.
        If None, defaults to rc figure.facecolor.""",
edgecolor="""edgecolor : {None, string}, optional
        Border color.
        If None, defaults to rc figure.edgecolor.""",
linewidth="""linewidth : {float, None}
        Width of the patch edge line.""",
frameon="""frameon : {True, False}
        Whether to draw the frame around the figure.""",
subplotpars="""subplotpars : {None, var}
        A :class:`SubplotParams` instance, defaults to rc""",
mandatoryplotargs="""args : var
        Mandatory arguments for the creation of the subplot.
        These arguments should be given as ``nb_of_rows``, ``nb_of_columns``,
        ``plot_number``, or as a single 3-digit number if the 3 previous numbers
        are all lower than 10.""" )


#----------------------------------------------------------------------
# Plotting functions and monkey patches

def tsplot(series, plotf, *args, **kwargs):
    """
    Plots a Series on the given Matplotlib axes object

    Parameters
    ----------
    axes : Axes
    series : Series

    Notes
    _____
    Supports same args and kwargs as Axes.plot

    """
    # Used inferred freq is possible, need a test case for inferred
    freq = getattr(series.index, 'freq', None)
    if freq is None and hasattr(series.index, 'inferred_freq'):
        freq = series.index.inferred_freq
    if isinstance(freq, DateOffset):
        freq = freq.rule_code

    freq = frequencies.offset_to_period_alias(freq)
    # Convert DatetimeIndex to PeriodIndex
    if isinstance(series.index, DatetimeIndex):
        idx = series.index.to_period(freq=freq)
        series = Series(series.values, idx, name=series.name)

    if not isinstance(series.index, PeriodIndex):
        raise TypeError('series argument to tsplot must have DatetimeIndex or '
                        'PeriodIndex')

    if 'ax' in kwargs:
        ax = kwargs.pop('ax')
    else:
        ax = plt.gca()

    # Specialized ts plotting attributes for Axes
    ax.freq = freq
    ax.legendlabels = [kwargs.get('label', None)]
    ax.view_interval = None
    ax.date_axis_info = None

    # format args and lot
    args = _check_plot_params(series, series.index, freq, *args)
    plotted = plotf(ax, *args,  **kwargs)

    format_dateaxis(ax, ax.freq)

    # when adding a right axis (using add_yaxis), for some reason the
    # x axis limits don't get properly set. This gets around the problem
    xlim = ax.get_xlim()
    if xlim[0] == 0.0 and xlim[1] == 1.0:
        # if xlim still at default values, autoscale the axis
        ax.autoscale_view()

    left = get_datevalue(series.index[0], freq)
    right = get_datevalue(series.index[-1], freq)
    ax.set_xlim(left, right)

    return plotted

tsplot.__doc__ %= _doc_parameters

def get_datevalue(date, freq):
    if isinstance(date, Period):
        return date.asfreq(freq).ordinal
    elif isinstance(date, str):
        return Period(date, freq).ordinal
    elif isinstance(date, (int, float)) or \
            (isinstance(date, np.ndarray) and (date.size == 1)):
        return date
    elif date is None:
        return None
    raise ValueError("Unrecognizable date '%s'" % date)


# Check and format plotting parameters

def _check_plot_params(series, xdata, freq, *args):
    """
    Defines the plot coordinates (and basic plotting arguments).
    """
    remaining = list(args)
    noinfo_msg = "No date information available!"

    # No args ? Use defaults, if any
    if len(args) == 0:
        if xdata is None:
            raise ValueError(noinfo_msg)
        return (xdata, series)

    output = []
    while len(remaining) > 0:
        a = remaining.pop(0)
        output.extend(_handle_param(a, remaining, series, xdata, freq))

    # Reinitialize the plot if needed ...........
    if xdata is None:
        xdata = output[0]

    # Force the xdata to the current frequency
    elif output[0].freq != freq:
        output = list(output)
        output[0] = output[0].asfreq(freq)

    return output

def _handle_param(curr, remaining, series, xdata, freq):
    # The argument is a format: use default dates/
    noinfo_msg = "No date information available!"
    if isinstance(curr, str):
        if xdata is None:
            raise ValueError(noinfo_msg)
        else:
            return [xdata, series, curr]

    # The argument is a Series: use its dates for x
    elif isinstance(curr, Series):
        (x, y) = (curr.index, curr.values)
        if len(remaining) > 0 and isinstance(remaining[0], str):
            b = remaining.pop(0)
            return [x, y, b]
        else:
            return [x, y]

    # The argument is a PeriodIndex............
    elif isinstance(curr, PeriodIndex):
        return _handle_period_index(curr, remaining, series, xdata, freq)

    # Otherwise..............................
    elif len(remaining) > 0 and isinstance(remaining[0], str):
        b = remaining.pop(0)
        if xdata is None:
            raise ValueError(noinfo_msg)
        else:
            return [xdata, curr, b]
    elif xdata is None:
        raise ValueError(noinfo_msg)
    else:
        return [xdata, curr]

def _handle_period_index(curr, remaining, series, xdata, freq):
    # Force to current freq
    noinfo_msg = "No date information available!"
    if freq is not None:
        if curr.freq != freq:
            curr = curr.asfreq(freq)

    # There's an argument after
    if len(remaining) > 0:
        #...and it's a format string
        if isinstance(remaining[0], str):
            b = remaining.pop(0)
            if series is None:
                raise ValueError(noinfo_msg)
            else:
                return [curr, series, b]

        #... and it's another date: use the default
        elif isinstance(remaining[0], PeriodIndex):
            if series is None:
                raise ValueError(noinfo_msg)
            else:
                return [curr, series]

        #... and it must be some data
        else:
            b = remaining.pop(0)
            if len(remaining) > 0:
                if isinstance(remaining[0], str):
                    c = remaining.pop(0)
                    return [curr, b, c]
                else:
                    return [curr, b]
    else:
        if series is None:
            raise ValueError(noinfo_msg)


##### -------------------------------------------------------------------------
#---- --- Locators ---
##### -------------------------------------------------------------------------

def _get_default_annual_spacing(nyears):
    """
    Returns a default spacing between consecutive ticks for annual data.
    """
    if nyears < 11:
        (min_spacing, maj_spacing) = (1, 1)
    elif nyears < 20:
        (min_spacing, maj_spacing) = (1, 2)
    elif nyears < 50:
        (min_spacing, maj_spacing) = (1, 5)
    elif nyears < 100:
        (min_spacing, maj_spacing) = (5, 10)
    elif nyears < 200:
        (min_spacing, maj_spacing) = (5, 25)
    elif nyears < 600:
        (min_spacing, maj_spacing) = (10, 50)
    else:
        factor = nyears // 1000 + 1
        (min_spacing, maj_spacing) = (factor * 20, factor * 100)
    return (min_spacing, maj_spacing)


def period_break(dates, period):
    """
    Returns the indices where the given period changes.

    Parameters
    ----------
    dates : PeriodIndex
        Array of intervals to monitor.
    period : string
        Name of the period to monitor.
    """
    current = getattr(dates, period)
    previous = getattr(dates - 1, period)
    return (current - previous).nonzero()[0]


def has_level_label(label_flags, vmin):
    """
    Returns true if the ``label_flags`` indicate there is at least one label
    for this level.

    if the minimum view limit is not an exact integer, then the first tick
    label won't be shown, so we must adjust for that.
    """
    if label_flags.size == 0 or (label_flags.size == 1 and
                                 label_flags[0] == 0 and
                                 vmin % 1 > 0.0):
        return False
    else:
        return True


def _daily_finder(vmin, vmax, freq):
    periodsperday = -1

    if freq >= FreqGroup.FR_HR:
        if freq == FreqGroup.FR_SEC:
            periodsperday = 24 * 60 * 60
        elif freq == FreqGroup.FR_MIN:
            periodsperday = 24 * 60
        elif freq == FreqGroup.FR_HR:
            periodsperday = 24
        else:
            raise ValueError("unexpected frequency: %s" % freq)
        periodsperyear = 365 * periodsperday
        periodspermonth = 28 * periodsperday

    elif freq == FreqGroup.FR_BUS:
        periodsperyear = 261
        periodspermonth = 19
    elif freq == FreqGroup.FR_DAY:
        periodsperyear = 365
        periodspermonth = 28
    elif frequencies.get_freq_group(freq) == FreqGroup.FR_WK:
        periodsperyear = 52
        periodspermonth = 3
    elif freq == FreqGroup.FR_UND:
        periodsperyear = 100
        periodspermonth = 10
    else:
        raise ValueError("unexpected frequency")

    # save this for later usage
    vmin_orig = vmin

    (vmin, vmax) = (Period(ordinal=int(vmin), freq=freq),
                    Period(ordinal=int(vmax), freq=freq))
    span = vmax.ordinal - vmin.ordinal + 1
    dates_ = PeriodIndex(start=vmin, end=vmax, freq=freq)
    # Initialize the output
    info = np.zeros(span,
                    dtype=[('val', np.int64), ('maj', bool),
                           ('min', bool), ('fmt', '|S20')])
    info['val'][:] = dates_.values
    info['fmt'][:] = ''
    info['maj'][[0, -1]] = True
    # .. and set some shortcuts
    info_maj = info['maj']
    info_min = info['min']
    info_fmt = info['fmt']

    def first_label(label_flags):
        if (label_flags[0] == 0) and (label_flags.size > 1) and \
            ((vmin_orig % 1) > 0.0):
                return label_flags[1]
        else:
            return label_flags[0]

    # Case 1. Less than a month
    if span <= periodspermonth:

        day_start = period_break(dates_, 'day')
        month_start = period_break(dates_, 'month')

        def _hour_finder(label_interval, force_year_start):
            _hour = dates_.hour
            _prev_hour = (dates_-1).hour
            hour_start = (_hour - _prev_hour) != 0
            info_maj[day_start] = True
            info_min[hour_start & (_hour % label_interval == 0)] = True
            year_start = period_break(dates_, 'year')
            info_fmt[hour_start & (_hour % label_interval == 0)] = '%H:%M'
            info_fmt[day_start] = '%H:%M\n%d-%b'
            info_fmt[year_start] = '%H:%M\n%d-%b\n%Y'
            if force_year_start and not has_level_label(year_start, vmin_orig):
                info_fmt[first_label(day_start)] = '%H:%M\n%d-%b\n%Y'

        def _minute_finder(label_interval):
            hour_start = period_break(dates_, 'hour')
            _minute = dates_.minute
            _prev_minute = (dates_-1).minute
            minute_start = (_minute - _prev_minute) != 0
            info_maj[hour_start] = True
            info_min[minute_start & (_minute % label_interval == 0)] = True
            year_start = period_break(dates_, 'year')
            info_fmt = info['fmt']
            info_fmt[minute_start & (_minute % label_interval == 0)] = '%H:%M'
            info_fmt[day_start] = '%H:%M\n%d-%b'
            info_fmt[year_start] = '%H:%M\n%d-%b\n%Y'

        def _second_finder(label_interval):
            minute_start = period_break(dates_, 'minute')
            _second = dates_.second
            _prev_second = (dates_-1).second
            second_start = (_second - _prev_second) != 0
            info['maj'][minute_start] = True
            info['min'][second_start & (_second % label_interval == 0)] = True
            year_start = period_break(dates_, 'year')
            info_fmt = info['fmt']
            info_fmt[second_start & (_second % label_interval == 0)] = '%H:%M:%S'
            info_fmt[day_start] = '%H:%M:%S\n%d-%b'
            info_fmt[year_start] = '%H:%M:%S\n%d-%b\n%Y'

        if span < periodsperday / 12000.0: _second_finder(1)
        elif span < periodsperday / 6000.0: _second_finder(2)
        elif span < periodsperday / 2400.0: _second_finder(5)
        elif span < periodsperday / 1200.0: _second_finder(10)
        elif span < periodsperday / 800.0: _second_finder(15)
        elif span < periodsperday / 400.0: _second_finder(30)
        elif span < periodsperday / 150.0: _minute_finder(1)
        elif span < periodsperday / 70.0: _minute_finder(2)
        elif span < periodsperday / 24.0: _minute_finder(5)
        elif span < periodsperday / 12.0: _minute_finder(15)
        elif span < periodsperday / 6.0:  _minute_finder(30)
        elif span < periodsperday / 2.5: _hour_finder(1, False)
        elif span < periodsperday / 1.5: _hour_finder(2, False)
        elif span < periodsperday * 1.25: _hour_finder(3, False)
        elif span < periodsperday * 2.5: _hour_finder(6, True)
        elif span < periodsperday * 4: _hour_finder(12, True)
        else:
            info_maj[month_start] = True
            info_min[day_start] = True
            year_start = period_break(dates_, 'year')
            info_fmt = info['fmt']
            info_fmt[day_start] = '%d'
            info_fmt[month_start] = '%d\n%b'
            info_fmt[year_start] = '%d\n%b\n%Y'
            if not has_level_label(year_start, vmin_orig):
                if not has_level_label(month_start, vmin_orig):
                    info_fmt[first_label(day_start)] = '%d\n%b\n%Y'
                else:
                    info_fmt[first_label(month_start)] = '%d\n%b\n%Y'

    # Case 2. Less than three months
    elif span <= periodsperyear // 4:
        month_start = period_break(dates_, 'month')
        info_maj[month_start] = True
        if freq < FreqGroup.FR_HR:
            info['min'] = True
        else:
            day_start = period_break(dates_, 'day')
            info['min'][day_start] = True
        week_start = period_break(dates_, 'week')
        year_start = period_break(dates_, 'year')
        info_fmt[week_start] = '%d'
        info_fmt[month_start] = '\n\n%b'
        info_fmt[year_start] = '\n\n%b\n%Y'
        if not has_level_label(year_start, vmin_orig):
            if not has_level_label(month_start, vmin_orig):
                info_fmt[first_label(week_start)] = '\n\n%b\n%Y'
            else:
                info_fmt[first_label(month_start)] = '\n\n%b\n%Y'
    # Case 3. Less than 14 months ...............
    elif span <= 1.15 * periodsperyear:
        year_start = period_break(dates_, 'year')
        month_start = period_break(dates_, 'month')
        week_start = period_break(dates_, 'week')
        info_maj[month_start] = True
        info_min[week_start] = True
        info_min[year_start] = False
        info_min[month_start] = False
        info_fmt[month_start] = '%b'
        info_fmt[year_start] = '%b\n%Y'
        if not has_level_label(year_start, vmin_orig):
            info_fmt[first_label(month_start)] = '%b\n%Y'
    # Case 4. Less than 2.5 years ...............
    elif span <= 2.5 * periodsperyear:
        year_start = period_break(dates_, 'year')
        quarter_start = period_break(dates_, 'quarter')
        month_start = period_break(dates_, 'month')
        info_maj[quarter_start] = True
        info_min[month_start] = True
        info_fmt[quarter_start] = '%b'
        info_fmt[year_start] = '%b\n%Y'
    # Case 4. Less than 4 years .................
    elif span <= 4 * periodsperyear:
        year_start = period_break(dates_, 'year')
        month_start = period_break(dates_, 'month')
        info_maj[year_start] = True
        info_min[month_start] = True
        info_min[year_start] = False

        month_break = dates_[month_start].month
        jan_or_jul = month_start[(month_break == 1) | (month_break == 7)]
        info_fmt[jan_or_jul] = '%b'
        info_fmt[year_start] = '%b\n%Y'
    # Case 5. Less than 11 years ................
    elif span <= 11 * periodsperyear:
        year_start = period_break(dates_, 'year')
        quarter_start = period_break(dates_, 'quarter')
        info_maj[year_start] = True
        info_min[quarter_start] = True
        info_min[year_start] = False
        info_fmt[year_start] = '%Y'
    # Case 6. More than 12 years ................
    else:
        year_start = period_break(dates_, 'year')
        year_break = dates_[year_start].year
        nyears = span / periodsperyear
        (min_anndef, maj_anndef) = _get_default_annual_spacing(nyears)
        major_idx = year_start[(year_break % maj_anndef == 0)]
        info_maj[major_idx] = True
        minor_idx = year_start[(year_break % min_anndef == 0)]
        info_min[minor_idx] = True
        info_fmt[major_idx] = '%Y'
    #............................................

    return info


def _monthly_finder(vmin, vmax, freq):
    if isinstance(freq, basestring):
        freq = frequencies.get_freq(freq)

    if freq != FreqGroup.FR_MTH:
        raise ValueError("Unexpected frequency")
    periodsperyear = 12

    vmin_orig = vmin
    (vmin, vmax) = (int(vmin), int(vmax))
    span = vmax - vmin + 1
    #..............
    # Initialize the output
    info = np.zeros(span,
                    dtype=[('val', int), ('maj', bool), ('min', bool),
                           ('fmt', '|S8')])
    info['val'] = np.arange(vmin, vmax + 1)
    dates_ = info['val']
    info['fmt'] = ''
    year_start = (dates_ % 12 == 1).nonzero()[0]
    info_maj = info['maj']
    info_fmt = info['fmt']
    #..............
    if span <= 1.15 * periodsperyear:
        info_maj[year_start] = True
        info['min'] = True

        info_fmt[:] = '%b'
        info_fmt[year_start] = '%b\n%Y'

        if not has_level_label(year_start, vmin_orig):
            if dates_.size > 1:
                idx = 1
            else:
                idx = 0
            info_fmt[idx] = '%b\n%Y'
    #..............
    elif span <= 2.5 * periodsperyear:
        quarter_start = (dates_ % 3 == 1).nonzero()
        info_maj[year_start] = True
        # TODO: Check the following : is it really info['fmt'] ?
        info['fmt'][quarter_start] = True
        info['min'] = True

        info_fmt[quarter_start] = '%b'
        info_fmt[year_start] = '%b\n%Y'
    #..............
    elif span <= 4 * periodsperyear:
        info_maj[year_start] = True
        info['min'] = True

        jan_or_jul = (dates_ % 12 == 1) | (dates_ % 12 == 7)
        info_fmt[jan_or_jul] = '%b'
        info_fmt[year_start] = '%b\n%Y'
    #..............
    elif span <= 11 * periodsperyear:
        quarter_start = (dates_ % 3 == 1).nonzero()
        info_maj[year_start] = True
        info['min'][quarter_start] = True

        info_fmt[year_start] = '%Y'
    #..................
    else:
        nyears = span / periodsperyear
        (min_anndef, maj_anndef) = _get_default_annual_spacing(nyears)
        years = dates_[year_start] // 12 + 1
        major_idx = year_start[(years % maj_anndef == 0)]
        info_maj[major_idx] = True
        info['min'][year_start[(years % min_anndef == 0)]] = True

        info_fmt[major_idx] = '%Y'
    #..............
    return info


def _quarterly_finder(vmin, vmax, freq):
    if isinstance(freq, basestring):
        freq = frequencies.get_freq(freq)

    if frequencies.get_freq_group(freq) != FreqGroup.FR_QTR:
        raise ValueError("Unexpected frequency")
    periodsperyear = 4
    vmin_orig = vmin
    (vmin, vmax) = (int(vmin), int(vmax))
    span = vmax - vmin + 1
    #............................................
    info = np.zeros(span,
                    dtype=[('val', int), ('maj', bool), ('min', bool),
                           ('fmt', '|S8')])
    info['val'] = np.arange(vmin, vmax + 1)
    info['fmt'] = ''
    dates_ = info['val']
    info_maj = info['maj']
    info_fmt = info['fmt']
    year_start = (dates_ % 4 == 1).nonzero()[0]
    #..............
    if span <= 3.5 * periodsperyear:
        info_maj[year_start] = True
        info['min'] = True

        info_fmt[:] = 'Q%q'
        info_fmt[year_start] = 'Q%q\n%F'
        if not has_level_label(year_start, vmin_orig):
            if dates_.size > 1:
                idx = 1
            else:
                idx = 0
            info_fmt[idx] = 'Q%q\n%F'
    #..............
    elif span <= 11 * periodsperyear:
        info_maj[year_start] = True
        info['min'] = True
        info_fmt[year_start] = '%F'
    #..............
    else:
        years = dates_[year_start] // 4 + 1
        nyears = span / periodsperyear
        (min_anndef, maj_anndef) = _get_default_annual_spacing(nyears)
        major_idx = year_start[(years % maj_anndef == 0)]
        info_maj[major_idx] = True
        info['min'][year_start[(years % min_anndef == 0)]] = True
        info_fmt[major_idx] = '%F'
    #..............
    return info


def _annual_finder(vmin, vmax, freq):
    if isinstance(freq, basestring):
        freq = frequencies.get_freq(freq)
    if frequencies.get_freq_group(freq) != FreqGroup.FR_ANN:
        raise ValueError("Unexpected frequency")
    (vmin, vmax) = (int(vmin), int(vmax + 1))
    span = vmax - vmin + 1
    #..............
    info = np.zeros(span,
                    dtype=[('val', int), ('maj', bool), ('min', bool),
                           ('fmt', '|S8')])
    info['val'] = np.arange(vmin, vmax + 1)
    info['fmt'] = ''
    dates_ = info['val']
    #..............
    (min_anndef, maj_anndef) = _get_default_annual_spacing(span)
    major_idx = dates_ % maj_anndef == 0
    info['maj'][major_idx] = True
    info['min'][(dates_ % min_anndef == 0)] = True
    info['fmt'][major_idx] = '%Y'
    #..............
    return info


def get_finder(freq):
    if isinstance(freq, basestring):
        freq = frequencies.get_freq(freq)
    fgroup = frequencies.get_freq_group(freq)

    if fgroup == FreqGroup.FR_ANN:
        return _annual_finder
    elif fgroup == FreqGroup.FR_QTR:
        return _quarterly_finder
    elif freq ==FreqGroup.FR_MTH:
        return _monthly_finder
    elif ((freq >= FreqGroup.FR_BUS) or (freq == FreqGroup.FR_UND) or
          fgroup == FreqGroup.FR_WK):
        return _daily_finder
    else:
        errmsg = "Unsupported frequency: %s" % (freq)
        raise NotImplementedError(errmsg)

class TimeSeries_DateLocator(Locator):
    """
    Locates the ticks along an axis controlled by a :class:`Series`.

    Parameters
    ----------
    freq : {var}
        Valid frequency specifier.
    minor_locator : {False, True}, optional
        Whether the locator is for minor ticks (True) or not.
    dynamic_mode : {True, False}, optional
        Whether the locator should work in dynamic mode.
    base : {int}, optional
    quarter : {int}, optional
    month : {int}, optional
    day : {int}, optional
    """

    def __init__(self, freq, minor_locator=False, dynamic_mode=True,
                 base=1, quarter=1, month=1, day=1, plot_obj=None):
        if isinstance(freq, basestring):
            freq = frequencies.get_freq(freq)
        self.freq = freq
        self.base = base
        (self.quarter, self.month, self.day) = (quarter, month, day)
        self.isminor = minor_locator
        self.isdynamic = dynamic_mode
        self.offset = 0
        self.plot_obj = plot_obj
        self.finder = get_finder(freq)

    def _get_default_locs(self, vmin, vmax):
        "Returns the default locations of ticks."

        if self.plot_obj.date_axis_info is None:
            self.plot_obj.date_axis_info = self.finder(vmin, vmax, self.freq)

        locator = self.plot_obj.date_axis_info

        if self.isminor:
            return np.compress(locator['min'], locator['val'])
        return np.compress(locator['maj'], locator['val'])

    def __call__(self):
        'Return the locations of the ticks.'
        # axis calls Locator.set_axis inside set_m<xxxx>_formatter
        vi = tuple(self.axis.get_view_interval())
        if vi != self.plot_obj.view_interval:
            self.plot_obj.date_axis_info = None
        self.plot_obj.view_interval = vi
        vmin, vmax = vi

        if vmax < vmin:
            vmin, vmax = vmax, vmin
        if self.isdynamic:
            locs = self._get_default_locs(vmin, vmax)
        else:
            base = self.base
            (d, m) = divmod(vmin, base)
            vmin = (d + 1) * base
            locs = range(vmin, vmax + 1, base)
        return locs

    def autoscale(self):
        """
        Sets the view limits to the nearest multiples of base that contain the
        data.
        """
        # requires matplotlib >= 0.98.0
        (vmin, vmax) = self.axis.get_data_interval()

        locs = self._get_default_locs(vmin, vmax)
        (vmin, vmax) = locs[[0, -1]]
        if vmin == vmax:
            vmin -= 1
            vmax += 1
        return nonsingular(vmin, vmax)

#####-------------------------------------------------------------------------
#---- --- Formatter ---
#####-------------------------------------------------------------------------
class TimeSeries_DateFormatter(Formatter):
    """
    Formats the ticks along an axis controlled by a :class:`PeriodIndex`.

    Parameters
    ----------
    freq : {int, string}
        Valid frequency specifier.
    minor_locator : {False, True}
        Whether the current formatter should apply to minor ticks (True) or
        major ticks (False).
    dynamic_mode : {True, False}
        Whether the formatter works in dynamic mode or not.
    """

    def __init__(self, freq, minor_locator=False, dynamic_mode=True,
                 plot_obj=None):
        if isinstance(freq, basestring):
            freq = frequencies.get_freq(freq)
        self.format = None
        self.freq = freq
        self.locs = []
        self.formatdict = None
        self.isminor = minor_locator
        self.isdynamic = dynamic_mode
        self.offset = 0
        self.plot_obj = plot_obj
        self.finder = get_finder(freq)

    def _set_default_format(self, vmin, vmax):
        "Returns the default ticks spacing."

        if self.plot_obj.date_axis_info is None:
            self.plot_obj.date_axis_info = self.finder(vmin, vmax, self.freq)
        info = self.plot_obj.date_axis_info

        if self.isminor:
            format = np.compress(info['min'] & np.logical_not(info['maj']),
                                 info)
        else:
            format = np.compress(info['maj'], info)
        self.formatdict = dict([(x, f) for (x, _, _, f) in format])
        return self.formatdict

    def set_locs(self, locs):
        'Sets the locations of the ticks'
        # don't actually use the locs. This is just needed to work with
        # matplotlib. Force to use vmin, vmax
        self.locs = locs

        (vmin, vmax) = vi = tuple(self.axis.get_view_interval())
        if vi != self.plot_obj.view_interval:
            self.plot_obj.date_axis_info = None
        self.plot_obj.view_interval = vi
        if vmax < vmin:
            (vmin, vmax) = (vmax, vmin)
        self._set_default_format(vmin, vmax)
    #
    def __call__(self, x, pos=0):
        if self.formatdict is None:
            return ''
        else:
            fmt = self.formatdict.pop(x, '')
            return Period(ordinal=int(x), freq=self.freq).strftime(fmt)

# Patch methods for subplot. Only format_dateaxis is currently used.
# Do we need the rest for convenience?

def format_dateaxis(subplot, freq):
    """
    Pretty-formats the date axis (x-axis).

    Major and minor ticks are automatically set for the frequency of the
    current underlying series.  As the dynamic mode is activated by
    default, changing the limits of the x axis will intelligently change
    the positions of the ticks.
    """
    majlocator = TimeSeries_DateLocator(freq, dynamic_mode=True,
                                        minor_locator=False,
                                        plot_obj=subplot)
    minlocator = TimeSeries_DateLocator(freq, dynamic_mode=True,
                                        minor_locator=True,
                                        plot_obj=subplot)
    subplot.xaxis.set_major_locator(majlocator)
    subplot.xaxis.set_minor_locator(minlocator)

    majformatter = TimeSeries_DateFormatter(freq, dynamic_mode=True,
                                            minor_locator=False,
                                            plot_obj=subplot)
    minformatter = TimeSeries_DateFormatter(freq, dynamic_mode=True,
                                            minor_locator=True,
                                            plot_obj=subplot)
    subplot.xaxis.set_major_formatter(majformatter)
    subplot.xaxis.set_minor_formatter(minformatter)
    pylab.draw_if_interactive()

def add_yaxis(fsp=None, position='right', yscale=None, basey=10, subsy=None):
    """
    Adds a second y-axis to a :class:`Subplot`.
    This function can also be used as a method.

    Parameters
    ----------
    fsp : {None, Subplot}
        Subplot to which the secondary y-axis is added.
        If None, the current subplot is selected: in that case, it should be
        a valid :class:`Subplot`.
        When used as a :class:`Subplot` method, this parameter points
        automatically to the calling subplot.
    position : {string}
        Position of the new axis, as either ``'left'`` or ``'right'``.
    yscale : {string}
        Scale of the new axis, as either ``'log'``, ``'linear'`` or ``None``.
        If None, uses the same scale as the first y axis.
    basey : {integer}
        Base of the logarithm for the new axis (if needed).
    subsy : {sequence}
        Sequence of the location of the minor ticks;
        None defaults to autosubs, which depend on the number of decades in
        the plot.
        Eg for base 10, ``subsy=(1,2,5)`` will  put minor ticks on 1, 2, 5, 11,
        12,15, 21, ....
        To turn off minor ticking, set ``subsy=[]``.

    Raises
    ------
    TypeError
        If the selected subplot is not a valid :class:`Subplot` object.

    """
    if fsp is None:
        fsp = pylab.gca()

    fig = fsp.figure
    axisini = fsp.axis()
    fsp_alt_args = (fsp._rows, fsp._cols, fsp._num + 1)
    fsp_alt = fig.add_subplot(frameon=False, position=fsp.get_position(),
                              sharex=fsp, *fsp_alt_args)
    # Set position ....................
    if position.lower() == 'right':
        (inipos, newpos) = ('left', 'right')
    else:
        (inipos, newpos) = ('right', 'left')
    # Force scales tics to one side ...
    fsp.yaxis.set_ticks_position(inipos)
    fsp.yaxis.set_label_position(inipos)
    # Force 2nd ticks to the other side..
    fsp_alt.yaxis.set_ticks_position(newpos)
    fsp_alt.yaxis.set_label_position(newpos)
    # Force period axis scale..........
    if yscale is None:
        yscale = fsp.get_yscale()
        try:
            basey = fsp.yaxis.get_major_locator()._base
        except AttributeError:
            basey = 10.
    fsp_alt.set_yscale(yscale, basey=basey, subsy=subsy)

    pylab.draw_if_interactive()
    return fsp_alt

def set_dlim(subplot, start_date=None, end_date=None):
    """
    Sets the date limits of the plot to ``start_date`` and ``end_date``.
    The dates can be given as :class:`~Period` objects, strings or
    integers.

    Parameters
    ----------
    start_date : {var}
        Starting date of the plot. If None, the current left limit
        (earliest date) is used.
    end_date : {var}
        Ending date of the plot. If None, the current right limit (latest
        date) is used.
    """
    freq = getattr(subplot, 'freq', None)
    if freq is None:
        raise ValueError("Undefined frequency! Date limits can't be set!")
    xleft = get_datevalue(start_date, freq)
    xright = get_datevalue(end_date, freq)
    subplot.set_xlim(xleft, xright)
    return (xleft, xright)

def get_dlim(subplot):
    """
    Returns the limits of the x axis as a :class:`~PeriodIndex`.
    """
    freq = getattr(subplot, 'freq', None)
    xlims = subplot.get_xlim()
    if freq is None:
        return xlims
    return PeriodIndex(xlims, freq=freq)
