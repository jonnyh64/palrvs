#
# Copyright 2025 Johann Hanne
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

# Version 1.0.0 (2025-04-23)

#
# Yet another implementation of the venerable Quine–McCluskey algorithm
#
# Used papers for the implementation of class QuineMcCluskeyAlgorithm:
# [1] The Problem of Simplifying Truth Functions
#     W. V. Quine
#     The American Mathematical Monthly, Vol. 59, No. 8 (Oct., 1952),
#     pp. 521-531
# [2] ALGEBRAIC MINIMIZATION AND THE DESIGN OF TWO-TERMINAL CONTACT NETWORKS
#     EDWARD JOSEPH McCLUSKEY, JR.
#     SUBMITTED IN PARTIAL FULFILLMENT OF THE REQUIREMENTS FOR THE DEGREE OF
#     DOCTOR OF SCIENCE at the MASSACHUSETTS INSTITUTE OF TECHNOLOGY
#     June, 1956
#
# Basic properties of this particular implementation:
# - The "mechanical routine" described under "Theorem 4" in [1] is used as
#   the core algorithm to to find the prime implicants
# - After finding the prime implicants, a table similar to what is described
#   under "Theorem 5" in [1] is constructed, but for selecting the
#   necessary prime implicants, "Petrick's method" is used, see below
# - Apart from the prime implicant table idea, "Theorems 5-8" in [1] are
#   unused
# - Only minterms are accepted as input ([1] calls this "developed
#   normal form", [2] calls this "standard sum"; in the BSTJ version of
#   his paper, McCluskey calls this "canonical expansion")
# - The program code does not use any symbols (like letters) for processing,
#   but relies on binary representation of minterms, as suggested in [2]
# - In particular, section "1.3 Prime Implicants" in [2] is followed
#   to find the prime implicants via binary representations of terms
# - The minterms are NOT ordered in groups of ascending number of "1" bits,
#   as suggested in [2] ("It is expedient to order these binary numbers so
#   that any numbers which contain no 1's come first, followed by any
#   numbers containing a single 1, etc."); reason: for following the
#   algorithm with pencil and paper, this ordering seems indeed "expedient",
#   but on a computer, the required sorting causes an overhead and it seems
#   at least unclear if this is computationally cheaper than simply comparing
#   all terms to each other
# - Similar to above, apart from the basic prime implicant table idea,
#   sections "1.4 Prime Implicant Tables" to "1.7 Cyclic Prime Implicant
#   Tables and Group Invariance" in [2] are unused
# - Support for the Section "1.8 Phi-Terms" is included, but the terms are
#   named "don't care terms", which seems the more common name in 2025
# - Only the prime implicants are computed according to above papers, for
#   further processing, "Petrick's method" is used, see below
#
# Supposedly used paper for the implementation of class PetricksMethod:
# [3] A Direct Determination of the Irredundant Forms of a Boolean Function
#     from the Set of Prime Implicants
#     S. R. Petrick
#     Air Force Cambridge Research Center. AFCRC Technical Report TR-56-110.
#
# The author was unable to find the original paper [3] on the Internet
# to check if the implemented algorithm matches it and instead relied on
# what it described at https://en.wikipedia.org/wiki/Petrick%27s_method
#

#
# Measure of simplicity:
# - [1] says: "Limiting ourselves to normal formulas, we still have some choice
#   as to our measure of simplicity. We might simply count all occurrences of
#   literals and alternation signs, or we might put a premium on fewness of
#   clauses and so resort to a count of occurrences of literals only when
#   comparing formulas which are alike in number of clauses. What I shall have
#   to say in this paper will not require any decision, however, between these
#   or other reasonable standards of simplicity."
# - [2] says: "The sum functions which have the fewest terms of all equivalent
#   sum functions will be called minimum sums unless these functions having
#   fewest terms do not all involve the same number of literals. In such cases,
#   only those functions which involve the fewest literals will be called
#   minimum sums."
# This implementation follows [2] regarding what is regarded as "minimum" and
# also refers to this as "simplest".
#

#
# Handling of edge cases this particular implementation:
# - If a boolean expression is always true, the Python boolean value "True"
#   is returned as result ([1] calls such formulas "valid")
# - If a boolean expression is always false, the Python boolean value "False"
#   is returned as result ([1] calls such formulas "inconsistent")
#

#
# Implementation of "dashes" as used in [2]:
# - For each implicant, a "mask" is stored; for each variable in the implicant,
#   this mask contains - in the bit position of the variable - either a 1 bit
#   bit indicating that this variable is relevant or a 0 bit indicating that
#   this variable has been replaced with a dash in the process of combining
#   terms
# - This mask is also kept when the simplest results are returned
# - Example: When a product "A*B*C" is expressed as bit pattern 0b111, the bit
#   pattern 0b1x1 with mask 0b101 would refer to the product "A*C", as "B"
#   has been eliminated by the algorithm
#

from collections import defaultdict, OrderedDict
import dataclasses

def get_term_string(length, term, mask):
    s = ''
    bit = 1
    for n in range(length):
        if mask & bit != 0:
            if term & bit != 0:
                b = '1'
            else:
                b = '0'
        else:
            b = '-'

        s = b + s

        bit <<= 1

    return s

class ImplicantTable:
    class Attrs:
        def __init__(self, covered_minterms):
            self._covered_minterms = covered_minterms
            self._was_combined = False

        covered_minterms = property(lambda self: self._covered_minterms)

        was_combined = property(lambda self: self._was_combined)

        def mark_as_combined(self):
            self._was_combined = True

    def __init__(self):
        # Indexes are the minterms, values are ImplicantTable.Attrs objects
        self._true_implicants = {}
        self._dontcare_implicants = {}

    def set_implicants(self, true_implicants, dontcare_implicants):
        self._true_implicants = {impl: ImplicantTable.Attrs({i}) for (i, impl) in enumerate(true_implicants)}
        self._dontcare_implicants = {impl: ImplicantTable.Attrs({-1}) for impl in dontcare_implicants}

    def add_true_implicant(self, minterm, covered_minterms):
        self._true_implicants[minterm] = ImplicantTable.Attrs(covered_minterms)

    def add_dontcare_implicant(self, minterm):
        self._dontcare_implicants[minterm] = ImplicantTable.Attrs((-1,))

def dump_prime_implicants(prime_implicants, length, prepend_index=False):
    for i, (impl, mask, covered_minterms) in enumerate(prime_implicants):
        s = get_term_string(length, impl, mask)
        prepend = f'p{i}: ' if prepend_index else ''
        print(f'{prepend}{s} ({','.join(str(i) for i in covered_minterms)})')

class QuineMcCluskeyAlgorithm:
    def __init__(self, numvars, minterms, dontcareterms, *, debug=False):
        self._numvars = numvars
        self._minterms = tuple(minterms)
        self._dontcareterms = tuple(dontcareterms)

        self._debug = debug

        self._pending_implicanttables = defaultdict(ImplicantTable)
        self._prime_implicants = None

        if debug:
            self.debug_print('--- QuineMcCluskeyAlgorithm input terms ---')
            self.debug_print('-- minterms:')
            for i, n in enumerate(self._minterms):
                self.debug_print(f'{n:0{numvars}b} ({i})')
            if len(self._dontcareterms) > 0:
                self.debug_print('-- dontcareterms:')
                for i, n in enumerate(self._dontcareterms):
                    self.debug_print(f'{n:0{numvars}b} ({i})')

    def debug_print(self, *args):
        if self._debug:
            print(*args)

    def _compute_prime_implicants(self):

        self.debug_print('--- computing prime implicants ---')

        # Some debug strings are a little expensive to compute, but the strings would be
        # built before debug_print would drop it; so add an up-front check in some cases
        _debug = self._debug

        self._prime_implicants = []

        mask = (1 << self._numvars) - 1
        self._pending_implicanttables[mask].set_implicants(self._minterms, self._dontcareterms)

        while len(self._pending_implicanttables) > 0:
            mask = next(iter(self._pending_implicanttables))
            impltbl = self._pending_implicanttables.pop(mask)

            self.debug_print(f"-- checking combinations for mask {mask:0{self._numvars}b}")

            # Using an OrderedDict() instead of a regular dict is not necessary for the
            # algorithm to work, but the traceability for debugging is improved when
            # traversing the items in FIFO order with OrderedDict.popitem(last=False)
            impls = OrderedDict(impltbl._true_implicants)

            while len(impls) > 0:

                impl, attrs = impls.popitem(last=False)

                if _debug:
                    termstr = get_term_string(self._numvars, impl, mask)
                    self.debug_print(f'min: {termstr} ({','.join(str(i) for i in attrs.covered_minterms)})')

                bit = 1
                for _ in range(self._numvars):

                    if mask & bit != 0:
                        combinable_impl = impl ^ bit
                        if combinable_impl in impltbl._true_implicants:
                            attrs.mark_as_combined()
                            impltbl._true_implicants[combinable_impl].mark_as_combined()

                            combined_mask = mask ^ bit
                            self._pending_implicanttables[combined_mask].add_true_implicant(impl & combined_mask, attrs.covered_minterms | impltbl._true_implicants[combinable_impl].covered_minterms)
                        elif combinable_impl in impltbl._dontcare_implicants:
                            attrs.mark_as_combined()

                            combined_mask = mask ^ bit
                            self._pending_implicanttables[combined_mask].add_true_implicant(impl & combined_mask, attrs.covered_minterms)


                    bit <<= 1

                if not attrs.was_combined:
                    if _debug:
                        self.debug_print(f'found new prime implicant: {termstr}')

                    self._prime_implicants.append((impl, mask, attrs.covered_minterms))

            # Using an OrderedDict() instead of a regular dict is not necessary for the
            # algorithm to work, but the traceability for debugging is improved when
            # traversing the items in FIFO order with OrderedDict.popitem(last=False)
            impls = OrderedDict(impltbl._dontcare_implicants)

            while len(impls) > 0:

                impl, _ = impls.popitem(last=False)

                if _debug:
                    termstr = get_term_string(self._numvars, impl, mask)
                    self.debug_print(f'dontcare: {termstr}')

                bit = 1
                for _ in range(self._numvars):
                    if mask & bit != 0:
                        combinable_impl = impl ^ bit

                        if impl in impltbl._dontcare_implicants and combinable_impl in impltbl._dontcare_implicants:
                            combined_mask = mask ^ bit
                            self._pending_implicanttables[combined_mask].add_dontcare_implicant(impl & combined_mask)

                    bit <<= 1

        if self._debug:
            self.debug_print(f'--- computed prime implicants ---')
            dump_prime_implicants(self._prime_implicants, self._numvars)

    @property
    def prime_implicants(self):
        if self._prime_implicants is None:
            self._compute_prime_implicants()

        return self._prime_implicants

class PetricksMethod:
    def __init__(self, prime_implicants, *, debug=False):
        self._prime_implicants = prime_implicants

        self._debug = debug

        self._product_of_sums = []
        self._simplest_results = None

        if debug:
            self.debug_print('--- PetricksMethod input prime implicants ---')
            numvars = max(impl[1] for impl in prime_implicants).bit_length()
            dump_prime_implicants(prime_implicants, numvars, prepend_index=True)

    def debug_print(self, *args):
        if self._debug:
            print(*args)

    @staticmethod
    def get_sum_str(summands):
        summandstrs = []
        for summand in summands:
            summandstrs.append('*'.join(f'p{i}' for i in summand))
        return '+'.join(summandstrs)

    def _compute_product_of_sums(self):
        self.debug_print(f"-- computing product of sums for {len(self._prime_implicants)} prime implicants")
        self._product_of_sums = []

        all_mintermidxs = set().union(*(p[2] for p in self._prime_implicants))

        MintermInfo = dataclasses.make_dataclass('MintermInfo', [ 'covered_by', 'absorbed' ])
        minterminfos = {}

        # Iterate over all minterms
        for mintermidx in all_mintermidxs:
            # mintermidxs: set of prime implicant indexes covering this minterm
            mintermidxs = set()
            for idx, p in enumerate(self._prime_implicants):
                # Does this prime implicant cover the minterm?
                if mintermidx in p[2]:
                    mintermidxs.add(idx)

            # In the next step, the sums will be multiplied out; before doing that for
            # a possibly very large number of sums, we already eliminate sums which are
            # redundant according to the boolean algebra absorption law [(A+B)*A = A] anyway
            absorbed = False
            for mintermidx2, info in minterminfos.items():
                if info.covered_by.issubset(mintermidxs):
                    absorbed = True
                elif mintermidxs.issubset(info.covered_by):
                    info.absorbed = True

            minterminfos[mintermidx] = MintermInfo(mintermidxs, absorbed)

        for idx, info in minterminfos.items():
            covered_by = [{idx} for idx in info.covered_by]
            absorbedstr = ' (absorbed)' if info.absorbed else ''
            self.debug_print(f"sum for covering minterm {idx}: {self.get_sum_str(covered_by)}{absorbedstr}")
            if not info.absorbed:
                self._product_of_sums.append(covered_by)

        self.debug_print(f'overall product of sums: {"*".join(("(" + self.get_sum_str(idxs) + ")" for idxs in self._product_of_sums))}')

    @staticmethod
    def _simplify(sumterm):
        simplified = []

        for i, term in enumerate(sumterm):
            for i2, term2 in enumerate(simplified):
                if term.issubset(term2):
                    # Drop term2 (apply the absorption law: X + XY = X) by replacing it with term
                    simplified[i2] = term
                    break
                elif term2.issubset(term):
                    # Drop term (apply the absorption law)
                    break
            else:
                simplified.append(term)

        return simplified

    def _convert_pos_to_sop(self):
        self.debug_print('-- converting product of sums to sum of products')

        # Some debug strings are a little expensive to compute, but the strings would be
        # built before debug_print would drop it; so add an up-front check in some cases
        _debug = self._debug

        if len(self._product_of_sums) > 0:
            sumterm = self._product_of_sums[0]

            for i in range(1, len(self._product_of_sums)):

                sum2 = self._product_of_sums[i]
                multsum = []

                if _debug:
                    self.debug_print(f"computing (step {i}/{len(self._product_of_sums) - 1}): ({self.get_sum_str(sumterm)})*({self.get_sum_str(sum2)})")

                # Multiply sums by applying distributive law
                for summand1 in sumterm:
                    for summand2 in sum2:
                        # As we store each summand as set, multiplication can be done by
                        # simply joining two sets; this also automatically simplifies XX = X
                        multsum.append(summand1 | summand2)

                if _debug:
                    self.debug_print(f"result: {self.get_sum_str(multsum)}")

                sumterm = self._simplify(multsum)

                if _debug:
                    self.debug_print(f"simplified result: {self.get_sum_str(sumterm)}")

            if _debug:
                self.debug_print(f"sum of products: {self.get_sum_str(sumterm)}")

            self._sum_of_products = sumterm
        else:
            self.debug_print(f"converted 0 sums to 0 products")
            self._sum_of_products = []

    def _compute_simplest_results(self):
        self.debug_print('-- computing simplest results')

        if len(self._sum_of_products) > 0:

            if len(self._sum_of_products) == 1 and len(self._sum_of_products[0]) == 1:
                # next(iter(s)) gets the first item from the set s
                # (in this case we have checked there is only one item)
                i = next(iter(self._sum_of_products[0]))
                if self._prime_implicants[i][1] == 0:
                    # If mask == 0, something like "A + A'" was the original input,
                    # which is always true...
                    self._simplest_results = True
                    self.debug_print("boolean expression is always true")
                    return

            results = []

            minlen = min(len(p) for p in self._sum_of_products)
            self.debug_print(f"mininum number of products: {minlen}")

            for p in self._sum_of_products:
                if len(p) == minlen:
                    result = []
                    for i in p:
                        result.append((self._prime_implicants[i][0], self._prime_implicants[i][1]))
                    results.append(result)

            if len(results) > 1:
                self.debug_print(f"{len(results)} results found with {minlen} products - finding results with minimum number of literals")

                # When there are multiple results with the same number of products,
                # get the results with the lowest number of literals
                minlen = min(sum(product[1].bit_count() for product in result) for result in results)
                self.debug_print(f"minimum number of literals: {minlen}")

                results2 = []
                for result in results:
                    if sum(product[1].bit_count() for product in result) == minlen:
                        results2.append(result)

                self.debug_print(f"{len(results2)} result(s) found with {minlen} literals")

                self._simplest_results = results2
            else:
                self.debug_print(f"1 result found with {minlen} products")

                self._simplest_results = results

            if self._debug:
                numvars = max(impl[1] for impl in self._prime_implicants).bit_length()
                for i, r in enumerate(self._simplest_results):
                    self.debug_print(f"result {i + 1}/{len(self._simplest_results)}:", ' + '.join((f'{get_term_string(numvars, i[0], i[1])}' for i in r)))

        else:
            # no products => boolean expression is always false
            self.debug_print("boolean expression is always false (as it is empty)")
            self._simplest_results = False

    @property
    def simplest_results(self):
        if self._simplest_results is None:
            self._compute_product_of_sums()
            self._convert_pos_to_sop()
            self._compute_simplest_results()

        return self._simplest_results

def simplify_minterms(numvars, minterms, dontcareterms, *, debug=False):
    qmca = QuineMcCluskeyAlgorithm(numvars, minterms, dontcareterms, debug=debug)
    pm = PetricksMethod(qmca.prime_implicants, debug=debug)
    return pm.simplest_results
