/* Carte « Visiteurs » — module Visiteurs (Basilik41/hass-visiteurs).
 *   type: custom:visiteurs-card
 *   mode: auto | gestion | accueil     (auto : tablette murale → accueil ; sinon gestion)
 *   title: Visiteurs
 */
const VERSION = "1.3.0";
const QR = (() => {
/* QR Code Generator for JavaScript — Copyright (c) 2009 Kazuhiko Arase — MIT license */
const define = undefined, exports = undefined, module = undefined;
//---------------------------------------------------------------------
//
// QR Code Generator for JavaScript
//
// Copyright (c) 2009 Kazuhiko Arase
//
// URL: http://www.d-project.com/
//
// Licensed under the MIT license:
//  http://www.opensource.org/licenses/mit-license.php
//
// The word 'QR Code' is registered trademark of
// DENSO WAVE INCORPORATED
//  http://www.denso-wave.com/qrcode/faqpatent-e.html
//
//---------------------------------------------------------------------

var qrcode = function() {

  //---------------------------------------------------------------------
  // qrcode
  //---------------------------------------------------------------------

  /**
   * qrcode
   * @param typeNumber 1 to 40
   * @param errorCorrectionLevel 'L','M','Q','H'
   */
  var qrcode = function(typeNumber, errorCorrectionLevel) {

    var PAD0 = 0xEC;
    var PAD1 = 0x11;

    var _typeNumber = typeNumber;
    var _errorCorrectionLevel = QRErrorCorrectionLevel[errorCorrectionLevel];
    var _modules = null;
    var _moduleCount = 0;
    var _dataCache = null;
    var _dataList = [];

    var _this = {};

    var makeImpl = function(test, maskPattern) {

      _moduleCount = _typeNumber * 4 + 17;
      _modules = function(moduleCount) {
        var modules = new Array(moduleCount);
        for (var row = 0; row < moduleCount; row += 1) {
          modules[row] = new Array(moduleCount);
          for (var col = 0; col < moduleCount; col += 1) {
            modules[row][col] = null;
          }
        }
        return modules;
      }(_moduleCount);

      setupPositionProbePattern(0, 0);
      setupPositionProbePattern(_moduleCount - 7, 0);
      setupPositionProbePattern(0, _moduleCount - 7);
      setupPositionAdjustPattern();
      setupTimingPattern();
      setupTypeInfo(test, maskPattern);

      if (_typeNumber >= 7) {
        setupTypeNumber(test);
      }

      if (_dataCache == null) {
        _dataCache = createData(_typeNumber, _errorCorrectionLevel, _dataList);
      }

      mapData(_dataCache, maskPattern);
    };

    var setupPositionProbePattern = function(row, col) {

      for (var r = -1; r <= 7; r += 1) {

        if (row + r <= -1 || _moduleCount <= row + r) continue;

        for (var c = -1; c <= 7; c += 1) {

          if (col + c <= -1 || _moduleCount <= col + c) continue;

          if ( (0 <= r && r <= 6 && (c == 0 || c == 6) )
              || (0 <= c && c <= 6 && (r == 0 || r == 6) )
              || (2 <= r && r <= 4 && 2 <= c && c <= 4) ) {
            _modules[row + r][col + c] = true;
          } else {
            _modules[row + r][col + c] = false;
          }
        }
      }
    };

    var getBestMaskPattern = function() {

      var minLostPoint = 0;
      var pattern = 0;

      for (var i = 0; i < 8; i += 1) {

        makeImpl(true, i);

        var lostPoint = QRUtil.getLostPoint(_this);

        if (i == 0 || minLostPoint > lostPoint) {
          minLostPoint = lostPoint;
          pattern = i;
        }
      }

      return pattern;
    };

    var setupTimingPattern = function() {

      for (var r = 8; r < _moduleCount - 8; r += 1) {
        if (_modules[r][6] != null) {
          continue;
        }
        _modules[r][6] = (r % 2 == 0);
      }

      for (var c = 8; c < _moduleCount - 8; c += 1) {
        if (_modules[6][c] != null) {
          continue;
        }
        _modules[6][c] = (c % 2 == 0);
      }
    };

    var setupPositionAdjustPattern = function() {

      var pos = QRUtil.getPatternPosition(_typeNumber);

      for (var i = 0; i < pos.length; i += 1) {

        for (var j = 0; j < pos.length; j += 1) {

          var row = pos[i];
          var col = pos[j];

          if (_modules[row][col] != null) {
            continue;
          }

          for (var r = -2; r <= 2; r += 1) {

            for (var c = -2; c <= 2; c += 1) {

              if (r == -2 || r == 2 || c == -2 || c == 2
                  || (r == 0 && c == 0) ) {
                _modules[row + r][col + c] = true;
              } else {
                _modules[row + r][col + c] = false;
              }
            }
          }
        }
      }
    };

    var setupTypeNumber = function(test) {

      var bits = QRUtil.getBCHTypeNumber(_typeNumber);

      for (var i = 0; i < 18; i += 1) {
        var mod = (!test && ( (bits >> i) & 1) == 1);
        _modules[Math.floor(i / 3)][i % 3 + _moduleCount - 8 - 3] = mod;
      }

      for (var i = 0; i < 18; i += 1) {
        var mod = (!test && ( (bits >> i) & 1) == 1);
        _modules[i % 3 + _moduleCount - 8 - 3][Math.floor(i / 3)] = mod;
      }
    };

    var setupTypeInfo = function(test, maskPattern) {

      var data = (_errorCorrectionLevel << 3) | maskPattern;
      var bits = QRUtil.getBCHTypeInfo(data);

      // vertical
      for (var i = 0; i < 15; i += 1) {

        var mod = (!test && ( (bits >> i) & 1) == 1);

        if (i < 6) {
          _modules[i][8] = mod;
        } else if (i < 8) {
          _modules[i + 1][8] = mod;
        } else {
          _modules[_moduleCount - 15 + i][8] = mod;
        }
      }

      // horizontal
      for (var i = 0; i < 15; i += 1) {

        var mod = (!test && ( (bits >> i) & 1) == 1);

        if (i < 8) {
          _modules[8][_moduleCount - i - 1] = mod;
        } else if (i < 9) {
          _modules[8][15 - i - 1 + 1] = mod;
        } else {
          _modules[8][15 - i - 1] = mod;
        }
      }

      // fixed module
      _modules[_moduleCount - 8][8] = (!test);
    };

    var mapData = function(data, maskPattern) {

      var inc = -1;
      var row = _moduleCount - 1;
      var bitIndex = 7;
      var byteIndex = 0;
      var maskFunc = QRUtil.getMaskFunction(maskPattern);

      for (var col = _moduleCount - 1; col > 0; col -= 2) {

        if (col == 6) col -= 1;

        while (true) {

          for (var c = 0; c < 2; c += 1) {

            if (_modules[row][col - c] == null) {

              var dark = false;

              if (byteIndex < data.length) {
                dark = ( ( (data[byteIndex] >>> bitIndex) & 1) == 1);
              }

              var mask = maskFunc(row, col - c);

              if (mask) {
                dark = !dark;
              }

              _modules[row][col - c] = dark;
              bitIndex -= 1;

              if (bitIndex == -1) {
                byteIndex += 1;
                bitIndex = 7;
              }
            }
          }

          row += inc;

          if (row < 0 || _moduleCount <= row) {
            row -= inc;
            inc = -inc;
            break;
          }
        }
      }
    };

    var createBytes = function(buffer, rsBlocks) {

      var offset = 0;

      var maxDcCount = 0;
      var maxEcCount = 0;

      var dcdata = new Array(rsBlocks.length);
      var ecdata = new Array(rsBlocks.length);

      for (var r = 0; r < rsBlocks.length; r += 1) {

        var dcCount = rsBlocks[r].dataCount;
        var ecCount = rsBlocks[r].totalCount - dcCount;

        maxDcCount = Math.max(maxDcCount, dcCount);
        maxEcCount = Math.max(maxEcCount, ecCount);

        dcdata[r] = new Array(dcCount);

        for (var i = 0; i < dcdata[r].length; i += 1) {
          dcdata[r][i] = 0xff & buffer.getBuffer()[i + offset];
        }
        offset += dcCount;

        var rsPoly = QRUtil.getErrorCorrectPolynomial(ecCount);
        var rawPoly = qrPolynomial(dcdata[r], rsPoly.getLength() - 1);

        var modPoly = rawPoly.mod(rsPoly);
        ecdata[r] = new Array(rsPoly.getLength() - 1);
        for (var i = 0; i < ecdata[r].length; i += 1) {
          var modIndex = i + modPoly.getLength() - ecdata[r].length;
          ecdata[r][i] = (modIndex >= 0)? modPoly.getAt(modIndex) : 0;
        }
      }

      var totalCodeCount = 0;
      for (var i = 0; i < rsBlocks.length; i += 1) {
        totalCodeCount += rsBlocks[i].totalCount;
      }

      var data = new Array(totalCodeCount);
      var index = 0;

      for (var i = 0; i < maxDcCount; i += 1) {
        for (var r = 0; r < rsBlocks.length; r += 1) {
          if (i < dcdata[r].length) {
            data[index] = dcdata[r][i];
            index += 1;
          }
        }
      }

      for (var i = 0; i < maxEcCount; i += 1) {
        for (var r = 0; r < rsBlocks.length; r += 1) {
          if (i < ecdata[r].length) {
            data[index] = ecdata[r][i];
            index += 1;
          }
        }
      }

      return data;
    };

    var createData = function(typeNumber, errorCorrectionLevel, dataList) {

      var rsBlocks = QRRSBlock.getRSBlocks(typeNumber, errorCorrectionLevel);

      var buffer = qrBitBuffer();

      for (var i = 0; i < dataList.length; i += 1) {
        var data = dataList[i];
        buffer.put(data.getMode(), 4);
        buffer.put(data.getLength(), QRUtil.getLengthInBits(data.getMode(), typeNumber) );
        data.write(buffer);
      }

      // calc num max data.
      var totalDataCount = 0;
      for (var i = 0; i < rsBlocks.length; i += 1) {
        totalDataCount += rsBlocks[i].dataCount;
      }

      if (buffer.getLengthInBits() > totalDataCount * 8) {
        throw 'code length overflow. ('
          + buffer.getLengthInBits()
          + '>'
          + totalDataCount * 8
          + ')';
      }

      // end code
      if (buffer.getLengthInBits() + 4 <= totalDataCount * 8) {
        buffer.put(0, 4);
      }

      // padding
      while (buffer.getLengthInBits() % 8 != 0) {
        buffer.putBit(false);
      }

      // padding
      while (true) {

        if (buffer.getLengthInBits() >= totalDataCount * 8) {
          break;
        }
        buffer.put(PAD0, 8);

        if (buffer.getLengthInBits() >= totalDataCount * 8) {
          break;
        }
        buffer.put(PAD1, 8);
      }

      return createBytes(buffer, rsBlocks);
    };

    _this.addData = function(data, mode) {

      mode = mode || 'Byte';

      var newData = null;

      switch(mode) {
      case 'Numeric' :
        newData = qrNumber(data);
        break;
      case 'Alphanumeric' :
        newData = qrAlphaNum(data);
        break;
      case 'Byte' :
        newData = qr8BitByte(data);
        break;
      case 'Kanji' :
        newData = qrKanji(data);
        break;
      default :
        throw 'mode:' + mode;
      }

      _dataList.push(newData);
      _dataCache = null;
    };

    _this.isDark = function(row, col) {
      if (row < 0 || _moduleCount <= row || col < 0 || _moduleCount <= col) {
        throw row + ',' + col;
      }
      return _modules[row][col];
    };

    _this.getModuleCount = function() {
      return _moduleCount;
    };

    _this.make = function() {
      if (_typeNumber < 1) {
        var typeNumber = 1;

        for (; typeNumber < 40; typeNumber++) {
          var rsBlocks = QRRSBlock.getRSBlocks(typeNumber, _errorCorrectionLevel);
          var buffer = qrBitBuffer();

          for (var i = 0; i < _dataList.length; i++) {
            var data = _dataList[i];
            buffer.put(data.getMode(), 4);
            buffer.put(data.getLength(), QRUtil.getLengthInBits(data.getMode(), typeNumber) );
            data.write(buffer);
          }

          var totalDataCount = 0;
          for (var i = 0; i < rsBlocks.length; i++) {
            totalDataCount += rsBlocks[i].dataCount;
          }

          if (buffer.getLengthInBits() <= totalDataCount * 8) {
            break;
          }
        }

        _typeNumber = typeNumber;
      }

      makeImpl(false, getBestMaskPattern() );
    };

    _this.createTableTag = function(cellSize, margin) {

      cellSize = cellSize || 2;
      margin = (typeof margin == 'undefined')? cellSize * 4 : margin;

      var qrHtml = '';

      qrHtml += '<table style="';
      qrHtml += ' border-width: 0px; border-style: none;';
      qrHtml += ' border-collapse: collapse;';
      qrHtml += ' padding: 0px; margin: ' + margin + 'px;';
      qrHtml += '">';
      qrHtml += '<tbody>';

      for (var r = 0; r < _this.getModuleCount(); r += 1) {

        qrHtml += '<tr>';

        for (var c = 0; c < _this.getModuleCount(); c += 1) {
          qrHtml += '<td style="';
          qrHtml += ' border-width: 0px; border-style: none;';
          qrHtml += ' border-collapse: collapse;';
          qrHtml += ' padding: 0px; margin: 0px;';
          qrHtml += ' width: ' + cellSize + 'px;';
          qrHtml += ' height: ' + cellSize + 'px;';
          qrHtml += ' background-color: ';
          qrHtml += _this.isDark(r, c)? '#000000' : '#ffffff';
          qrHtml += ';';
          qrHtml += '"/>';
        }

        qrHtml += '</tr>';
      }

      qrHtml += '</tbody>';
      qrHtml += '</table>';

      return qrHtml;
    };

    _this.createSvgTag = function(cellSize, margin, alt, title) {

      var opts = {};
      if (typeof arguments[0] == 'object') {
        // Called by options.
        opts = arguments[0];
        // overwrite cellSize and margin.
        cellSize = opts.cellSize;
        margin = opts.margin;
        alt = opts.alt;
        title = opts.title;
      }

      cellSize = cellSize || 2;
      margin = (typeof margin == 'undefined')? cellSize * 4 : margin;

      // Compose alt property surrogate
      alt = (typeof alt === 'string') ? {text: alt} : alt || {};
      alt.text = alt.text || null;
      alt.id = (alt.text) ? alt.id || 'qrcode-description' : null;

      // Compose title property surrogate
      title = (typeof title === 'string') ? {text: title} : title || {};
      title.text = title.text || null;
      title.id = (title.text) ? title.id || 'qrcode-title' : null;

      var size = _this.getModuleCount() * cellSize + margin * 2;
      var c, mc, r, mr, qrSvg='', rect;

      rect = 'l' + cellSize + ',0 0,' + cellSize +
        ' -' + cellSize + ',0 0,-' + cellSize + 'z ';

      qrSvg += '<svg version="1.1" xmlns="http://www.w3.org/2000/svg"';
      qrSvg += !opts.scalable ? ' width="' + size + 'px" height="' + size + 'px"' : '';
      qrSvg += ' viewBox="0 0 ' + size + ' ' + size + '" ';
      qrSvg += ' preserveAspectRatio="xMinYMin meet"';
      qrSvg += (title.text || alt.text) ? ' role="img" aria-labelledby="' +
          escapeXml([title.id, alt.id].join(' ').trim() ) + '"' : '';
      qrSvg += '>';
      qrSvg += (title.text) ? '<title id="' + escapeXml(title.id) + '">' +
          escapeXml(title.text) + '</title>' : '';
      qrSvg += (alt.text) ? '<description id="' + escapeXml(alt.id) + '">' +
          escapeXml(alt.text) + '</description>' : '';
      qrSvg += '<rect width="100%" height="100%" fill="white" cx="0" cy="0"/>';
      qrSvg += '<path d="';

      for (r = 0; r < _this.getModuleCount(); r += 1) {
        mr = r * cellSize + margin;
        for (c = 0; c < _this.getModuleCount(); c += 1) {
          if (_this.isDark(r, c) ) {
            mc = c*cellSize+margin;
            qrSvg += 'M' + mc + ',' + mr + rect;
          }
        }
      }

      qrSvg += '" stroke="transparent" fill="black"/>';
      qrSvg += '</svg>';

      return qrSvg;
    };

    _this.createDataURL = function(cellSize, margin) {

      cellSize = cellSize || 2;
      margin = (typeof margin == 'undefined')? cellSize * 4 : margin;

      var size = _this.getModuleCount() * cellSize + margin * 2;
      var min = margin;
      var max = size - margin;

      return createDataURL(size, size, function(x, y) {
        if (min <= x && x < max && min <= y && y < max) {
          var c = Math.floor( (x - min) / cellSize);
          var r = Math.floor( (y - min) / cellSize);
          return _this.isDark(r, c)? 0 : 1;
        } else {
          return 1;
        }
      } );
    };

    _this.createImgTag = function(cellSize, margin, alt) {

      cellSize = cellSize || 2;
      margin = (typeof margin == 'undefined')? cellSize * 4 : margin;

      var size = _this.getModuleCount() * cellSize + margin * 2;

      var img = '';
      img += '<img';
      img += '\u0020src="';
      img += _this.createDataURL(cellSize, margin);
      img += '"';
      img += '\u0020width="';
      img += size;
      img += '"';
      img += '\u0020height="';
      img += size;
      img += '"';
      if (alt) {
        img += '\u0020alt="';
        img += escapeXml(alt);
        img += '"';
      }
      img += '/>';

      return img;
    };

    var escapeXml = function(s) {
      var escaped = '';
      for (var i = 0; i < s.length; i += 1) {
        var c = s.charAt(i);
        switch(c) {
        case '<': escaped += '&lt;'; break;
        case '>': escaped += '&gt;'; break;
        case '&': escaped += '&amp;'; break;
        case '"': escaped += '&quot;'; break;
        default : escaped += c; break;
        }
      }
      return escaped;
    };

    var _createHalfASCII = function(margin) {
      var cellSize = 1;
      margin = (typeof margin == 'undefined')? cellSize * 2 : margin;

      var size = _this.getModuleCount() * cellSize + margin * 2;
      var min = margin;
      var max = size - margin;

      var y, x, r1, r2, p;

      var blocks = {
        '██': '█',
        '█ ': '▀',
        ' █': '▄',
        '  ': ' '
      };

      var blocksLastLineNoMargin = {
        '██': '▀',
        '█ ': '▀',
        ' █': ' ',
        '  ': ' '
      };

      var ascii = '';
      for (y = 0; y < size; y += 2) {
        r1 = Math.floor((y - min) / cellSize);
        r2 = Math.floor((y + 1 - min) / cellSize);
        for (x = 0; x < size; x += 1) {
          p = '█';

          if (min <= x && x < max && min <= y && y < max && _this.isDark(r1, Math.floor((x - min) / cellSize))) {
            p = ' ';
          }

          if (min <= x && x < max && min <= y+1 && y+1 < max && _this.isDark(r2, Math.floor((x - min) / cellSize))) {
            p += ' ';
          }
          else {
            p += '█';
          }

          // Output 2 characters per pixel, to create full square. 1 character per pixels gives only half width of square.
          ascii += (margin < 1 && y+1 >= max) ? blocksLastLineNoMargin[p] : blocks[p];
        }

        ascii += '\n';
      }

      if (size % 2 && margin > 0) {
        return ascii.substring(0, ascii.length - size - 1) + Array(size+1).join('▀');
      }

      return ascii.substring(0, ascii.length-1);
    };

    _this.createASCII = function(cellSize, margin) {
      cellSize = cellSize || 1;

      if (cellSize < 2) {
        return _createHalfASCII(margin);
      }

      cellSize -= 1;
      margin = (typeof margin == 'undefined')? cellSize * 2 : margin;

      var size = _this.getModuleCount() * cellSize + margin * 2;
      var min = margin;
      var max = size - margin;

      var y, x, r, p;

      var white = Array(cellSize+1).join('██');
      var black = Array(cellSize+1).join('  ');

      var ascii = '';
      var line = '';
      for (y = 0; y < size; y += 1) {
        r = Math.floor( (y - min) / cellSize);
        line = '';
        for (x = 0; x < size; x += 1) {
          p = 1;

          if (min <= x && x < max && min <= y && y < max && _this.isDark(r, Math.floor((x - min) / cellSize))) {
            p = 0;
          }

          // Output 2 characters per pixel, to create full square. 1 character per pixels gives only half width of square.
          line += p ? white : black;
        }

        for (r = 0; r < cellSize; r += 1) {
          ascii += line + '\n';
        }
      }

      return ascii.substring(0, ascii.length-1);
    };

    _this.renderTo2dContext = function(context, cellSize) {
      cellSize = cellSize || 2;
      var length = _this.getModuleCount();
      for (var row = 0; row < length; row++) {
        for (var col = 0; col < length; col++) {
          context.fillStyle = _this.isDark(row, col) ? 'black' : 'white';
          context.fillRect(row * cellSize, col * cellSize, cellSize, cellSize);
        }
      }
    }

    return _this;
  };

  //---------------------------------------------------------------------
  // qrcode.stringToBytes
  //---------------------------------------------------------------------

  qrcode.stringToBytesFuncs = {
    'default' : function(s) {
      var bytes = [];
      for (var i = 0; i < s.length; i += 1) {
        var c = s.charCodeAt(i);
        bytes.push(c & 0xff);
      }
      return bytes;
    }
  };

  qrcode.stringToBytes = qrcode.stringToBytesFuncs['default'];

  //---------------------------------------------------------------------
  // qrcode.createStringToBytes
  //---------------------------------------------------------------------

  /**
   * @param unicodeData base64 string of byte array.
   * [16bit Unicode],[16bit Bytes], ...
   * @param numChars
   */
  qrcode.createStringToBytes = function(unicodeData, numChars) {

    // create conversion map.

    var unicodeMap = function() {

      var bin = base64DecodeInputStream(unicodeData);
      var read = function() {
        var b = bin.read();
        if (b == -1) throw 'eof';
        return b;
      };

      var count = 0;
      var unicodeMap = {};
      while (true) {
        var b0 = bin.read();
        if (b0 == -1) break;
        var b1 = read();
        var b2 = read();
        var b3 = read();
        var k = String.fromCharCode( (b0 << 8) | b1);
        var v = (b2 << 8) | b3;
        unicodeMap[k] = v;
        count += 1;
      }
      if (count != numChars) {
        throw count + ' != ' + numChars;
      }

      return unicodeMap;
    }();

    var unknownChar = '?'.charCodeAt(0);

    return function(s) {
      var bytes = [];
      for (var i = 0; i < s.length; i += 1) {
        var c = s.charCodeAt(i);
        if (c < 128) {
          bytes.push(c);
        } else {
          var b = unicodeMap[s.charAt(i)];
          if (typeof b == 'number') {
            if ( (b & 0xff) == b) {
              // 1byte
              bytes.push(b);
            } else {
              // 2bytes
              bytes.push(b >>> 8);
              bytes.push(b & 0xff);
            }
          } else {
            bytes.push(unknownChar);
          }
        }
      }
      return bytes;
    };
  };

  //---------------------------------------------------------------------
  // QRMode
  //---------------------------------------------------------------------

  var QRMode = {
    MODE_NUMBER :    1 << 0,
    MODE_ALPHA_NUM : 1 << 1,
    MODE_8BIT_BYTE : 1 << 2,
    MODE_KANJI :     1 << 3
  };

  //---------------------------------------------------------------------
  // QRErrorCorrectionLevel
  //---------------------------------------------------------------------

  var QRErrorCorrectionLevel = {
    L : 1,
    M : 0,
    Q : 3,
    H : 2
  };

  //---------------------------------------------------------------------
  // QRMaskPattern
  //---------------------------------------------------------------------

  var QRMaskPattern = {
    PATTERN000 : 0,
    PATTERN001 : 1,
    PATTERN010 : 2,
    PATTERN011 : 3,
    PATTERN100 : 4,
    PATTERN101 : 5,
    PATTERN110 : 6,
    PATTERN111 : 7
  };

  //---------------------------------------------------------------------
  // QRUtil
  //---------------------------------------------------------------------

  var QRUtil = function() {

    var PATTERN_POSITION_TABLE = [
      [],
      [6, 18],
      [6, 22],
      [6, 26],
      [6, 30],
      [6, 34],
      [6, 22, 38],
      [6, 24, 42],
      [6, 26, 46],
      [6, 28, 50],
      [6, 30, 54],
      [6, 32, 58],
      [6, 34, 62],
      [6, 26, 46, 66],
      [6, 26, 48, 70],
      [6, 26, 50, 74],
      [6, 30, 54, 78],
      [6, 30, 56, 82],
      [6, 30, 58, 86],
      [6, 34, 62, 90],
      [6, 28, 50, 72, 94],
      [6, 26, 50, 74, 98],
      [6, 30, 54, 78, 102],
      [6, 28, 54, 80, 106],
      [6, 32, 58, 84, 110],
      [6, 30, 58, 86, 114],
      [6, 34, 62, 90, 118],
      [6, 26, 50, 74, 98, 122],
      [6, 30, 54, 78, 102, 126],
      [6, 26, 52, 78, 104, 130],
      [6, 30, 56, 82, 108, 134],
      [6, 34, 60, 86, 112, 138],
      [6, 30, 58, 86, 114, 142],
      [6, 34, 62, 90, 118, 146],
      [6, 30, 54, 78, 102, 126, 150],
      [6, 24, 50, 76, 102, 128, 154],
      [6, 28, 54, 80, 106, 132, 158],
      [6, 32, 58, 84, 110, 136, 162],
      [6, 26, 54, 82, 110, 138, 166],
      [6, 30, 58, 86, 114, 142, 170]
    ];
    var G15 = (1 << 10) | (1 << 8) | (1 << 5) | (1 << 4) | (1 << 2) | (1 << 1) | (1 << 0);
    var G18 = (1 << 12) | (1 << 11) | (1 << 10) | (1 << 9) | (1 << 8) | (1 << 5) | (1 << 2) | (1 << 0);
    var G15_MASK = (1 << 14) | (1 << 12) | (1 << 10) | (1 << 4) | (1 << 1);

    var _this = {};

    var getBCHDigit = function(data) {
      var digit = 0;
      while (data != 0) {
        digit += 1;
        data >>>= 1;
      }
      return digit;
    };

    _this.getBCHTypeInfo = function(data) {
      var d = data << 10;
      while (getBCHDigit(d) - getBCHDigit(G15) >= 0) {
        d ^= (G15 << (getBCHDigit(d) - getBCHDigit(G15) ) );
      }
      return ( (data << 10) | d) ^ G15_MASK;
    };

    _this.getBCHTypeNumber = function(data) {
      var d = data << 12;
      while (getBCHDigit(d) - getBCHDigit(G18) >= 0) {
        d ^= (G18 << (getBCHDigit(d) - getBCHDigit(G18) ) );
      }
      return (data << 12) | d;
    };

    _this.getPatternPosition = function(typeNumber) {
      return PATTERN_POSITION_TABLE[typeNumber - 1];
    };

    _this.getMaskFunction = function(maskPattern) {

      switch (maskPattern) {

      case QRMaskPattern.PATTERN000 :
        return function(i, j) { return (i + j) % 2 == 0; };
      case QRMaskPattern.PATTERN001 :
        return function(i, j) { return i % 2 == 0; };
      case QRMaskPattern.PATTERN010 :
        return function(i, j) { return j % 3 == 0; };
      case QRMaskPattern.PATTERN011 :
        return function(i, j) { return (i + j) % 3 == 0; };
      case QRMaskPattern.PATTERN100 :
        return function(i, j) { return (Math.floor(i / 2) + Math.floor(j / 3) ) % 2 == 0; };
      case QRMaskPattern.PATTERN101 :
        return function(i, j) { return (i * j) % 2 + (i * j) % 3 == 0; };
      case QRMaskPattern.PATTERN110 :
        return function(i, j) { return ( (i * j) % 2 + (i * j) % 3) % 2 == 0; };
      case QRMaskPattern.PATTERN111 :
        return function(i, j) { return ( (i * j) % 3 + (i + j) % 2) % 2 == 0; };

      default :
        throw 'bad maskPattern:' + maskPattern;
      }
    };

    _this.getErrorCorrectPolynomial = function(errorCorrectLength) {
      var a = qrPolynomial([1], 0);
      for (var i = 0; i < errorCorrectLength; i += 1) {
        a = a.multiply(qrPolynomial([1, QRMath.gexp(i)], 0) );
      }
      return a;
    };

    _this.getLengthInBits = function(mode, type) {

      if (1 <= type && type < 10) {

        // 1 - 9

        switch(mode) {
        case QRMode.MODE_NUMBER    : return 10;
        case QRMode.MODE_ALPHA_NUM : return 9;
        case QRMode.MODE_8BIT_BYTE : return 8;
        case QRMode.MODE_KANJI     : return 8;
        default :
          throw 'mode:' + mode;
        }

      } else if (type < 27) {

        // 10 - 26

        switch(mode) {
        case QRMode.MODE_NUMBER    : return 12;
        case QRMode.MODE_ALPHA_NUM : return 11;
        case QRMode.MODE_8BIT_BYTE : return 16;
        case QRMode.MODE_KANJI     : return 10;
        default :
          throw 'mode:' + mode;
        }

      } else if (type < 41) {

        // 27 - 40

        switch(mode) {
        case QRMode.MODE_NUMBER    : return 14;
        case QRMode.MODE_ALPHA_NUM : return 13;
        case QRMode.MODE_8BIT_BYTE : return 16;
        case QRMode.MODE_KANJI     : return 12;
        default :
          throw 'mode:' + mode;
        }

      } else {
        throw 'type:' + type;
      }
    };

    _this.getLostPoint = function(qrcode) {

      var moduleCount = qrcode.getModuleCount();

      var lostPoint = 0;

      // LEVEL1

      for (var row = 0; row < moduleCount; row += 1) {
        for (var col = 0; col < moduleCount; col += 1) {

          var sameCount = 0;
          var dark = qrcode.isDark(row, col);

          for (var r = -1; r <= 1; r += 1) {

            if (row + r < 0 || moduleCount <= row + r) {
              continue;
            }

            for (var c = -1; c <= 1; c += 1) {

              if (col + c < 0 || moduleCount <= col + c) {
                continue;
              }

              if (r == 0 && c == 0) {
                continue;
              }

              if (dark == qrcode.isDark(row + r, col + c) ) {
                sameCount += 1;
              }
            }
          }

          if (sameCount > 5) {
            lostPoint += (3 + sameCount - 5);
          }
        }
      };

      // LEVEL2

      for (var row = 0; row < moduleCount - 1; row += 1) {
        for (var col = 0; col < moduleCount - 1; col += 1) {
          var count = 0;
          if (qrcode.isDark(row, col) ) count += 1;
          if (qrcode.isDark(row + 1, col) ) count += 1;
          if (qrcode.isDark(row, col + 1) ) count += 1;
          if (qrcode.isDark(row + 1, col + 1) ) count += 1;
          if (count == 0 || count == 4) {
            lostPoint += 3;
          }
        }
      }

      // LEVEL3

      for (var row = 0; row < moduleCount; row += 1) {
        for (var col = 0; col < moduleCount - 6; col += 1) {
          if (qrcode.isDark(row, col)
              && !qrcode.isDark(row, col + 1)
              &&  qrcode.isDark(row, col + 2)
              &&  qrcode.isDark(row, col + 3)
              &&  qrcode.isDark(row, col + 4)
              && !qrcode.isDark(row, col + 5)
              &&  qrcode.isDark(row, col + 6) ) {
            lostPoint += 40;
          }
        }
      }

      for (var col = 0; col < moduleCount; col += 1) {
        for (var row = 0; row < moduleCount - 6; row += 1) {
          if (qrcode.isDark(row, col)
              && !qrcode.isDark(row + 1, col)
              &&  qrcode.isDark(row + 2, col)
              &&  qrcode.isDark(row + 3, col)
              &&  qrcode.isDark(row + 4, col)
              && !qrcode.isDark(row + 5, col)
              &&  qrcode.isDark(row + 6, col) ) {
            lostPoint += 40;
          }
        }
      }

      // LEVEL4

      var darkCount = 0;

      for (var col = 0; col < moduleCount; col += 1) {
        for (var row = 0; row < moduleCount; row += 1) {
          if (qrcode.isDark(row, col) ) {
            darkCount += 1;
          }
        }
      }

      var ratio = Math.abs(100 * darkCount / moduleCount / moduleCount - 50) / 5;
      lostPoint += ratio * 10;

      return lostPoint;
    };

    return _this;
  }();

  //---------------------------------------------------------------------
  // QRMath
  //---------------------------------------------------------------------

  var QRMath = function() {

    var EXP_TABLE = new Array(256);
    var LOG_TABLE = new Array(256);

    // initialize tables
    for (var i = 0; i < 8; i += 1) {
      EXP_TABLE[i] = 1 << i;
    }
    for (var i = 8; i < 256; i += 1) {
      EXP_TABLE[i] = EXP_TABLE[i - 4]
        ^ EXP_TABLE[i - 5]
        ^ EXP_TABLE[i - 6]
        ^ EXP_TABLE[i - 8];
    }
    for (var i = 0; i < 255; i += 1) {
      LOG_TABLE[EXP_TABLE[i] ] = i;
    }

    var _this = {};

    _this.glog = function(n) {

      if (n < 1) {
        throw 'glog(' + n + ')';
      }

      return LOG_TABLE[n];
    };

    _this.gexp = function(n) {

      while (n < 0) {
        n += 255;
      }

      while (n >= 256) {
        n -= 255;
      }

      return EXP_TABLE[n];
    };

    return _this;
  }();

  //---------------------------------------------------------------------
  // qrPolynomial
  //---------------------------------------------------------------------

  function qrPolynomial(num, shift) {

    if (typeof num.length == 'undefined') {
      throw num.length + '/' + shift;
    }

    var _num = function() {
      var offset = 0;
      while (offset < num.length && num[offset] == 0) {
        offset += 1;
      }
      var _num = new Array(num.length - offset + shift);
      for (var i = 0; i < num.length - offset; i += 1) {
        _num[i] = num[i + offset];
      }
      return _num;
    }();

    var _this = {};

    _this.getAt = function(index) {
      return _num[index];
    };

    _this.getLength = function() {
      return _num.length;
    };

    _this.multiply = function(e) {

      var num = new Array(_this.getLength() + e.getLength() - 1);

      for (var i = 0; i < _this.getLength(); i += 1) {
        for (var j = 0; j < e.getLength(); j += 1) {
          num[i + j] ^= QRMath.gexp(QRMath.glog(_this.getAt(i) ) + QRMath.glog(e.getAt(j) ) );
        }
      }

      return qrPolynomial(num, 0);
    };

    _this.mod = function(e) {

      if (_this.getLength() - e.getLength() < 0) {
        return _this;
      }

      var ratio = QRMath.glog(_this.getAt(0) ) - QRMath.glog(e.getAt(0) );

      var num = new Array(_this.getLength() );
      for (var i = 0; i < _this.getLength(); i += 1) {
        num[i] = _this.getAt(i);
      }

      for (var i = 0; i < e.getLength(); i += 1) {
        num[i] ^= QRMath.gexp(QRMath.glog(e.getAt(i) ) + ratio);
      }

      // recursive call
      return qrPolynomial(num, 0).mod(e);
    };

    return _this;
  };

  //---------------------------------------------------------------------
  // QRRSBlock
  //---------------------------------------------------------------------

  var QRRSBlock = function() {

    var RS_BLOCK_TABLE = [

      // L
      // M
      // Q
      // H

      // 1
      [1, 26, 19],
      [1, 26, 16],
      [1, 26, 13],
      [1, 26, 9],

      // 2
      [1, 44, 34],
      [1, 44, 28],
      [1, 44, 22],
      [1, 44, 16],

      // 3
      [1, 70, 55],
      [1, 70, 44],
      [2, 35, 17],
      [2, 35, 13],

      // 4
      [1, 100, 80],
      [2, 50, 32],
      [2, 50, 24],
      [4, 25, 9],

      // 5
      [1, 134, 108],
      [2, 67, 43],
      [2, 33, 15, 2, 34, 16],
      [2, 33, 11, 2, 34, 12],

      // 6
      [2, 86, 68],
      [4, 43, 27],
      [4, 43, 19],
      [4, 43, 15],

      // 7
      [2, 98, 78],
      [4, 49, 31],
      [2, 32, 14, 4, 33, 15],
      [4, 39, 13, 1, 40, 14],

      // 8
      [2, 121, 97],
      [2, 60, 38, 2, 61, 39],
      [4, 40, 18, 2, 41, 19],
      [4, 40, 14, 2, 41, 15],

      // 9
      [2, 146, 116],
      [3, 58, 36, 2, 59, 37],
      [4, 36, 16, 4, 37, 17],
      [4, 36, 12, 4, 37, 13],

      // 10
      [2, 86, 68, 2, 87, 69],
      [4, 69, 43, 1, 70, 44],
      [6, 43, 19, 2, 44, 20],
      [6, 43, 15, 2, 44, 16],

      // 11
      [4, 101, 81],
      [1, 80, 50, 4, 81, 51],
      [4, 50, 22, 4, 51, 23],
      [3, 36, 12, 8, 37, 13],

      // 12
      [2, 116, 92, 2, 117, 93],
      [6, 58, 36, 2, 59, 37],
      [4, 46, 20, 6, 47, 21],
      [7, 42, 14, 4, 43, 15],

      // 13
      [4, 133, 107],
      [8, 59, 37, 1, 60, 38],
      [8, 44, 20, 4, 45, 21],
      [12, 33, 11, 4, 34, 12],

      // 14
      [3, 145, 115, 1, 146, 116],
      [4, 64, 40, 5, 65, 41],
      [11, 36, 16, 5, 37, 17],
      [11, 36, 12, 5, 37, 13],

      // 15
      [5, 109, 87, 1, 110, 88],
      [5, 65, 41, 5, 66, 42],
      [5, 54, 24, 7, 55, 25],
      [11, 36, 12, 7, 37, 13],

      // 16
      [5, 122, 98, 1, 123, 99],
      [7, 73, 45, 3, 74, 46],
      [15, 43, 19, 2, 44, 20],
      [3, 45, 15, 13, 46, 16],

      // 17
      [1, 135, 107, 5, 136, 108],
      [10, 74, 46, 1, 75, 47],
      [1, 50, 22, 15, 51, 23],
      [2, 42, 14, 17, 43, 15],

      // 18
      [5, 150, 120, 1, 151, 121],
      [9, 69, 43, 4, 70, 44],
      [17, 50, 22, 1, 51, 23],
      [2, 42, 14, 19, 43, 15],

      // 19
      [3, 141, 113, 4, 142, 114],
      [3, 70, 44, 11, 71, 45],
      [17, 47, 21, 4, 48, 22],
      [9, 39, 13, 16, 40, 14],

      // 20
      [3, 135, 107, 5, 136, 108],
      [3, 67, 41, 13, 68, 42],
      [15, 54, 24, 5, 55, 25],
      [15, 43, 15, 10, 44, 16],

      // 21
      [4, 144, 116, 4, 145, 117],
      [17, 68, 42],
      [17, 50, 22, 6, 51, 23],
      [19, 46, 16, 6, 47, 17],

      // 22
      [2, 139, 111, 7, 140, 112],
      [17, 74, 46],
      [7, 54, 24, 16, 55, 25],
      [34, 37, 13],

      // 23
      [4, 151, 121, 5, 152, 122],
      [4, 75, 47, 14, 76, 48],
      [11, 54, 24, 14, 55, 25],
      [16, 45, 15, 14, 46, 16],

      // 24
      [6, 147, 117, 4, 148, 118],
      [6, 73, 45, 14, 74, 46],
      [11, 54, 24, 16, 55, 25],
      [30, 46, 16, 2, 47, 17],

      // 25
      [8, 132, 106, 4, 133, 107],
      [8, 75, 47, 13, 76, 48],
      [7, 54, 24, 22, 55, 25],
      [22, 45, 15, 13, 46, 16],

      // 26
      [10, 142, 114, 2, 143, 115],
      [19, 74, 46, 4, 75, 47],
      [28, 50, 22, 6, 51, 23],
      [33, 46, 16, 4, 47, 17],

      // 27
      [8, 152, 122, 4, 153, 123],
      [22, 73, 45, 3, 74, 46],
      [8, 53, 23, 26, 54, 24],
      [12, 45, 15, 28, 46, 16],

      // 28
      [3, 147, 117, 10, 148, 118],
      [3, 73, 45, 23, 74, 46],
      [4, 54, 24, 31, 55, 25],
      [11, 45, 15, 31, 46, 16],

      // 29
      [7, 146, 116, 7, 147, 117],
      [21, 73, 45, 7, 74, 46],
      [1, 53, 23, 37, 54, 24],
      [19, 45, 15, 26, 46, 16],

      // 30
      [5, 145, 115, 10, 146, 116],
      [19, 75, 47, 10, 76, 48],
      [15, 54, 24, 25, 55, 25],
      [23, 45, 15, 25, 46, 16],

      // 31
      [13, 145, 115, 3, 146, 116],
      [2, 74, 46, 29, 75, 47],
      [42, 54, 24, 1, 55, 25],
      [23, 45, 15, 28, 46, 16],

      // 32
      [17, 145, 115],
      [10, 74, 46, 23, 75, 47],
      [10, 54, 24, 35, 55, 25],
      [19, 45, 15, 35, 46, 16],

      // 33
      [17, 145, 115, 1, 146, 116],
      [14, 74, 46, 21, 75, 47],
      [29, 54, 24, 19, 55, 25],
      [11, 45, 15, 46, 46, 16],

      // 34
      [13, 145, 115, 6, 146, 116],
      [14, 74, 46, 23, 75, 47],
      [44, 54, 24, 7, 55, 25],
      [59, 46, 16, 1, 47, 17],

      // 35
      [12, 151, 121, 7, 152, 122],
      [12, 75, 47, 26, 76, 48],
      [39, 54, 24, 14, 55, 25],
      [22, 45, 15, 41, 46, 16],

      // 36
      [6, 151, 121, 14, 152, 122],
      [6, 75, 47, 34, 76, 48],
      [46, 54, 24, 10, 55, 25],
      [2, 45, 15, 64, 46, 16],

      // 37
      [17, 152, 122, 4, 153, 123],
      [29, 74, 46, 14, 75, 47],
      [49, 54, 24, 10, 55, 25],
      [24, 45, 15, 46, 46, 16],

      // 38
      [4, 152, 122, 18, 153, 123],
      [13, 74, 46, 32, 75, 47],
      [48, 54, 24, 14, 55, 25],
      [42, 45, 15, 32, 46, 16],

      // 39
      [20, 147, 117, 4, 148, 118],
      [40, 75, 47, 7, 76, 48],
      [43, 54, 24, 22, 55, 25],
      [10, 45, 15, 67, 46, 16],

      // 40
      [19, 148, 118, 6, 149, 119],
      [18, 75, 47, 31, 76, 48],
      [34, 54, 24, 34, 55, 25],
      [20, 45, 15, 61, 46, 16]
    ];

    var qrRSBlock = function(totalCount, dataCount) {
      var _this = {};
      _this.totalCount = totalCount;
      _this.dataCount = dataCount;
      return _this;
    };

    var _this = {};

    var getRsBlockTable = function(typeNumber, errorCorrectionLevel) {

      switch(errorCorrectionLevel) {
      case QRErrorCorrectionLevel.L :
        return RS_BLOCK_TABLE[(typeNumber - 1) * 4 + 0];
      case QRErrorCorrectionLevel.M :
        return RS_BLOCK_TABLE[(typeNumber - 1) * 4 + 1];
      case QRErrorCorrectionLevel.Q :
        return RS_BLOCK_TABLE[(typeNumber - 1) * 4 + 2];
      case QRErrorCorrectionLevel.H :
        return RS_BLOCK_TABLE[(typeNumber - 1) * 4 + 3];
      default :
        return undefined;
      }
    };

    _this.getRSBlocks = function(typeNumber, errorCorrectionLevel) {

      var rsBlock = getRsBlockTable(typeNumber, errorCorrectionLevel);

      if (typeof rsBlock == 'undefined') {
        throw 'bad rs block @ typeNumber:' + typeNumber +
            '/errorCorrectionLevel:' + errorCorrectionLevel;
      }

      var length = rsBlock.length / 3;

      var list = [];

      for (var i = 0; i < length; i += 1) {

        var count = rsBlock[i * 3 + 0];
        var totalCount = rsBlock[i * 3 + 1];
        var dataCount = rsBlock[i * 3 + 2];

        for (var j = 0; j < count; j += 1) {
          list.push(qrRSBlock(totalCount, dataCount) );
        }
      }

      return list;
    };

    return _this;
  }();

  //---------------------------------------------------------------------
  // qrBitBuffer
  //---------------------------------------------------------------------

  var qrBitBuffer = function() {

    var _buffer = [];
    var _length = 0;

    var _this = {};

    _this.getBuffer = function() {
      return _buffer;
    };

    _this.getAt = function(index) {
      var bufIndex = Math.floor(index / 8);
      return ( (_buffer[bufIndex] >>> (7 - index % 8) ) & 1) == 1;
    };

    _this.put = function(num, length) {
      for (var i = 0; i < length; i += 1) {
        _this.putBit( ( (num >>> (length - i - 1) ) & 1) == 1);
      }
    };

    _this.getLengthInBits = function() {
      return _length;
    };

    _this.putBit = function(bit) {

      var bufIndex = Math.floor(_length / 8);
      if (_buffer.length <= bufIndex) {
        _buffer.push(0);
      }

      if (bit) {
        _buffer[bufIndex] |= (0x80 >>> (_length % 8) );
      }

      _length += 1;
    };

    return _this;
  };

  //---------------------------------------------------------------------
  // qrNumber
  //---------------------------------------------------------------------

  var qrNumber = function(data) {

    var _mode = QRMode.MODE_NUMBER;
    var _data = data;

    var _this = {};

    _this.getMode = function() {
      return _mode;
    };

    _this.getLength = function(buffer) {
      return _data.length;
    };

    _this.write = function(buffer) {

      var data = _data;

      var i = 0;

      while (i + 2 < data.length) {
        buffer.put(strToNum(data.substring(i, i + 3) ), 10);
        i += 3;
      }

      if (i < data.length) {
        if (data.length - i == 1) {
          buffer.put(strToNum(data.substring(i, i + 1) ), 4);
        } else if (data.length - i == 2) {
          buffer.put(strToNum(data.substring(i, i + 2) ), 7);
        }
      }
    };

    var strToNum = function(s) {
      var num = 0;
      for (var i = 0; i < s.length; i += 1) {
        num = num * 10 + chatToNum(s.charAt(i) );
      }
      return num;
    };

    var chatToNum = function(c) {
      if ('0' <= c && c <= '9') {
        return c.charCodeAt(0) - '0'.charCodeAt(0);
      }
      throw 'illegal char :' + c;
    };

    return _this;
  };

  //---------------------------------------------------------------------
  // qrAlphaNum
  //---------------------------------------------------------------------

  var qrAlphaNum = function(data) {

    var _mode = QRMode.MODE_ALPHA_NUM;
    var _data = data;

    var _this = {};

    _this.getMode = function() {
      return _mode;
    };

    _this.getLength = function(buffer) {
      return _data.length;
    };

    _this.write = function(buffer) {

      var s = _data;

      var i = 0;

      while (i + 1 < s.length) {
        buffer.put(
          getCode(s.charAt(i) ) * 45 +
          getCode(s.charAt(i + 1) ), 11);
        i += 2;
      }

      if (i < s.length) {
        buffer.put(getCode(s.charAt(i) ), 6);
      }
    };

    var getCode = function(c) {

      if ('0' <= c && c <= '9') {
        return c.charCodeAt(0) - '0'.charCodeAt(0);
      } else if ('A' <= c && c <= 'Z') {
        return c.charCodeAt(0) - 'A'.charCodeAt(0) + 10;
      } else {
        switch (c) {
        case ' ' : return 36;
        case '$' : return 37;
        case '%' : return 38;
        case '*' : return 39;
        case '+' : return 40;
        case '-' : return 41;
        case '.' : return 42;
        case '/' : return 43;
        case ':' : return 44;
        default :
          throw 'illegal char :' + c;
        }
      }
    };

    return _this;
  };

  //---------------------------------------------------------------------
  // qr8BitByte
  //---------------------------------------------------------------------

  var qr8BitByte = function(data) {

    var _mode = QRMode.MODE_8BIT_BYTE;
    var _data = data;
    var _bytes = qrcode.stringToBytes(data);

    var _this = {};

    _this.getMode = function() {
      return _mode;
    };

    _this.getLength = function(buffer) {
      return _bytes.length;
    };

    _this.write = function(buffer) {
      for (var i = 0; i < _bytes.length; i += 1) {
        buffer.put(_bytes[i], 8);
      }
    };

    return _this;
  };

  //---------------------------------------------------------------------
  // qrKanji
  //---------------------------------------------------------------------

  var qrKanji = function(data) {

    var _mode = QRMode.MODE_KANJI;
    var _data = data;

    var stringToBytes = qrcode.stringToBytesFuncs['SJIS'];
    if (!stringToBytes) {
      throw 'sjis not supported.';
    }
    !function(c, code) {
      // self test for sjis support.
      var test = stringToBytes(c);
      if (test.length != 2 || ( (test[0] << 8) | test[1]) != code) {
        throw 'sjis not supported.';
      }
    }('\u53cb', 0x9746);

    var _bytes = stringToBytes(data);

    var _this = {};

    _this.getMode = function() {
      return _mode;
    };

    _this.getLength = function(buffer) {
      return ~~(_bytes.length / 2);
    };

    _this.write = function(buffer) {

      var data = _bytes;

      var i = 0;

      while (i + 1 < data.length) {

        var c = ( (0xff & data[i]) << 8) | (0xff & data[i + 1]);

        if (0x8140 <= c && c <= 0x9FFC) {
          c -= 0x8140;
        } else if (0xE040 <= c && c <= 0xEBBF) {
          c -= 0xC140;
        } else {
          throw 'illegal char at ' + (i + 1) + '/' + c;
        }

        c = ( (c >>> 8) & 0xff) * 0xC0 + (c & 0xff);

        buffer.put(c, 13);

        i += 2;
      }

      if (i < data.length) {
        throw 'illegal char at ' + (i + 1);
      }
    };

    return _this;
  };

  //=====================================================================
  // GIF Support etc.
  //

  //---------------------------------------------------------------------
  // byteArrayOutputStream
  //---------------------------------------------------------------------

  var byteArrayOutputStream = function() {

    var _bytes = [];

    var _this = {};

    _this.writeByte = function(b) {
      _bytes.push(b & 0xff);
    };

    _this.writeShort = function(i) {
      _this.writeByte(i);
      _this.writeByte(i >>> 8);
    };

    _this.writeBytes = function(b, off, len) {
      off = off || 0;
      len = len || b.length;
      for (var i = 0; i < len; i += 1) {
        _this.writeByte(b[i + off]);
      }
    };

    _this.writeString = function(s) {
      for (var i = 0; i < s.length; i += 1) {
        _this.writeByte(s.charCodeAt(i) );
      }
    };

    _this.toByteArray = function() {
      return _bytes;
    };

    _this.toString = function() {
      var s = '';
      s += '[';
      for (var i = 0; i < _bytes.length; i += 1) {
        if (i > 0) {
          s += ',';
        }
        s += _bytes[i];
      }
      s += ']';
      return s;
    };

    return _this;
  };

  //---------------------------------------------------------------------
  // base64EncodeOutputStream
  //---------------------------------------------------------------------

  var base64EncodeOutputStream = function() {

    var _buffer = 0;
    var _buflen = 0;
    var _length = 0;
    var _base64 = '';

    var _this = {};

    var writeEncoded = function(b) {
      _base64 += String.fromCharCode(encode(b & 0x3f) );
    };

    var encode = function(n) {
      if (n < 0) {
        // error.
      } else if (n < 26) {
        return 0x41 + n;
      } else if (n < 52) {
        return 0x61 + (n - 26);
      } else if (n < 62) {
        return 0x30 + (n - 52);
      } else if (n == 62) {
        return 0x2b;
      } else if (n == 63) {
        return 0x2f;
      }
      throw 'n:' + n;
    };

    _this.writeByte = function(n) {

      _buffer = (_buffer << 8) | (n & 0xff);
      _buflen += 8;
      _length += 1;

      while (_buflen >= 6) {
        writeEncoded(_buffer >>> (_buflen - 6) );
        _buflen -= 6;
      }
    };

    _this.flush = function() {

      if (_buflen > 0) {
        writeEncoded(_buffer << (6 - _buflen) );
        _buffer = 0;
        _buflen = 0;
      }

      if (_length % 3 != 0) {
        // padding
        var padlen = 3 - _length % 3;
        for (var i = 0; i < padlen; i += 1) {
          _base64 += '=';
        }
      }
    };

    _this.toString = function() {
      return _base64;
    };

    return _this;
  };

  //---------------------------------------------------------------------
  // base64DecodeInputStream
  //---------------------------------------------------------------------

  var base64DecodeInputStream = function(str) {

    var _str = str;
    var _pos = 0;
    var _buffer = 0;
    var _buflen = 0;

    var _this = {};

    _this.read = function() {

      while (_buflen < 8) {

        if (_pos >= _str.length) {
          if (_buflen == 0) {
            return -1;
          }
          throw 'unexpected end of file./' + _buflen;
        }

        var c = _str.charAt(_pos);
        _pos += 1;

        if (c == '=') {
          _buflen = 0;
          return -1;
        } else if (c.match(/^\s$/) ) {
          // ignore if whitespace.
          continue;
        }

        _buffer = (_buffer << 6) | decode(c.charCodeAt(0) );
        _buflen += 6;
      }

      var n = (_buffer >>> (_buflen - 8) ) & 0xff;
      _buflen -= 8;
      return n;
    };

    var decode = function(c) {
      if (0x41 <= c && c <= 0x5a) {
        return c - 0x41;
      } else if (0x61 <= c && c <= 0x7a) {
        return c - 0x61 + 26;
      } else if (0x30 <= c && c <= 0x39) {
        return c - 0x30 + 52;
      } else if (c == 0x2b) {
        return 62;
      } else if (c == 0x2f) {
        return 63;
      } else {
        throw 'c:' + c;
      }
    };

    return _this;
  };

  //---------------------------------------------------------------------
  // gifImage (B/W)
  //---------------------------------------------------------------------

  var gifImage = function(width, height) {

    var _width = width;
    var _height = height;
    var _data = new Array(width * height);

    var _this = {};

    _this.setPixel = function(x, y, pixel) {
      _data[y * _width + x] = pixel;
    };

    _this.write = function(out) {

      //---------------------------------
      // GIF Signature

      out.writeString('GIF87a');

      //---------------------------------
      // Screen Descriptor

      out.writeShort(_width);
      out.writeShort(_height);

      out.writeByte(0x80); // 2bit
      out.writeByte(0);
      out.writeByte(0);

      //---------------------------------
      // Global Color Map

      // black
      out.writeByte(0x00);
      out.writeByte(0x00);
      out.writeByte(0x00);

      // white
      out.writeByte(0xff);
      out.writeByte(0xff);
      out.writeByte(0xff);

      //---------------------------------
      // Image Descriptor

      out.writeString(',');
      out.writeShort(0);
      out.writeShort(0);
      out.writeShort(_width);
      out.writeShort(_height);
      out.writeByte(0);

      //---------------------------------
      // Local Color Map

      //---------------------------------
      // Raster Data

      var lzwMinCodeSize = 2;
      var raster = getLZWRaster(lzwMinCodeSize);

      out.writeByte(lzwMinCodeSize);

      var offset = 0;

      while (raster.length - offset > 255) {
        out.writeByte(255);
        out.writeBytes(raster, offset, 255);
        offset += 255;
      }

      out.writeByte(raster.length - offset);
      out.writeBytes(raster, offset, raster.length - offset);
      out.writeByte(0x00);

      //---------------------------------
      // GIF Terminator
      out.writeString(';');
    };

    var bitOutputStream = function(out) {

      var _out = out;
      var _bitLength = 0;
      var _bitBuffer = 0;

      var _this = {};

      _this.write = function(data, length) {

        if ( (data >>> length) != 0) {
          throw 'length over';
        }

        while (_bitLength + length >= 8) {
          _out.writeByte(0xff & ( (data << _bitLength) | _bitBuffer) );
          length -= (8 - _bitLength);
          data >>>= (8 - _bitLength);
          _bitBuffer = 0;
          _bitLength = 0;
        }

        _bitBuffer = (data << _bitLength) | _bitBuffer;
        _bitLength = _bitLength + length;
      };

      _this.flush = function() {
        if (_bitLength > 0) {
          _out.writeByte(_bitBuffer);
        }
      };

      return _this;
    };

    var getLZWRaster = function(lzwMinCodeSize) {

      var clearCode = 1 << lzwMinCodeSize;
      var endCode = (1 << lzwMinCodeSize) + 1;
      var bitLength = lzwMinCodeSize + 1;

      // Setup LZWTable
      var table = lzwTable();

      for (var i = 0; i < clearCode; i += 1) {
        table.add(String.fromCharCode(i) );
      }
      table.add(String.fromCharCode(clearCode) );
      table.add(String.fromCharCode(endCode) );

      var byteOut = byteArrayOutputStream();
      var bitOut = bitOutputStream(byteOut);

      // clear code
      bitOut.write(clearCode, bitLength);

      var dataIndex = 0;

      var s = String.fromCharCode(_data[dataIndex]);
      dataIndex += 1;

      while (dataIndex < _data.length) {

        var c = String.fromCharCode(_data[dataIndex]);
        dataIndex += 1;

        if (table.contains(s + c) ) {

          s = s + c;

        } else {

          bitOut.write(table.indexOf(s), bitLength);

          if (table.size() < 0xfff) {

            if (table.size() == (1 << bitLength) ) {
              bitLength += 1;
            }

            table.add(s + c);
          }

          s = c;
        }
      }

      bitOut.write(table.indexOf(s), bitLength);

      // end code
      bitOut.write(endCode, bitLength);

      bitOut.flush();

      return byteOut.toByteArray();
    };

    var lzwTable = function() {

      var _map = {};
      var _size = 0;

      var _this = {};

      _this.add = function(key) {
        if (_this.contains(key) ) {
          throw 'dup key:' + key;
        }
        _map[key] = _size;
        _size += 1;
      };

      _this.size = function() {
        return _size;
      };

      _this.indexOf = function(key) {
        return _map[key];
      };

      _this.contains = function(key) {
        return typeof _map[key] != 'undefined';
      };

      return _this;
    };

    return _this;
  };

  var createDataURL = function(width, height, getPixel) {
    var gif = gifImage(width, height);
    for (var y = 0; y < height; y += 1) {
      for (var x = 0; x < width; x += 1) {
        gif.setPixel(x, y, getPixel(x, y) );
      }
    }

    var b = byteArrayOutputStream();
    gif.write(b);

    var base64 = base64EncodeOutputStream();
    var bytes = b.toByteArray();
    for (var i = 0; i < bytes.length; i += 1) {
      base64.writeByte(bytes[i]);
    }
    base64.flush();

    return 'data:image/gif;base64,' + base64;
  };

  //---------------------------------------------------------------------
  // returns qrcode function.

  return qrcode;
}();

// multibyte support
!function() {

  qrcode.stringToBytesFuncs['UTF-8'] = function(s) {
    // http://stackoverflow.com/questions/18729405/how-to-convert-utf8-string-to-byte-array
    function toUTF8Array(str) {
      var utf8 = [];
      for (var i=0; i < str.length; i++) {
        var charcode = str.charCodeAt(i);
        if (charcode < 0x80) utf8.push(charcode);
        else if (charcode < 0x800) {
          utf8.push(0xc0 | (charcode >> 6),
              0x80 | (charcode & 0x3f));
        }
        else if (charcode < 0xd800 || charcode >= 0xe000) {
          utf8.push(0xe0 | (charcode >> 12),
              0x80 | ((charcode>>6) & 0x3f),
              0x80 | (charcode & 0x3f));
        }
        // surrogate pair
        else {
          i++;
          // UTF-16 encodes 0x10000-0x10FFFF by
          // subtracting 0x10000 and splitting the
          // 20 bits of 0x0-0xFFFFF into two halves
          charcode = 0x10000 + (((charcode & 0x3ff)<<10)
            | (str.charCodeAt(i) & 0x3ff));
          utf8.push(0xf0 | (charcode >>18),
              0x80 | ((charcode>>12) & 0x3f),
              0x80 | ((charcode>>6) & 0x3f),
              0x80 | (charcode & 0x3f));
        }
      }
      return utf8;
    }
    return toUTF8Array(s);
  };

}();

(function (factory) {
  if (typeof define === 'function' && define.amd) {
      define([], factory);
  } else if (typeof exports === 'object') {
      module.exports = factory();
  }
}(function () {
    return qrcode;
}));

qrcode.stringToBytes = qrcode.stringToBytesFuncs['UTF-8'];
return qrcode;
})();

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pad = (n) => String(n).padStart(2, "0");
const TYPES = { sur_place: "Reste sur place", passage: "Passage" };
const JOURS = ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."];
// passages réguliers : lundi = 0 (comme le serveur)
const JL = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."];
const JLONG = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"];
const hfr = (hm) => { const [h, m] = String(hm || "").split(":").map(Number); return isNaN(h) ? "?" : `${h} h${m ? " " + pad(m) : ""}`; };
function repText(r) {
  if (!r) return "";
  const d = (r.jours || []).map((j) => JLONG[j]);
  let jours = d.length === 7 ? "tous les jours" : d.length > 1 ? `${d.slice(0, -1).join(", ")} et ${d.at(-1)}` : d[0] || "?";
  const sur = r.toutes === 2 ? "deux" : r.toutes;
  if (d.length < 7) jours = r.toutes > 1 ? `${jours} (une semaine sur ${sur})` : `chaque ${jours}`;
  else if (r.toutes > 1) jours += `, une semaine sur ${sur}`;
  return `${jours}, ${hfr(r.de)} – ${hfr(r.a)}`;
}
const dateInput = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
// fin de série (minuit après le dernier jour) → dernier jour
const lastDay = (iso) => new Date(new Date(iso).getTime() - 1000);
const dfr = (d) => `${d.getDate()}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;

function qrSvg(text) {
  if (!text) return "";
  try {
    const q = QR(0, "M");
    q.addData(text, "Byte");
    q.make();
    return q.createSvgTag({ cellSize: 4, margin: 2, scalable: true });
  } catch (e) {
    return "";
  }
}

// « 2026-11-22T14:30 » (heure locale du navigateur) pour <input type=datetime-local>
function toLocalInput(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function fromLocalInput(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(s || "");
  return m ? new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]) : null;
}
// envoyé au serveur : heure locale sans fuseau (le serveur applique le fuseau de Home Assistant)
const toServer = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:00`;

function quand(iso, now = new Date()) {
  const d = new Date(iso);
  if (isNaN(d)) return "?";
  const h = `${d.getHours()} h${d.getMinutes() ? " " + pad(d.getMinutes()) : ""}`;
  const days = Math.round((new Date(d.getFullYear(), d.getMonth(), d.getDate()) - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 864e5);
  if (days === 0) return `aujourd'hui ${h}`;
  if (days === 1) return `demain ${h}`;
  if (days === -1) return `hier ${h}`;
  return `${JOURS[d.getDay()]} ${d.getDate()}/${pad(d.getMonth() + 1)} ${h}`;
}

function atHour(base, days, hour) {
  const d = new Date(base);
  d.setDate(d.getDate() + days);
  d.setHours(hour, 0, 0, 0);
  return d;
}

// choix rapides de départ selon le type (à partir de l'arrivée)
function quickEnds(type, start) {
  const plus = (h) => new Date(start.getTime() + h * 3600e3);
  const sameDay = (h) => { const d = atHour(start, 0, h); return d > start ? d : null; };
  if (type === "passage") {
    return [["1 h", plus(1)], ["2 h", plus(2)], ["4 h", plus(4)], ["Fin de journée", sameDay(19)], ["Demain 19 h", atHour(start, 1, 19)]]
      .filter(([, d]) => d);
  }
  return [["Ce soir", sameDay(23)], ["Demain matin", atHour(start, 1, 10)], ["2 jours", atHour(start, 2, 10)],
    ["1 semaine", atHour(start, 7, 10)]].filter(([, d]) => d);
}

const CSS = `
  :host { display:block; }
  ha-card { padding:16px; }
  .tete { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
  .tete h2 { flex:1; margin:0; font-size:1.25em; font-weight:500; }
  button { font:inherit; cursor:pointer; border-radius:10px; border:1px solid var(--divider-color,#ccc);
    background:var(--card-background-color,#fff); color:var(--primary-text-color); padding:8px 12px; min-height:40px; }
  button.p { background:var(--primary-color); color:var(--text-primary-color,#fff); border-color:transparent; }
  button.d { color:var(--error-color,#c62828); }
  button.d.sure { background:var(--error-color,#c62828); color:#fff; }
  button:disabled { opacity:.5; cursor:default; }
  h3 { margin:16px 0 6px; font-size:.85em; text-transform:uppercase; letter-spacing:.05em; color:var(--secondary-text-color); }
  .vide { color:var(--secondary-text-color); margin:8px 0; }
  .v { border:1px solid var(--divider-color,#ddd); border-radius:14px; padding:12px; margin:8px 0; }
  .v.en_cours { border-color:var(--success-color,#2e7d32); }
  .l1 { display:flex; align-items:center; gap:10px; }
  .av { width:40px; height:40px; border-radius:50%; display:flex; align-items:center; justify-content:center; flex:none;
    background:var(--primary-color); color:var(--text-primary-color,#fff); font-weight:600; font-size:1.1em; }
  .v.passage .av { background:var(--info-color,#0288d1); }
  .v.terminee .av { background:var(--disabled-color,#9e9e9e); }
  .nom { font-weight:600; font-size:1.05em; }
  .sub { color:var(--secondary-text-color); font-size:.9em; }
  .tags { display:flex; flex-wrap:wrap; gap:6px; margin:8px 0 0; }
  .tag { font-size:.85em; padding:3px 8px; border-radius:999px; background:var(--secondary-background-color,#eee); }
  .tag.ok { background:rgba(46,125,50,.15); color:var(--success-color,#2e7d32); }
  .tag.code { font-family:monospace; letter-spacing:.15em; cursor:pointer; }
  .acts { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
  .acts button { min-height:36px; padding:6px 10px; font-size:.9em; }
  details summary { cursor:pointer; color:var(--secondary-text-color); margin-top:12px; }
  .err { color:var(--error-color,#c62828); margin:6px 0; }
  .accueil { text-align:center; }
  .accueil .bienv { font-size:1.5em; font-weight:500; margin:6px 0 12px; }
  .wifi { display:flex; gap:16px; align-items:center; justify-content:center; flex-wrap:wrap; margin:8px 0; }
  .qr { width:180px; height:180px; background:#fff; padding:6px; border-radius:12px; }
  .qr svg { width:100%; height:100%; display:block; }
  .wtxt { text-align:left; }
  .wtxt b { font-size:1.15em; }
  .mdp { font-family:monospace; font-size:1.15em; user-select:all; }
  .consignes { white-space:pre-wrap; text-align:left; background:var(--secondary-background-color,#f5f5f5); border-radius:12px; padding:12px; margin-top:12px; }
  /* formulaire */
  .fond { position:fixed; inset:0; background:rgba(0,0,0,.45); z-index:9; display:flex; align-items:flex-end; justify-content:center; }
  @media (min-width:600px) { .fond { align-items:center; } }
  .boite { background:var(--card-background-color,#fff); color:var(--primary-text-color); width:min(560px,100%); max-height:92vh; overflow:auto;
    border-radius:18px 18px 0 0; padding:18px; box-sizing:border-box; }
  @media (min-width:600px) { .boite { border-radius:18px; } }
  .boite h2 { margin:0 0 10px; font-size:1.2em; }
  label.c { display:block; font-size:.85em; color:var(--secondary-text-color); margin:12px 0 4px; }
  input[type=text], input[type=tel], input[type=datetime-local], textarea { width:100%; box-sizing:border-box; font:inherit;
    padding:10px; border-radius:10px; border:1px solid var(--divider-color,#ccc); background:var(--card-background-color,#fff); color:inherit; }
  textarea { min-height:70px; }
  .seg { display:flex; gap:6px; flex-wrap:wrap; }
  .seg button { flex:1; min-width:fit-content; }
  .seg button.on { background:var(--primary-color); color:var(--text-primary-color,#fff); border-color:transparent; }
  .chips { display:flex; flex-wrap:wrap; gap:6px; }
  .chips button { min-height:34px; padding:4px 10px; font-size:.9em; }
  .chips button.on { background:var(--primary-color); color:var(--text-primary-color,#fff); border-color:transparent; }
  .res { font-size:.9em; color:var(--secondary-text-color); margin-top:6px; }
  .chk { display:flex; align-items:center; gap:8px; margin:6px 0; min-height:36px; }
  .chk input { width:20px; height:20px; }
  .warn { color:var(--warning-color,#ef6c00); font-size:.85em; }
  .pied { display:flex; justify-content:flex-end; gap:8px; margin-top:16px; position:sticky; bottom:-18px; background:inherit; padding:8px 0; }
  .grandcode { font-family:monospace; font-size:2em; letter-spacing:.3em; text-align:center; margin:8px 0; }
`;

class VisiteursCard extends HTMLElement {
  setConfig(config) {
    this.config = { mode: "auto", title: "Visiteurs", ...config };
    if (!["auto", "gestion", "accueil"].includes(this.config.mode)) throw new Error("mode : auto, gestion ou accueil");
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this.info = null; this.form = null; this.result = null; this.sure = null; this.reveal = new Set();
    this._render();
  }

  getCardSize() { return 4; }
  static getStubConfig() { return { title: "Visiteurs" }; }

  set hass(h) {
    const first = !this._hass;
    this._hass = h;
    if (first) { this._load(); return; }
    // rechargé quand une entité du module change (début, fin, arrivée…)
    const sig = Object.keys(h.states).filter((e) => /^(sensor|binary_sensor)\..*visit/.test(e))
      .map((e) => h.states[e].last_updated).join("|");
    if (sig !== this._sig) { const had = this._sig !== undefined; this._sig = sig; if (had && !this.reg && !this.form && !this.stay) this._load(); }
  }

  connectedCallback() {
    clearInterval(this._timer);
    this._timer = setInterval(() => { if (!this.form && !this.reg && !this.stay) this._load(); }, 60000);
  }
  disconnectedCallback() { clearInterval(this._timer); }

  get tablet() { return /tabdomo/i.test(this._hass?.user?.name || ""); }
  get mode() {
    if (this.config.mode !== "auto") return this.config.mode;
    return this.tablet || (this.info && !this.info.gestion) ? "accueil" : "gestion";
  }

  async _ws(msg) { return this._hass.callWS(msg); }

  async _load() {
    if (!this._hass) return;
    try {
      this.info = await this._ws({ type: "visiteurs/info" });
      this._err = null;
    } catch (e) {
      this._err = e?.code === "unknown_command" ? "Module « Visiteurs » non installé." : (e?.message || String(e));
    }
    this._render();
  }

  _toast(msg) {
    this.dispatchEvent(new CustomEvent("hass-notification", { detail: { message: msg }, bubbles: true, composed: true }));
  }

  // ───────── affichage ─────────
  _render() {
    if (!this.shadowRoot) return;
    let body;
    if (this._err) body = `<p class="err">${esc(this._err)}</p>`;
    else if (!this.info) body = `<p class="vide">Chargement…</p>`;
    else body = this.mode === "accueil" ? this._accueil() : this._gestion();
    this.shadowRoot.innerHTML = `<style>${CSS}</style><ha-card>${body}</ha-card>${this.form ? this._formHtml() : ""}${this.result ? this._resultHtml() : ""}${this.reg ? this._regHtml() : ""}${this.stay ? this._stayHtml() : ""}`;
    this._bind();
  }

  _accueil() {
    const i = this.info;
    const cur = i.visites.filter((v) => v.statut === "en_cours");
    const noms = cur.map((v) => v.nom);
    const w = i.wifi || {};
    const qr = w.qr ? qrSvg(w.qr) : "";
    const bienv = noms.length ? `Bienvenue ${esc(noms.length > 1 ? noms.slice(0, -1).join(", ") + " et " + noms.at(-1) : noms[0])} !` : esc(this.config.title_accueil || "Bienvenue !");
    return `<div class="accueil">
      <div class="bienv">${bienv}</div>
      ${w.ssid ? `<div class="wifi">${qr ? `<div class="qr" aria-label="QR code du Wi-Fi">${qr}</div>` : ""}
        <div class="wtxt"><div>📶 Wi-Fi</div><b>${esc(w.ssid)}</b>${w.mot_de_passe ? `<div class="sub">Mot de passe</div><div class="mdp">${esc(w.mot_de_passe)}</div>` : ""}
        <div class="sub" style="margin-top:6px">Scannez le QR code avec l'appareil photo.</div></div></div>`
        : (i.gestion ? `<p class="vide">Wi-Fi invité non réglé (options du module Visiteurs).</p>` : "")}
      ${i.consignes ? `<div class="consignes">${esc(i.consignes)}</div>` : ""}
    </div>`;
  }

  _gestion() {
    const i = this.info;
    const by = (s) => i.visites.filter((v) => v.statut === s);
    const cur = by("en_cours"), next = by("prevue"), done = by("terminee");
    return `<div class="tete"><h2>${esc(this.config.title)}</h2>
        ${i.admin ? `<button data-a="reglages" aria-label="Réglages des visiteurs" title="Réglages">⚙️</button>` : ""}
        ${i.gestion ? `<button class="p" data-a="nouveau">＋ Visiteur</button>` : ""}</div>
      ${cur.length ? `<h3>En ce moment</h3>${cur.map((v) => this._item(v)).join("")}` : `<p class="vide">Aucun visiteur en ce moment.</p>`}
      ${next.length ? `<h3>À venir</h3>${next.map((v) => this._item(v)).join("")}` : ""}
      ${done.length ? `<details ${this._open ? "open" : ""}><summary>Terminées (${done.length})</summary>${done.map((v) => this._item(v)).join("")}</details>` : ""}`;
  }

  _item(v) {
    const i = this.info, g = i.gestion;
    const serie = v.recurrence;
    let when;
    if (serie && v.dort_ici && v.statut === "en_cours") when = `🛏️ dort ici, jusqu'à ${quand(v.fin)}`;
    else if (serie && v.dort_ici && v.statut === "prevue") when = `arrive ${quand(v.debut)}, dort ici jusqu'à ${quand(v.fin)}`;
    else if (serie && v.statut === "en_cours") when = `passage en cours, jusqu'à ${quand(v.fin)}`;
    else if (serie && v.statut === "prevue") when = `prochain passage ${quand(v.debut)}`;
    else if (serie) when = "passages terminés";
    else if (v.statut === "en_cours") when = `jusqu'à ${quand(v.fin)}`;
    else if (v.statut === "prevue") when = `arrive ${quand(v.debut)} · jusqu'à ${quand(v.fin)}`;
    else when = `${quand(v.debut)} → ${quand(v.fin)}`;
    const tags = [];
    tags.push(`<span class="tag">${esc(TYPES[v.type] || v.type)}</span>`);
    if (serie) {
      tags.push(`<span class="tag">🔁 ${esc(repText(serie))}</span>`);
      if (v.serie_fin) tags.push(`<span class="tag">jusqu'au ${esc(dfr(lastDay(v.serie_fin)))}</span>`);
      (v.sejours || []).filter((x) => !(v.dort_ici && new Date(x.fin) <= new Date(v.fin)))
        .forEach((x) => tags.push(`<span class="tag">🛏️ dort ici ${esc(quand(x.debut))} → ${esc(quand(x.fin))}</span>`));
    }
    if (v.arrivee) tags.push(`<span class="tag ok">✓ arrivé·e ${esc(quand(v.arrivee.t))}</span>`);
    (v.plaques || []).forEach((p) => tags.push(`<span class="tag">🚗 ${esc(p)}</span>`));
    if (v.a_un_code && g && v.code) {
      const show = this.reveal.has(v.id);
      tags.push(`<span class="tag code" data-a="voir" data-id="${esc(v.id)}" role="button" aria-label="${show ? "Masquer" : "Afficher"} le code">🔑 ${show ? esc(v.code) : "••••••"}</span>`);
    } else if (v.a_un_code) tags.push(`<span class="tag">🔑 code</span>`);
    if (v.acces?.length) {
      const names = Object.fromEntries((i.acces || []).map((a) => [a.entity_id, a.nom]));
      tags.push(`<span class="tag">ouvre : ${esc(v.acces.map((e) => names[e] || e).join(", "))}</span>`);
    }
    if (v.note) tags.push(`<span class="tag">📝 ${esc(v.note)}</span>`);
    const sure = (k) => this.sure === `${k}:${v.id}`;
    const acts = !g ? "" : `<div class="acts">
      ${v.statut !== "terminee" ? `<button data-a="message" data-id="${esc(v.id)}">✉️ Message</button>` : ""}
      ${v.statut === "en_cours" && !serie ? `<button data-a="plus" data-id="${esc(v.id)}">＋2 h</button>` : ""}
      <button data-a="modifier" data-id="${esc(v.id)}">${v.statut === "terminee" ? "Revenir" : "Modifier"}</button>
      ${v.statut !== "terminee" && (serie || v.type === "passage") ? `<button data-a="nuit" data-id="${esc(v.id)}">🛏️ Dort ici</button>` : ""}
      ${serie && v.sejours?.length ? `<button class="${sure("sansnuit") ? "d sure" : ""}" data-a="sansnuit" data-id="${esc(v.id)}">${sure("sansnuit") ? "Confirmer : plus de nuit" : "Annuler la nuit"}</button>` : ""}
      ${serie && v.statut === "prevue" ? `<button class="${sure("sauter") ? "d sure" : ""}" data-a="sauter" data-id="${esc(v.id)}">${sure("sauter") ? `Confirmer : pas ${esc(quand(v.debut))}` : "Pas cette fois"}</button>` : ""}
      ${v.statut === "en_cours" ? `<button class="d ${sure("terminer") ? "sure" : ""}" data-a="terminer" data-id="${esc(v.id)}">${sure("terminer") ? "Confirmer le départ" : "Parti·e"}</button>` : ""}
      ${v.statut !== "en_cours" || serie ? `<button class="d ${sure("supprimer") ? "sure" : ""}" data-a="supprimer" data-id="${esc(v.id)}">${sure("supprimer") ? (serie ? "Confirmer : tous les passages" : "Confirmer") : "Supprimer"}</button>` : ""}
    </div>`;
    return `<div class="v ${esc(v.statut)} ${esc(v.type)}"><div class="l1"><div class="av">${esc((v.nom || "?").slice(0, 1).toUpperCase())}</div>
      <div><div class="nom">${esc(v.nom)}</div><div class="sub">${esc(when)}</div></div></div>
      <div class="tags">${tags.join("")}</div>${acts}</div>`;
  }

  // ───────── formulaire ─────────
  _newForm(v) {
    const now = new Date();
    if (!v) {
      return { id: null, nom: "", type: "sur_place", maintenant: true, debut: toLocalInput(new Date(now.getTime() + 3600e3)),
        fin: null, choix: null, plaques: "", telephone: "", note: "", code: false, acces: [], alarme: false, err: "", busy: false, statut: "nouvelle",
        ...this._repDefaults(now) };
    }
    if (v.recurrence) {
      const r = v.recurrence;
      return { id: v.id, nom: v.nom, type: v.type_serie || v.type, regulier: true, wasSerie: true, jours: [...r.jours], de: r.de, a: r.a, toutes: r.toutes || 1,
        depuis: dateInput(new Date(v.serie_debut || v.debut)), jusqu: dateInput(lastDay(v.serie_fin || v.fin)),
        maintenant: false, debut: toLocalInput(new Date(now.getTime() + 3600e3)), fin: null, choix: null,
        plaques: (v.plaques || []).join(", "), telephone: v.telephone || "", note: v.note || "",
        code: !!v.a_un_code, codeMode: "garder", acces: [...(v.acces || [])], alarme: !!v.alarme, err: "", busy: false, statut: v.statut };
    }
    return { id: v.id, nom: v.nom, type: v.type, maintenant: false, debut: toLocalInput(new Date(v.debut)),
      fin: toLocalInput(new Date(v.statut === "terminee" ? Math.max(Date.now() + 2 * 3600e3, new Date(v.fin)) : new Date(v.fin))),
      choix: "autre", plaques: (v.plaques || []).join(", "), telephone: v.telephone || "", note: v.note || "",
      code: !!v.a_un_code, codeMode: "garder", acces: [...(v.acces || [])], alarme: !!v.alarme, err: "", busy: false, statut: v.statut,
      ...this._repDefaults(now) };
  }

  _repDefaults(now) {
    const fin = new Date(now);
    fin.setFullYear(fin.getFullYear() + 1);
    return { regulier: false, wasSerie: false, jours: [(now.getDay() + 6) % 7], de: "08:00", a: "12:00", toutes: 1,
      depuis: dateInput(now), jusqu: dateInput(fin) };
  }

  _start(f) { return f.maintenant ? new Date() : fromLocalInput(f.debut); }

  _formHtml() {
    const f = this.form, i = this.info;
    const start = this._start(f) || new Date();
    const quick = quickEnds(f.type, start);
    const fin = f.choix === "autre" ? fromLocalInput(f.fin) : (quick.find(([k]) => k === f.choix)?.[1] || null);
    const started = f.statut === "en_cours" && !f.wasSerie;
    const acc = i.acces || [];
    const alarmChecked = f.acces.some((e) => e.startsWith("alarm_control_panel."));
    return `<div class="fond"><div class="boite" role="dialog" aria-modal="true" aria-labelledby="ft">
      <h2 id="ft">${f.id ? `Modifier — ${esc(f.nom)}` : "Nouveau visiteur"}</h2>
      ${f.err ? `<p class="err" role="alert">${esc(f.err)}</p>` : ""}
      <label class="c" for="nom">Nom</label><input id="nom" type="text" maxlength="60" autocomplete="off" value="${esc(f.nom)}" placeholder="Prénom ou nom">
      <label class="c">Type</label><div class="seg">
        <button data-f="type" data-v="sur_place" class="${f.type === "sur_place" ? "on" : ""}">🛏️ Reste sur place</button>
        <button data-f="type" data-v="passage" class="${f.type === "passage" ? "on" : ""}">🔧 Passage</button></div>
      <div class="res">${f.type === "sur_place" ? "Compte comme quelqu'un à la maison : pas d'extinction ni de mode absence, pas d'armement automatique." : "Artisan, livreur, voisin… : les caméras le signalent en simple info (sauf la nuit)."}</div>
      <label class="c">Quand</label><div class="seg">
        <button data-f="regulier" data-v="0" class="${!f.regulier ? "on" : ""}">Une fois</button>
        <button data-f="regulier" data-v="1" class="${f.regulier ? "on" : ""}">🔁 Régulièrement</button></div>
      ${f.regulier ? this._repHtml(f) : this._onceHtml(f, started, quick, fin, start)}
      <label class="c" for="plaques">Véhicule (plaque, facultatif)</label><input id="plaques" type="text" maxlength="60" value="${esc(f.plaques)}" placeholder="AB-123-CD" autocapitalize="characters">
      <label class="c" for="tel">Téléphone (pour lui envoyer le message)</label><input id="tel" type="tel" maxlength="30" value="${esc(f.telephone)}">
      ${acc.length ? `<label class="chk"><input type="checkbox" id="code" ${f.code ? "checked" : ""}> Donner un code visiteur (tablette)</label>
        ${f.code ? `<div style="margin-left:8px">${acc.map((a) => `<label class="chk"><input type="checkbox" data-acc="${esc(a.entity_id)}" ${f.acces.includes(a.entity_id) ? "checked" : ""}> ${esc(a.nom)}${a.alarme ? " (alarme)" : ""}</label>`).join("")}
          ${alarmChecked ? `<label class="chk"><input type="checkbox" id="alarme" ${f.alarme ? "checked" : ""}> Peut désarmer l'alarme</label><div class="warn">Sans cette case, le code ne désarme jamais l'alarme.</div>` : ""}
          ${f.id && f.codeMode !== undefined && this._wasCoded ? `<label class="chk"><input type="checkbox" id="nouveaucode" ${f.codeMode === "nouveau" ? "checked" : ""}> Changer le code</label>` : ""}
          <div class="res">Le code ne marche que pendant la visite, sur les tablettes, et vous prévient à chaque usage.</div></div>` : ""}`
        : ""}
      <label class="c" for="note">Note</label><textarea id="note" maxlength="500">${esc(f.note)}</textarea>
      <div class="pied"><button data-a="annuler">Annuler</button><button class="p" data-a="enregistrer" ${f.busy ? "disabled" : ""}>Enregistrer</button></div>
    </div></div>`;
  }

  _onceHtml(f, started, quick, fin, start) {
    const i = this.info;
    return `${started ? "" : `<label class="c">Arrivée</label><div class="seg">
        <button data-f="maintenant" data-v="1" class="${f.maintenant ? "on" : ""}">Là maintenant</button>
        <button data-f="maintenant" data-v="0" class="${!f.maintenant ? "on" : ""}">Plus tard</button></div>
        ${f.maintenant ? "" : `<input id="debut" type="datetime-local" value="${esc(f.debut)}" style="margin-top:6px">`}`}
      <label class="c">Départ</label><div class="chips">
        ${quick.map(([k]) => `<button data-f="choix" data-v="${esc(k)}" class="${f.choix === k ? "on" : ""}">${esc(k)}</button>`).join("")}
        <button data-f="choix" data-v="autre" class="${f.choix === "autre" ? "on" : ""}">Autre…</button></div>
      ${f.choix === "autre" ? `<input id="fin" type="datetime-local" value="${esc(f.fin || toLocalInput(new Date(start.getTime() + 2 * 3600e3)))}" style="margin-top:6px">` : ""}
      <div class="res">${fin ? `Jusqu'à ${esc(quand(fin.toISOString()))}` : (f.id ? "" : `Sans choix : ${esc(String(f.type === "passage" ? i.durees?.passage : i.durees?.sur_place))} h`)}</div>`;
  }

  _repHtml(f) {
    const timeIn = (id, val) => `<input id="${id}" type="time" value="${esc(val)}" style="padding:10px;border-radius:10px;border:1px solid var(--divider-color,#ccc);font:inherit;background:var(--card-background-color,#fff);color:inherit">`;
    const dateIn = (id, val) => `<input id="${id}" type="date" value="${esc(val)}" style="padding:10px;border-radius:10px;border:1px solid var(--divider-color,#ccc);font:inherit;background:var(--card-background-color,#fff);color:inherit">`;
    const r = { jours: [...f.jours].sort(), de: f.de, a: f.a, toutes: f.toutes };
    return `<label class="c">Jours</label><div class="chips">
        ${JL.map((j, n) => `<button data-f="jour" data-v="${n}" class="${f.jours.includes(n) ? "on" : ""}" aria-pressed="${f.jours.includes(n)}">${j}</button>`).join("")}</div>
      <label class="c">Horaires de chaque passage</label>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">de ${timeIn("rep_de", f.de)} à ${timeIn("rep_a", f.a)}</div>
      <label class="c">Fréquence</label><div class="seg">
        ${[[1, "Chaque semaine"], [2, "Une sur deux"], [3, "Une sur trois"], [4, "Une sur quatre"]].map(([n, lab]) => `<button data-f="toutes" data-v="${n}" class="${f.toutes === n ? "on" : ""}">${lab}</button>`).join("")}</div>
      <label class="c">Période</label>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">du ${dateIn("rep_depuis", f.depuis)} au ${dateIn("rep_jusqu", f.jusqu)}</div>
      <div class="res">${f.jours.length && f.de && f.a && f.de !== f.a ? esc(repText(r)) + (f.a < f.de ? " (jusqu'au lendemain)" : "") : "Choisir au moins un jour et des horaires."}</div>`;
  }

  // ───────── « dort ici » : nuit sur place pour un visiteur de passage ─────────
  _openStay(v) {
    const enCours = v.statut === "en_cours";
    let base = enCours ? new Date() : new Date(v.debut);
    if (isNaN(base)) base = new Date();
    const fin = atHour(base, 1, 10);
    this.stay = { id: v.id, nom: v.nom, serie: !!v.recurrence, enCours, debut: toLocalInput(base), fin: toLocalInput(fin), err: "", busy: false };
  }

  _stayHtml() {
    const st = this.stay;
    const base = (st.enCours || !st.serie ? null : fromLocalInput(st.debut)) || new Date();
    const chips = [["Demain matin", atHour(base, 1, 10)], ["Demain soir", atHour(base, 1, 19)], ["2 nuits", atHour(base, 2, 10)], ["3 nuits", atHour(base, 3, 10)]];
    return `<div class="fond" data-fond="stay"><div class="boite" role="dialog" aria-modal="true" aria-labelledby="stt">
      <h2 id="stt">🛏️ ${esc(st.nom)} reste dormir</h2>
      ${st.err ? `<p class="err" role="alert">${esc(st.err)}</p>` : ""}
      ${st.serie && !st.enCours ? `<label class="c" for="s_debut">Arrivée</label><input id="s_debut" type="datetime-local" value="${esc(st.debut)}">` : ""}
      <label class="c">Départ</label><div class="chips">
        ${chips.map(([k, d]) => `<button data-s="${esc(toLocalInput(d))}" class="${st.fin === toLocalInput(d) ? "on" : ""}">${esc(k)}</button>`).join("")}</div>
      <input id="s_fin" type="datetime-local" value="${esc(st.fin)}" style="margin-top:6px">
      <div class="res">Pendant ce temps, il compte comme quelqu'un à la maison (pas de mode absence ni d'armement automatique).${st.serie ? " Même code, mêmes accès ; les passages habituels continuent ensuite." : ""}</div>
      <div class="pied"><button data-a="s_annuler">Annuler</button><button class="p" data-a="s_ok" ${st.busy ? "disabled" : ""}>Enregistrer</button></div>
    </div></div>`;
  }

  _readStay() {
    const R = this.shadowRoot, st = this.stay;
    if (!st) return;
    if (R.getElementById("s_debut")) st.debut = R.getElementById("s_debut").value;
    if (R.getElementById("s_fin")) st.fin = R.getElementById("s_fin").value;
  }

  async _saveStay() {
    this._readStay();
    const st = this.stay;
    st.err = "";
    const fin = fromLocalInput(st.fin);
    const debut = st.serie && !st.enCours ? fromLocalInput(st.debut) : null;
    if (!fin) { st.err = "Indiquer l'heure de départ."; return this._render(); }
    if (st.serie && !st.enCours && !debut) { st.err = "Indiquer l'heure d'arrivée."; return this._render(); }
    if (fin <= (debut || new Date())) { st.err = "Le départ doit être après l'arrivée."; return this._render(); }
    const msg = st.serie ? { type: "visiteurs/sejour", visite: st.id, fin: toServer(fin) }
      : { type: "visiteurs/modifier", visite: st.id, type_visite: "sur_place", fin: toServer(fin) };
    if (debut) msg.debut = toServer(debut);
    st.busy = true; this._render();
    try {
      const r = await this._ws(msg);
      st.busy = false;
      if (!r.ok) { st.err = r.message || "Refusé"; return this._render(); }
      this.stay = null;
      await this._load();
      this._toast(`${st.nom} dort ici jusqu'à ${quand(fin.toISOString())}`);
    } catch (e) {
      st.busy = false; st.err = e?.message || String(e);
    }
    this._render();
  }

  // ───────── réglages (administrateurs) ─────────
  _regHtml() {
    const r = this.reg, v = r.v;
    if (!r.data) return `<div class="fond"><div class="boite"><p>Chargement…</p></div></div>`;
    const d = r.data;
    const num = (k, lab, unit, min, max, step) => `<label class="c" for="r_${k}">${lab}</label>
      <div style="display:flex;align-items:center;gap:8px"><input id="r_${k}" data-r="${k}" type="number" min="${min}" max="${max}" step="${step}" value="${esc(v[k])}" style="width:110px;padding:10px;border-radius:10px;border:1px solid var(--divider-color,#ccc);font:inherit;background:var(--card-background-color,#fff);color:inherit"> ${unit}</div>`;
    const sel = (k, opts) => `<div class="seg">${opts.map(([val, lab]) => `<button data-rs="${k}" data-v="${esc(val)}" class="${String(v[k]) === String(val) ? "on" : ""}">${esc(lab)}</button>`).join("")}</div>`;
    const timeIn = (k) => `<input data-r="${k}" type="time" value="${esc(String(v[k] || "").slice(0, 5))}" style="padding:10px;border-radius:10px;border:1px solid var(--divider-color,#ccc);font:inherit;background:var(--card-background-color,#fff);color:inherit">`;
    return `<div class="fond"><div class="boite" role="dialog" aria-modal="true" aria-labelledby="rgt">
      <h2 id="rgt">Réglages des visiteurs — ${esc(this.info.site || "")}</h2>
      ${r.err ? `<p class="err" role="alert">${esc(r.err)}</p>` : ""}
      <h3>Wi-Fi invité</h3>
      <label class="c" for="r_ssid">Nom du réseau</label><input id="r_ssid" data-r="wifi_ssid" type="text" maxlength="32" value="${esc(v.wifi_ssid || "")}" placeholder="ex. Les Roches Invités">
      <label class="c" for="r_mdp">Mot de passe</label>
      <div style="display:flex;gap:6px"><input id="r_mdp" data-r="wifi_mot_de_passe" type="text" maxlength="63" value="${esc(v.wifi_mot_de_passe || "")}" autocomplete="off" spellcheck="false" style="flex:1"><button data-a="r_gen">🎲 Générer</button></div>
      <label class="c">Sécurité</label>${sel("wifi_securite", [["WPA", "WPA2"], ["SAE", "WPA3"], ["nopass", "Ouvert"]])}
      <div class="res">Le réseau se crée dans UniFi avec ce nom et ce mot de passe. Ici, ils servent au QR code de la tablette et au message d'accueil.</div>
      <h3>Accueil</h3>
      <label class="c" for="r_cons">Consignes</label><textarea id="r_cons" data-r="consignes" maxlength="2000" placeholder="ex. Fermer le portail derrière vous. Les chiens ne doivent pas sortir.">${esc(v.consignes || "")}</textarea>
      <label class="c" for="r_lum">Lumière d'accueil (allumée au début d'une visite s'il fait nuit)</label>
      <select id="r_lum" data-r="lumiere_accueil" style="width:100%;padding:10px;border-radius:10px;font:inherit;border:1px solid var(--divider-color,#ccc);background:var(--card-background-color,#fff);color:inherit">
        <option value="">Aucune</option>${d.lumieres_possibles.map((l) => `<option value="${esc(l.entity_id)}" ${v.lumiere_accueil === l.entity_id ? "selected" : ""}>${esc(l.nom)}</option>`).join("")}</select>
      <h3>Accès qu'on peut donner avec un code visiteur</h3>
      <div class="res">Pour chaque visite, on coche ensuite seulement ceux qu'on veut.</div>
      ${d.acces_possibles.map((a) => `<label class="chk"><input type="checkbox" data-racc="${esc(a.entity_id)}" ${(v.acces_proposes || []).includes(a.entity_id) ? "checked" : ""}> ${esc(a.nom)}${a.alarme ? " (alarme)" : ""}</label>`).join("") || `<p class="vide">Aucune porte, serrure ou alarme trouvée.</p>`}
      <h3>Comportement pendant une visite</h3>
      ${Object.entries(d.regles).map(([k, lab]) => `<label class="chk"><input type="checkbox" data-rb="${k}" ${v[k] !== false ? "checked" : ""}> ${esc(lab)}</label>`).join("")}
      <label class="c">Nuit (de … à …)</label><div style="display:flex;gap:8px;align-items:center">${timeIn("nuit_debut")} → ${timeIn("nuit_fin")}</div>
      <h3>Durées</h3>
      ${num("duree_passage_h", "Passage, par défaut", "h", 0.25, 24, 0.25)}
      ${num("duree_sur_place_h", "Séjour sur place, par défaut", "h", 1, 720, 1)}
      ${num("marge_avant_min", "Marge avant l'arrivée prévue", "min", 0, 240, 5)}
      ${num("marge_apres_min", "Marge après le départ prévu", "min", 0, 240, 5)}
      <h3>Notifications</h3>
      <label class="c">Prévenir de</label>${sel("prevenir", [["tout", "Tout"], ["arrivee_depart", "Arrivées, codes, fins"], ["codes", "Codes seulement"], ["rien", "Rien"]])}
      <label class="c">Qui</label>${sel("niveau", [["alerte", "Richard et Julie"], ["admin", "Administrateurs"], ["info", "Discord seulement"]])}
      <div class="pied"><button data-a="r_annuler">Annuler</button><button class="p" data-a="r_enregistrer" ${r.busy ? "disabled" : ""}>Enregistrer</button></div>
    </div></div>`;
  }

  _readReg() {
    const R = this.shadowRoot, v = this.reg?.v;
    if (!v) return;
    R.querySelectorAll("[data-r]").forEach((el) => { v[el.dataset.r] = el.type === "number" ? Number(el.value) : el.value; });
    R.querySelectorAll("[data-rb]").forEach((el) => { v[el.dataset.rb] = el.checked; });
    const acc = [];
    R.querySelectorAll("[data-racc]").forEach((el) => { if (el.checked) acc.push(el.dataset.racc); });
    if (R.querySelector("[data-racc]")) v.acces_proposes = acc;
  }

  async _openReg() {
    this.reg = { v: {}, data: null, err: "", busy: false };
    this._render();
    try {
      const r = await this._ws({ type: "visiteurs/reglages" });
      if (!r.ok) { this.reg = null; this._toast(r.message); return this._render(); }
      this.reg.data = r; this.reg.v = { ...r.valeurs };
    } catch (e) { this.reg = null; this._toast(e?.message || String(e)); }
    this._render();
  }

  async _saveReg(gen) {
    this._readReg();
    const v = this.reg.v;
    const msg = { type: "visiteurs/regler" };
    for (const [k, val] of Object.entries(v)) {
      if (val === null || val === undefined) continue;
      if (k === "nuit_debut" || k === "nuit_fin") { if (/^\d{2}:\d{2}/.test(val)) msg[k] = val.slice(0, 5) + ":00"; continue; }
      msg[k] = val;
    }
    if (gen) msg.wifi_generer = true;
    this.reg.busy = true; this.reg.err = ""; this._render();
    try {
      const r = await this._ws(msg);
      this.reg.busy = false;
      if (!r.ok) { this.reg.err = r.message; return this._render(); }
      if (gen) { this.reg.data = r; this.reg.v.wifi_mot_de_passe = r.valeurs.wifi_mot_de_passe; this._toast("Nouveau mot de passe enregistré"); }
      else { this.reg = null; this._toast("Réglages enregistrés"); }
      await this._load();
    } catch (e) { this.reg.busy = false; this.reg.err = e?.message || String(e); }
    this._render();
  }

  _resultHtml() {
    const r = this.result;
    const sms = r.telephone ? `sms:${encodeURIComponent(r.telephone.replace(/[^\d+]/g, ""))}?body=${encodeURIComponent(r.message)}` : "";
    return `<div class="fond"><div class="boite" role="dialog" aria-modal="true" aria-labelledby="rt">
      <h2 id="rt">${esc(r.titre)}</h2>
      ${r.code ? `<div class="sub" style="text-align:center">Code visiteur</div><div class="grandcode">${esc(r.code)}</div>` : ""}
      <label class="c" for="msg">Message à envoyer</label><textarea id="msg" readonly style="min-height:160px">${esc(r.message)}</textarea>
      <div class="pied"><button data-a="fermer">Fermer</button><button data-a="copier">Copier</button>
        ${navigator.share ? `<button data-a="partager">Partager</button>` : ""}
        ${sms ? `<a href="${esc(sms)}" style="text-decoration:none"><button class="p" type="button">SMS</button></a>` : ""}</div>
    </div></div>`;
  }

  _readForm() {
    const R = this.shadowRoot, f = this.form;
    if (!f) return;
    const val = (id) => R.getElementById(id)?.value;
    if (R.getElementById("nom")) f.nom = val("nom");
    if (R.getElementById("debut")) f.debut = val("debut");
    if (R.getElementById("fin")) f.fin = val("fin");
    if (R.getElementById("plaques")) f.plaques = val("plaques");
    if (R.getElementById("tel")) f.telephone = val("tel");
    if (R.getElementById("note")) f.note = val("note");
    if (R.getElementById("rep_de")) f.de = val("rep_de");
    if (R.getElementById("rep_a")) f.a = val("rep_a");
    if (R.getElementById("rep_depuis")) f.depuis = val("rep_depuis");
    if (R.getElementById("rep_jusqu")) f.jusqu = val("rep_jusqu");
    if (R.getElementById("alarme")) f.alarme = R.getElementById("alarme").checked;
    if (R.getElementById("nouveaucode")) f.codeMode = R.getElementById("nouveaucode").checked ? "nouveau" : "garder";
  }

  _bind() {
    const R = this.shadowRoot;
    R.querySelectorAll("[data-a]").forEach((b) => b.addEventListener("click", (e) => { e.stopPropagation(); this._act(b.dataset.a, b.dataset.id); }));
    R.querySelector("details")?.addEventListener("toggle", (e) => { this._open = e.target.open; });
    if (this.form) {
      R.querySelectorAll("[data-f]").forEach((b) => b.addEventListener("click", () => {
        this._readForm();
        const k = b.dataset.f, v = b.dataset.v;
        if (k === "maintenant") this.form.maintenant = v === "1";
        else if (k === "regulier") { this.form.regulier = v === "1"; if (this.form.regulier && !this.form.id) this.form.type = "passage"; }
        else if (k === "jour") { const n = +v; this.form.jours = this.form.jours.includes(n) ? this.form.jours.filter((x) => x !== n) : [...this.form.jours, n].sort(); }
        else if (k === "toutes") this.form.toutes = +v;
        else if (k === "type") { this.form.type = v; if (this.form.choix !== "autre") this.form.choix = null; }
        else if (k === "choix") {
          this.form.choix = v;
          if (v === "autre" && !this.form.fin) this.form.fin = toLocalInput(new Date((this._start(this.form) || new Date()).getTime() + 2 * 3600e3));
        }
        this._render();
      }));
      R.getElementById("code")?.addEventListener("change", (e) => { this._readForm(); this.form.code = e.target.checked; this._render(); });
      R.querySelectorAll("[data-acc]").forEach((c) => c.addEventListener("change", () => {
        this._readForm();
        const id = c.dataset.acc;
        this.form.acces = c.checked ? [...new Set([...this.form.acces, id])] : this.form.acces.filter((x) => x !== id);
        if (!this.form.acces.some((x) => x.startsWith("alarm_control_panel."))) this.form.alarme = false;
        this._render();
      }));
      R.querySelector(".fond")?.addEventListener("click", (e) => { if (e.target.classList.contains("fond") && !this.form.busy) { this.form = null; this._render(); } });
      if (!this._focused) { R.getElementById("nom")?.focus(); this._focused = true; }
    }
    if (this.reg) {
      R.querySelectorAll("[data-rs]").forEach((b) => b.addEventListener("click", () => { this._readReg(); this.reg.v[b.dataset.rs] = b.dataset.v; this._render(); }));
    }
    if (this.stay) {
      R.querySelectorAll("[data-s]").forEach((b) => b.addEventListener("click", () => { this._readStay(); this.stay.fin = b.dataset.s; this._render(); }));
      R.querySelector('[data-fond="stay"]')?.addEventListener("click", (e) => { if (e.target.classList.contains("fond") && !this.stay.busy) { this.stay = null; this._render(); } });
    }
    if (this.result) R.querySelector(".fond")?.addEventListener("click", (e) => { if (e.target.classList.contains("fond")) { this.result = null; this._render(); } });
  }

  async _act(a, id) {
    const v = id ? this.info.visites.find((x) => x.id === id) : null;
    if (a !== "terminer" && a !== "supprimer" && a !== "sauter" && a !== "sansnuit") this.sure = null;
    switch (a) {
      case "reglages": return this._openReg();
      case "r_annuler": this.reg = null; break;
      case "r_enregistrer": return this._saveReg(false);
      case "r_gen": return this._saveReg(true);
      case "nouveau": this.form = this._newForm(null); this._wasCoded = false; this._focused = false; break;
      case "modifier": this.form = this._newForm(v); this._wasCoded = !!v?.a_un_code; this._focused = false; break;
      case "annuler": this.form = null; break;
      case "nuit": this._openStay(v); break;
      case "s_annuler": this.stay = null; break;
      case "s_ok": return this._saveStay();
      case "fermer": this.result = null; break;
      case "voir": this.reveal.has(id) ? this.reveal.delete(id) : this.reveal.add(id); break;
      case "enregistrer": return this._save();
      case "copier": return this._copy();
      case "partager":
        try { await navigator.share({ text: this.result.message }); } catch (e) { /* annulé */ }
        return;
      case "message": {
        const r = await this._call({ type: "visiteurs/message", visite: id });
        if (r) this.result = { titre: `Message pour ${v.nom}`, message: r.message, code: v.code, telephone: v.telephone };
        break;
      }
      case "plus": {
        const fin = new Date(Math.max(new Date(v.fin).getTime(), Date.now()) + 2 * 3600e3);
        if (await this._call({ type: "visiteurs/modifier", visite: id, fin: toServer(fin) })) this._toast(`${v.nom} : prolongé jusqu'à ${quand(fin.toISOString())}`);
        break;
      }
      case "terminer":
      case "supprimer":
      case "sauter":
      case "sansnuit":
        if (this.sure !== `${a}:${id}`) {
          this.sure = `${a}:${id}`;
          clearTimeout(this._sureT);
          this._sureT = setTimeout(() => { this.sure = null; this._render(); }, 4000);
          break;
        }
        this.sure = null;
        if (await this._call(a === "sansnuit" ? { type: "visiteurs/sejour", visite: id, retirer: true } : { type: `visiteurs/${a}`, visite: id })) {
          this._toast(a === "sansnuit" ? `${v.nom} : nuit annulée` : a === "sauter" ? `${v.nom} : pas de passage ${quand(v.debut)}`
            : a === "terminer" ? (v.recurrence ? `${v.nom} : passage terminé` : `Visite de ${v.nom} terminée`)
              : v.recurrence ? "Passages supprimés" : "Visite supprimée");
        }
        break;
      default: break;
    }
    this._render();
  }

  async _call(msg) {
    try {
      const r = await this._ws(msg);
      if (!r.ok) { this._toast(r.message || "Refusé"); return null; }
      await this._load();
      return r;
    } catch (e) {
      this._toast(e?.message || String(e));
      return null;
    }
  }

  async _copy() {
    const ta = this.shadowRoot.getElementById("msg");
    try { await navigator.clipboard.writeText(this.result.message); this._toast("Message copié"); }
    catch (e) { ta?.select(); try { document.execCommand("copy"); this._toast("Message copié"); } catch (e2) { this._toast("Copie impossible : sélectionner le texte"); } }
  }

  async _save() {
    this._readForm();
    const f = this.form, i = this.info;
    f.err = "";
    const nom = (f.nom || "").trim();
    if (!nom) { f.err = "Indiquer le nom du visiteur."; return this._render(); }
    if (f.regulier) return this._saveSerie(f, nom);
    const start = f.maintenant ? null : fromLocalInput(f.debut);
    if (!f.maintenant && f.statut !== "en_cours" && !start) { f.err = "Indiquer l'heure d'arrivée."; return this._render(); }
    const base = start || new Date();
    const quick = quickEnds(f.type, base);
    const fin = f.choix === "autre" ? fromLocalInput(f.fin) : (quick.find(([k]) => k === f.choix)?.[1] || null);
    if (f.choix === "autre" && !fin) { f.err = "Indiquer l'heure de départ."; return this._render(); }
    if (fin && fin <= base && f.statut !== "en_cours") { f.err = "Le départ doit être après l'arrivée."; return this._render(); }
    if (f.code && !f.acces.length) { f.err = "Cocher au moins un accès pour le code (ou décocher le code)."; return this._render(); }
    const msg = { type: f.id ? "visiteurs/modifier" : "visiteurs/ajouter", nom, type_visite: f.type, plaques: f.plaques,
      telephone: f.telephone, note: f.note, acces: f.code ? f.acces : [], alarme: f.code && f.alarme };
    if (f.id) msg.visite = f.id;
    if (f.statut !== "en_cours" && start) msg.debut = toServer(start); // « là maintenant » : le serveur prend l'heure actuelle
    if (fin) msg.fin = toServer(fin);
    if (!i.acces?.length) delete msg.acces;
    msg.code = f.code ? (f.id && this._wasCoded ? (f.codeMode || "garder") : "nouveau") : "aucun";
    if (!f.id && !f.code) msg.code = false;
    if (f.wasSerie) { // série → visite simple
      msg.repetition_jours = [];
      if (!msg.debut) msg.debut = toServer(start || new Date());
      if (!msg.fin) msg.fin = toServer(new Date((start || new Date()).getTime() + (f.type === "passage" ? i.durees?.passage || 2 : i.durees?.sur_place || 24) * 3600e3));
    }
    return this._send(msg, f);
  }

  _saveSerie(f, nom) {
    const i = this.info;
    if (!f.jours.length) { f.err = "Choisir au moins un jour."; return this._render(); }
    if (!f.de || !f.a || f.de === f.a) { f.err = "Indiquer l'heure de début et l'heure de fin (différentes)."; return this._render(); }
    if (!f.depuis || !f.jusqu || f.jusqu < f.depuis) { f.err = "La fin de la période doit être après son début."; return this._render(); }
    if (f.code && !f.acces.length) { f.err = "Cocher au moins un accès pour le code (ou décocher le code)."; return this._render(); }
    const msg = { type: f.id ? "visiteurs/modifier" : "visiteurs/ajouter", nom, type_visite: f.type, plaques: f.plaques,
      telephone: f.telephone, note: f.note, acces: f.code ? f.acces : [], alarme: f.code && f.alarme,
      repetition_jours: f.jours.map((n) => JLONG[n]), heure_debut: f.de, heure_fin: f.a, toutes_les: f.toutes,
      debut: f.depuis, jusqu_au: f.jusqu };
    if (f.id) msg.visite = f.id;
    if (!i.acces?.length) delete msg.acces;
    msg.code = f.code ? (f.id && this._wasCoded ? (f.codeMode || "garder") : "nouveau") : "aucun";
    if (!f.id && !f.code) msg.code = false;
    return this._send(msg, f);
  }

  async _send(msg, f) {
    f.busy = true; this._render();
    try {
      const r = await this._ws(msg);
      f.busy = false;
      if (!r.ok) { f.err = r.message || "Refusé"; return this._render(); }
      this.form = null;
      await this._load();
      if (!f.id) {
        const v = r.visite;
        this.result = { titre: `${v.nom} : ${v.recurrence ? "passages enregistrés" : "visite enregistrée"}`, message: r.message, code: v.code, telephone: v.telephone };
      } else this._toast("Visite modifiée");
    } catch (e) {
      f.busy = false; f.err = e?.message || String(e);
    }
    this._render();
  }
}

if (!customElements.get("visiteurs-card")) {
  customElements.define("visiteurs-card", VisiteursCard);
  window.customCards = window.customCards || [];
  window.customCards.push({ type: "visiteurs-card", name: "Visiteurs", description: "Visites, codes visiteur et accueil (Wi-Fi)" });
  console.info(`%c VISITEURS-CARD %c ${VERSION} `, "background:#2e7d32;color:#fff", "");
}
