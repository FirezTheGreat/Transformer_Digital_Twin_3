"""Unit test suite for physical unit registry and conversions."""

import pytest
from app.core.units import (
    canonicalize_unit_code,
    convert_quantity,
    format_quantity,
    get_unit_registry,
    is_compatible,
    validate_unit,
)


def test_unit_registry_singleton() -> None:
    """Verify get_unit_registry returns a valid Pint UnitRegistry."""
    ureg = get_unit_registry()
    assert ureg is not None
    assert hasattr(ureg, "Quantity")


def test_canonicalize_unit_code() -> None:
    """Verify UCUM canonical mapping for common raw symbols."""
    assert canonicalize_unit_code("degC") == "Cel"
    assert canonicalize_unit_code("°C") == "Cel"
    assert canonicalize_unit_code("celsius") == "Cel"
    assert canonicalize_unit_code("Cel") == "Cel"
    assert canonicalize_unit_code("V") == "V"
    assert canonicalize_unit_code("volt") == "V"
    assert canonicalize_unit_code("kV") == "kV"
    assert canonicalize_unit_code("A") == "A"
    assert canonicalize_unit_code("amp") == "A"
    assert canonicalize_unit_code("kW") == "kW"
    assert canonicalize_unit_code("kvar") == "kvar"
    assert canonicalize_unit_code("kVA") == "kVA"
    assert canonicalize_unit_code("Hz") == "Hz"
    assert canonicalize_unit_code("s") == "s"
    assert canonicalize_unit_code("min") == "min"
    assert canonicalize_unit_code("h") == "h"
    assert canonicalize_unit_code("hr") == "h"
    assert canonicalize_unit_code("%") == "%"
    assert canonicalize_unit_code("pct") == "%"
    assert canonicalize_unit_code("1") == "1"


def test_validate_unit() -> None:
    """Verify validation of valid and invalid unit strings."""
    assert validate_unit("V") is True
    assert validate_unit("A") is True
    assert validate_unit("kW") is True
    assert validate_unit("kvar") is True
    assert validate_unit("kVA") is True
    assert validate_unit("Cel") is True
    assert validate_unit("degC") is True
    assert validate_unit("Hz") is True
    assert validate_unit("h") is True
    assert validate_unit("1") is True
    assert validate_unit("%") is True

    # Invalid unit strings
    assert validate_unit("") is False
    assert validate_unit("not_a_real_unit_123") is False
    assert validate_unit("unknown_dimension_xyz") is False


def test_is_compatible() -> None:
    """Verify dimensional compatibility checks."""
    assert is_compatible("V", "kV") is True
    assert is_compatible("kW", "W") is True
    assert is_compatible("A", "kA") is True
    assert is_compatible("kVA", "VA") is True
    assert is_compatible("kvar", "var") is True
    assert is_compatible("s", "h") is True
    assert is_compatible("min", "h") is True
    assert is_compatible("Cel", "degC") is True
    assert is_compatible("Cel", "K") is True

    # Incompatible pairs
    assert is_compatible("V", "A") is False
    assert is_compatible("kW", "Cel") is False
    assert is_compatible("Hz", "V") is False
    assert is_compatible("h", "kW") is False


def test_electrical_conversions() -> None:
    """Verify electrical unit conversions."""
    assert convert_quantity(1.5, "kV", "V") == 1500.0
    assert convert_quantity(1500.0, "V", "kV") == 1.5
    assert convert_quantity(2.5, "kW", "W") == 2500.0
    assert convert_quantity(250.0, "W", "kW") == 0.25
    assert convert_quantity(50.0, "kVA", "VA") == 50000.0
    assert convert_quantity(25.0, "kvar", "var") == 25000.0
    assert convert_quantity(100.0, "A", "kA") == 0.1


def test_thermal_conversions() -> None:
    """Verify thermal unit conversions and identity mappings."""
    # Identity in Celsius
    assert convert_quantity(65.4, "degC", "Cel") == 65.4
    assert convert_quantity(72.0, "Cel", "Cel") == 72.0
    # Celsius to Kelvin
    assert convert_quantity(0.0, "Cel", "K") == 273.15
    assert convert_quantity(100.0, "Cel", "K") == 373.15
    # Kelvin to Celsius
    assert convert_quantity(273.15, "K", "Cel") == 0.0
    assert convert_quantity(373.15, "K", "Cel") == 100.0


def test_time_conversions() -> None:
    """Verify temporal conversions for delta-t and exposure calculations."""
    assert convert_quantity(900.0, "s", "min") == 15.0
    assert convert_quantity(900.0, "s", "h") == 0.25
    assert convert_quantity(15.0, "min", "h") == 0.25
    assert convert_quantity(2.0, "h", "min") == 120.0
    assert convert_quantity(2.0, "h", "s") == 7200.0


def test_incompatible_conversion_raises() -> None:
    """Verify ValueError is raised on incompatible or invalid conversions."""
    with pytest.raises(ValueError, match="Cannot convert"):
        convert_quantity(100.0, "V", "A")

    with pytest.raises(ValueError, match="Cannot convert"):
        convert_quantity(50.0, "kW", "Cel")

    with pytest.raises(ValueError, match="Cannot convert"):
        convert_quantity(1.0, "invalid_unit", "V")


def test_format_quantity() -> None:
    """Verify quantity string formatting."""
    assert format_quantity(230.456, "V", precision=1) == "230.5 V"
    assert format_quantity(65.1234, "degC", precision=2) == "65.12 Cel"
    assert format_quantity(0.952, "1", precision=2) == "0.95 1"
