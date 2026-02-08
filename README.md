# SkyBox Architect

[![Release](https://img.shields.io/github/v/release/fl4te/skybox_architect?label=latest%20release)](https://github.com/fl4te/skybox_architect/releases) &nbsp;•&nbsp; [![Build Status](https://github.com/fl4te/skybox_architect/actions/workflows/build_and_release.yml/badge.svg?branch=main)](https://github.com/fl4te/skybox_architect/actions/workflows/build_and_release.yml) &nbsp;•&nbsp; [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**A tool for converting equirectangular panoramas into cubemaps.**

![SkyBox Architect Screenshot](https://i.ibb.co/B2wWfWbj/Bildschirmfoto-20260208-024707.png)

---

## Features

- **Panorama to Skybox Conversion**: Convert equirectangular (360°) images into 6 cube faces for Q3 based games.
- **Customizable Output**: Adjust resolution (512, 1024, 2048, 4096), prefix, and orientation (yaw, pitch).
- **Engine-Specific Tweaks**: Flip top/bottom faces and rotate them to match Q3 standards.
- **Real-Time Preview**: Visualize all 6 faces before exporting.

---

## Usage

### Import a Panorama:

Click "Import Image" and select a 360° equirectangular image (JPG, PNG, TGA).


### Adjust Settings:

Prefix: Set a name for your skybox files (e.g., my_skybox).
Size: Choose the output resolution (512, 1024, 2048, 4096).
Yaw/Pitch: Fine-tune the horizontal/vertical orientation.
Flip UP/DN: Toggle to match Q3’s coordinate system.
Rotate Top/Bottom: Fix orientation issues for top/bottom faces.


### Preview & Export:

Preview all 6 faces in real-time.
Click "Export" to save the skybox faces to a folder.


### Output Files
The tool exports 6 JPG files with the following naming convention:
```
<prefix>_ft.jpg  # Front
<prefix>_bk.jpg  # Back
<prefix>_lf.jpg  # Left
<prefix>_rt.jpg  # Right
<prefix>_up.jpg  # Top
<prefix>_dn.jpg  # Bottom
```

## GitHub Workflow
This project includes a GitHub Actions workflow to automatically build and release executables for Windows, Linux, and macOS.
