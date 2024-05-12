#
# Copyright 2024 Johann Hanne
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do
# so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

# Version 1.0.0 (2024-05-12)

import argparse
import pathlib
import re
from collections import namedtuple

class Lexer:
    WHITESPACE = re.compile('([\t ]+)', re.ASCII | re.IGNORECASE)
    KEYWORD_PIN = re.compile('(PIN)[\t ]+', re.ASCII | re.IGNORECASE)
    IDENTIFIER = re.compile(r'([_A-Za-z][_A-Za-z0-9]*)', re.ASCII | re.IGNORECASE)
    NUMBER = re.compile(r'(0|[1-9][0-9]*)', re.ASCII | re.IGNORECASE)
    NUMBERBINARY = re.compile(r'\'b\'([01]+)', re.ASCII | re.IGNORECASE)
    OR = re.compile(r'([|+#])', re.ASCII | re.IGNORECASE)
    AND = re.compile(r'([&*])', re.ASCII | re.IGNORECASE)
    NOT = re.compile(r'([!~/])', re.ASCII | re.IGNORECASE)
    EQUALS = re.compile(r'(=)', re.ASCII | re.IGNORECASE)
    DOT = re.compile(r'(\.)', re.ASCII | re.IGNORECASE)
    SEMICOLON = re.compile(r'(;)', re.ASCII | re.IGNORECASE)

    class Token:
        def __init__(self, linenumber):
            self._linenumber = linenumber

        linenumber = property(lambda self: self._linenumber)

    class TokenKeywordPin(Token):
        toktype = 'KeywordPin'

        name = property(lambda self: self._name)

    class TokenIdentifier(Token):
        toktype = 'Identifier'

        def __init__(self, linenumber, name):
            super().__init__(linenumber)
            self._name = name

        name = property(lambda self: self._name)

    class TokenNumber(Token):
        toktype = 'Number'

        def __init__(self, linenumber, number):
            super().__init__(linenumber)
            self._number = number

        number = property(lambda self: self._number)

    class TokenOr(Token):
        toktype = 'Or'

    class TokenAnd(Token):
        toktype = 'And'

    class TokenNot(Token):
        toktype = 'Not'

    class TokenEquals(Token):
        toktype = 'Equals'

    class TokenDot(Token):
        toktype = 'Dot'

    class TokenEndCmd(Token):
        toktype = 'EndCmd'

    def __init__(self):
        self.projectname = None

    def read(self, fname):
        tokens = []

        f = open(fname, 'rt')
        lines = f.readlines()
        f.close()

        self.projectname = None
        multilinecommentactive = False
        cmdempty = True

        for i, l in enumerate(lines):
            if l[0] == ';':
                # Skip over comments
                continue
            elif l.lower().startswith('name '):
                self.projectname = l[5:].strip()
                if self.projectname[-1] == ';':
                    self.projectname = self.projectname[:-1].rstrip()
                continue
            elif l.lower().startswith('device ') or \
                 l.lower().startswith('partno ') or \
                 l.lower().startswith('revision ') or \
                 l.lower().startswith('date ') or \
                 l.lower().startswith('designer ') or \
                 l.lower().startswith('company ') or \
                 l.lower().startswith('assembly ') or \
                 l.lower().startswith('location '):
                # Skip over all these informational lines; do not even try
                # to tokenize them as they might contain characters leading
                # to tokenization errors (e.g. '-')
                continue

            while True:
                if multilinecommentactive:
                    commentend = l.find("*/", commentstart)
                    if commentend >= 0:
                        l = l[commentend + 2:]
                        multilinecommentactive = False
                        continue
                    else:
                        l = ""
                        break
                else:
                    commentstart = l.find("/*")
                if commentstart >= 0:
                    commentend = l.find("*/", commentstart)
                    if commentend >= 0:
                        l = l[:commentstart] + l[commentend + 2:]
                    else:
                        l = l[:commentstart]
                        multilinecommentactive = True
                        break
                else:
                    break

            l = l.rstrip()

            if l != '' and not re.match(self.WHITESPACE, l):
                # If a line does not start with whitespace, it starts a new command
                # => Artificially create a TokenEndCmd
                if not cmdempty:
                    tokens.append(self.TokenEndCmd(i))
                cmdempty = True

            while l != '':
                m = None
                t = None

                if m := re.match(self.WHITESPACE, l):
                    pass
                elif m := re.match(self.KEYWORD_PIN, l):
                    t = self.TokenKeywordPin(i + 1)
                elif m := re.match(self.IDENTIFIER, l):
                    t = self.TokenIdentifier(i + 1, m.group(1))
                elif m := re.match(self.NUMBER, l):
                    t = self.TokenNumber(i + 1, int(m.group(1)))
                elif m := re.match(self.NUMBERBINARY, l):
                    t = self.TokenNumber(i + 1, int(m.group(1), 2))
                elif m := re.match(self.OR, l):
                    t = self.TokenOr(i + 1)
                elif m := re.match(self.AND, l):
                    t = self.TokenAnd(i + 1)
                elif m := re.match(self.NOT, l):
                    t = self.TokenNot(i + 1)
                elif m := re.match(self.EQUALS, l):
                    t = self.TokenEquals(i + 1)
                elif m := re.match(self.DOT, l):
                    t = self.TokenDot(i + 1)
                elif m := re.match(self.SEMICOLON, l):
                    t = self.TokenEndCmd(i + 1)
                else:
                    raise RuntimeError(f'Invalid character in line {i + 1} ("{l}")')

                l = l[len(m.group(0)):]

                if t is not None:
                    cmdempty = False
                    tokens.append(t)

        if not cmdempty:
            tokens.append(self.TokenEndCmd(i))

        return tokens

class Assembler:
    Equation = namedtuple('Equation', [ 'negated', 'sum_of_products' ])

    def __init__(self):
        self._pinname_by_pinnumber = {}
        self._pinnumber_by_pinname = {}

        self._equations = {}
        self._oe_equations = {}

        self._pin_fusemap = {}
        self._pin_oe_fusemap = {}

    # Returns a tuple (next_i, sum_of_products)
    def _get_equation(self, tokens, i):

        if isinstance(tokens[i], Lexer.TokenNumber):
            if tokens[i].number == 0:
                sum_of_products = 0
            elif tokens[i].number == 1:
                sum_of_products = 1
            else:
                raise RuntimeError(f"Invalid syntax in line {tokens[i]._linenumber} (expected 0/1, got {tokens[i].number})")

            i += 1

            if not isinstance(tokens[i], Lexer.TokenEndCmd):
                raise RuntimeError(f"Invalid syntax in line {tokens[i]._linenumber} (expected EndCmd, got {tokens[i].toktype})")

        else:
            sum_of_products = []
            cur_product = set()

            while True:
                if isinstance(tokens[i], Lexer.TokenNot):
                    idneg = True
                    i += 1
                elif isinstance(tokens[i], Lexer.TokenIdentifier):
                    idneg = False
                else:
                    raise RuntimeError(f"Invalid syntax in line {tokens[i]._linenumber} (expected Not/TokenIdentifier, got {tokens[i].toktype})")

                if not isinstance(tokens[i], Lexer.TokenIdentifier):
                    raise RuntimeError(f"Invalid syntax in line {tokens[i]._linenumber} (expected TokenIdentifier, got {tokens[i].toktype})")
                name = tokens[i].name
                i += 1

                #print(f' {name}')
                if idneg:
                    cur_product.add('!' + name)
                else:
                    cur_product.add(name)

                if isinstance(tokens[i], Lexer.TokenAnd):
                    i += 1
                elif isinstance(tokens[i], Lexer.TokenOr):
                    sum_of_products.append(cur_product)
                    cur_product = set()
                    i += 1
                elif isinstance(tokens[i], Lexer.TokenEndCmd):
                    sum_of_products.append(cur_product)
                    break
                else:
                    raise RuntimeError(f"Invalid syntax in line {tokens[i]._linenumber} (expected And/Or/EndCmd, got {tokens[i].toktype})")

        return i, sum_of_products

    def assemble(self, tokens):

        i = 0

        while i < len(tokens):

            if isinstance(tokens[i], Lexer.TokenNot) and isinstance(tokens[i + 1], Lexer.TokenIdentifier) :
                eqneg = True
                i += 1
            else:
                eqneg = False

            if isinstance(tokens[i], Lexer.TokenKeywordPin):
                if not isinstance(tokens[i + 1], Lexer.TokenNumber):
                    raise RuntimeError(f"Keyword 'PIN' not followed by a number in line {tokens[i]._linenumber}")

                if not isinstance(tokens[i + 2], Lexer.TokenEquals):
                    raise RuntimeError(f"Pin number not followed by equals in line {tokens[i + 1]._linenumber}")

                if not isinstance(tokens[i + 3], Lexer.TokenIdentifier):
                    raise RuntimeError(f"Equals not followed by identifier in line {tokens[i + 3]._linenumber}")

                if not isinstance(tokens[i + 4], Lexer.TokenEndCmd):
                    raise RuntimeError(f"Unexpected token after identifier in line {tokens[i + 4]._linenumber}")

                number = tokens[i + 1].number

                if number in self._pinname_by_pinnumber:
                    raise RuntimeError(f"Duplicate pin number {number} in line {tokens[i + 1]._linenumber}")

                name = tokens[i + 3].name

                if number in self._pinnumber_by_pinname:
                    raise RuntimeError(f"Duplicate pin name '{name}' in line {tokens[i + 3]._linenumber}")

                self._pinname_by_pinnumber[number] = name
                self._pinnumber_by_pinname[name] = number

                i += 4

            elif isinstance(tokens[i], Lexer.TokenIdentifier) and isinstance(tokens[i + 1], Lexer.TokenEquals):
                #print("EQUATION")

                name = tokens[i].name

                i += 2

                i, sum_of_products = self._get_equation(tokens, i)

                self._equations[name] = self.Equation(negated=eqneg, sum_of_products=sum_of_products)

            elif isinstance(tokens[i], Lexer.TokenIdentifier) and isinstance(tokens[i + 1], Lexer.TokenDot) and \
                 isinstance(tokens[i + 2], Lexer.TokenIdentifier) and isinstance(tokens[i + 3], Lexer.TokenEquals):
                #print("OE EQUATION")

                if tokens[i + 2].name not in ("OE", "oe"):
                    raise RuntimeError(f"Invalid sub-identifier '{tokens[i + 2].name}' in line {tokens[i]._linenumber}")

                name = tokens[i].name

                i += 4

                i, sum_of_products = self._get_equation(tokens, i)

                self._oe_equations[name] = self.Equation(negated=eqneg, sum_of_products=sum_of_products)

            elif isinstance(tokens[i], Lexer.TokenEndCmd):
                # Skip over empty commands
                pass

            else:
                raise RuntimeError(f"Invalid syntax in line {tokens[i]._linenumber}")


            # Skip over TokenEndCmd
            i += 1

        for outputidx, outputpinnum in enumerate(range(19, 11, -1)):
            outputpinname = self._pinname_by_pinnumber[outputpinnum]
            #print(outputpinname)

            pin_fusemap = bytearray(7 * 32)
            pin_oe_fusemap = bytearray(32)

            if outputpinname in self._equations:

                if outputpinname not in self._oe_equations:
                    # No corresponding OE equation => Always enable output
                    pin_oe_fusemap[0:32] = 32 * (1, )

                eq = self._equations[outputpinname]

                #print(eq)

                if not eq.negated:
                    raise RuntimeError(f'Non-negated equations unsupported ({outputpinname})')

                if isinstance(eq.sum_of_products, int):
                    if eq.sum_of_products != 0:
                        pin_fusemap[0:32] = 32 * (1, )
                else:
                    productidx = 0

                    for _product in eq.sum_of_products:

                        product = set(_product)

                        if productidx > 6:
                            raise RuntimeError(f'More than 7 products are not supported ({outputpinname})')

                        for inputidx, inputpinnum in enumerate((2, 1, 3, 18, 4, 17, 5, 16, 6, 15, 7, 14, 8, 13, 9, 11)):
                            inputpinname = self._pinname_by_pinnumber[inputpinnum]

                            fuseidx = 32 * productidx + 2 * inputidx

                            if inputpinname in product:
                                # Leave fusemap entry at 0
                                product.remove(inputpinname)
                            else:
                                pin_fusemap[fuseidx] = 1

                            if '!' + inputpinname in product:
                                # Leave fusemap entry at 0
                                product.remove('!' + inputpinname)
                            else:
                                pin_fusemap[fuseidx + 1] = 1

                        if len(product) != 0:
                            raise RuntimeError(f'Equation for {outputpinname} contains undefined pin(s): {", ".join(product)}')

                        productidx += 1

            # else: Leave fusemap entries at "0"

            if outputpinname in self._oe_equations:

                #if outputpinname not in self._equations:
                #    raise RuntimeError(f'Got OE equations without corresponding equation ({outputpinname})')

                eq = self._oe_equations[outputpinname]

                #print(eq)

                if eq.negated:
                    raise RuntimeError(f'Negated OE equations unsupported ({outputpinname})')

                if isinstance(eq.sum_of_products, int):
                    if eq.sum_of_products != 0:
                        pin_oe_fusemap[0:32] = 32 * (1, )
                else:
                    if len(eq.sum_of_products) > 1:
                        raise RuntimeError(f'More than 1 OE product is not supported ({outputpinname})')

                    productidx = 0

                    product = set(eq.sum_of_products[0])

                    for inputidx, inputpinnum in enumerate((2, 1, 3, 18, 4, 17, 5, 16, 6, 15, 7, 14, 8, 13, 9, 11)):
                        inputpinname = self._pinname_by_pinnumber[inputpinnum]

                        fuseidx = 2 * inputidx

                        if inputpinname in product:
                            # Leave fusemap entry at 0
                            product.remove(inputpinname)
                        else:
                            pin_oe_fusemap[fuseidx] = 1

                        if '!' + inputpinname in product:
                            # Leave fusemap entry at 0
                            product.remove('!' + inputpinname)
                        else:
                            pin_oe_fusemap[fuseidx + 1] = 1

                    if len(product) != 0:
                        raise RuntimeError(f'Equation for {outputpinname} contains undefined pin(s): {", ".join(product)}')


            # else: Leave OE fusemap entries at "0"

            self._pin_fusemap[outputpinnum] = bytes(pin_fusemap)
            self._pin_oe_fusemap[outputpinnum] = bytes(pin_oe_fusemap)

    def get_pin_fusemap(self, pinnumber):
        return self._pin_fusemap[pinnumber]

    def get_pin_oe_fusemap(self, pinnumber):
        return self._pin_oe_fusemap[pinnumber]

    def dump(self):
        for name, eq in self._equations.items():
            print(name)

            sum_of_products = eq.sum_of_products

            if isinstance(sum_of_products, int):
                print(sum_of_products)
            else:
                for product in sum_of_products:
                    print(product)

    def dump_fusemap(self):

        transtbl = bytes.maketrans(b'\x00\x01', b'x-')

        for outputidx, outputpinnum in enumerate(range(19, 11, -1)):
            outputpinname = self._pinname_by_pinnumber[outputpinnum]
            print(outputpinname)

            line = self._pin_oe_fusemap[outputpinnum].translate(transtbl)
            print(line.decode('ascii'))

            for fuseline in range(7):
                fuselineidx = fuseline * 32
                line = self._pin_fusemap[outputpinnum][fuselineidx:fuselineidx + 32].translate(transtbl)
                print(line.decode('ascii'))

# Only supports GAL16V8
class JedWriter:

    def __init__(self):
        self._fusemap = bytearray(2194 * b'0')

    @staticmethod
    def _pinnumber_to_index(pinnumber):
        if pinnumber > 19 or pinnumber < 12:
            raise RuntimeError(f'Got invalid pin number ({pinnumber})')

        return (19 - pinnumber)

    def set_pin_oe_term(self, pinnumber, statuses):
        offset = self._pinnumber_to_index(pinnumber) * 256
        s = iter(statuses)
        for i in range(32):
            self._fusemap[offset + i] = ord('1') if next(s) else ord('0')

    def set_pin_terms(self, pinnumber, statuses):
        offset = self._pinnumber_to_index(pinnumber) * 256 + 32
        s = iter(statuses)
        for i in range(224):
            self._fusemap[offset + i] = ord('1') if next(s) else ord('0')

    # Output polarity
    def set_output_polarity(self, pinnumber, status):
        index = self._pinnumber_to_index(pinnumber)
        self._fusemap[2048 + index] = ord('1') if status else ord('0')

    # No functionality, just 64 bits for project name or similar
    def set_signature(self, statuses):
        s = iter(statuses)
        for i in range(64):
            self._fusemap[2056 + i] = ord('1') if next(s) else ord('0')

    # For AC0 = 1, the AC1 bits of all outputs must be set to 1 for combinatorial mode
    def set_ac1_bit(self, pinnumber, status):
        index = self._pinnumber_to_index(pinnumber)
        self._fusemap[2120 + index] = ord('1') if status else ord('0')

    def set_product_term_disable_bits(self, pinnumber, statuses):
        pinindex = self._pinnumber_to_index(pinnumber)
        s = iter(statuses)
        for i in range(8):
            self._fusemap[2128 + 8 * pinindex + i] = ord('1') if next(s) else ord('0')

    def set_syn(self, status):
        self._fusemap[2192] = ord('1') if status else ord('0')

    def set_ac0(self, status):
        self._fusemap[2193] = ord('1') if status else ord('0')

    def get_file(self):
        data = b""

        # STX
        data += b"\x02"

        data += b"Device: GAL16V8\r\n"

        # Default fuse state for unspecified fuses
        data += b"*F0\r\n"

        # Security fuse
        data += b"*G0\r\n"

        # Number of fuses in device
        data += b"*QF%d\r\n" % len(self._fusemap)

        for offset in range(0, 2048, 32):
            line = self._fusemap[offset:offset + 32]
            if line != b'00000000000000000000000000000000':
                data += b"*L%04d %s\r\n" % (offset, line)

        # Output polarity
        offset = 2048
        line = self._fusemap[offset:offset + 8]
        if line != b'00000000':
            data += b"*L%04d %s\r\n" % (offset, line)

        # Signature
        offset = 2056
        line = self._fusemap[offset:offset + 64]
        if line != b'0000000000000000000000000000000000000000000000000000000000000000':
            data += b"*L%04d %s\r\n" % (offset, line)

        # AC1 bits
        offset = 2120
        line = self._fusemap[offset:offset + 8]
        if line != b'00000000':
            data += b"*L%04d %s\r\n" % (offset, line)

        # Product disable bits
        offset = 2128
        line = self._fusemap[offset:offset + 64]
        if line != b'0000000000000000000000000000000000000000000000000000000000000000':
            data += b"*L%04d %s\r\n" % (offset, line)

        # SYN
        offset = 2192
        line = self._fusemap[offset:offset + 1]
        if line != b'0':
            data += b"*L%04d %s\r\n" % (offset, line)

        # AC1
        offset = 2193
        line = self._fusemap[offset:offset + 1]
        if line != b'0':
               data += b"*L%04d %s\r\n" % (offset, line)

        # fuse checksum
        # The fusemap checksum is the 16bit sum of all the 8bit fuse values.
        fusecsum = 0
        for i in range(0, len(self._fusemap), 8):
            bstr = self._fusemap[i:i+8]
            b = int(bstr[::-1], 2)
            fusecsum += b
        data += b"*C%04x\r\n" % fusecsum

        # End of commands
        data += b"*\r\n"

        # ETX
        data += b"\x03"

        # The transmission checksum is a 16 bit sum of all bytes between
        # (and including) the STX and ETX markers
        csum = 0
        for b in data:
            csum += b
        csum &= 0xffff
        data += b"%04x" % csum

        return data

parser = argparse.ArgumentParser(prog = 'simplegalasm',
                    description = 'Simple GAL assembler to transform pete.py into a jed file')
parser.add_argument('filename')
args = parser.parse_args()

fpath = pathlib.Path(args.filename)

lexer = Lexer()
tokens = lexer.read(fpath)
#print(tokens)

jedbasename = lexer.projectname
if jedbasename is None:
    jedbasename = fpath.stem
jedfname = fpath.parent / (jedbasename + '.jed')

assembler = Assembler()
assembler.assemble(tokens)
#assembler.dump()
#assembler.dump_fusemap()

jedwriter = JedWriter()
for pinnumber in range(19, 11, -1):
    pin_oe_fusemap = assembler.get_pin_oe_fusemap(pinnumber)
    pin_fusemap = assembler.get_pin_fusemap(pinnumber)

    jedwriter.set_pin_oe_term(pinnumber, pin_oe_fusemap)
    jedwriter.set_pin_terms(pinnumber, pin_fusemap)
    # XOR = 0 => Active low output
    jedwriter.set_output_polarity(pinnumber, 0)
    # AC1 = 1 => Combinatorial
    jedwriter.set_ac1_bit(pinnumber, 1)
    jedwriter.set_product_term_disable_bits(pinnumber, (1, 1, 1, 1, 1, 1, 1, 1))
    # SYN = 1 => Purely combinatorial mode (pins 1 and 11 are ordinary inputs)
    jedwriter.set_syn(1)
    jedwriter.set_ac0(1)

f = open(jedfname, "wb")
f.write(jedwriter.get_file())
f.close()
