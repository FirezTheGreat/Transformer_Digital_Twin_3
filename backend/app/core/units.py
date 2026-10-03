"""Physical unit registry, conversion utilities, and UCUM validation helpers."""

from typing import Any
import pint

# Global Pint Unit Registry instance
ureg = pint.UnitRegistry()

# Define electrical and domain-specific units if not already in Pint
try:
    ureg.define("var = volt * ampere = VAR")
except pint.errors.RedefinitionError:
    pass

try:
    ureg.define("kvar = 1000 * var = kVAR")
except pint.errors.RedefinitionError:
    pass

try:
    ureg.define("Mvar = 1000000 * var = MVAR")
except pint.errors.RedefinitionError:
    pass

try:
    ureg.define("VA = volt * ampere")
except pint.errors.RedefinitionError:
    pass

try:
    ureg.define("kVA = 1000 * VA")
except pint.errors.RedefinitionError:
    pass

try:
    ureg.define("MVA = 1000000 * VA")
except pint.errors.RedefinitionError:
    pass

try:
    ureg.define("Cel = degC = celsius")
except pint.errors.RedefinitionError:
    pass

try:
    ureg.define("percent = 0.01 * count = pct = %")
except pint.errors.RedefinitionError:
    pass


# Canonical UCUM Mapping dictionary for incoming raw/source units
UCUM_CANONICAL_MAP: dict[str, str] = {
    # Voltage
    "v": "V",
    "volt": "V",
    "volts": "V",
    "kv": "kV",
    "kilovolt": "kV",
    # Current
    "a": "A",
    "amp": "A",
    "amps": "A",
    "ampere": "A",
    "amperes": "A",
    "ka": "kA",
    # Power
    "w": "W",
    "watt": "W",
    "watts": "W",
    "kw": "kW",
    "kilowatt": "kW",
    "mw": "MW",
    "var": "var",
    "kvar": "kvar",
    "mvar": "Mvar",
    "va": "VA",
    "kva": "kVA",
    "mva": "MVA",
    # Frequency
    "hz": "Hz",
    "hertz": "Hz",
    # Thermal
    "cel": "Cel",
    "degc": "Cel",
    "deg_c": "Cel",
    "°c": "Cel",
    "celsius": "Cel",
    "k": "K",
    "kelvin": "K",
    # Time / Duration
    "s": "s",
    "sec": "s",
    "second": "s",
    "seconds": "s",
    "min": "min",
    "minute": "min",
    "minutes": "min",
    "h": "h",
    "hr": "h",
    "hour": "h",
    "hours": "h",
    "d": "day",
    "day": "day",
    "days": "day",
    # Dimensionless / Ratio
    "1": "1",
    "dimensionless": "1",
    "ratio": "1",
    "%": "%",
    "pct": "%",
    "percent": "%",
}


def get_unit_registry() -> pint.UnitRegistry:
    """Return the application-wide Pint UnitRegistry singleton."""
    return ureg


def canonicalize_unit_code(unit_str: str) -> str:
    """Convert an arbitrary unit representation to its canonical UCUM/Pint symbol.
    
    Returns the canonical string if recognized, otherwise returns the stripped input.
    """
    if not unit_str:
        return "1"
    normalized = unit_str.strip().lower()
    return UCUM_CANONICAL_MAP.get(normalized, unit_str.strip())


def validate_unit(unit_str: str) -> bool:
    """Validate whether a given unit string is recognized by the UnitRegistry."""
    if not unit_str:
        return False
    canonical = canonicalize_unit_code(unit_str)
    try:
        ureg.parse_units(canonical)
        return True
    except (pint.errors.UndefinedUnitError, pint.errors.PintError, Exception):
        return False


def is_compatible(from_unit: str, to_unit: str) -> bool:
    """Check whether two unit strings are dimensionally compatible."""
    canon_from = canonicalize_unit_code(from_unit)
    canon_to = canonicalize_unit_code(to_unit)
    try:
        u_from = ureg.parse_units(canon_from)
        u_to = ureg.parse_units(canon_to)
        return ureg.Quantity(1.0, u_from).check(u_to)
    except Exception:
        return False


def convert_quantity(
    value: float,
    from_unit: str,
    to_unit: str,
    round_decimals: int | None = 6,
) -> float:
    """Convert a scalar value between dimensionally compatible units with precision control.
    
    Raises:
        ValueError: If units are invalid or dimensionally incompatible.
    """
    canon_from = canonicalize_unit_code(from_unit)
    canon_to = canonicalize_unit_code(to_unit)
    
    if canon_from == canon_to:
        return round(value, round_decimals) if round_decimals is not None else value
    
    try:
        # For temperature in Celsius, handle quantity conversion carefully
        if canon_from in ("Cel", "degC") and canon_to in ("Cel", "degC"):
            result = float(value)
        elif canon_from in ("Cel", "degC") and canon_to == "K":
            qty = ureg.Quantity(value, ureg.degC)
            result = float(qty.to(ureg.kelvin).magnitude)
        elif canon_from == "K" and canon_to in ("Cel", "degC"):
            qty = ureg.Quantity(value, ureg.kelvin)
            result = float(qty.to(ureg.degC).magnitude)
        else:
            qty = ureg.Quantity(value, canon_from)
            result = float(qty.to(canon_to).magnitude)
            
        if round_decimals is not None:
            return round(result, round_decimals)
        return result
    except (pint.errors.DimensionalityError, pint.errors.UndefinedUnitError, Exception) as exc:
        raise ValueError(
            f"Cannot convert {value} from '{from_unit}' (canonical: '{canon_from}') "
            f"to '{to_unit}' (canonical: '{canon_to}'): {exc}"
        ) from exc


def format_quantity(value: float, unit_str: str, precision: int = 2) -> str:
    """Format a numeric value with its canonical unit code."""
    canon_unit = canonicalize_unit_code(unit_str)
    return f"{value:.{precision}f} {canon_unit}"
