#
# Copyright 2024-2025 Johann Hanne
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

# Version 1.1.0 (2025-04-23)

import argparse
import pathlib
import boolexprsimplifier

parser = argparse.ArgumentParser(prog = 'pete',
                    description = 'Transform PAL EPROM dump to equations')
parser.add_argument('-p', dest = 'pinnames', help = 'Comma separated pin names: pin1,pin2,pin3,...,pin9,pin11,pin12,pin13,...,pin19')
parser.add_argument('-a', dest = 'andstr', default = '&' , help = 'string to use for logical and')
parser.add_argument('-o', dest = 'orstr',  default = '#' , help = 'string to use for logical or')
parser.add_argument('-n', dest = 'notstr', default = '!' , help = 'string to use for logical not')
parser.add_argument('filename')
args = parser.parse_args()

if args.pinnames is None:
    pin_names = {k:f'pin{k}' for k in list(range(1,10)) + list(range(11,20))}
else:
    userpinnames = args.pinnames.split(',')
    if len(userpinnames) != 18:
        raise RuntimeError('Wrong number of pin names (no names for GND and VCC!)')
    pin_names = dict(zip(list(range(1,10)) + list(range(11,20)), userpinnames))

pin_name_maxlen = max((len(s) for s in pin_names.values()))

fpath = pathlib.Path(args.filename)

f = fpath.open("rb")
dumpdata = f.read()
f.close()

f_truthtable = (fpath.parent / (fpath.stem + '_pete_truthtable.txt')).open("wt")
f_equations = (fpath.parent / (fpath.stem + '_pete_equations.pld')).open("wt")

f_equations.write(f"""\
Name {fpath.stem};
Device G16V8MA;
Partno ;
Revision ;
Date ;
Designer ;
Company ;
Assembly ;
Location ;
""")

for number, name in pin_names.items():
    f_equations.write(f'PIN {number}={name};\n')

andstr = args.andstr
orstr = args.orstr
notstr = args.notstr

if len(dumpdata) != 262144:
    raise RuntimeError("File with 262144 bytes expected")

# epromaddrbitpos is 0 for A0, 1 for A1, etc.
# returned PAL pinnum is in range [1,19]
def epromaddrbitpos_to_palpinnum(epromaddrbitpos):
    if epromaddrbitpos <= 8:
        # A0 is connected to PAL pin 1
        # A1 is connected to PAL pin 2
        # ...
        # A8 is connected to PAL pin 9
        return epromaddrbitpos + 1
    else:
        # As PAL pin 10 is GND:
        # A9 is connected to PAL pin 11
        # A10 is connected to PAL pin 12
        # ...
        return epromaddrbitpos + 2

# PAL pinnum is in range [1,19]
# returned EPROM addrbitpos is in range [0,17]
def palpinnum_to_epromaddrbitpos(palpinnum):
    if palpinnum <= 9:
        # A0 is connected to PAL pin 1
        # A1 is connected to PAL pin 2
        # ...
        # A8 is connected to PAL pin 9
        return palpinnum - 1
    else:
        # As PAL pin 10 is GND:
        # A9 is connected to PAL pin 11
        # A10 is connected to PAL pin 12
        # ...
        return palpinnum - 2

# PAL pinnum is in range [11,19]
# returned EPROM databitpos is in range [0,7]
def palpinnum_to_epromdatabitpos(palpinnum):
    # D0 is connected to PAL pin 12
    # D1 is connected to PAL pin 13
    # D2 is connected to PAL pin 14
    # D3 is connected to PAL pin 15
    # D4 is connected to PAL pin 16
    # D5 is connected to PAL pin 17
    # D6 is connected to PAL pin 18
    # D7 is connected to PAL pin 19
    return palpinnum - 12

def epromdatabitpos_to_palpinnum(epromdatabitpos):
    # D0 is connected to PAL pin 12
    # D1 is connected to PAL pin 13
    # D2 is connected to PAL pin 14
    # D3 is connected to PAL pin 15
    # D4 is connected to PAL pin 16
    # D5 is connected to PAL pin 17
    # D6 is connected to PAL pin 18
    # D7 is connected to PAL pin 19
    return epromdatabitpos + 12

# Iterates over all binary combinations for the specified bitmask
# E.g., iterate_mask(0b1010) yields:
# 0b0000
# 0b0010
# 0b1000
# 0b1010
def iterate_mask(mask):
    if mask < 1:
        return

    bits = []

    bit = 1   
    while bit <= mask:
        if (mask & bit) != 0:
            bits.append(bit) 
        bit <<= 1

    for n in range(2 ** len(bits)):
        r = 0

        srcmask = 1
        for bit in bits:
            if (n & srcmask) != 0:
                r |= bit
            srcmask <<= 1

        yield r

def gen_bitmask(numbits):
    return (1 << numbits) - 1

def pretty_print_truthtable(f, resultstr, indent, conditionslist):
    isfirstline = True

    for list_i, conditions in enumerate(conditionslist):
        if isfirstline:
            line = f'{resultstr.ljust(indent)} = '
            isfirstline = False
        else:
            line = ' ' * indent + f' {orstr} '

        for cond_i, cond in enumerate(conditions):
            if cond_i != 0:
                line += f' {andstr} '

            if cond_i < len(conditions) - 1:
                line += cond.ljust(pin_name_maxlen + 1)
            else:
                line += cond

        if list_i < len(conditionslist) - 1:
            f.write(line + ' \n')
        else:
            f.write(line + ';\n')

# Generator which yields the bit numbers set
# Example: for bitcount=5 and bits=0b01011, yielded values will be 0, 1, 3
def get_set_bits(bitcount, bits):
    bitnum = 0
    bit = 1
    while bitnum < bitcount:
        if (bits & bit) != 0:
            yield bitnum
        bitnum += 1
        bit <<= 1

def pretty_print_sop(f, resultstr, pinnames, results):
    if results is True:
        f.write(resultstr + " = b'1'\n")
    elif results is False:
        f.write(resultstr + " = b'0'\n")
    else:
        result = results[0]

        isfirstproduct = True

        # Sorting is mainly done here to have a reproducible output order,
        # the output would also be correct without sorting
        result = sorted(result, key=lambda r: tuple(get_set_bits(len(pinnames), r[1])))

        for i, p in enumerate(result):
            bits = p[0]
            mask = p[1]

            symbols = []

            bit = 1
            for bitnum, pinname in enumerate(pinnames):
                if (mask & bit) != 0:
                    if (bits & bit) != 0:
                        symbols.append(pinname)
                    else:
                        symbols.append('!' + pinname)
                bit <<= 1

            line = ' & '.join(symbols)

            if i == len(result) - 1:
                eol = ";"
            else:
                eol = ""

            if isfirstproduct:
                f.write(resultstr + ' = ' + line + eol + '\n')
                isfirstproduct = False
            else:
                f.write(f'  {orstr} ' + line + eol + '\n')

# Key: output pin bit position
# Value: input pin bits this output pin depends on
depends_map = [0] * 8
oe_depends_map = [0] * 8

# Key: output pin bit position
# Value: 1 if low level output has been seen on this pin at least once
seen_low_output = [0] * 8

# Key: output pin bit position
# Value: 1 if high level output has been seen on this pin at least once
seen_high_output = [0] * 8

# Iterate over a 17 bit address range...
for i in range(2 ** 17):
    # ...and insert the 18th bit in each position sequentially
    for bitpos in range(18):
        bit = 1 << bitpos
        mask_left = gen_bitmask(17 - bitpos) << bitpos
        mask_right = gen_bitmask(bitpos)
        addr = ((i & mask_left) << 1) | (i & mask_right)
                
        data0 = dumpdata[addr]
        data1 = dumpdata[addr | bit]
                
        for outputpinbitpos in range(0, 8):
            outputpinnum = epromdatabitpos_to_palpinnum(outputpinbitpos)
            outputpinbit = 1 << outputpinbitpos
                
            inputpinnum = epromaddrbitpos_to_palpinnum(bitpos)
                
            #
            # For high-z probing, pins A10..A17 are connected (via resistors)
            # to pins D0..D7; as we loop over all inputs (in variable "bitpos")
            # and all outputs (in variable "outputpinbitpos"), we will
            # sometimes hit the situation where "input pin == output pin". In
            # this condition, we skip both the checks:
            # - does this output level depend on this input?
            # - does this output high-z state depend on this input?
            # Reason: A PAL pin can never depend on itself, i.e. its input
            # level can never (via internal logic) control its own output
            # level or its own high-z state.
            # (The high-z probing itself is done separately - see below.)
            #
            if inputpinnum != outputpinnum:
                
                # For the current PAL output pin (D0..D7)...
                #highzprobedatabitpos = outputpinbitpos
                highzprobedatabit = outputpinbit 
                # ...determine the high-z probe address bit (A10..A17)
                highzprobeaddrbitpos = palpinnum_to_epromaddrbitpos(outputpinnum)
                highzprobeaddrbit = 1 << highzprobeaddrbitpos
                
                # The high-z probe bit is used to check if an output pin is in high-z state:
                # If changing the high-z probe bit (on A10..A17) also changes the output
                # bit (on D0..D7) which it is connected to (via a resistor!), the PAL output
                # pin itself does not drive the output, i.e. it is in high-z state (as an
                # active PAL output pin would "override" the level set by the probe output).
                
                # When this bit is NOT set, will changing the high-z probe output change the output bit?
                data2 = dumpdata[addr & ~highzprobeaddrbit]
                data3 = dumpdata[addr | highzprobeaddrbit]
                highz_on_bitclear = (data2 & highzprobedatabit) != (data3 & highzprobedatabit)
        
                # When this bit is set, will changing the high-z probe output change the output bit?
                data2 = dumpdata[(addr | bit) & ~highzprobeaddrbit]
                data3 = dumpdata[(addr | bit) | highzprobeaddrbit]
                highz_on_bitset = (data2 & highzprobedatabit) != (data3 & highzprobedatabit)

                # In summary, does this input pin affect the high-z status of the output pin?
                if highz_on_bitclear != highz_on_bitset:
                    oe_depends_map[outputpinbitpos] |= bit
            
                # Does this input pin affect the output pin?
                #
                # Justification why we do NOT need to put an input pin into the depends_map
                # of an output pin if a high-Z output condition occurs for this input pin in
                # EITHER low OR high state: 
                # Given the following truth table
                # 1) ~Pin1 & ~Pin2 & ~Pin3 -> low
                # 2) ~Pin1 & ~Pin2 &  Pin3 -> low
                # 3) ~Pin1 &  Pin2 & ~Pin3 -> high
                # 4) ~Pin1 &  Pin2 &  Pin3 -> high-Z (=> "don't care")
                # 5)  Pin1 & ~Pin2 & ~Pin3 -> low
                # 6)  Pin1 & ~Pin2 &  Pin3 -> low
                # 7)  Pin1 &  Pin2 & ~Pin3 -> low
                # 8)  Pin1 &  Pin2 &  Pin3 -> high-Z (=> "don't care")
                # As high-Z means that the output equation result is irrelevant, we could
                # also write lines 3/4 as:
                # 3) ~Pin1 &  Pin2 & ~Pin3 -> high
                # 4) ~Pin1 &  Pin2 &  Pin3 -> high
                # which can then be simplified to:
                # 3) ~Pin1 &  Pin2 &  -> high
                # 4) (line removed)
                # In other words, Pin3 can be ignored for the situation "~Pin1 &  Pin2",
                # and all other situations are separately analyzed anyway.
                #
                if (data0 & outputpinbit) != (data1 & outputpinbit) and not highz_on_bitclear and not highz_on_bitset:
                    depends_map[outputpinbitpos] |= bit

                if not highz_on_bitclear:
                    if (data0 & outputpinbit) == 0:
                        seen_low_output[outputpinbitpos] = 1
                    else:
                        seen_high_output[outputpinbitpos] = 1

                if not highz_on_bitset:
                    if (data1 & outputpinbit) == 0:
                        seen_low_output[outputpinbitpos] = 1
                    else:
                        seen_high_output[outputpinbitpos] = 1
        
for outputpinbitpos in range(0, 8):
    outputpinnum = epromdatabitpos_to_palpinnum(outputpinbitpos)
    outputpinname = pin_names[outputpinnum]

    depends_on = depends_map[outputpinbitpos]
    oe_depends_on = oe_depends_map[outputpinbitpos]

    highzprobeaddrbitpos = palpinnum_to_epromaddrbitpos(outputpinnum)
    highzprobeaddrbit = 1 << highzprobeaddrbitpos

    # If a pin always has the same output level, depends_on will be 0
    if depends_on == 0:
        if seen_high_output[outputpinbitpos]:
            f_truthtable.write(f" {outputpinname:9s} = 1;\n")
            f_truthtable.write(f"{notstr}{outputpinname:9s} = 0;\n")

            f_equations.write(f"{notstr}{outputpinname} = 'b'0;\n")
        elif seen_low_output[outputpinbitpos]:
            f_truthtable.write(f" {outputpinname:9s} = 0;\n")
            f_truthtable.write(f"{notstr}{outputpinname:9s} = 1;\n")

            f_equations.write(f"{notstr}{outputpinname} = 'b'1;\n")
        # else PIN is always in high-z mode
    else:
        depends_on_pinnames = []
        depends_on_bits = []

        for inputpinbitpos in range(0, 18):
            inputpinbit = 1 << inputpinbitpos

            inputpinnum = epromaddrbitpos_to_palpinnum(inputpinbitpos)
            inputpinname = pin_names[inputpinnum]

            if (depends_on & inputpinbit) != 0:
                if inputpinbit != highzprobeaddrbit:
                    depends_on_pinnames.append(inputpinname)
                    depends_on_bits.append(inputpinbit)

        outputpinbit = 1 << outputpinbitpos

        dontcareconditionslist = []
        negconditionslist = []
        posconditionslist = []
        dontcareterms = []
        negminterms = []
        posminterms = []

        numpins = len(depends_on_bits)

        # Iterate over all 0/1 combinations on the input pins which this output pin depends on
        for epromaddr in iterate_mask(depends_on):
            conditions = []
            minterm = 0

            for pinidx in range(numpins):
                if (epromaddr & depends_on_bits[pinidx]) == 0:
                    conditions.append(f"{notstr}{depends_on_pinnames[pinidx]}")
                else:
                    conditions.append(f" {depends_on_pinnames[pinidx]}")
                    minterm |= (1 << pinidx)

            data = None

            # The overall input combination in epromaddr (all bits which are not set in depends_on
            # default to 0!) might result in a high-z condition for the currently computed output
            # pin - so we need to find an epromaddr which does NOT result in high-z
            otherinputbitsmask = ((2 ** 18) - 1) ^ depends_on
            for otherepromaddrbits in iterate_mask(otherinputbitsmask):
                epromaddr2 = epromaddr | otherepromaddrbits

                # For the current PAL output pin (D0..D7)
                # determine the high-z probe address bit (A10..A17)
                highzprobeaddrbitpos = palpinnum_to_epromaddrbitpos(outputpinnum)
                highzprobeaddrbit = 1 << highzprobeaddrbitpos

                if (dumpdata[epromaddr2] & outputpinbit) == (dumpdata[epromaddr2 ^ highzprobeaddrbit] & outputpinbit):
                    # Toggling the high-z probe pin does NOT change the data, so the output
                    # pin is actively driven by the PAL
                    data = dumpdata[epromaddr2]
                    break

            if data is None:
                raise RuntimeError(f'Could not find input combination which does not lead to high-z for pin {outputpinname}')

            # Pins 12-19 on a PAL16L8 can act as output and input at the same time; when a certain
            # combination of input levels is applied, one or more of pins 12-19 might be driven by
            # the PAL itself, overriding an external input on such pins; testing for such a "PAL
            # internal override" is possible by comparing A10..A17 to D0..D7 of the EPROM dump;
            # given the currently checked input pin configuration ("epromaddr & depends_on"), we
            # need to combine this configuration with ALL input pin configuration of the other
            # pins; if A10..A17 does NOT equal to D0..D7 for ALL this combinations, then the
            # input combination is irrelevant, meaning "don't care" in boolean algebra
            is_input_relevant = False
            otherinputbitsmask = ((2 ** 18) - 1) ^ depends_on
            for otherepromaddrbits in iterate_mask(otherinputbitsmask):
                epromaddr2 = epromaddr | otherepromaddrbits

                # Compare A17..A10 to D7..D0
                if ((epromaddr2 & 0x3fc00) >> 10) == dumpdata[epromaddr2]:
                    is_input_relevant = True
                    break
            
            if not is_input_relevant:
                dontcareconditionslist.append(conditions)
                dontcareterms.append(minterm)
            elif (data & outputpinbit) == 0:
                negconditionslist.append(conditions)
                negminterms.append(minterm)
            else:
                posconditionslist.append(conditions)
                posminterms.append(minterm)

        pretty_print_truthtable(f_truthtable, f' {outputpinname}', pin_name_maxlen + 1, posconditionslist)
        pretty_print_truthtable(f_truthtable, f'{notstr}{outputpinname}', pin_name_maxlen + 1, negconditionslist)
        if len(dontcareconditionslist) != 0:
            pretty_print_truthtable(f_truthtable, f'{outputpinname}_DC', pin_name_maxlen + 3, dontcareconditionslist)

        negresults = boolexprsimplifier.simplify_minterms(len(depends_on_pinnames), negminterms, dontcareterms, debug=False)
        pretty_print_sop(f_equations, f'{notstr}{outputpinname}', depends_on_pinnames, negresults)
        #posresults = boolexprsimplifier.simplify_minterms(len(depends_on_pinnames), posminterms, dontcareterms, debug=False)
        #pretty_print_sop(f_equations, f'{outputpinname}', depends_on_pinnames, posresults)

    if oe_depends_on == 0:
        if seen_high_output[outputpinbitpos] or seen_low_output[outputpinbitpos]:
            f_truthtable.write(f" {outputpinname+'.oe':12s} = 1;\n")
            f_truthtable.write(f"{notstr}{outputpinname+'.oe':12s} = 0;\n")

            f_equations.write(f"{outputpinname+'.oe'} = 'b'1;\n")
        else:
            f_truthtable.write(f" {outputpinname+'.oe':12s} = 0;\n")
            f_truthtable.write(f"{notstr}{outputpinname+'.oe':12s} = 1;\n")

            f_equations.write(f"{outputpinname+'.oe'} = 'b'0;\n")
    else:
        oe_depends_on_pinnames = []
        oe_depends_on_bits = []

        for inputpinbitpos in range(0, 18):
            inputpinbit = 1 << inputpinbitpos

            inputpinnum = epromaddrbitpos_to_palpinnum(inputpinbitpos)
            inputpinname = pin_names[inputpinnum]

            if (oe_depends_on & inputpinbit) != 0:
                oe_depends_on_pinnames.append(inputpinname)
                oe_depends_on_bits.append(inputpinbit)

        outputpinbit = 1 << outputpinbitpos

        negconditionslist = []
        posconditionslist = []
        negminterms = []
        posminterms = []

        numpins = len(oe_depends_on_bits)

        # Iterate over all 0/1 combinations on the input pins which this output pin OE depends on
        for epromaddr in iterate_mask(oe_depends_on):
            conditions = []
            minterm = 0

            for pinidx in range(numpins):
                if (epromaddr & oe_depends_on_bits[pinidx]) == 0:
                    conditions.append(f"{notstr}{oe_depends_on_pinnames[pinidx]}")
                else:
                    conditions.append(f" {oe_depends_on_pinnames[pinidx]}")
                    minterm |= (1 << pinidx)

            highzprobeaddrbitpos = palpinnum_to_epromaddrbitpos(outputpinnum)
            highzprobeaddrbit = 1 << highzprobeaddrbitpos

            if (dumpdata[epromaddr] & outputpinbit) != (dumpdata[epromaddr | highzprobeaddrbit] & outputpinbit):
                negconditionslist.append(conditions)
                negminterms.append(minterm)
            else:
                posconditionslist.append(conditions)
                posminterms.append(minterm)

        pretty_print_truthtable(f_truthtable, f' {outputpinname+".oe"}', pin_name_maxlen + 4, posconditionslist)
        pretty_print_truthtable(f_truthtable, f'{notstr}{outputpinname+".oe"}', pin_name_maxlen + 4, negconditionslist)

        #negresults = boolexprsimplifier.simplify_minterms(len(oe_depends_on_pinnames), negminterms, [], debug=False)
        #pretty_print_sop(f_equations, f'{notstr}{outputpinname}.oe', oe_depends_on_pinnames, negresults)
        posresults = boolexprsimplifier.simplify_minterms(len(oe_depends_on_pinnames), posminterms, [], debug=False)
        pretty_print_sop(f_equations, f'{outputpinname}.oe', oe_depends_on_pinnames, posresults)

f_truthtable.close()
f_equations.close()
