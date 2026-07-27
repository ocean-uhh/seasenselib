import logging
from types import SimpleNamespace
import warnings

import numpy as np

from seasenselib.readers import sbe_cnv_reader
from seasenselib.readers.sbe_cnv_reader import SbeCnvReader


CNV_HEADER = "\n".join(
    [
        "# interval = seconds: 15",
        "# start_time = May 04 2026 08:00:01 [Instrument's time stamp, first data scan]",
    ]
)


def _calculate_time_coordinates(xarray_data, max_count=None):
    reader = object.__new__(SbeCnvReader)
    cnv = SimpleNamespace(header=CNV_HEADER, date=None)
    if max_count is None:
        max_count = len(next(iter(xarray_data.values())))
    coords = reader._SbeCnvReader__calculate_time_coordinates(  # noqa: SLF001
        xarray_data,
        cnv,
        max_count,
    )
    return reader, coords


def test_timek_is_used_for_time_coordinate_before_pipeline_mapping():
    data = {
        "temperature": np.arange(4),
        "timeK": np.array(
            [
                831196801.0,
                831196816.0,
                831196832.0,
                831196846.0,
            ]
        ),
    }

    reader, coords = _calculate_time_coordinates(data)

    expected = np.array(
        [
            "2026-05-04T08:00:01",
            "2026-05-04T08:00:16",
            "2026-05-04T08:00:32",
            "2026-05-04T08:00:46",
        ],
        dtype="datetime64[ns]",
    )
    np.testing.assert_array_equal(coords, expected)
    np.testing.assert_array_equal(
        np.diff(coords).astype("timedelta64[s]").astype(int),
        np.array([15, 16, 14]),
    )
    assert reader._time_coordinate_source_name == "timeK"
    assert reader._time_coordinate_source_type == "seconds_since_2000"


def test_times_is_preferred_over_timeq_when_both_are_present():
    data = {
        "timeQ": np.array([831196801.0, 831196801.0, 831196802.0]),
        "timeS": np.array([0.0, 0.5, 1.0]),
    }

    reader, coords = _calculate_time_coordinates(data)

    expected = np.array(
        [
            "2026-05-04T08:00:01",
            "2026-05-04T08:00:01.500000000",
            "2026-05-04T08:00:02",
        ],
        dtype="datetime64[ns]",
    )
    np.testing.assert_array_equal(coords, expected)
    assert reader._time_coordinate_source_name == "timeS"
    assert reader._time_coordinate_source_type == "seconds_since_start_time"


def test_interval_fallback_is_used_only_without_time_source_channel():
    data = {"temperature": np.arange(4)}

    reader, coords = _calculate_time_coordinates(data, max_count=4)

    expected = np.array(
        [
            "2026-05-04T08:00:01",
            "2026-05-04T08:00:16",
            "2026-05-04T08:00:31",
            "2026-05-04T08:00:46",
        ],
        dtype="datetime64[ns]",
    )
    np.testing.assert_array_equal(coords, expected)
    assert reader._time_coordinate_source_name == "start_time + interval"
    assert reader._time_coordinate_source_type == "start_time_plus_interval"


def test_pkg_resources_deprecation_warning_is_suppressed():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with sbe_cnv_reader._suppress_pkg_resources_deprecation():  # noqa: SLF001
            warnings.warn(
                "pkg_resources is deprecated as an API. See setuptools docs.",
                UserWarning,
            )

    assert caught == []


def test_preserve_root_logging_restores_basic_config_changes():
    root_logger = logging.getLogger()
    original_level = root_logger.level
    original_handlers = list(root_logger.handlers)

    try:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
        root_logger.setLevel(logging.WARNING)

        with sbe_cnv_reader._preserve_root_logging():  # noqa: SLF001
            logging.basicConfig(level=logging.INFO)

        assert root_logger.level == logging.WARNING
        assert root_logger.handlers == []
    finally:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
            if handler not in original_handlers:
                handler.close()
        for handler in original_handlers:
            root_logger.addHandler(handler)
        root_logger.setLevel(original_level)


def test_capture_pycnv_stdout_routes_prints_to_debug(caplog, capsys):
    with caplog.at_level(
        logging.DEBUG,
        logger="seasenselib.readers.sbe_cnv_reader",
    ):
        with sbe_cnv_reader._capture_pycnv_stdout():  # noqa: SLF001
            print("Computing date")

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "pycnv stdout: Computing date" in caplog.text


def test_controlled_pycnv_logging_filters_and_restores_logger(caplog):
    pycnv_logger = logging.getLogger("pycnv")
    original_level = pycnv_logger.level
    original_handlers = list(pycnv_logger.handlers)
    original_propagate = pycnv_logger.propagate

    with caplog.at_level(
        logging.DEBUG,
        logger="seasenselib.readers.sbe_cnv_reader",
    ):
        with sbe_cnv_reader._controlled_pycnv_logging(logging.ERROR):  # noqa: SLF001
            pycnv_logger.info("hidden info")
            pycnv_logger.error("visible error")

    assert "hidden info" not in caplog.text
    assert "pycnv: visible error" in caplog.text
    assert pycnv_logger.level == original_level
    assert pycnv_logger.handlers == original_handlers
    assert pycnv_logger.propagate == original_propagate
