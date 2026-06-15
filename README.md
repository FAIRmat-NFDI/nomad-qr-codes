[![Publish to PyPI](https://github.com/FAIRmat-NFDI/nomad-qr-codes/actions/workflows/python-publish.yml/badge.svg)](https://github.com/FAIRmat-NFDI/nomad-qr-codes/actions/workflows/python-publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/nomad-qr-codes.svg)](https://pypi.org/project/nomad-qr-codes/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

# NOMAD QR Codes

Generate branded QR codes (PNG or SVG) with rounded dots, styled finder eyelets, and an embedded center logo:

![NOMAD QR code](./examples/nomad-dark.png#gh-dark-mode-only)
![NOMAD QR code](./examples/nomad-light.png#gh-light-mode-only)

The package installs a CLI command:

- `nomad-qr-codes`

## Installation

Install from PyPI:

```bash
pip install nomad-qr-codes
```

If you prefer uv:

```bash
uv pip install nomad-qr-codes
```

For editable local development:

```bash
pip install -e .
```

## Quick Start

Generate a QR code using the default preset and transparent background:

```bash
uv run nomad-qr-codes "https://nomad-lab.eu"
```

This creates:

- generated-nomad-qr.png

## CLI Usage

```bash
nomad-qr-codes DATA [OPTIONS]
```

### Required argument

- DATA: URL or text to encode.

Example:

```bash
nomad-qr-codes "https://nomad-lab.eu"
```

### Options

- --preset {default,dark,oasis,dtu}
	- Selects preset colors and bundled logo.
	- Default: default
- --output PATH
	- Output file path.
	- Default: generated-nomad-qr.png
- --logo PATH
	- Use a custom center logo SVG instead of bundled logos.
- --color HEX
	- Override QR foreground color (example: #192E87).
- --eyelet-color HEX
	- Override finder eyelet color.
- --format {png,svg}
	- Output format.
	- If omitted, inferred from output file extension.
- --white-background
	- Enables white page background and white logo backing.
	- Without this flag, background is transparent.

## Examples

Generate transparent PNG with default preset:

```bash
uv run nomad-qr-codes "https://nomad-lab.eu"
```

Generate white-background PNG:

```bash
uv run nomad-qr-codes "https://nomad-lab.eu" --white-background
```

Generate SVG output:

```bash
uv run nomad-qr-codes "https://nomad-lab.eu" --format svg --output nomad-qr.svg
```

Use oasis preset:

```bash
uv run nomad-qr-codes "https://nomad-lab.eu" --preset oasis
```

Use custom colors:

```bash
uv run nomad-qr-codes "https://nomad-lab.eu" --color "#0B1E4D" --eyelet-color "#22A06B"
```

Use a custom logo:

```bash
uv run nomad-qr-codes "https://nomad-lab.eu" --logo ./my-logo.svg
```

## Presets

- default: NOMAD default palette
- dark: NOMAD dark palette
- oasis: Oasis palette
- dtu: DTU red palette

Bundled logos are packaged with the Python package under src/nomad_qr_codes/assets/logos.

## Notes

- For best scanning reliability, keep high contrast between foreground and background.
- Very large center logos can hurt scan performance.
- SVG output is ideal when you need scalable print assets.
