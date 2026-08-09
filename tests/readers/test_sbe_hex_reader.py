from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pytest
import xarray as xr

from seasenselib.readers.sbe_hex_reader import (
    SbeHexReader,
    _read_hex_file_fast,
    _select_sbe37_instrument_type,
    detect_sbe_hex_layout,
    parse_hex_header_sensors,
)

_FIXTURES = Path(__file__).parent / "fixtures"
_HEX_FIXTURE = _FIXTURES / "7508_caldip_short.hex"


@pytest.mark.skipif(not _HEX_FIXTURE.exists(), reason="fixture 7508_caldip_short.hex not present")
class TestSbeHexReaderConductivityUnits:
    """Integration tests against the real 7508 SBE37 fixture.

    The seabirdscientific library converts conductivity to mS/cm internally.
    The pipeline unit_handling stage relabels mS/cm → mS cm-1 without touching values.
    ConductivityNormalizer should be a no-op (already in mS cm-1 after normalizer relabel).
    """

    @staticmethod
    def _require_seabird():
        pytest.importorskip("seabirdscientific.instrument_data")

    def test_raw_conductivity_unit_is_mscm_slash(self):
        """Reader assigns mS/cm (slash notation) before pipeline."""
        self._require_seabird()
        raw_ds = SbeHexReader(str(_HEX_FIXTURE), use_steps=False).data
        assert "cond" in raw_ds.data_vars
        assert raw_ds["cond"].attrs.get("units") == "mS/cm"

    def test_raw_conductivity_values_in_mscm_range(self):
        """Values should be ~34 (mS/cm), not ~3.4 (S/m)."""
        self._require_seabird()
        raw_ds = SbeHexReader(str(_HEX_FIXTURE), use_steps=False).data
        median = float(np.median(raw_ds["cond"].values))
        assert 20.0 < median < 60.0, f"Expected mS/cm range (20–60), got {median:.3f}"

    def test_pipeline_relabels_unit_to_cf_space(self):
        """After pipeline, unit is mS cm-1 (CF space notation)."""
        self._require_seabird()
        ds = SbeHexReader(str(_HEX_FIXTURE)).data
        assert ds["conductivity"].attrs.get("units") == "mS cm-1"

    def test_pipeline_does_not_convert_values(self):
        """Values must stay in mS/cm range — no ×10 conversion should occur."""
        self._require_seabird()
        ds = SbeHexReader(str(_HEX_FIXTURE)).data
        median = float(np.median(ds["conductivity"].values))
        assert 20.0 < median < 60.0, (
            f"Expected conductivity ~34 mS cm-1 after pipeline, got {median:.3f}. "
            "A value > 60 would mean double-conversion happened."
        )
        assert "conductivity_normalised_from" not in ds["conductivity"].attrs


def _seabird_instrument_data():
    return pytest.importorskip("seabirdscientific.instrument_data")


def test_sbe_hex_reader_exposes_format_metadata():
    assert SbeHexReader.format_key() == "sbe-hex"
    assert SbeHexReader.format_name() == "SeaBird SBE37 HEX"
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
    assert abs(float(with_reference_pressure["cond"].values[0]) - 34.245203) < 1e-6
    assert abs(float(without_reference_pressure["cond"].values[0]) - 34.245203) > 1e-3


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
