# OpenScreen background presets

These are exact, unmodified copies of the wallpapers shipped by OpenScreen at
revision `47ab52fd0907ed07336fa1ff868e671d5d5a469f`. The upstream repository publishes
them under its [MIT license](../OPENSCREEN-LICENSE). Original filenames, source
revision, dimensions, and SHA-256 digests are recorded in `manifest.json`.

- **Aurora** (default): flowing teal, coral and cream.
- **Spectrum**: energetic blue and orange painterly strokes.
- **Coastline**: calmer teal and gold layered scenery.

Source: https://github.com/getopenscreen/openscreen/tree/47ab52fd0907ed07336fa1ff868e671d5d5a469f/public/wallpapers

`helpers/openscreen_backgrounds.py` resolves these portable assets. Project
preparation copies the selected wallpaper into the project's reproducible bundle;
the OpenScreen runtime draws it through its own native compositor. The helpers do
not generate or re-encode the background.
