"""Assemble la carte : source + générateur de QR code (MIT, Kazuhiko Arase) dans un seul fichier."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).parents[1]
lib = (ROOT / "vendor" / "qrcode-generator-1.4.4.js").read_text()
qr = ("(() => {\n/* QR Code Generator for JavaScript — Copyright (c) 2009 Kazuhiko Arase — MIT license */\n"
      "const define = undefined, exports = undefined, module = undefined;\n" + lib +
      "\nqrcode.stringToBytes = qrcode.stringToBytesFuncs['UTF-8'];\nreturn qrcode;\n})()")
src = (ROOT / "src" / "visiteurs-card.src.js").read_text()
assert "__QR__;" in src
out = src.replace("/* global __QR__ */\n", "").replace("const QR = __QR__;", "const QR = " + qr + ";", 1)
dest = ROOT / "custom_components" / "visiteurs" / "frontend" / "visiteurs-card.js"
dest.write_text(out)
subprocess.run(["node", "--check", str(dest)], check=True)
print(dest, len(out))
