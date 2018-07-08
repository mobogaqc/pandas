import pytest

import pandas as pd
import pandas.util.testing as tm
from pandas.util.testing import assert_frame_equal, assert_raises_regex


def test_compression_roundtrip(compression):
    df = pd.DataFrame([[0.123456, 0.234567, 0.567567],
                       [12.32112, 123123.2, 321321.2]],
                      index=['A', 'B'], columns=['X', 'Y', 'Z'])

    with tm.ensure_clean() as path:
        df.to_json(path, compression=compression)
        assert_frame_equal(df, pd.read_json(path,
                                            compression=compression))

        # explicitly ensure file was compressed.
        with tm.decompress_file(path, compression) as fh:
            result = fh.read().decode('utf8')
        assert_frame_equal(df, pd.read_json(result))


def test_read_zipped_json(datapath):
    uncompressed_path = datapath("io", "json", "data", "tsframe_v012.json")
    uncompressed_df = pd.read_json(uncompressed_path)

    compressed_path = datapath("io", "json", "data", "tsframe_v012.json.zip")
    compressed_df = pd.read_json(compressed_path, compression='zip')

    assert_frame_equal(uncompressed_df, compressed_df)


def test_with_s3_url(compression):
    boto3 = pytest.importorskip('boto3')
    pytest.importorskip('s3fs')
    moto = pytest.importorskip('moto')

    df = pd.read_json('{"a": [1, 2, 3], "b": [4, 5, 6]}')
    with moto.mock_s3():
        conn = boto3.resource("s3", region_name="us-east-1")
        bucket = conn.create_bucket(Bucket="pandas-test")

        with tm.ensure_clean() as path:
            df.to_json(path, compression=compression)
            with open(path, 'rb') as f:
                bucket.put_object(Key='test-1', Body=f)

        roundtripped_df = pd.read_json('s3://pandas-test/test-1',
                                       compression=compression)
        assert_frame_equal(df, roundtripped_df)


def test_lines_with_compression(compression):

    with tm.ensure_clean() as path:
        df = pd.read_json('{"a": [1, 2, 3], "b": [4, 5, 6]}')
        df.to_json(path, orient='records', lines=True,
                   compression=compression)
        roundtripped_df = pd.read_json(path, lines=True,
                                       compression=compression)
        assert_frame_equal(df, roundtripped_df)


def test_chunksize_with_compression(compression):

    with tm.ensure_clean() as path:
        df = pd.read_json('{"a": ["foo", "bar", "baz"], "b": [4, 5, 6]}')
        df.to_json(path, orient='records', lines=True,
                   compression=compression)

        res = pd.read_json(path, lines=True, chunksize=1,
                           compression=compression)
        roundtripped_df = pd.concat(res)
        assert_frame_equal(df, roundtripped_df)


def test_write_unsupported_compression_type():
    df = pd.read_json('{"a": [1, 2, 3], "b": [4, 5, 6]}')
    with tm.ensure_clean() as path:
        msg = "Unrecognized compression type: unsupported"
        assert_raises_regex(ValueError, msg, df.to_json,
                            path, compression="unsupported")


def test_read_unsupported_compression_type():
    with tm.ensure_clean() as path:
        msg = "Unrecognized compression type: unsupported"
        assert_raises_regex(ValueError, msg, pd.read_json,
                            path, compression="unsupported")


@pytest.mark.parametrize("to_infer", [True, False])
@pytest.mark.parametrize("read_infer", [True, False])
def test_to_json_compression(compression_only,
                             read_infer, to_infer):
    # see gh-15008
    compression = compression_only

    if compression == "zip":
        pytest.skip("{compression} is not supported "
                    "for to_csv".format(compression=compression))

    # We'll complete file extension subsequently.
    filename = "test."

    if compression == "gzip":
        filename += "gz"
    else:
        # xz --> .xz
        # bz2 --> .bz2
        filename += compression

    df = pd.DataFrame({"A": [1]})

    to_compression = "infer" if to_infer else compression
    read_compression = "infer" if read_infer else compression

    with tm.ensure_clean(filename) as path:
        df.to_json(path, compression=to_compression)
        result = pd.read_json(path, compression=read_compression)
        tm.assert_frame_equal(result, df)
