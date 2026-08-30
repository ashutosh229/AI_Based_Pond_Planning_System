import io
import re
import zipfile
from dataclasses import dataclass

from lxml import etree

# ExtendedData / SimpleData field names commonly used for elevation across
# different contour-export tools. Checked in order if <name> isn't numeric.
_ELEVATION_FIELD_CANDIDATES = ("elevation", "elev", "height", "contour", "value", "z")


@dataclass(frozen=True)
class ContourLine:
    elevation: float
    points: list[tuple[float, float]]  # (lon, lat)
    is_closed: bool


class KMLParseError(ValueError):
    pass


def _local_tag(element) -> str:
    """Strip the XML namespace prefix, e.g. '{http://...}Placemark' -> 'Placemark'."""
    return etree.QName(element).localname


def _extract_kml_bytes(raw: bytes, filename: str) -> bytes:
    """Return raw KML bytes, unwrapping a .kmz archive if needed."""
    if filename.lower().endswith(".kmz") or raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            kml_names = [n for n in zf.namelist() if n.lower().endswith(".kml")]
            if not kml_names:
                raise KMLParseError("KMZ archive does not contain a .kml file")
            # doc.kml is the conventional primary file; fall back to the first entry
            preferred = [n for n in kml_names if n.lower() == "doc.kml"]
            return zf.read(preferred[0] if preferred else kml_names[0])
    return raw


def _parse_coordinates(text: str) -> list[tuple[float, float]]:
    """Parse a KML <coordinates> text blob into a list of (lon, lat).
    KML coordinates are 'lon,lat[,alt]' tuples separated by whitespace."""
    points = []
    for token in text.split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        lon, lat = float(parts[0]), float(parts[1])
        points.append((lon, lat))
    return points


def _points_form_closed_ring(points: list[tuple[float, float]], tolerance_deg: float = 1e-7) -> bool:
    if len(points) < 4:
        return False
    (x0, y0), (x1, y1) = points[0], points[-1]
    return abs(x0 - x1) < tolerance_deg and abs(y0 - y1) < tolerance_deg


def _extract_elevation(placemark) -> float | None:
    """Try <name> first (the convention used by our sample file and most
    gdal_contour-style exports), then fall back to common ExtendedData
    field names. Returns None if no elevation could be determined —
    callers should skip such placemarks rather than guessing."""
    for child in placemark:
        if _local_tag(child) == "name" and child.text:
            try:
                return float(child.text.strip())
            except ValueError:
                pass  # not numeric (e.g. "land", "sources") — fall through

    for extended_data in placemark.iter():
        if _local_tag(extended_data) == "SimpleData":
            field_name = (extended_data.get("name") or "").lower()
            if any(candidate in field_name for candidate in _ELEVATION_FIELD_CANDIDATES):
                try:
                    return float((extended_data.text or "").strip())
                except ValueError:
                    continue
    return None


def parse_contours(raw: bytes, filename: str) -> list[ContourLine]:
    """Parse a KML/KMZ file's bytes into a list of ContourLine.

    Only Placemarks containing a LineString AND a resolvable elevation are
    returned — Point placemarks (elevation labels), Polygon placemarks
    (e.g. a land-boundary outline), and any line without a usable
    elevation are silently skipped, since they are not contour lines.
    """
    kml_bytes = _extract_kml_bytes(raw, filename)

    try:
        root = etree.fromstring(kml_bytes)
    except etree.XMLSyntaxError as exc:
        raise KMLParseError(f"Could not parse KML XML: {exc}") from exc

    contours: list[ContourLine] = []
    for placemark in root.iter():
        if _local_tag(placemark) != "Placemark":
            continue

        line_string = None
        for child in placemark.iter():
            if _local_tag(child) == "LineString":
                line_string = child
                break
        if line_string is None:
            continue  # not a line (could be a Point label or a Polygon)

        coords_el = None
        for child in line_string.iter():
            if _local_tag(child) == "coordinates":
                coords_el = child
                break
        if coords_el is None or not coords_el.text:
            continue

        elevation = _extract_elevation(placemark)
        if elevation is None:
            continue  # can't use a contour line whose elevation is unknown

        points = _parse_coordinates(coords_el.text)
        if len(points) < 2:
            continue

        contours.append(ContourLine(
            elevation=elevation,
            points=points,
            is_closed=_points_form_closed_ring(points),
        ))

    if not contours:
        raise KMLParseError(
            "No contour lines found. Expected Placemarks containing a "
            "LineString with a numeric elevation (in <name> or ExtendedData)."
        )
    return contours
