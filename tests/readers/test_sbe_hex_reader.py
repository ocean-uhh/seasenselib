from __future__ import annotations

import json
import numpy as np
import pytest
import xarray as xr

import gsw

from seasenselib.readers.sbe_hex_reader import (
    SbeHexReader,
    _read_hex_file_fast,
    _select_sbe37_instrument_type,
    channel_of,
    detect_sbe_hex_family,
    detect_sbe_hex_layout,
    parse_hex_header_sensors,
    parse_hex_header_sbe911,
    read_xmlcon,
    sbe911_hex_reader,
)

_FIXTURE_DIR = "tests/readers/fixtures"
_MIXSED2_HEX = f"{_FIXTURE_DIR}/MIXSED2_000.hex"
_MIXSED2_XMLCON = f"{_FIXTURE_DIR}/MIXSED2_000.xmlcon"
_MSM_HEX = f"{_FIXTURE_DIR}/msm_142_1_056_short.hex"
_MSM_XMLCON = f"{_FIXTURE_DIR}/MSM_142_1_056.XMLCON"


def _seabird_instrument_data():
    return pytest.importorskip("seabirdscientific.instrument_data")


def test_sbe_hex_reader_exposes_format_metadata():
    assert SbeHexReader.format_key() == "sbe-hex"
    assert SbeHexReader.format_name() == "SeaBird SBE HEX"
    assert SbeHexReader.file_extension() == ".hex"
    assert SbeHexReader._get_valid_extensions() == (".hex",)


def test_sbe_hex_reader_loads_through_wrapped_function(tmp_path, monkeypatch):
    hex_file = tmp_path / "microcat.hex"
    hex_file.write_text("* header\n000000\n", encoding="utf-8")
    expected = xr.Dataset(
        {"temp": ("time", np.array([1.0, 2.0]))},
        coords={
            "time": np.array(
                ["2024-01-01", "2024-01-02"], dtype="datetime64[ns]"
            )
        },
    )
    calls = []

    def fake_sbe37_hex_reader(input_file, **kwargs):
        calls.append((input_file, kwargs))
        return expected

    monkeypatch.setattr(
        "seasenselib.readers.sbe_hex_reader.sbe37_hex_reader",
        fake_sbe37_hex_reader,
    )

    reader = SbeHexReader(str(hex_file), perform_default_postprocessing=False)

    assert reader.data is expected
    assert calls == [
        (
            str(hex_file),
            {
                "instrument_type": None,
                "moored_mode": False,
                "is_shallow": True,
                "frequency_channels_suppressed": 0,
                "voltage_words_suppressed": 0,
                "header_info": {
                    "enabled_sensors": [],
                    "calibration_coefficients": {},
                    "device_type": None,
                    "sample_length": None,
                    "tx_real_time": None,
                    "reference_pressure": None,
                    "output_flags": {},
                },
                "xmlcon_info": None,
                "xmlcon_path": None,
                "create_pressure_from_reference_pressure": False,
            },
        )
    ]


def test_sbe_hex_reader_passes_decoder_options(tmp_path, monkeypatch):
    hex_file = tmp_path / "microcat.hex"
    hex_file.write_text("* header\n000000\n", encoding="utf-8")
    expected = xr.Dataset(
        {"temp": ("time", np.array([1.0]))},
        coords={"time": np.array(["2024-01-01"], dtype="datetime64[ns]")},
    )
    calls = []

    def fake_sbe37_hex_reader(input_file, **kwargs):
        calls.append((input_file, kwargs))
        return expected

    monkeypatch.setattr(
        "seasenselib.readers.sbe_hex_reader.sbe37_hex_reader",
        fake_sbe37_hex_reader,
    )

    reader = SbeHexReader(
        str(hex_file),
        perform_default_postprocessing=False,
        instrument_type="SBE37SMP",
        moored_mode=True,
    )

    assert reader.data is expected
    assert calls[0][1]["instrument_type"] == "SBE37SMP"
    assert calls[0][1]["moored_mode"] is True


def test_parse_hex_header_sensors_detects_sensors_and_coefficients(tmp_path):
    hex_file = tmp_path / "microcat.hex"
    hex_file.write_text(
        "\n".join(
            [
                "*<Sensor id='Temperature'/>",
                "*<Sensor id='Conductivity'/>",
                "*<Sensor id='Pressure'/>",
                '*<HardwareData DeviceType="SBE37SMP-ODO" SerialNumber="1">',
                '*  <Sensor id="Oxygen"/>',
                "*</HardwareData>",
                "*<SampleLength>21</SampleLength>",
                "*<TxRealTime>yes</TxRealTime>",
                "*<ReferencePressure>8.740000e+02</ReferencePressure>",
                "*<CalibrationCoefficients>",
                "*  <Calibration id='Temperature' format='TEMP'>",
                "*    <A0>1.0</A0>",
                "*    <A1>2.0</A1>",
                "*  </Calibration>",
                "*  <Calibration id='Conductivity' format='COND'>",
                "*    <G>3.0</G>",
                "*    <PCOR>4.0</PCOR>",
                "*  </Calibration>",
                "*</CalibrationCoefficients>",
                "000000",
            ]
        ),
        encoding="utf-8",
    )

    info = parse_hex_header_sensors(hex_file)

    assert info["enabled_sensors"] == [
        "temperature",
        "conductivity",
        "pressure",
        "oxygen",
    ]
    assert info["device_type"] == "SBE37SMP-ODO"
    assert info["sample_length"] == 21
    assert info["tx_real_time"] is True
    assert info["reference_pressure"] == 874.0
    assert (
        info["calibration_coefficients"]["temperature"]["coefficients"]["a0"] == 1.0
    )
    assert info["calibration_coefficients"]["conductivity"]["coefficients"]["g"] == 3.0
    assert (
        info["calibration_coefficients"]["conductivity"]["coefficients"]["cpcor"]
        == 4.0
    )


def test_sbe_hex_reader_preserves_header_calibration_in_raw_metadata(
    tmp_path,
    monkeypatch,
):
    hex_file = tmp_path / "microcat.hex"
    hex_file.write_text(
        "\n".join(
            [
                "* Sea-Bird SBE37SM-RS232 Data File:",
                '*<HardwareData DeviceType="SBE37SM-RS232" SerialNumber="03725586">',
                '*  <Sensor id="Temperature"/>',
                '*  <Sensor id="Conductivity"/>',
                "*</HardwareData>",
                "*<SampleLength>10</SampleLength>",
                "*<TxRealTime>yes</TxRealTime>",
                "*<OutputTemperature>yes</OutputTemperature>",
                "*<OutputConductivity>yes</OutputConductivity>",
                "*<CalibrationCoefficients>",
                '*  <Calibration id="Temperature" format="TEMP1">',
                "*    <SerialNum>03725586</SerialNum>",
                "*    <CalDate>12-Feb-23</CalDate>",
                "*    <A0>-1.074513e-04</A0>",
                "*    <A1>3.084169e-04</A1>",
                "*    <A2>-4.679346e-06</A2>",
                "*    <A3>2.069519e-07</A3>",
                "*  </Calibration>",
                '*  <Calibration id="Conductivity" format="WBCOND0">',
                "*    <SerialNum>03725586</SerialNum>",
                "*    <CalDate>12-Feb-23</CalDate>",
                "*    <G>-1.005547e+00</G>",
                "*    <H>1.500570e-01</H>",
                "*    <I>-4.063591e-04</I>",
                "*    <J>5.294997e-05</J>",
                "*    <PCOR>-9.570000e-08</PCOR>",
                "*    <TCOR>3.250000e-06</TCOR>",
                "*    <WBOTC>-9.634356e-08</WBOTC>",
                "*  </Calibration>",
                "*</CalibrationCoefficients>",
                "*END*",
                "03DA5C0A22C8318B0E81",
            ]
        ),
        encoding="utf-8",
    )
    expected = xr.Dataset(
        {
            "temp": ("time", np.array([1.0])),
            "cond": ("time", np.array([2.0])),
        },
        coords={"time": np.array(["2024-01-01"], dtype="datetime64[ns]")},
    )
    expected["temp"].attrs["units"] = "degrees_C"
    expected["cond"].attrs["units"] = "mS/cm"

    def fake_sbe37_hex_reader(input_file, **kwargs):
        return expected

    monkeypatch.setattr(
        "seasenselib.readers.sbe_hex_reader.sbe37_hex_reader",
        fake_sbe37_hex_reader,
    )

    ds = SbeHexReader(str(hex_file)).data

    payload = json.loads(ds.attrs["raw_metadata"])
    assert "A0" in payload["blocks"]["header"]
    assert payload["blocks"]["attributes"]["device_type"] == "SBE37SM-RS232"
    assert payload["blocks"]["attributes"]["enabled_sensors"] == [
        "temperature",
        "conductivity",
    ]
    assert payload["blocks"]["configuration"]["output_flags"] == {
        "OutputTemperature": True,
        "OutputConductivity": True,
    }
    calibration = payload["blocks"]["calibration"]["hex_header"]
    assert calibration["temperature"]["format"] == "TEMP1"
    assert calibration["temperature"]["serial_number"] == "03725586"
    assert calibration["temperature"]["calibration_date"] == "12-Feb-23"
    assert calibration["temperature"]["coefficients"]["a0"] == -1.074513e-04
    assert calibration["conductivity"]["coefficients"]["g"] == -1.005547
    assert payload["variables"]["temp"]["sensor_type"] == "temperature"
    assert payload["variables"]["temp"]["serial_number"] == "03725586"
    assert payload["variables"]["cond"]["sensor_type"] == "conductivity"


def test_sbe_hex_reader_preserves_companion_xmlcon_calibration(
    tmp_path,
    monkeypatch,
):
    hex_file = tmp_path / "microcat.hex"
    hex_file.write_text(
        "\n".join(
            [
                "*<Sensor id='Temperature'/>",
                "*<SampleLength>10</SampleLength>",
                "*<TxRealTime>yes</TxRealTime>",
                "*END*",
                "03DA5C0A22C8318B0E81",
            ]
        ),
        encoding="utf-8",
    )
    xmlcon_file = tmp_path / "microcat.xmlcon"
    xmlcon_file.write_text(
        "\n".join(
            [
                '<?xml version="1.0" encoding="UTF-8"?>',
                "<SBE_InstrumentConfiguration>",
                "  <Instrument>",
                '    <SensorArray Size="1">',
                '      <Sensor index="0" SensorID="58">',
                '        <TemperatureSensor SensorID="58">',
                "          <SerialNumber>13840</SerialNumber>",
                "          <CalibrationDate>27-Aug-15</CalibrationDate>",
                "          <A0>-1.48631100e-004</A0>",
                "          <A1>3.12384300e-004</A1>",
                "          <A2>-4.72688900e-006</A2>",
                "          <A3>2.06721200e-007</A3>",
                "          <Slope>1.00000000</Slope>",
                "          <Offset>0.0000</Offset>",
                "        </TemperatureSensor>",
                "      </Sensor>",
                "    </SensorArray>",
                "  </Instrument>",
                "</SBE_InstrumentConfiguration>",
            ]
        ),
        encoding="utf-8",
    )
    expected = xr.Dataset(
        {"temp": ("time", np.array([1.0]))},
        coords={"time": np.array(["2024-01-01"], dtype="datetime64[ns]")},
    )
    expected["temp"].attrs["units"] = "degrees_C"

    def fake_sbe37_hex_reader(input_file, **kwargs):
        return expected

    monkeypatch.setattr(
        "seasenselib.readers.sbe_hex_reader.sbe37_hex_reader",
        fake_sbe37_hex_reader,
    )

    ds = SbeHexReader(str(hex_file)).data

    payload = json.loads(ds.attrs["raw_metadata"])
    assert payload["blocks"]["attributes"]["xmlcon_file"] == str(xmlcon_file)
    xmlcon_calibration = payload["blocks"]["calibration"]["xmlcon"]
    assert xmlcon_calibration["temperature"]["serial_number"] == "13840"
    assert xmlcon_calibration["temperature"]["calibration_date"] == "27-Aug-15"
    assert xmlcon_calibration["temperature"]["coefficients"]["a0"] == -1.486311e-4
    assert xmlcon_calibration["temperature"]["metadata"] == {
        "slope": 1.0,
        "offset": 0.0,
    }


def test_select_sbe37_instrument_type_from_header_and_override():
    id = _seabird_instrument_data()

    assert (
        _select_sbe37_instrument_type(id, device_type="SBE37SMP-ODO")
        == id.InstrumentType.SBE37SMPODO
    )
    assert (
        _select_sbe37_instrument_type(id, instrument_type="SBE37IMP")
        == id.InstrumentType.SBE37IMP
    )


def test_detect_sbe_hex_layout_names_current_format0_temp_cond_layout():
    id = _seabird_instrument_data()

    layout = detect_sbe_hex_layout(
        {
            "device_type": "SBE37SM-RS232",
            "sample_length": 10,
            "tx_real_time": True,
        },
        ["temperature", "conductivity"],
        id.InstrumentType.SBE37SM,
    )

    assert layout.name == "sbe37_format0_temp_cond_time"
    assert layout.decoder_backend == "seabirdscientific.read_hex"
    assert layout.expected_hex_chars == 20
    assert [field.name for field in layout.fields] == [
        "temperature",
        "conductivity",
        "date time",
    ]


def test_detect_sbe_hex_layout_accepts_non_realtime_matching_row_layout():
    id = _seabird_instrument_data()

    layout = detect_sbe_hex_layout(
        {
            "device_type": "SBE37SM-RS232",
            "sample_length": 10,
            "tx_real_time": False,
        },
        ["temperature", "conductivity"],
        id.InstrumentType.SBE37SM,
    )

    assert layout.name == "sbe37_format0_temp_cond_time"
    assert layout.expected_hex_chars == 20


def test_sbe_hex_reader_can_create_pressure_from_reference_pressure(tmp_path):
    _seabird_instrument_data()

    hex_file = tmp_path / "microcat.hex"
    hex_file.write_text(
        "\n".join(
            [
                "* Sea-Bird SBE37SM-RS232 Data File:",
                '*<HardwareData DeviceType="SBE37SM-RS232" SerialNumber="03706105">',
                '*  <Sensor id="Temperature"/>',
                '*  <Sensor id="Conductivity"/>',
                "*</HardwareData>",
                "*<SampleLength>10</SampleLength>",
                "*<TxRealTime>no</TxRealTime>",
                "*<ReferencePressure>8.740000e+02</ReferencePressure>",
                "*<CalibrationCoefficients>",
                '*  <Calibration id="Temperature" format="TEMP1">',
                "*    <A0>7.623170e-05</A0>",
                "*    <A1>2.609968e-04</A1>",
                "*    <A2>-1.417782e-06</A2>",
                "*    <A3>1.248235e-07</A3>",
                "*  </Calibration>",
                '*  <Calibration id="Conductivity" format="WBCOND0">',
                "*    <G>-1.010095e+00</G>",
                "*    <H>1.329295e-01</H>",
                "*    <I>-1.301659e-04</I>",
                "*    <J>2.642814e-05</J>",
                "*    <PCOR>-9.570000e-08</PCOR>",
                "*    <TCOR>3.250000e-06</TCOR>",
                "*    <WBOTC>2.416966e-07</WBOTC>",
                "*  </Calibration>",
                "*</CalibrationCoefficients>",
                "*END*",
                "0914DE168CE931E4B481",
            ]
        ),
        encoding="utf-8",
    )

    without_reference_pressure = SbeHexReader(
        str(hex_file),
        perform_default_postprocessing=False,
    ).data
    with_reference_pressure = SbeHexReader(
        str(hex_file),
        perform_default_postprocessing=False,
        create_pressure_from_reference_pressure=True,
    ).data

    assert "press" not in without_reference_pressure
    assert "press" in with_reference_pressure
    assert with_reference_pressure["press"].values.tolist() == [874.0]
    assert (
        with_reference_pressure["press"].attrs["sensor_source_basis"]
        == "sbe_header_reference_pressure"
    )
    assert abs(float(with_reference_pressure["cond"].values[0]) - 3.424520) < 1e-5
    assert abs(float(without_reference_pressure["cond"].values[0]) - 3.424520) > 1e-4


def test_read_hex_file_fast_uses_seabird_line_decoder(tmp_path):
    id = _seabird_instrument_data()

    hex_file = tmp_path / "microcat.hex"
    hex_file.write_text(
        "\n".join(
            [
                "* header",
                "*END*",
                "03DA5C0A22C8318B0E81",
                "03DA0C0A22C6318B0E90",
            ]
        ),
        encoding="utf-8",
    )

    raw = _read_hex_file_fast(
        hex_file,
        instrument_type=id.InstrumentType.SBE37SM,
        enabled_sensors=[id.Sensors.Temperature, id.Sensors.Conductivity],
    )

    assert list(raw.columns) == ["temperature", "conductivity", "date time"]
    assert len(raw) == 2
    assert raw["temperature"].tolist() == [252508, 252428]


def test_read_hex_file_fast_validates_detected_layout_length(tmp_path):
    id = _seabird_instrument_data()

    hex_file = tmp_path / "microcat.hex"
    hex_file.write_text(
        "\n".join(
            [
                "* header",
                "*END*",
                "03DA5C0A22C8318B0E8",
            ]
        ),
        encoding="utf-8",
    )
    layout = detect_sbe_hex_layout(
        {"sample_length": 10, "tx_real_time": True},
        ["temperature", "conductivity"],
        id.InstrumentType.SBE37SM,
    )

    with pytest.raises(ValueError, match="sbe37_format0_temp_cond_time"):
        _read_hex_file_fast(
            hex_file,
            instrument_type=id.InstrumentType.SBE37SM,
            enabled_sensors=[id.Sensors.Temperature, id.Sensors.Conductivity],
            layout=layout,
        )


# ---------------------------------------------------------------------------
# SBE 911+ tests
# ---------------------------------------------------------------------------


def test_detect_sbe_hex_family_returns_sbe37_for_microcat(tmp_path):
    hex_file = tmp_path / "micro.hex"
    hex_file.write_text("* Sea-Bird SBE37SM-RS232 Data File:\n000000\n")
    assert detect_sbe_hex_family(hex_file) == "sbe37"


def test_detect_sbe_hex_family_returns_sbe911plus_for_sbe9_header(tmp_path):
    hex_file = tmp_path / "cast.hex"
    hex_file.write_text("* Sea-Bird SBE 9 Data File:\n000000\n")
    assert detect_sbe_hex_family(hex_file) == "sbe911plus"


def test_detect_sbe_hex_family_on_real_mixsed2_fixture():
    assert detect_sbe_hex_family(_MIXSED2_HEX) == "sbe911plus"


def test_parse_hex_header_sbe911_extracts_core_fields():
    info = parse_hex_header_sbe911(_MIXSED2_HEX)
    assert info["bytes_per_scan"] == 37
    assert info["voltage_words"] == 4
    assert info["scans_averaged"] == 1
    assert abs(info["sample_interval"] - 1 / 24) < 1e-9
    assert info["store_lat_lon"] is True


def test_parse_hex_header_sbe911_parses_nmea_coordinates():
    info = parse_hex_header_sbe911(_MIXSED2_HEX)
    # "65 13.78 N" → 65 + 13.78/60
    assert abs(info["nmea_latitude"] - (65 + 13.78 / 60)) < 1e-4
    # "024 39.57 W" → -(24 + 39.57/60)
    assert abs(info["nmea_longitude"] - (-(24 + 39.57 / 60))) < 1e-4


def test_parse_hex_header_sbe911_user_header_station_and_depth():
    info = parse_hex_header_sbe911(_MIXSED2_HEX)
    user = info["user_header"]
    assert user.get("Station") == "st_000"
    assert user.get("Depth") == 84


def test_parse_hex_header_sbe911_handles_latin1_ship_name(tmp_path):
    # Ship name with latin-1 byte (0xF3 = ó); should not raise
    header_bytes = (
        "* Sea-Bird SBE 9 Data File:\n"
        "* Number of Bytes Per Scan = 37\n"
        "* Number of Voltage Words = 4\n"
        "* Number of Scans Averaged by the Deck Unit = 1\n"
        "** Ship: Od\xf3n de Buen\n"
        "*END*\n"
    ).encode("latin-1")
    hex_file = tmp_path / "latin.hex"
    hex_file.write_bytes(header_bytes)
    info = parse_hex_header_sbe911(hex_file)
    assert info["voltage_words"] == 4
    assert "Ship" in info["user_header"]


def test_detect_sbe911plus_layout_raises_on_bytes_per_scan_mismatch():
    # bytes_per_scan=38 → expects 76 hex chars, but 5+4 volt+nmea+status = 74 chars
    with pytest.raises(ValueError, match="Bytes Per Scan"):
        detect_sbe_hex_layout(
            {
                "bytes_per_scan": 38,  # wrong: correct value is 37
                "voltage_words": 4,
                "store_lat_lon": True,
            },
            [],
            None,
            family="sbe911plus",
        )


def test_read_xmlcon_primary_temperature_sensor():
    cm = read_xmlcon(_MIXSED2_XMLCON)
    t1 = cm.sensors[("frequency", 0)]
    assert t1.sensor_type == "temperature"
    assert t1.role == "primary"
    assert t1.serial_number == "4798"
    coefs = t1.coefficients
    # 911+ temperature uses frequency-based calibration (g/h/i/j/f0)
    assert hasattr(coefs, "g") and hasattr(coefs, "h") and hasattr(coefs, "f0")


def test_read_xmlcon_dual_tc_have_different_coefficients():
    cm = read_xmlcon(_MIXSED2_XMLCON)
    assert cm.sensors[("frequency", 0)].coefficients != cm.sensors[("frequency", 3)].coefficients
    assert cm.sensors[("frequency", 1)].coefficients != cm.sensors[("frequency", 4)].coefficients


def test_read_xmlcon_not_in_use_sensors_excluded():
    """NotInUse sensors are skipped and do not appear in the sensor map."""
    cm = read_xmlcon(_MIXSED2_XMLCON)
    assert all(info.sensor_type != "not_in_use" for info in cm.sensors.values())


def test_read_xmlcon_unknown_sensor_raises(tmp_path):
    xmlcon = tmp_path / "bad.xmlcon"
    xmlcon.write_text(
        "\n".join([
            '<?xml version="1.0" encoding="UTF-8"?>',
            "<SBE_InstrumentConfiguration>",
            "  <Instrument>",
            '    <SensorArray Size="1">',
            '      <Sensor index="0" SensorID="99">',
            "        <UnknownAlienSensor SensorID=\"99\">",
            "          <SerialNumber>999</SerialNumber>",
            "        </UnknownAlienSensor>",
            "      </Sensor>",
            "    </SensorArray>",
            "  </Instrument>",
            "</SBE_InstrumentConfiguration>",
        ])
    )
    with pytest.raises(ValueError):
        read_xmlcon(xmlcon)


def test_sbe911_hex_reader_integration_mixsed2():
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ds = SbeHexReader(_MIXSED2_HEX, perform_default_postprocessing=False).data

    # Shape and time coordinate
    assert len(ds.time) == 500
    assert all(
        ds.time.values[i] < ds.time.values[i + 1] for i in range(len(ds.time) - 1)
    ), "time coordinate is not monotonically increasing"

    # Required variables present (raw names, no postprocessing pipeline)
    for var in ("temp", "cond", "press", "temp2", "cond2", "oxygen", "fluorescence", "turbidity"):
        assert var in ds, f"expected variable '{var}' missing from dataset"

    # Numerical sanity: first scan, from smoke test
    assert abs(float(ds["temp"][0]) - 11.04) < 0.05
    assert abs(float(ds["cond"][0]) - 38.64) < 0.10
    assert abs(float(ds["press"][0]) - 6.09) < 0.10

    # Derived salinity should be near 34.5 PSU (cond is mS/cm)
    sp = gsw.SP_from_C(
        float(ds["cond"][0]),
        float(ds["temp"][0]),
        float(ds["press"][0]),
    )
    assert abs(sp - 34.56) < 0.20, f"salinity {sp:.3f} PSU outside expected range"

    # sample_interval attribute recorded
    assert "sample_interval" in ds.attrs


_M104_HEX = f"{_FIXTURE_DIR}/M104_154_01_short.hex"
_M104_XMLCON = f"{_FIXTURE_DIR}/M104_154_01.XMLCON"
_M84_HEX = f"{_FIXTURE_DIR}/m84_3_287_short.hex"
_M84_XMLCON = f"{_FIXTURE_DIR}/M84_3_287.XMLCON"
_MSM72_HEX = f"{_FIXTURE_DIR}/MSM72_002_2_short.hex"
_MSM72_XMLCON = f"{_FIXTURE_DIR}/MSM72_002_2.XMLCON"


def test_sbe911_hex_reader_integration_m104_par_and_spar():
    """M104: Seasave 7.22.4, PAR_BiosphericalLicorChelseaSensor on volt channel + SurfaceParVoltageAdded."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ds = sbe911_hex_reader(_M104_HEX, xmlcon_path=_M104_XMLCON)

    assert len(ds.time) == 527

    for var in ("temp", "cond", "press", "temp2", "cond2",
                "oxygen", "oxygen_ml_l", "fluorescence", "altimeter", "par", "spar"):
        assert var in ds, f"expected variable '{var}' missing from dataset"

    # PAR is computed from logarithmic formula; values near zero are expected
    # for the start of a short cast (sensor in darkness).
    import numpy as np
    assert bool(np.all(np.isfinite(ds["par"].values)))
    assert bool(np.all(np.isfinite(ds["spar"].values)))

    # SPAR is biospherical linear: spar = volts * conversion_factor
    assert float(ds["spar"].values[0]) >= 0.0


def test_read_xmlcon_m104_par_coefficients():
    """PAR calibration coefficients are correctly mapped from M104 XMLCON.

    The formula is PAR = Multiplier * 1e9 * 10^(V/M) / CalibrationConstant + Offset.
    Mapped to PARCoefficients: im = 1e9 * Multiplier / CC, a0 = 0, a1 = M.
    """
    cm = read_xmlcon(_M104_XMLCON)
    par_info = cm.sensors[("volt", 6)]
    assert par_info.sensor_type == "par"
    coefs = par_info.coefficients
    # im should be 1e9 * 1.0 / 18340000000 ≈ 0.05451
    assert abs(coefs.im - 1e9 / 18340000000.0) < 1e-8
    assert coefs.a0 == 0.0
    assert coefs.a1 == 1.0
    # Offset stored separately on SensorInfo
    assert abs(par_info.offset - (-0.09468947)) < 1e-6


def test_sbe911_hex_reader_integration_m84_old_xmlcon():
    """m84: Seasave 7.20c, old conductivity XMLCON (no equation=1 wrapper),
    FluoroSeapoint sensor, user-polynomial DO/Temperature channels, SurfacePAR."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ds = sbe911_hex_reader(_M84_HEX, xmlcon_path=_M84_XMLCON)

    assert len(ds.time) == 220

    for var in ("temp", "cond", "press", "temp2", "cond2",
                "oxygen", "oxygen_ml_l", "fluorescence", "altimeter",
                "do", "temperature", "spar"):
        assert var in ds, f"expected variable '{var}' missing from dataset"

    import numpy as np
    assert bool(np.all(np.isfinite(ds["spar"].values)))


def test_read_xmlcon_m84_old_conductivity():
    """Old-format XMLCON (Seasave 7.20c) parses conductivity without equation=1 wrapper."""
    cm = read_xmlcon(_M84_XMLCON)
    cond_info = cm.sensors[("frequency", 1)]
    assert cond_info.sensor_type == "conductivity"
    assert cond_info.role == "primary"
    coefs = cond_info.coefficients
    # Old XMLCON has G/H/I/J directly under the sensor element; check that we got values
    assert coefs.g != 0.0 or coefs.h != 0.0  # at least one non-zero coefficient


def test_sbe911_hex_reader_integration_msm72_volt_suppressed():
    """MSM72: Seasave 7.22, VoltageWordsSuppressed=1 (6 active volt channels),
    FluoroSeapoint sensor."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ds = sbe911_hex_reader(_MSM72_HEX, xmlcon_path=_MSM72_XMLCON)

    assert len(ds.time) == 504

    for var in ("temp", "cond", "press", "temp2", "cond2",
                "oxygen", "oxygen_ml_l", "fluorescence", "altimeter"):
        assert var in ds, f"expected variable '{var}' missing from dataset"

    # VoltSuppressed=1 → 6 active channels; SPAR suppressed, so no 'spar'
    assert "spar" not in ds


def test_read_xmlcon_msm72_volt_suppressed_channels():
    """VoltageWordsSuppressed=1 → no channels at index 6 or 7 in sensor map."""
    cm = read_xmlcon(_MSM72_XMLCON)
    assert cm.meta["voltage_words_suppressed"] == 1
    # All sensor keys with volt channels must have index 0-5 (active range)
    volt_indices = [ch for (kind, ch) in cm.sensors if kind == "volt"]
    assert all(i < 6 for i in volt_indices), (
        f"Suppressed volt channel found in sensor map: {[i for i in volt_indices if i >= 6]}"
    )
    # Channels 6-7 are suppressed — not in the sensor map
    assert ("volt", 6) not in cm.sensors
    assert ("volt", 7) not in cm.sensors


# ---------------------------------------------------------------------------
# MSM 142-1-056 fixture tests  (NmeaTimeAdded=1, ScanTimeAdded=1, dual O2)
# ---------------------------------------------------------------------------

def test_detect_sbe_hex_family_on_real_msm_fixture():
    assert detect_sbe_hex_family(_MSM_HEX) == "sbe911plus"


def test_parse_hex_header_msm_store_system_time():
    info = parse_hex_header_sbe911(_MSM_HEX)
    assert info["bytes_per_scan"] == 45
    assert info["voltage_words"] == 4
    assert info["store_lat_lon"] is True
    assert info["store_system_time"] is True, (
        "'Append System Time to Every Scan' bare flag not parsed from MSM header"
    )


def test_read_xmlcon_msm_timing_flags():
    cm = read_xmlcon(_MSM_XMLCON)
    assert cm.meta["scan_time_added"] is True, "ScanTimeAdded=1 not read from XMLCON"
    assert cm.meta["nmea_time_added"] is True, "NmeaTimeAdded=1 not read from XMLCON"


def test_read_xmlcon_msm_dual_oxygen():
    cm = read_xmlcon(_MSM_XMLCON)
    oxy_entries = {k: v for k, v in cm.sensors.items() if v.sensor_type == "oxygen"}
    assert len(oxy_entries) == 2, f"Expected 2 oxygen entries, got {len(oxy_entries)}"
    roles = {v.role for v in oxy_entries.values()}
    assert roles == {"primary", "secondary"}, f"Unexpected roles: {roles}"
    serials = {v.serial_number for v in oxy_entries.values()}
    assert len(serials) == 2, "Primary and secondary oxygen should have different serials"
    assert None not in serials, "Oxygen sensor serial is missing"


def test_sbe911_hex_reader_integration_msm():
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ds = sbe911_hex_reader(_MSM_HEX, xmlcon_path=_MSM_XMLCON)

    # Shape and time coordinate
    assert len(ds.time) == 559
    assert all(
        ds.time.values[i] < ds.time.values[i + 1] for i in range(len(ds.time) - 1)
    ), "time coordinate is not monotonically increasing"

    # Dual oxygen and other expected variables
    for var in ("temp", "cond", "press", "temp2", "cond2",
                "oxygen", "oxygen2", "oxygen_ml_l", "oxygen2_ml_l",
                "fluorescence", "turbidity", "altimeter"):
        assert var in ds, f"expected variable '{var}' missing from dataset"

    # oxygen and oxygen2 use different calibration coefficients so their values differ
    import numpy as np
    assert not np.allclose(ds["oxygen"].values, ds["oxygen2"].values), (
        "oxygen and oxygen2 should differ (different sensors)"
    )

    # Both oxygen arrays are finite (no NaN from failed conversion)
    assert bool(np.all(np.isfinite(ds["oxygen"].values)))
    assert bool(np.all(np.isfinite(ds["oxygen2"].values)))

    # sample_interval attribute recorded
    assert "sample_interval" in ds.attrs
