import calendar
from datetime import datetime, timedelta

import dateutil.tz
from dateutil.tz import tzutc
import numpy as np
import pytest
import pytz

from pandas.errors import OutOfBoundsDatetime

from pandas import Period, Timedelta, Timestamp, compat

from pandas.tseries import offsets


class TestTimestampConstructors:
    def test_constructor(self):
        base_str = "2014-07-01 09:00"
        base_dt = datetime(2014, 7, 1, 9)
        base_expected = 1_404_205_200_000_000_000

        # confirm base representation is correct
        assert calendar.timegm(base_dt.timetuple()) * 1_000_000_000 == base_expected

        tests = [
            (base_str, base_dt, base_expected),
            (
                "2014-07-01 10:00",
                datetime(2014, 7, 1, 10),
                base_expected + 3600 * 1_000_000_000,
            ),
            (
                "2014-07-01 09:00:00.000008000",
                datetime(2014, 7, 1, 9, 0, 0, 8),
                base_expected + 8000,
            ),
            (
                "2014-07-01 09:00:00.000000005",
                Timestamp("2014-07-01 09:00:00.000000005"),
                base_expected + 5,
            ),
        ]

        timezones = [
            (None, 0),
            ("UTC", 0),
            (pytz.utc, 0),
            ("Asia/Tokyo", 9),
            ("US/Eastern", -4),
            ("dateutil/US/Pacific", -7),
            (pytz.FixedOffset(-180), -3),
            (dateutil.tz.tzoffset(None, 18000), 5),
        ]

        for date_str, date, expected in tests:
            for result in [Timestamp(date_str), Timestamp(date)]:
                # only with timestring
                assert result.value == expected

                # re-creation shouldn't affect to internal value
                result = Timestamp(result)
                assert result.value == expected

            # with timezone
            for tz, offset in timezones:
                for result in [Timestamp(date_str, tz=tz), Timestamp(date, tz=tz)]:
                    expected_tz = expected - offset * 3600 * 1_000_000_000
                    assert result.value == expected_tz

                    # should preserve tz
                    result = Timestamp(result)
                    assert result.value == expected_tz

                    # should convert to UTC
                    if tz is not None:
                        result = Timestamp(result).tz_convert("UTC")
                    else:
                        result = Timestamp(result, tz="UTC")
                    expected_utc = expected - offset * 3600 * 1_000_000_000
                    assert result.value == expected_utc

    def test_constructor_with_stringoffset(self):
        # GH 7833
        base_str = "2014-07-01 11:00:00+02:00"
        base_dt = datetime(2014, 7, 1, 9)
        base_expected = 1_404_205_200_000_000_000

        # confirm base representation is correct
        assert calendar.timegm(base_dt.timetuple()) * 1_000_000_000 == base_expected

        tests = [
            (base_str, base_expected),
            ("2014-07-01 12:00:00+02:00", base_expected + 3600 * 1_000_000_000),
            ("2014-07-01 11:00:00.000008000+02:00", base_expected + 8000),
            ("2014-07-01 11:00:00.000000005+02:00", base_expected + 5),
        ]

        timezones = [
            (None, 0),
            ("UTC", 0),
            (pytz.utc, 0),
            ("Asia/Tokyo", 9),
            ("US/Eastern", -4),
            ("dateutil/US/Pacific", -7),
            (pytz.FixedOffset(-180), -3),
            (dateutil.tz.tzoffset(None, 18000), 5),
        ]

        for date_str, expected in tests:
            for result in [Timestamp(date_str)]:
                # only with timestring
                assert result.value == expected

                # re-creation shouldn't affect to internal value
                result = Timestamp(result)
                assert result.value == expected

            # with timezone
            for tz, offset in timezones:
                result = Timestamp(date_str, tz=tz)
                expected_tz = expected
                assert result.value == expected_tz

                # should preserve tz
                result = Timestamp(result)
                assert result.value == expected_tz

                # should convert to UTC
                result = Timestamp(result).tz_convert("UTC")
                expected_utc = expected
                assert result.value == expected_utc

        # This should be 2013-11-01 05:00 in UTC
        # converted to Chicago tz
        result = Timestamp("2013-11-01 00:00:00-0500", tz="America/Chicago")
        assert result.value == Timestamp("2013-11-01 05:00").value
        expected = "Timestamp('2013-11-01 00:00:00-0500', tz='America/Chicago')"  # noqa
        assert repr(result) == expected
        assert result == eval(repr(result))

        # This should be 2013-11-01 05:00 in UTC
        # converted to Tokyo tz (+09:00)
        result = Timestamp("2013-11-01 00:00:00-0500", tz="Asia/Tokyo")
        assert result.value == Timestamp("2013-11-01 05:00").value
        expected = "Timestamp('2013-11-01 14:00:00+0900', tz='Asia/Tokyo')"
        assert repr(result) == expected
        assert result == eval(repr(result))

        # GH11708
        # This should be 2015-11-18 10:00 in UTC
        # converted to Asia/Katmandu
        result = Timestamp("2015-11-18 15:45:00+05:45", tz="Asia/Katmandu")
        assert result.value == Timestamp("2015-11-18 10:00").value
        expected = "Timestamp('2015-11-18 15:45:00+0545', tz='Asia/Katmandu')"
        assert repr(result) == expected
        assert result == eval(repr(result))

        # This should be 2015-11-18 10:00 in UTC
        # converted to Asia/Kolkata
        result = Timestamp("2015-11-18 15:30:00+05:30", tz="Asia/Kolkata")
        assert result.value == Timestamp("2015-11-18 10:00").value
        expected = "Timestamp('2015-11-18 15:30:00+0530', tz='Asia/Kolkata')"
        assert repr(result) == expected
        assert result == eval(repr(result))

    def test_constructor_invalid(self):
        with pytest.raises(TypeError, match="Cannot convert input"):
            Timestamp(slice(2))
        with pytest.raises(ValueError, match="Cannot convert Period"):
            Timestamp(Period("1000-01-01"))

    def test_constructor_invalid_tz(self):
        # GH#17690
        with pytest.raises(TypeError, match="must be a datetime.tzinfo"):
            Timestamp("2017-10-22", tzinfo="US/Eastern")

        with pytest.raises(ValueError, match="at most one of"):
            Timestamp("2017-10-22", tzinfo=pytz.utc, tz="UTC")

        with pytest.raises(ValueError, match="Invalid frequency:"):
            # GH#5168
            # case where user tries to pass tz as an arg, not kwarg, gets
            # interpreted as a `freq`
            Timestamp("2012-01-01", "US/Pacific")

    def test_constructor_strptime(self):
        # GH25016
        # Test support for Timestamp.strptime
        fmt = "%Y%m%d-%H%M%S-%f%z"
        ts = "20190129-235348-000001+0000"
        with pytest.raises(NotImplementedError):
            Timestamp.strptime(ts, fmt)

    def test_constructor_tz_or_tzinfo(self):
        # GH#17943, GH#17690, GH#5168
        stamps = [
            Timestamp(year=2017, month=10, day=22, tz="UTC"),
            Timestamp(year=2017, month=10, day=22, tzinfo=pytz.utc),
            Timestamp(year=2017, month=10, day=22, tz=pytz.utc),
            Timestamp(datetime(2017, 10, 22), tzinfo=pytz.utc),
            Timestamp(datetime(2017, 10, 22), tz="UTC"),
            Timestamp(datetime(2017, 10, 22), tz=pytz.utc),
        ]
        assert all(ts == stamps[0] for ts in stamps)

    def test_constructor_positional(self):
        # see gh-10758
        with pytest.raises(TypeError):
            Timestamp(2000, 1)
        with pytest.raises(ValueError):
            Timestamp(2000, 0, 1)
        with pytest.raises(ValueError):
            Timestamp(2000, 13, 1)
        with pytest.raises(ValueError):
            Timestamp(2000, 1, 0)
        with pytest.raises(ValueError):
            Timestamp(2000, 1, 32)

        # see gh-11630
        assert repr(Timestamp(2015, 11, 12)) == repr(Timestamp("20151112"))
        assert repr(Timestamp(2015, 11, 12, 1, 2, 3, 999999)) == repr(
            Timestamp("2015-11-12 01:02:03.999999")
        )

    def test_constructor_keyword(self):
        # GH 10758
        with pytest.raises(TypeError):
            Timestamp(year=2000, month=1)
        with pytest.raises(ValueError):
            Timestamp(year=2000, month=0, day=1)
        with pytest.raises(ValueError):
            Timestamp(year=2000, month=13, day=1)
        with pytest.raises(ValueError):
            Timestamp(year=2000, month=1, day=0)
        with pytest.raises(ValueError):
            Timestamp(year=2000, month=1, day=32)

        assert repr(Timestamp(year=2015, month=11, day=12)) == repr(
            Timestamp("20151112")
        )

        assert repr(
            Timestamp(
                year=2015,
                month=11,
                day=12,
                hour=1,
                minute=2,
                second=3,
                microsecond=999999,
            )
        ) == repr(Timestamp("2015-11-12 01:02:03.999999"))

    def test_constructor_fromordinal(self):
        base = datetime(2000, 1, 1)

        ts = Timestamp.fromordinal(base.toordinal(), freq="D")
        assert base == ts
        assert ts.freq == "D"
        assert base.toordinal() == ts.toordinal()

        ts = Timestamp.fromordinal(base.toordinal(), tz="US/Eastern")
        assert Timestamp("2000-01-01", tz="US/Eastern") == ts
        assert base.toordinal() == ts.toordinal()

        # GH#3042
        dt = datetime(2011, 4, 16, 0, 0)
        ts = Timestamp.fromordinal(dt.toordinal())
        assert ts.to_pydatetime() == dt

        # with a tzinfo
        stamp = Timestamp("2011-4-16", tz="US/Eastern")
        dt_tz = stamp.to_pydatetime()
        ts = Timestamp.fromordinal(dt_tz.toordinal(), tz="US/Eastern")
        assert ts.to_pydatetime() == dt_tz

    @pytest.mark.parametrize(
        "result",
        [
            Timestamp(datetime(2000, 1, 2, 3, 4, 5, 6), nanosecond=1),
            Timestamp(
                year=2000,
                month=1,
                day=2,
                hour=3,
                minute=4,
                second=5,
                microsecond=6,
                nanosecond=1,
            ),
            Timestamp(
                year=2000,
                month=1,
                day=2,
                hour=3,
                minute=4,
                second=5,
                microsecond=6,
                nanosecond=1,
                tz="UTC",
            ),
            Timestamp(2000, 1, 2, 3, 4, 5, 6, 1, None),
            Timestamp(2000, 1, 2, 3, 4, 5, 6, 1, pytz.UTC),
        ],
    )
    def test_constructor_nanosecond(self, result):
        # GH 18898
        expected = Timestamp(datetime(2000, 1, 2, 3, 4, 5, 6), tz=result.tz)
        expected = expected + Timedelta(nanoseconds=1)
        assert result == expected

    @pytest.mark.parametrize("z", ["Z0", "Z00"])
    def test_constructor_invalid_Z0_isostring(self, z):
        # GH 8910
        with pytest.raises(ValueError):
            Timestamp("2014-11-02 01:00{}".format(z))

    @pytest.mark.parametrize(
        "arg",
        [
            "year",
            "month",
            "day",
            "hour",
            "minute",
            "second",
            "microsecond",
            "nanosecond",
        ],
    )
    def test_invalid_date_kwarg_with_string_input(self, arg):
        kwarg = {arg: 1}
        with pytest.raises(ValueError):
            Timestamp("2010-10-10 12:59:59.999999999", **kwarg)

    def test_out_of_bounds_integer_value(self):
        # GH#26651 check that we raise OutOfBoundsDatetime, not OverflowError
        with pytest.raises(OutOfBoundsDatetime):
            Timestamp(Timestamp.max.value * 2)
        with pytest.raises(OutOfBoundsDatetime):
            Timestamp(Timestamp.min.value * 2)

    def test_out_of_bounds_value(self):
        one_us = np.timedelta64(1).astype("timedelta64[us]")

        # By definition we can't go out of bounds in [ns], so we
        # convert the datetime64s to [us] so we can go out of bounds
        min_ts_us = np.datetime64(Timestamp.min).astype("M8[us]")
        max_ts_us = np.datetime64(Timestamp.max).astype("M8[us]")

        # No error for the min/max datetimes
        Timestamp(min_ts_us)
        Timestamp(max_ts_us)

        # One us less than the minimum is an error
        with pytest.raises(ValueError):
            Timestamp(min_ts_us - one_us)

        # One us more than the maximum is an error
        with pytest.raises(ValueError):
            Timestamp(max_ts_us + one_us)

    def test_out_of_bounds_string(self):
        with pytest.raises(ValueError):
            Timestamp("1676-01-01")
        with pytest.raises(ValueError):
            Timestamp("2263-01-01")

    def test_barely_out_of_bounds(self):
        # GH#19529
        # GH#19382 close enough to bounds that dropping nanos would result
        # in an in-bounds datetime
        with pytest.raises(OutOfBoundsDatetime):
            Timestamp("2262-04-11 23:47:16.854775808")

    def test_bounds_with_different_units(self):
        out_of_bounds_dates = ("1677-09-21", "2262-04-12")

        time_units = ("D", "h", "m", "s", "ms", "us")

        for date_string in out_of_bounds_dates:
            for unit in time_units:
                dt64 = np.datetime64(date_string, unit)
                with pytest.raises(ValueError):
                    Timestamp(dt64)

        in_bounds_dates = ("1677-09-23", "2262-04-11")

        for date_string in in_bounds_dates:
            for unit in time_units:
                dt64 = np.datetime64(date_string, unit)
                Timestamp(dt64)

    def test_min_valid(self):
        # Ensure that Timestamp.min is a valid Timestamp
        Timestamp(Timestamp.min)

    def test_max_valid(self):
        # Ensure that Timestamp.max is a valid Timestamp
        Timestamp(Timestamp.max)

    def test_now(self):
        # GH#9000
        ts_from_string = Timestamp("now")
        ts_from_method = Timestamp.now()
        ts_datetime = datetime.now()

        ts_from_string_tz = Timestamp("now", tz="US/Eastern")
        ts_from_method_tz = Timestamp.now(tz="US/Eastern")

        # Check that the delta between the times is less than 1s (arbitrarily
        # small)
        delta = Timedelta(seconds=1)
        assert abs(ts_from_method - ts_from_string) < delta
        assert abs(ts_datetime - ts_from_method) < delta
        assert abs(ts_from_method_tz - ts_from_string_tz) < delta
        assert (
            abs(
                ts_from_string_tz.tz_localize(None)
                - ts_from_method_tz.tz_localize(None)
            )
            < delta
        )

    def test_today(self):
        ts_from_string = Timestamp("today")
        ts_from_method = Timestamp.today()
        ts_datetime = datetime.today()

        ts_from_string_tz = Timestamp("today", tz="US/Eastern")
        ts_from_method_tz = Timestamp.today(tz="US/Eastern")

        # Check that the delta between the times is less than 1s (arbitrarily
        # small)
        delta = Timedelta(seconds=1)
        assert abs(ts_from_method - ts_from_string) < delta
        assert abs(ts_datetime - ts_from_method) < delta
        assert abs(ts_from_method_tz - ts_from_string_tz) < delta
        assert (
            abs(
                ts_from_string_tz.tz_localize(None)
                - ts_from_method_tz.tz_localize(None)
            )
            < delta
        )

    @pytest.mark.parametrize("tz", [None, pytz.timezone("US/Pacific")])
    def test_disallow_setting_tz(self, tz):
        # GH 3746
        ts = Timestamp("2010")
        with pytest.raises(AttributeError):
            ts.tz = tz

    @pytest.mark.parametrize("offset", ["+0300", "+0200"])
    def test_construct_timestamp_near_dst(self, offset):
        # GH 20854
        expected = Timestamp(
            "2016-10-30 03:00:00{}".format(offset), tz="Europe/Helsinki"
        )
        result = Timestamp(expected).tz_convert("Europe/Helsinki")
        assert result == expected

    @pytest.mark.parametrize(
        "arg", ["2013/01/01 00:00:00+09:00", "2013-01-01 00:00:00+09:00"]
    )
    def test_construct_with_different_string_format(self, arg):
        # GH 12064
        result = Timestamp(arg)
        expected = Timestamp(datetime(2013, 1, 1), tz=pytz.FixedOffset(540))
        assert result == expected

    def test_construct_timestamp_preserve_original_frequency(self):
        # GH 22311
        result = Timestamp(Timestamp("2010-08-08", freq="D")).freq
        expected = offsets.Day()
        assert result == expected

    def test_constructor_invalid_frequency(self):
        # GH 22311
        with pytest.raises(ValueError, match="Invalid frequency:"):
            Timestamp("2012-01-01", freq=[])

    @pytest.mark.parametrize("box", [datetime, Timestamp])
    def test_raise_tz_and_tzinfo_in_datetime_input(self, box):
        # GH 23579
        kwargs = {"year": 2018, "month": 1, "day": 1, "tzinfo": pytz.utc}
        with pytest.raises(ValueError, match="Cannot pass a datetime or Timestamp"):
            Timestamp(box(**kwargs), tz="US/Pacific")
        with pytest.raises(ValueError, match="Cannot pass a datetime or Timestamp"):
            Timestamp(box(**kwargs), tzinfo=pytz.timezone("US/Pacific"))

    def test_dont_convert_dateutil_utc_to_pytz_utc(self):
        result = Timestamp(datetime(2018, 1, 1), tz=tzutc())
        expected = Timestamp(datetime(2018, 1, 1)).tz_localize(tzutc())
        assert result == expected

    def test_constructor_subclassed_datetime(self):
        # GH 25851
        # ensure that subclassed datetime works for
        # Timestamp creation
        class SubDatetime(datetime):
            pass

        data = SubDatetime(2000, 1, 1)
        result = Timestamp(data)
        expected = Timestamp(2000, 1, 1)
        assert result == expected

    @pytest.mark.skipif(
        not compat.PY38,
        reason="datetime.fromisocalendar was added in Python version 3.8",
    )
    def test_constructor_fromisocalendar(self):
        # GH 30395
        expected_timestamp = Timestamp("2000-01-03 00:00:00")
        expected_stdlib = datetime.fromisocalendar(2000, 1, 1)
        result = Timestamp.fromisocalendar(2000, 1, 1)
        assert result == expected_timestamp
        assert result == expected_stdlib
        assert isinstance(result, Timestamp)


def test_constructor_ambigous_dst():
    # GH 24329
    # Make sure that calling Timestamp constructor
    # on Timestamp created from ambiguous time
    # doesn't change Timestamp.value
    ts = Timestamp(1382835600000000000, tz="dateutil/Europe/London")
    expected = ts.value
    result = Timestamp(ts).value
    assert result == expected


@pytest.mark.parametrize("epoch", [1552211999999999872, 1552211999999999999])
def test_constructor_before_dst_switch(epoch):
    # GH 31043
    # Make sure that calling Timestamp constructor
    # on time just before DST switch doesn't lead to
    # nonexistent time or value change
    ts = Timestamp(epoch, tz="dateutil/America/Los_Angeles")
    result = ts.tz.dst(ts)
    expected = timedelta(seconds=0)
    assert Timestamp(ts).value == epoch
    assert result == expected


def test_timestamp_constructor_identity():
    # Test for #30543
    expected = Timestamp("2017-01-01T12")
    result = Timestamp(expected)
    assert result is expected
