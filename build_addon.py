"""Package the add-on into dist/achernar-<version>.nvda-addon.

An .nvda-addon is a zip whose entries use forward slashes, which Python's
zipfile writes, so NVDA can read the archive on every Windows version. Only
the add-on's own top-level items are packaged; repository files such as
README.md, the helper/ source, and the licence files are not part of the
package.

Run:  python build_addon.py
"""

import os
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
VERSION = "1.0.0"
OUT_NAME = "achernar-%s.nvda-addon" % VERSION
INCLUDE = ("manifest.ini", "doc", "synthDrivers")
SKIP_DIRS = {"__pycache__"}
SKIP_EXT = {".pyc", ".pyo"}


def main():
    if not os.path.isfile(os.path.join(ROOT, "manifest.ini")):
        raise SystemExit("manifest.ini not found in %s" % ROOT)
    out_dir = os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, OUT_NAME)

    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in INCLUDE:
            path = os.path.join(ROOT, name)
            if os.path.isfile(path):
                z.write(path, name)
                count += 1
                continue
            for base, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for f in files:
                    if os.path.splitext(f)[1] in SKIP_EXT:
                        continue
                    full = os.path.join(base, f)
                    rel = os.path.relpath(full, ROOT).replace("\\", "/")
                    z.write(full, rel)
                    count += 1

    print("wrote %s (%d files, %.1f MB)"
          % (out, count, os.path.getsize(out) / (1024 * 1024)))


if __name__ == "__main__":
    main()
