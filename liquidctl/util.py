"""Assorted utilities used by drivers and the CLI.

Copyright (C) 2018–2020  Jonas Malaco
Copyright (C) 2018–2020  each contribution's author

This file is part of liquidctl.

liquidctl is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

liquidctl is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import colorsys
import logging

from ast import literal_eval
from enum import Enum, unique

LOGGER = logging.getLogger(__name__)


HUE2_MAX_ACCESSORIES_IN_CHANNEL = 6


@unique
class Hue2Accessory(Enum):
    """Mapping of HUE 2 accessory IDs and names.

    >>> Hue2Accessory(4)
    <Hue2Accessory.HUE2_LED_STRIP_300: 4>
    >>> str(Hue2Accessory(4))
    'HUE 2 LED Strip 300 mm'

    Unknown IDs are automatically translated to equivalent pseudo-names.

    >>> Hue2Accessory(59)
    <Hue2Accessory.UNKNOWN_59: 59>
    >>> Hue2Accessory(59).value == Hue2Accessory(59).value
    True
    >>> Hue2Accessory(59) != Hue2Accessory(58)
    True
    """

    HUE_PLUS_LED_STRIP = (0x01, 'HUE+ LED Strip')
    AER_RGB1_FAN = (0x02, 'AER RGB 1')
    HUE2_LED_STRIP_300 = (0x04, 'HUE 2 LED Strip 300 mm')
    HUE2_LED_STRIP_250 = (0x05, 'HUE 2 LED Strip 250 mm')
    HUE2_LED_STRIP_200 = (0x06, 'HUE 2 LED Strip 200 mm')
    HUE2_CABLE_COMB = (0x07, 'HUE 2 Cable Comb')
    HUE2_UNDERGLOW_300 = (0x09, 'HUE 2 Underglow 300 mm')
    HUE2_UNDERGLOW_200 = (0x0a, 'HUE 2 Underglow 200 mm')
    AER_RGB2_120 = (0x0b, 'AER RGB 2 120 mm')
    AER_RGB2_140 = (0x0c, 'AER RGB 2 140 mm')
    KRAKENX_GEN4_RING = (0x10, 'Kraken X (X53, X63 or X73) Pump Ring')
    KRAKENX_GEN4_LOGO = (0x11, 'Kraken X (X53, X63 or X73) Pump Logo')

    def __new__(cls, value, pretty_name):
        member = object.__new__(cls)
        member.pretty_name = pretty_name
        member._value_ = value
        return member

    @classmethod
    def _missing_(cls, value):
        dummy = object.__new__(cls)
        dummy.pretty_name = 'Unknown'
        dummy._name_ = f'UNKNOWN_{value}'
        dummy._value_ = value
        return dummy

    def __str__(self):
        return self.pretty_name

    def __eq__(self, other):
        return self.value == other.value


def clamp(value, clampmin, clampmax):
    """Clamp numeric `value` to interval [`clampmin`, `clampmax`]."""
    clamped = max(clampmin, min(clampmax, value))
    if clamped != value:
        LOGGER.debug('clamped %s to interval [%s, %s]', value, clampmin, clampmax)
    return clamped


def delta(profile):
    """Compute a profile's Δx and Δy."""
    return [(cur[0]-prev[0], cur[1]-prev[1])
            for cur,prev in zip(profile[1:], profile[:-1])]


def normalize_profile(profile, critx):
    """Normalize a [(x:int, y:int), ...] profile.

    The normalized profile will ensure that:

     - the profile is a monotonically increasing function
       (i.e. for every i, i > 1, x[i] - x[i-1] > 0 and y[i] - y[i-1] >= 0)
     - the profile is sorted
     - a (critx, 100) failsafe is enforced

    >>> normalize_profile([(30, 40), (25, 25), (35, 30), (40, 35), (40, 80)], 60)
    [(25, 25), (30, 40), (35, 40), (40, 80), (60, 100)]
    """
    profile = sorted(list(profile) + [(critx, 100)], key=lambda p: (p[0], -p[1]))
    mono = profile[0:1]
    for (x, y), (xb, yb) in zip(profile[1:], profile[:-1]):
        if x == xb:
            continue
        if y < yb:
            y = yb
        mono.append((x, y))
    return mono


def interpolate_profile(profile, x):
    """Interpolate y given x and a [(x: int, y: int), ...] profile.

    Requires the profile to be sorted by x, with no duplicate x values (see
    normalize_profile).  Expects profiles with integer x and y values, and
    returns duty rounded to the nearest integer.

    >>> interpolate_profile([(20, 50), (50, 70), (60, 100)], 33)
    59
    >>> interpolate_profile([(20, 50), (50, 70)], 19)
    50
    >>> interpolate_profile([(20, 50), (50, 70)], 51)
    70
    >>> interpolate_profile([(20, 50)], 20)
    50
    """
    lower, upper = profile[0], profile[-1]
    for step in profile:
        if step[0] <= x:
            lower = step
        if step[0] >= x:
            upper = step
            break
    if lower[0] == upper[0]:
        return lower[1]
    return round(lower[1] + (x - lower[0])/(upper[0] - lower[0])*(upper[1] - lower[1]))


def color_from_str(x):
    """Parse a color, and, if necessary, translate it into the RGB model.

    The input string can be encoded in several formats:

     - ffffff: hexadecimal RGB implicit tuple
     - rgb(255, 255, 255): explicit RGB, R,G,B ∊ [0, 255]
     - hsv(360, 100, 100): explicit HSV, H ∊ [0, 360], SV ∊ [0, 100]
     - hsl(360, 100, 100): explicit HSL, H ∊ [0, 360], SV ∊ [0, 100]

    >>> color_from_str('fF7f3f')
    [255, 127, 63]
    >>> color_from_str('Rgb(255, 127, 63)')
    [255, 127, 63]
    >>> color_from_str('Hsv(20, 75, 100)')
    [255, 128, 64]
    >>> color_from_str('Hsl(20, 100, 62)')
    [255, 126, 61]

    >>> color_from_str('fF7f3f1f')
    Traceback (most recent call last):
        ...
    ValueError: Cannot parse color: fF7f3f1f
    >>> color_from_str('rgb()')
    Traceback (most recent call last):
        ...
    ValueError: Expected 3-element triple: rgb()
    >>> color_from_str('rgb(255)')
    Traceback (most recent call last):
        ...
    ValueError: Expected 3-element triple: rgb(255)
    >>> color_from_str('rgb(300, 255, 255)')
    Traceback (most recent call last):
        ...
    ValueError: Expected value in range [0, 255]: 300 in rgb(300, 255, 255)
    >>> color_from_str('hsv(360, 150, 100)')
    Traceback (most recent call last):
        ...
    ValueError: Expected value in range [0, 100]: 150 in hsv(360, 150, 100)
    >>> color_from_str('hsl(360, 100, 150)')
    Traceback (most recent call last):
        ...
    ValueError: Expected value in range [0, 100]: 150 in hsl(360, 100, 150)
    """

    def parse_triple(sub, maxvalues):
        literal = literal_eval(sub)
        if not isinstance(literal, tuple) or len(literal) != 3:
            raise ValueError(f'Expected 3-element triple: {x}')
        for value, maxvalue in zip(literal, maxvalues):
            if not isinstance(value, int) and not isinstance(value, float):
                raise ValueError(f'Expected float or int: {value} in {x}')
            if value < 0 or value > maxvalue:
                raise ValueError(f'Expected value in range [0, {maxvalue}]: {value} in {x}')
        return literal

    if x.lower().startswith('rgb('):
        r, g, b = parse_triple(x[3:], (255, 255, 255))
        return [r, g, b]
    elif x.lower().startswith('hsv('):
        h, s, v = parse_triple(x[3:], (360, 100, 100))
        return list(map(lambda b: round(b*255), colorsys.hsv_to_rgb(h/360, s/100, v/100)))
    elif x.lower().startswith('hsl('):
        h, s, l = parse_triple(x[3:], (360, 100, 100))
        return list(map(lambda b: round(b*255), colorsys.hls_to_rgb(h/360, l/100, s/100)))
    elif len(x) == 6:
        return list(bytes.fromhex(x))
    else:
        raise ValueError(f'Cannot parse color: {x}')
