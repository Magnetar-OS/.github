#!/usr/bin/env python3
"""Draw every image in profile/assets/ for the Magnetar-OS organisation profile.

GitHub renders a profile README with no stylesheet and no web fonts, so every
visual here is an SVG file the README embeds with <img>. Inside an image SVG
the viewer's installed fonts are all that is available, which would turn the
brand's typefaces into whatever sans-serif the reader has. To avoid that, all
text is converted to outlines at build time from the same variable fonts
magnetaros.com ships (Anybody, Atkinson Hyperlegible Next, Martian Mono, all
SIL OFL), read out of magnetar-web's node_modules.

Animation is CSS @keyframes and SMIL inside the SVGs, which browsers run for
<img> too. Scripts never run there, so nothing here depends on them.

Inputs:
  --brand  magnetar-brand checkout: the logo and the app icons
  --web    magnetar-web checkout with `pnpm install` done: the fonts

Run from anywhere:  python3 tools/build.py
"""

from __future__ import annotations

import argparse
import html
import math
import random
import re
from dataclasses import dataclass
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'profile' / 'assets'


# --------------------------------------------------------------------- data

@dataclass(frozen=True)
class App:
    name: str
    slug: str
    package: str
    category: str
    summary: str
    benchmark: str | None
    hue: str


# Mirrors magnetar-web/src/data/suite.ts: summaries are the apps' AppStream
# <summary> lines, benchmarks the parity floors, hues the icon palette.
APPS = [
    App('Slate', 'slate', 'slate', 'Calendar & tasks', 'View and manage your events and tasks.', 'GNOME Calendar', '#5B7CFF'),
    App('Envelope', 'envelope', 'envelope', 'Mail', 'Read and write your mail.', 'Thunderbird’s mail core', '#59C77A'),
    App('Circle', 'circle', 'circle', 'Contacts', 'Find and edit the people in your address book.', 'GNOME Contacts', '#FF7A6B'),
    App('Locket', 'locket', 'locket', 'Passwords & keyring', 'Keep passwords, keys and secrets for your desktop.', 'KeePassXC', '#F2B84B'),
    App('Jump', 'jump', 'jump', 'Launcher', 'Search applications, windows, files and clipboard.', 'Raycast', '#FF8A3D'),
    App('Peek', 'peek', 'magnetar-peek', 'File preview', 'Preview files without opening them.', 'macOS Quick Look', '#3ED2C8'),
    App('Pencil', 'pencil', 'magnetar-pencil', 'Documents', 'Write and format documents.', None, '#A66BFF'),
    App('Pocket', 'pocket', 'pocket', 'Passes & tickets', 'Boarding passes, tickets and cards, with their barcodes ready to scan.', None, '#FF6FA8'),
]

# Same figures and date as the "Measured in …" line on magnetaros.com.
MEASURED = 'SEPTEMBER 2026'
STATS = [('222,506', 'lines of Rust'), ('3,085', 'tests'), ('0', 'todo!() calls'), ('GPL-3.0', 'apps · MPL-2.0 substrate')]

LAYERS = [
    ('MAGNETOSPHERE', 'The suite', '#A66BFF',
     'Mail, calendar, contacts, passwords, a launcher and more, written in Rust for COSMIC and wired '
     'into the system. Locket is the keyring, Jump opens on Super+Space, and Envelope hands meeting '
     'invitations to Slate.'),
    ('CRUST', 'COSMIC', '#7CC4FF',
     'System76’s Rust desktop on Wayland, set up from the first boot: the COSMIC greeter, PipeWire '
     'audio, Qt apps themed to match, Ghostty as the terminal, and firmware updates through fwupd.'),
    ('CORE', 'Arch & CachyOS', '#FFB14A',
     'Arch Linux’s rolling base and pacman, with CachyOS’s kernel, hardware detection and packages '
     'rebuilt for x86-64-v3, v4 and Zen 4. Magnetar follows both upstreams rather than forking them, '
     'so their fixes reach you as they ship.'),
]

# Brand tokens, from magnetar-web/src/styles/global.css and the logo.
VOID, INK, CORONA, DIM, FIELD, FLARE = '#04060C', '#0A1020', '#EAF2FF', '#8795AB', '#7CC4FF', '#FFB14A'
VIOLET, CYAN, ICE = '#7B5CFF', '#2AA9E0', '#9BE8FF'


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    bg2: str
    text: str
    dim: str
    rule: str
    rule_op: float
    glow_op: float


DARK = Theme('dark', '#0B1222', '#070B16', CORONA, DIM, FIELD, 0.16, 0.30)
LIGHT = Theme('light', '#FFFFFF', '#F3F6FB', INK, '#56637A', INK, 0.11, 0.17)


def mix(a: str, b: str, t: float) -> str:
    """Blend hex colour a toward b by t (0..1)."""
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(x + (y - x) * t):02X}' for x, y in zip(pa, pb))


def ink(hue: str, theme: Theme) -> str:
    """A hue as text: as-is on dark, darkened enough to read on white."""
    return hue if theme is DARK else mix(hue, INK, 0.38)


# -------------------------------------------------------------------- fonts

class Face:
    """One static instance of a variable font, drawn as SVG outlines."""

    def __init__(self, path: Path, axes: dict[str, float]):
        font = instantiateVariableFont(TTFont(path), axes)
        self.glyphs = font.getGlyphSet()
        self.cmap = font.getBestCmap()
        self.upm = font['head'].unitsPerEm
        self.hmtx = font['hmtx']

    def _glyph(self, ch: str) -> str:
        name = self.cmap.get(ord(ch))
        if name is None:
            raise ValueError(f'{ch!r} (U+{ord(ch):04X}) is not in this font subset')
        return name

    def measure(self, text: str, size: float, tracking: float = 0.0) -> float:
        scale = size / self.upm
        return sum(self.hmtx[self._glyph(c)][0] * scale + tracking for c in text) - (tracking if text else 0.0)

    def outline(self, text: str, x: float, y: float, size: float, tracking: float = 0.0) -> str:
        scale = size / self.upm
        pen = SVGPathPen(self.glyphs, ntos=lambda v: f'{v:.2f}'.rstrip('0').rstrip('.'))
        for c in text:
            name = self._glyph(c)
            self.glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, y)))
            x += self.hmtx[name][0] * scale + tracking
        return pen.getCommands()

    def wrap(self, text: str, size: float, width: float) -> list[str]:
        lines: list[str] = []
        for word in text.split():
            if lines and self.measure(f'{lines[-1]} {word}', size) <= width:
                lines[-1] += f' {word}'
            else:
                lines.append(word)
        return lines


@dataclass(frozen=True)
class Fonts:
    display: Face
    display_black: Face
    body: Face
    body_bold: Face
    mono: Face


def load_fonts(web: Path) -> Fonts:
    base = web / 'node_modules' / '@fontsource-variable'
    anybody = base / 'anybody/files/anybody-latin-standard-normal.woff2'
    atkinson = base / 'atkinson-hyperlegible-next/files/atkinson-hyperlegible-next-latin-wght-normal.woff2'
    martian = base / 'martian-mono/files/martian-mono-latin-standard-normal.woff2'
    for f in (anybody, atkinson, martian):
        if not f.exists():
            raise SystemExit(f'missing font {f} — run `pnpm install` in {web}')
    return Fonts(
        display=Face(anybody, {'wght': 650, 'wdth': 100}),
        display_black=Face(anybody, {'wght': 820, 'wdth': 118}),
        body=Face(atkinson, {'wght': 400}),
        body_bold=Face(atkinson, {'wght': 650}),
        mono=Face(martian, {'wght': 420, 'wdth': 100}),
    )


def text(face: Face, s: str, x: float, y: float, size: float, fill: str, *,
         tracking: float = 0.0, anchor: str = 'start', opacity: float | None = None) -> str:
    if anchor == 'middle':
        x -= face.measure(s, size, tracking) / 2
    elif anchor == 'end':
        x -= face.measure(s, size, tracking)
    op = f' fill-opacity="{opacity}"' if opacity is not None else ''
    return f'<path d="{face.outline(s, x, y, size, tracking)}" fill="{fill}"{op}/>'


# -------------------------------------------------------------------- reuse

def nested(svg: str, prefix: str, x: float, y: float, size: float) -> str:
    """Embed a standalone SVG at (x, y, size), with its ids prefixed so two
    embedded documents (or the host's own defs) cannot collide."""
    view = re.search(r'viewBox="([^"]+)"', svg)
    if view is None:
        raise ValueError('embedded SVG has no viewBox')
    inner = re.sub(r'^.*?<svg[^>]*>|</svg>\s*$', '', svg, flags=re.S)
    inner = re.sub(r'<!--.*?-->', '', inner, flags=re.S)
    inner = re.sub(r'id="([^"]+)"', rf'id="{prefix}\1"', inner)
    inner = re.sub(r'url\(#([^)]+)\)', rf'url(#{prefix}\1)', inner)
    inner = re.sub(r'href="#([^"]+)"', rf'href="#{prefix}\1"', inner)
    return f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="{view.group(1)}">{inner}</svg>'


def document(w: int, h: int, title: str, body: str, style: str = '') -> str:
    css = f'<style>{style}@media (prefers-reduced-motion: reduce){{*{{animation:none!important}}}}</style>' if style else ''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{html.escape(title)}"><title>{html.escape(title)}</title>{css}{body}</svg>\n')


def keyframes(name: str, steps: int, frame) -> str:
    """CSS keyframes sampled from frame(t) for t in [0, 1]; linear timing
    between samples approximates the curve."""
    body = ''.join(f'{100 * i / steps:.3f}%{{{frame(i / steps)}}}' for i in range(steps + 1))
    return f'@keyframes {name}{{{body}}}'


# --------------------------------------------------------------------- hero

def dipole(L: float, th0: float = 0.2, steps: int = 72) -> str:
    """One closed field line of a dipole in its meridian plane, r = L·sin²θ,
    with the magnetic axis vertical and the star at the origin."""
    pts = []
    for k in range(steps + 1):
        th = th0 + (math.pi - 2 * th0) * k / steps
        r = L * math.sin(th) ** 2
        pts.append(f'{r * math.sin(th):.1f} {-r * math.cos(th):.1f}')
    return 'M' + ' L'.join(pts)


def starfield(rng: random.Random, W: int, H: int, n: int) -> str:
    stars = []
    for i in range(n):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        r = rng.choice([0.5, 0.6, 0.8, 1.0, 1.3])
        op = rng.uniform(0.15, 0.85)
        cls = f' class="tw" style="animation-delay:-{rng.uniform(0, 6):.2f}s;animation-duration:{rng.uniform(3, 7):.1f}s"' if i % 6 == 0 else ''
        stars.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#DCEBFF" opacity="{op:.2f}"{cls}/>')
    return f'<g>{"".join(stars)}</g>'


def magnetosphere(hues: list[str], loops: list[float], period: float) -> str:
    """Field lines around a star at the origin, one flux tube per hue, each
    spinning about the magnetic axis (see SPACE_STYLE) and carrying a particle."""
    tubes = []
    for i, hue in enumerate(hues):
        lines = []
        for j, (L, w, op) in enumerate(zip(loops, (1.5, 1.2, 1.0), (0.9, 0.7, 0.55))):
            d = dipole(L)
            lines.append(f'<path d="{d}" stroke="{hue}" stroke-width="{w * 4}" stroke-opacity="{op * 0.12:.3f}"/>'
                         f'<path d="{d}" stroke="{hue}" stroke-width="{w}" stroke-opacity="{op}"/>')
            if j == 0:
                dur = 5.5 + (i % 3) * 0.8
                lines.append(f'<circle r="2.4" fill="#FFFFFF"><animateMotion dur="{dur}s" begin="-{i * 0.9:.1f}s" '
                             f'repeatCount="indefinite" path="{d}"/></circle>'
                             f'<circle r="6" fill="{hue}" opacity=".35"><animateMotion dur="{dur}s" '
                             f'begin="-{i * 0.9:.1f}s" repeatCount="indefinite" path="{d}"/></circle>')
        tubes.append(f'<g class="tube" style="animation-delay:-{period * i / len(hues):.2f}s">{"".join(lines)}</g>')
    beam = ('<polygon points="-3,-14 3,-14 26,-270 -26,-270" fill="url(#beam)"/>'
            '<polygon points="-1.2,-14 1.2,-14 4,-250 -4,-250" fill="url(#beamcore)"/>')
    return f'<g class="beam">{beam}<g transform="scale(1 -1)">{beam}</g></g><g class="field">{"".join(tubes)}</g>'


def space_defs(W: int, H: int, sky_cx: str) -> str:
    return f'''
  <clipPath id="frame"><rect width="{W}" height="{H}" rx="22"/></clipPath>
  <radialGradient id="sky" cx="{sky_cx}" cy="52%" r="85%"><stop offset="0" stop-color="#101A33"/><stop offset=".55" stop-color="{INK}"/><stop offset="1" stop-color="{VOID}"/></radialGradient>
  <radialGradient id="halo"><stop offset="0" stop-color="{ICE}" stop-opacity=".55"/><stop offset=".35" stop-color="{ICE}" stop-opacity=".16"/><stop offset="1" stop-color="{ICE}" stop-opacity="0"/></radialGradient>
  <radialGradient id="core" cx="40%" cy="36%" r="70%"><stop offset="0" stop-color="#FFFFFF"/><stop offset=".45" stop-color="{ICE}"/><stop offset="1" stop-color="#1E8FD0"/></radialGradient>
  <linearGradient id="beam" x1="0" y1="-14" x2="0" y2="-270" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="{ICE}" stop-opacity=".55"/><stop offset="1" stop-color="{ICE}" stop-opacity="0"/></linearGradient>
  <linearGradient id="beamcore" x1="0" y1="-14" x2="0" y2="-250" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#FFFFFF" stop-opacity=".95"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>
  <linearGradient id="word" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#BFD9FF"/></linearGradient>
  <filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="60"/></filter>'''


def space_style(period: float) -> str:
    # A field line at azimuth φ projects to x·cos φ, and sits in front of the
    # star while sin φ > 0. Each tube runs the same cycle, offset by its index.
    spin = keyframes('spin', 32, lambda t: (
        f'transform:scaleX({math.cos(2 * math.pi * t):.3f});'
        f'opacity:{0.5 + 0.5 * math.sin(2 * math.pi * t):.3f}'))
    return (spin +
            f'.tube{{animation:spin {period}s linear infinite;transform-origin:0 0}}'
            '.halo{animation:breathe 4.2s ease-in-out infinite alternate;transform-origin:0 0}'
            '@keyframes breathe{from{transform:scale(.82);opacity:.75}to{transform:scale(1.12);opacity:1}}'
            '.beam{animation:pulse 2.6s ease-in-out infinite alternate}'
            '@keyframes pulse{from{opacity:.35}to{opacity:1}}'
            '.tw{animation:twinkle 5s ease-in-out infinite alternate}'
            '@keyframes twinkle{from{opacity:.08}to{opacity:.95}}')


STAR = ('<circle r="78" fill="url(#halo)" class="halo"/><circle r="15" fill="url(#core)"/>'
        '<circle r="15" fill="none" stroke="#FFFFFF" stroke-opacity=".5" stroke-width="1"/>')


def hero(f: Fonts, logo: str) -> str:
    W, H = 1280, 520
    rng = random.Random(1054)  # fixed seed: the starfield must not change between builds
    period = 18.0

    # Right-hand column: mark, wordmark, the dictionary entry from the site's hero.
    x0 = 650
    defs_y = 266
    entry = []
    for n, line in enumerate([
        'A neutron star whose magnetic field is a thousand trillion times Earth’s.',
        'A Linux distribution built on Arch and CachyOS, with the COSMIC desktop and a suite of apps made for it.',
    ]):
        entry.append(text(f.mono, str(n + 1), x0, defs_y + 1, 16, FLARE))
        for line_text in f.body.wrap(line, 23, 560):
            entry.append(text(f.body, line_text, x0 + 30, defs_y, 23, CORONA, opacity=0.88))
            defs_y += 32
        defs_y += 16

    body = f'''
<defs>{space_defs(W, H, "28%")}</defs>
<g clip-path="url(#frame)">
  <rect width="{W}" height="{H}" fill="url(#sky)"/>
  <g filter="url(#blur)">
    <ellipse cx="330" cy="280" rx="300" ry="170" fill="{VIOLET}" opacity=".20"/>
    <ellipse cx="1080" cy="90" rx="260" ry="120" fill="{CYAN}" opacity=".12"/>
    <ellipse cx="820" cy="520" rx="300" ry="90" fill="#FF6FA8" opacity=".06"/>
  </g>
  {starfield(rng, W, H, 230)}
  <g transform="translate(330 270) rotate(-22)" fill="none" stroke-linecap="round">
    {magnetosphere([a.hue for a in APPS], [220, 150, 96], period)}
    {STAR}
  </g>
  {nested(logo, 'mk', x0 - 6, 112, 76)}
  {text(f.display_black, "Magnetar", x0 + 82, 176, 72, "url(#word)", tracking=0.5)}
  {text(f.mono, 'MAG·NE·TAR  —  NOUN', x0, 224, 14, DIM, tracking=3)}
  {"".join(entry)}
  {text(f.mono, 'ARCH · CACHYOS · COSMIC · WAYLAND · RUST', x0, 466, 13.5, FIELD, tracking=2, opacity=0.9)}
  <rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="21.5" fill="none" stroke="{FIELD}" stroke-opacity=".18"/>
</g>'''
    return document(W, H, 'Magnetar — COSMIC on CachyOS', body, space_style(period))


# ------------------------------------------------------------------ banners

@dataclass(frozen=True)
class Repo:
    repo: str
    name: str
    label: str
    hue: str
    tagline: str
    icon: str | None = None  # app name in com.magnetaros.<icon>.svg, when the repo has one


def _app(slug: str) -> App:
    return next(a for a in APPS if a.slug == slug)


# Taglines are the repositories' GitHub descriptions (or, where that reads
# poorly as a sentence, the README's own opening line).
REPOS = [
    *(Repo(a.slug, a.name, a.category.upper(), a.hue, d, a.name) for a, d in [
        (_app('slate'), 'Calendar and tasks for the COSMIC desktop: plain iCalendar files, CalDAV sync, reminders, a panel applet and a launcher plugin.'),
        (_app('envelope'), 'Mail for the COSMIC desktop: IMAP and Gmail, browser sign-in, threads, a rich composer, and SMTP sending with a durable outbox.'),
        (_app('circle'), 'Contacts for the COSMIC desktop: plain vCard files, CardDAV sync, photos and groups.'),
        (_app('locket'), 'Keep passwords, keys and secrets for your desktop — a Secret Service, SSH agent and vault for COSMIC.'),
        (_app('jump'), 'A Spotlight-class launcher for COSMIC and GNOME.'),
        (_app('peek'), 'A QuickLook-class file previewer for the COSMIC desktop.'),
        (_app('pencil'), 'A rich text editor for the COSMIC desktop: Markdown, MDC, MDX, HTML and plain text, with syntax highlighting, spell checking, a project tree and printing.'),
        (_app('pocket'), 'Boarding passes, tickets and cards for the COSMIC desktop — held as the .pkpass files they arrived in, with barcodes ready to scan.'),
    ]),
    Repo('grabit', 'grabit', 'SELECTION ACTIONS', '#FFC857',
         'Selection actions for Wayland: copy, search, translate, transform, run. PopClip’s idea, built for Wayland.'),
    Repo('magnetar-accounts', 'Accounts', 'ONLINE ACCOUNTS', '#7B9CFF',
         'Add mail, calendar and contacts accounts once — by address, browser sign-in or GNOME Online Accounts — for Envelope, Slate and Circle.'),
    Repo('cosmic-pim', 'cosmic-pim', 'LIBRARY · PIM SUBSTRATE', FIELD,
         'The shared substrate under Slate, Circle and Envelope: storage, sync, credentials, and the iCalendar/vCard layer.'),
    Repo('cosmic-ext-nib', 'Nib', 'LIBRARY · RICH TEXT ENGINE', '#B48CFF',
         'A rich text engine for COSMIC: a document model with invertible steps, HTML, Markdown, MDC, MDX and plain text in and out, and an editor widget libcosmic does not have.'),
    Repo('cosmic-ext-widgets', 'cosmic-ext-widgets', 'LIBRARY · WIDGETS', '#5FD3F3',
         'Widgets libcosmic does not have: an animated reveal, a nav rail, and a sidebar that moves between them.'),
    Repo('magnetar', 'Magnetar', 'DISTRIBUTION', VIOLET,
         'COSMIC on CachyOS, as an actual distribution: a live ISO, a pacman repository, and the packages that make a stock CachyOS install into this one.'),
    Repo('arch-repo', '[magnetar]', 'PACMAN REPOSITORY', CYAN,
         'The signed [magnetar] pacman repository, served from repo.magnetaros.com. Install and upgrade with plain pacman.'),
    Repo('magnetar-web', 'magnetaros.com', 'WEBSITE', ICE,
         'The source of magnetaros.com: a single static page built with Astro, with a live magnetar drawn behind it in three.js.'),
    Repo('logitech-bolt-hidpp-dkms', 'logitech-bolt-hidpp-dkms', 'HARDWARE · DKMS', '#8FB3D9',
         'hid-logitech-hidpp with hi-res wheel diversion on Bolt receivers — the MX Master 4 scroll fix — built by DKMS.'),
    Repo('audient-id24-dkms', 'audient-id24-dkms', 'HARDWARE · DKMS · UCM', '#FF9F6B',
         'The Audient iD24 on Linux: a snd-usb-audio mixer map built by DKMS, and a UCM profile.'),
]


def banner(f: Fonts, r: Repo, icon: str | None, logo: str) -> str:
    W, H = 1280, 400
    rng = random.Random(r.repo)  # per-repo, but stable between builds
    period = 18.0
    x0, width = 600, 1280 - 600 - 64

    if r.repo == 'magnetar':
        hues = [a.hue for a in APPS]
    else:
        hues = [r.hue, mix(r.hue, '#FFFFFF', 0.35), mix(r.hue, VIOLET, 0.35), mix(r.hue, CYAN, 0.3)] * 2

    size = 80.0
    while f.display_black.measure(r.name, size, 0.5) > width:
        size -= 2
    for body_size in (23, 21):
        lines = f.body.wrap(r.tagline, body_size, width)
        if len(lines) <= 3:
            break
    else:
        raise ValueError(f'{r.repo}: tagline needs {len(lines)} lines, the banner holds 3')
    lead = body_size * 1.38
    tag = ''.join(text(f.body, l, x0, 258 + lead * i, body_size, CORONA, opacity=0.86) for i, l in enumerate(lines))

    cx, cy = 300, 200
    if icon is not None:
        centre = (f'<circle cx="{cx}" cy="{cy}" r="120" fill="url(#halo)" class="halo" style="transform-origin:{cx}px {cy}px"/>'
                  + nested(icon, 'ic', cx - 64, cy - 64, 128))
    elif r.repo in ('magnetar', 'arch-repo', 'magnetar-web'):
        centre = (f'<circle cx="{cx}" cy="{cy}" r="110" fill="url(#halo)" class="halo" style="transform-origin:{cx}px {cy}px"/>'
                  f'<circle cx="{cx}" cy="{cy}" r="62" fill="{VOID}" fill-opacity=".72" stroke="{FIELD}" stroke-opacity=".3"/>'
                  + nested(logo, 'mk', cx - 44, cy - 44, 88))
    else:
        centre = f'<g transform="translate({cx} {cy})">{STAR}</g>'

    body = f'''
<defs>{space_defs(W, H, "24%")}</defs>
<g clip-path="url(#frame)">
  <rect width="{W}" height="{H}" fill="url(#sky)"/>
  <g filter="url(#blur)">
    <ellipse cx="{cx}" cy="{cy}" rx="300" ry="160" fill="{r.hue}" opacity=".16"/>
    <ellipse cx="{cx + 80}" cy="{cy + 60}" rx="240" ry="120" fill="{VIOLET}" opacity=".14"/>
    <ellipse cx="1100" cy="60" rx="260" ry="110" fill="{CYAN}" opacity=".10"/>
  </g>
  {starfield(rng, W, H, 170)}
  <g transform="translate({cx} {cy}) rotate(-22)" fill="none" stroke-linecap="round">
    {magnetosphere(hues, [210, 145, 92], period)}
  </g>
  {centre}
  {text(f.mono, r.label, x0, 120, 14, mix(r.hue, '#FFFFFF', 0.25), tracking=3)}
  {text(f.display_black, r.name, x0, 200, size, 'url(#word)', tracking=0.5)}
  {tag}
  {text(f.mono, 'PART OF MAGNETAR · COSMIC ON CACHYOS', x0, 362, 12.5, FIELD, tracking=2, opacity=0.85)}
  <rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="21.5" fill="none" stroke="{FIELD}" stroke-opacity=".18"/>
</g>'''
    return document(W, H, f'{r.name} — {r.tagline}', body, space_style(period))


# -------------------------------------------------------------------- cards

def arrow(cx: float, cy: float, color: str, op: float) -> str:
    return (f'<g fill="none" stroke="{color}" stroke-opacity="{op}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
            f'<circle cx="{cx}" cy="{cy}" r="17" stroke-width="1"/>'
            f'<path d="M{cx - 5} {cy + 5} L{cx + 5} {cy - 5} M{cx - 3} {cy - 5} H{cx + 5} V{cy + 3}"/></g>')


def card(f: Fonts, app: App, icon: str, t: Theme) -> str:
    W, H = 600, 236
    hue_text = ink(app.hue, t)
    summary = f.body.wrap(app.summary, 19, W - 140 - 40)
    if len(summary) > 2:
        raise ValueError(f'{app.name}: summary wraps to {len(summary)} lines, the card holds 2')
    lines = ''.join(text(f.body, s, 140, 132 + 26 * i, 19, t.text, opacity=0.8) for i, s in enumerate(summary))

    footer = []
    if app.benchmark:
        label = 'PARITY WITH'
        footer.append(text(f.mono, label, 32, 209, 12, t.dim, tracking=1.2))
        lx = 32 + f.mono.measure(label, 12, 1.2) + 12
        footer.append(text(f.body_bold, app.benchmark, lx, 210, 17, t.text, opacity=0.9))
    footer.append(text(f.mono, f'pacman -S {app.package}', W - 32, 209, 13, t.dim, anchor='end'))

    body = f'''
<defs>
  <clipPath id="c"><rect width="{W}" height="{H}" rx="20"/></clipPath>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t.bg}"/><stop offset="1" stop-color="{t.bg2}"/></linearGradient>
  <radialGradient id="glow"><stop offset="0" stop-color="{app.hue}" stop-opacity="{t.glow_op}"/><stop offset="1" stop-color="{app.hue}" stop-opacity="0"/></radialGradient>
  <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{app.hue}" stop-opacity=".75"/><stop offset=".45" stop-color="{t.rule}" stop-opacity="{t.rule_op}"/><stop offset="1" stop-color="{t.rule}" stop-opacity="{t.rule_op}"/></linearGradient>
</defs>
<g clip-path="url(#c)">
  <rect width="{W}" height="{H}" fill="url(#bg)"/>
  <circle cx="72" cy="70" r="190" fill="url(#glow)"/>
  {nested(icon, 'ic', 26, 26, 92)}
  {text(f.display, app.name, 140, 68, 34, t.text, tracking=0.3)}
  {text(f.mono, app.category.upper(), 140, 96, 13, hue_text, tracking=1.4)}
  {lines}
  <line x1="32" y1="180" x2="{W - 32}" y2="180" stroke="{t.rule}" stroke-opacity="{t.rule_op}"/>
  {"".join(footer)}
  {arrow(W - 46, 46, t.text, 0.45)}
</g>
<rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5}" rx="19.25" fill="none" stroke="url(#edge)" stroke-width="1.5"/>'''
    return document(W, H, f'{app.name} — {app.category}: {app.summary}', body)


# ------------------------------------------------------------------- layers

def layers(f: Fonts, t: Theme) -> str:
    W, x, size, lead = 1200, 480, 18, 26
    rows, y = [], 72
    for label, title, color, desc in LAYERS:
        rows.append(f'<rect x="{x}" y="{y - 11}" width="10" height="10" rx="2" fill="{color}"/>')
        rows.append(text(f.mono, label, x + 20, y, 13, ink(color, t), tracking=2))
        rows.append(text(f.display, title, x, y + 40, 30, t.text))
        lines = f.body.wrap(desc, size, W - x - 44)
        for i, line in enumerate(lines):
            rows.append(text(f.body, line, x, y + 74 + lead * i, size, t.text, opacity=0.74))
        y += 74 + lead * len(lines) + 34
    H = y - 14
    cx, cy = 235, H // 2
    orbit = ''.join(
        f'<circle cx="{cx + 196 * math.cos(2 * math.pi * i / len(APPS)):.1f}" '
        f'cy="{cy + 196 * math.sin(2 * math.pi * i / len(APPS)):.1f}" r="7" fill="{a.hue}"/>'
        for i, a in enumerate(APPS))

    body = f'''
<defs>
  <clipPath id="c"><rect width="{W}" height="{H}" rx="22"/></clipPath>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t.bg}"/><stop offset="1" stop-color="{t.bg2}"/></linearGradient>
  <radialGradient id="core" cx="42%" cy="38%" r="70%"><stop offset="0" stop-color="#FFE2A8"/><stop offset=".55" stop-color="{FLARE}"/><stop offset="1" stop-color="#E9692C"/></radialGradient>
  <radialGradient id="corona"><stop offset=".55" stop-color="{FIELD}" stop-opacity="0"/><stop offset=".8" stop-color="{FIELD}" stop-opacity="{.22 if t is DARK else .16}"/><stop offset="1" stop-color="{FIELD}" stop-opacity="0"/></radialGradient>
  <radialGradient id="aura"><stop offset="0" stop-color="{VIOLET}" stop-opacity="{.20 if t is DARK else .10}"/><stop offset="1" stop-color="{VIOLET}" stop-opacity="0"/></radialGradient>
</defs>
<g clip-path="url(#c)">
  <rect width="{W}" height="{H}" fill="url(#bg)"/>
  <circle cx="{cx}" cy="{cy}" r="240" fill="url(#aura)"/>
  <circle cx="{cx}" cy="{cy}" r="196" fill="none" stroke="{t.rule}" stroke-opacity="{t.rule_op * 2:.2f}" stroke-dasharray="2 7" stroke-linecap="round"/>
  <g class="orbit">{orbit}</g>
  <circle cx="{cx}" cy="{cy}" r="150" fill="url(#corona)"/>
  <circle cx="{cx}" cy="{cy}" r="122" fill="{FIELD}" fill-opacity="{.10 if t is DARK else .12}" stroke="{FIELD}" stroke-opacity=".55" stroke-width="1.5"/>
  <circle cx="{cx}" cy="{cy}" r="64" fill="url(#core)" class="pulse"/>
  {"".join(rows)}
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="21.5" fill="none" stroke="{t.rule}" stroke-opacity="{t.rule_op}"/>'''
    style = (f'.orbit{{animation:orbit 80s linear infinite;transform-origin:{cx}px {cy}px}}'
             '@keyframes orbit{to{transform:rotate(360deg)}}'
             f'.pulse{{animation:pulse 3.4s ease-in-out infinite alternate;transform-origin:{cx}px {cy}px}}'
             '@keyframes pulse{from{transform:scale(.94)}to{transform:scale(1.04)}}')
    return document(W, H, 'Three layers: the suite on COSMIC on Arch and CachyOS', body, style)


# -------------------------------------------------------------------- stats

def stats(f: Fonts, t: Theme) -> str:
    W, H = 1200, 196
    col = (W - 80) / len(STATS)
    cells = []
    for i, (big, label) in enumerate(STATS):
        x = 40 + col * i + 24
        if f.display.measure(big, 56) > col - 48:
            raise ValueError(f'stat {big!r} is wider than its column')
        cells.append(text(f.display, big, x, 114, 56, 'url(#num)'))
        cells.append(text(f.body, label, x, 148, 16.5, t.text, opacity=0.72))
        if i:
            cells.append(f'<line x1="{40 + col * i}" y1="60" x2="{40 + col * i}" y2="160" stroke="{t.rule}" stroke-opacity="{t.rule_op}"/>')
    body = f'''
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t.bg}"/><stop offset="1" stop-color="{t.bg2}"/></linearGradient>
  <linearGradient id="num" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{VIOLET if t is DARK else '#5B3FE0'}"/><stop offset="1" stop-color="{ICE if t is DARK else '#1A86BF'}"/></linearGradient>
</defs>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="21.5" fill="url(#bg)" stroke="{t.rule}" stroke-opacity="{t.rule_op}"/>
{text(f.mono, f'MEASURED  ·  {MEASURED}  ·  COMMITTED main OF EVERY RUST REPOSITORY', 64, 42, 12, t.dim, tracking=1.4)}
{"".join(cells)}'''
    return document(W, H, '222,506 lines of Rust, 3,085 tests, zero todo!() calls; apps GPL-3.0, substrate MPL-2.0. Measured September 2026.', body)


# -------------------------------------------------------------------- pills

def pill(f: Fonts, label: str, t: Theme | None) -> str:
    """A link button. t=None is the filled brand-gradient one, the same in both schemes."""
    size, pad, h = 16, 26, 46
    tw = f.body_bold.measure(label, size)
    W = round(tw + pad * 2 + 22)
    fg = '#FFFFFF' if t is None else t.text
    if t is None:
        shape = (f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{VIOLET}"/>'
                 f'<stop offset="1" stop-color="{CYAN}"/></linearGradient></defs>'
                 f'<rect width="{W}" height="{h}" rx="{h / 2}" fill="url(#g)"/>')
    else:
        shape = (f'<rect x=".75" y=".75" width="{W - 1.5}" height="{h - 1.5}" rx="{(h - 1.5) / 2}" fill="{t.bg}" '
                 f'stroke="{t.rule}" stroke-opacity="{t.rule_op * 2.2:.2f}" stroke-width="1.5"/>')
    ax, ay = pad + tw + 14, h / 2
    head = (f'<path d="M{ax - 4} {ay + 4} L{ax + 4} {ay - 4} M{ax - 2} {ay - 4} H{ax + 4} V{ay + 2}" fill="none" '
            f'stroke="{fg}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>')
    return document(W, h, label, shape + text(f.body_bold, label, pad, h / 2 + 5.6, size, fg) + head)


# --------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--brand', type=Path, default=ROOT.parent / 'magnetar-brand')
    ap.add_argument('--web', type=Path, default=ROOT.parent / 'magnetar-web')
    args = ap.parse_args()

    fonts = load_fonts(args.web)
    logo = (args.brand / 'distribution/logo/magnetar.svg').read_text()
    for d in (OUT, OUT / 'repos', OUT / 'icons'):
        d.mkdir(parents=True, exist_ok=True)

    out = {'hero.svg': hero(fonts, logo), 'pill-site.svg': pill(fonts, 'magnetaros.com', None), 'mark.svg': logo}
    for t in (DARK, LIGHT):
        for app in APPS:
            icon = (args.brand / f'icons/hicolor/scalable/apps/com.magnetaros.{app.name}.svg').read_text()
            out[f'card-{app.slug}-{t.name}.svg'] = card(fonts, app, icon, t)
        out[f'layers-{t.name}.svg'] = layers(fonts, t)
        out[f'stats-{t.name}.svg'] = stats(fonts, t)
        out[f'pill-install-{t.name}.svg'] = pill(fonts, 'Install', t)
        out[f'pill-repos-{t.name}.svg'] = pill(fonts, 'All repositories', t)
        out[f'pill-releases-{t.name}.svg'] = pill(fonts, 'Releases', t)

    # Shared art for every repository's own README: a banner each, and the
    # app icons for the suite strip in their footers.
    for r in REPOS:
        icon = (args.brand / f'icons/hicolor/scalable/apps/com.magnetaros.{r.icon}.svg').read_text() if r.icon else None
        out[f'repos/{r.repo}.svg'] = banner(fonts, r, icon, logo)
    for app in APPS:
        out[f'icons/{app.slug}.svg'] = (args.brand / f'icons/hicolor/scalable/apps/com.magnetaros.{app.name}.svg').read_text()

    for name, svg in out.items():
        (OUT / name).write_text(svg)
    print(f'wrote {len(out)} files to {OUT.relative_to(ROOT)}/')


if __name__ == '__main__':
    main()
