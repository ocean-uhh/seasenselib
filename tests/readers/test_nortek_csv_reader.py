from __future__ import annotations

import json

import numpy as np

import seasenselib as ssl
from seasenselib.readers import get_reader_by_format_key
from seasenselib.readers.nortek_csv_reader import (
    NortekCsvReader,
    load_nortek_csv_data,
)


def _write_nortek_csv(tmp_path):
    csv_file = tmp_path / "Average Velocity DF3.csv"
    csv_file.write_text(
        "\n".join(
            [
                (
                    "dateTime;serialNumber;temperature;pressure;heading;pitch;roll;"
                    "speedOfSound;batteryVoltage;velBeam1#1;ampBeam1#1;"
                    "corrBeam1#1;velBeam2#1;velBeam3#1"
                ),
                (
                    "2026-07-11 12:00:00;A123;8.1;12.5;101.0;1.2;-0.5;"
                    "1450.0;12.1;0.11;55;98;0.21;0.31"
                ),
                (
                    "2026-07-11 12:00:01;A123;8.2;12.6;102.0;1.3;-0.6;"
                    "1450.2;12.0;0.12;56;97;0.22;0.32"
                ),
            ]
        ),
        encoding="utf-8",
    )
    return csv_file


def _write_nortek_csv_metadata_files(tmp_path, coordinate_system="ENU"):
    header_file = tmp_path / "String Data.csv"
    header_file.write_text(
        "\n".join(
            [
                "idx;string",
                (
                    '0;GETCLOCKSTR,TIME="2026-07-11 12:00:00",OFFSET="+00:00"|'
                    'ID,STR="Aquadopp Deep Water 2 MHz D2VC",SN=400115|'
                    f'GETAVG,NC=1,CS=0.75,BD=0.50,CY="{coordinate_system}",'
                    'NB=3,NPING=12|'
                    'GETXFAVG,ROWS=3,COLS=3,'
                    'M11=0.7356,M12=-0.3677,M13=-0.3677,'
                    'M21=0.0000,M22=-0.6370,M23=0.6370,'
                    'M31=0.7888,M32=0.7888,M33=0.7888|'
                    'GETCOMPASSCAL,DX=-1353,DY=1436,DZ=-434,'
                    'M11=32767,M12=-2372,M13=-11,'
                    'M21=1800,M22=32311,M23=478,'
                    'M31=-84,M32=-579,M33=32507|'
                    'CALCOMPGET,DX=-1353,DY=1436,DZ=-434,'
                    'M11=32767,M12=-2372,M13=-11,'
                    'M21=1800,M22=32311,M23=478,'
                    'M31=-84,M32=-579,M33=32507|'
                    'CALMAGNALIGNGET,M11=1,M12=0,M13=0,'
                    'M21=0,M22=-1,M23=0,M31=0,M32=0,M33=-1|'
                    'GETHW,FW=10003,FPGA=2018'
                ),
            ]
        ),
        encoding="utf-8",
    )

    units_file = tmp_path / "Units.csv"
    units_file.write_text(
        "\n".join(
            [
                "Variable,Unit,Description",
                "speedOfSound,m/s,Speed of sound used by the instrument.",
                "temperature,degC,Reading from the temperature sensor.",
                "pressure,dBar,Raw pressure data.",
                "heading,deg,Heading.",
                "pitch,deg,Pitch.",
                "roll,deg,Roll.",
                "batteryVoltage,V,Battery voltage.",
                "vel,m/s,Velocity data.",
                "amp,dB,Amplitude data.",
                "corr,%,Correlation data.",
            ]
        ),
        encoding="utf-8",
    )

    return header_file, units_file


def _write_nortek_csv_with_coordinate_system(tmp_path, coordinate_system="ENU"):
    csv_file = tmp_path / "Average Velocity DF3.csv"
    csv_file.write_text(
        "\n".join(
            [
                (
                    "dateTime;serialNumber;temperature;pressure;heading;pitch;roll;"
                    "speedOfSound;batteryVoltage;coordinateSystem;velBeam1#1;"
                    "velBeam2#1;velBeam3#1;ampBeam1#1;corrBeam1#1"
                ),
                (
                    "2026-07-11 12:00:00;A123;8.1;12.5;101.0;1.2;-0.5;"
                    f"1450.0;12.1;{coordinate_system};0.11;0.21;0.31;55;98"
                ),
                (
                    "2026-07-11 12:00:01;A123;8.2;12.6;102.0;1.3;-0.6;"
                    f"1450.2;12.0;{coordinate_system};0.12;0.22;0.32;56;97"
                ),
            ]
        ),
        encoding="utf-8",
    )
    return csv_file


def _write_nortek_csv_with_velocity_components(
    tmp_path,
    coordinate_system,
    component_columns,
):
    csv_file = tmp_path / "Average Velocity DF3.csv"
    csv_file.write_text(
        "\n".join(
            [
                (
                    "dateTime;serialNumber;temperature;coordinateSystem;"
                    f"{component_columns[0]};{component_columns[1]};"
                    f"{component_columns[2]};ampBeam1#1;corrBeam1#1"
                ),
                (
                    "2026-07-11 12:00:00;A123;8.1;"
                    f"{coordinate_system};0.11;0.21;0.31;55;98"
                ),
                (
                    "2026-07-11 12:00:01;A123;8.2;"
                    f"{coordinate_system};0.12;0.22;0.32;56;97"
                ),
            ]
        ),
        encoding="utf-8",
    )
    return csv_file


def test_load_nortek_csv_data_preserves_original_helper_logic(tmp_path):
    csv_file = _write_nortek_csv(tmp_path)

    ds = load_nortek_csv_data(csv_file)

    assert ds.sizes["time"] == 2
    assert ds.attrs["instrument_type"] == "Nortek_Aquadopp"
    assert ds.attrs["data_format"] == "Nortek_CSV_Export"
    assert ds.attrs["coordinate_system"] == "BEAM"
    assert ds.attrs["serial_number"] == "A123"
    assert ds["time"].values[0] == np.datetime64("2026-07-11T12:00:00")
    assert ds["temperature"].values.tolist() == [8.1, 8.2]
    assert ds["velocity_beam1"].values.tolist() == [0.11, 0.12]
    assert ds["amplitude_beam1"].values.tolist() == [55, 56]
    assert ds["correlation_beam1"].values.tolist() == [98, 97]
    assert ds["velocity_beam1"].attrs["coordinate_system"] == "BEAM"
    assert ds["speed_of_sound"].attrs["units"] == "m/s"


def test_nortek_csv_reader_wraps_helper_as_seasenselib_reader(tmp_path):
    csv_file = _write_nortek_csv(tmp_path)

    reader = NortekCsvReader(
        str(csv_file),
        perform_default_postprocessing=False,
    )
    ds = reader.data

    assert reader.format_key() == "nortek-csv"
    assert reader.format_name() == "Nortek CSV"
    assert reader.file_extension() is None
    assert reader._get_valid_extensions() == (".csv",)
    assert ds.attrs["filename"] == str(csv_file)
    assert ds["battery_voltage"].values.tolist() == [12.1, 12.0]


def test_nortek_csv_reader_is_discoverable_by_format_key():
    assert get_reader_by_format_key("nortek-csv") is NortekCsvReader


def test_nortek_csv_reader_loads_through_public_api(tmp_path):
    csv_file = _write_nortek_csv(tmp_path)

    ds = ssl.read(
        str(csv_file),
        file_format="nortek-csv",
        use_steps=False,
    )

    assert ds.attrs["data_format"] == "Nortek_CSV_Export"
    assert ds["velocity_beam2"].values.tolist() == [0.21, 0.22]


def test_nortek_csv_metadata_files_set_coordinate_system_and_units(tmp_path):
    csv_file = _write_nortek_csv_with_coordinate_system(tmp_path, "ENU")
    header_file, units_file = _write_nortek_csv_metadata_files(tmp_path, "ENU")

    ds = load_nortek_csv_data(
        csv_file,
        header_file=header_file,
        units_file=units_file,
    )

    assert ds.attrs["coordinate_system"] == "ENU"
    assert {"velocity_east", "velocity_north", "velocity_up"}.issubset(ds.data_vars)
    assert "velocity_beam1" not in ds.data_vars
    assert ds["east_velocity"].values.tolist() == [0.11, 0.12]
    assert ds["east_velocity"].attrs["coordinate_system"] == "ENU"
    assert ds["east_velocity"].attrs["original_name"] == "velBeam1#1"
    assert ds["east_velocity"].attrs["units"] == "m/s"
    assert ds["temperature"].attrs["units"] == "degC"
    assert ds["amplitude_beam1"].attrs["units"] == "dB"
    assert ds["correlation_beam1"].attrs["units"] == "%"


def test_nortek_csv_beam_coordinate_system_keeps_beam_velocity_names(tmp_path):
    csv_file = _write_nortek_csv_with_coordinate_system(tmp_path, "BEAM")
    header_file, units_file = _write_nortek_csv_metadata_files(tmp_path, "BEAM")

    ds = load_nortek_csv_data(
        csv_file,
        header_file=header_file,
        units_file=units_file,
    )

    assert ds.attrs["coordinate_system"] == "BEAM"
    assert {"velocity_beam1", "velocity_beam2", "velocity_beam3"}.issubset(
        ds.data_vars
    )
    assert {"east_velocity", "north_velocity", "up_velocity"}.isdisjoint(
        ds.data_vars
    )
    assert ds["velocity_beam1"].values.tolist() == [0.11, 0.12]
    assert ds["velocity_beam1"].attrs["coordinate_system"] == "BEAM"
    assert ds["velocity_beam1"].attrs["original_name"] == "velBeam1#1"


def test_nortek_csv_explicit_enu_columns_use_standard_velocity_names(tmp_path):
    csv_file = _write_nortek_csv_with_velocity_components(
        tmp_path,
        "ENU",
        ("velEast#1", "velNorth#1", "velUp#1"),
    )

    ds = load_nortek_csv_data(csv_file)

    assert ds.attrs["coordinate_system"] == "ENU"
    assert {"east_velocity", "north_velocity", "up_velocity"}.issubset(ds.data_vars)
    assert "velocity_east" not in ds.data_vars
    assert ds["east_velocity"].values.tolist() == [0.11, 0.12]
    assert ds["east_velocity"].attrs["original_name"] == "velEast#1"
    assert ds["east_velocity"].attrs["coordinate_system"] == "ENU"


def test_nortek_csv_explicit_xyz_columns_use_standard_velocity_names(tmp_path):
    csv_file = _write_nortek_csv_with_velocity_components(
        tmp_path,
        "XYZ",
        ("velX#1", "velY#1", "velZ#1"),
    )

    ds = load_nortek_csv_data(csv_file)

    assert ds.attrs["coordinate_system"] == "XYZ"
    assert {"x_velocity", "y_velocity", "z_velocity"}.issubset(ds.data_vars)
    assert ds["x_velocity"].values.tolist() == [0.11, 0.12]
    assert ds["x_velocity"].attrs["original_name"] == "velX#1"
    assert ds["x_velocity"].attrs["coordinate_system"] == "XYZ"


def test_nortek_csv_raw_metadata_matches_ascii_shape(tmp_path):
    csv_file = _write_nortek_csv_with_coordinate_system(tmp_path, "ENU")
    header_file, units_file = _write_nortek_csv_metadata_files(tmp_path, "ENU")

    ds = NortekCsvReader(
        str(csv_file),
        input_header_file=str(header_file),
        units_file=str(units_file),
    ).data

    assert ds.attrs["coordinate_system"] == "ENU"
    assert "raw_metadata" in ds.attrs
    payload = json.loads(ds.attrs["raw_metadata"])

    assert "header" not in payload["blocks"]
    assert payload["blocks"]["attributes"]["coordinate_system"] == "ENU"
    assert payload["blocks"]["attributes"]["instrument_type"] == (
        "Aquadopp Deep Water 2 MHz D2VC"
    )
    assert payload["blocks"]["configuration"]["GETAVG"]["CY"] == "ENU"
    assert payload["blocks"]["calibration"]["source_commands"]["GETXFAVG"] == {
        "ROWS": 3,
        "COLS": 3,
        "M11": 0.7356,
        "M12": -0.3677,
        "M13": -0.3677,
        "M21": 0.0,
        "M22": -0.637,
        "M23": 0.637,
        "M31": 0.7888,
        "M32": 0.7888,
        "M33": 0.7888,
    }
    assert payload["blocks"]["calibration"]["source_commands"]["GETCOMPASSCAL"] == {
        "DX": -1353,
        "DY": 1436,
        "DZ": -434,
        "M11": 32767,
        "M12": -2372,
        "M13": -11,
        "M21": 1800,
        "M22": 32311,
        "M23": 478,
        "M31": -84,
        "M32": -579,
        "M33": 32507,
    }
    assert payload["blocks"]["calibration"]["source_commands"]["CALCOMPGET"] == {
        "DX": -1353,
        "DY": 1436,
        "DZ": -434,
        "M11": 32767,
        "M12": -2372,
        "M13": -11,
        "M21": 1800,
        "M22": 32311,
        "M23": 478,
        "M31": -84,
        "M32": -579,
        "M33": 32507,
    }
    assert payload["blocks"]["calibration"]["transformation_matrix"] == [
        [0.7356, -0.3677, -0.3677],
        [0.0, -0.637, 0.637],
        [0.7888, 0.7888, 0.7888],
    ]
    assert payload["blocks"]["calibration"]["magnetometer_calibration_matrix"] == [
        [32767, -2372, -11],
        [1800, 32311, 478],
        [-84, -579, 32507],
    ]
    assert payload["blocks"]["calibration"]["compass_hard_iron_calibration"] == [
        -1353,
        1436,
        -434,
    ]
    assert payload["blocks"]["calibration"]["magnetometer_alignment_matrix"] == [
        [1, 0, 0],
        [0, -1, 0],
        [0, 0, -1],
    ]
    assert payload["blocks"]["units"]["vel"]["units"] == "m/s"
    assert payload["variables"]["velocity_east"] == {
        "column_number": "11",
        "original_name": "velBeam1#1",
        "units": "m/s",
        "description": "Velocity data.",
    }
