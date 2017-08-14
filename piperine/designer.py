#!/usr/bin/env python
from __future__ import division, print_function

import sys
import pkg_resources
import numpy as np
import os
import os.path
import importlib

from . import energyfuncs_james
from . import DSDClasses

small_crn = pkg_resources.resource_filename('piperine', "data/small.crn")
data_dir = os.path.dirname(small_crn)

def call_compiler(basename,
                    args = (7, 15, 2),
                    outputname=None,
                    savename=None,
                    fixed_file=None,
                    synth=True,
                    includes=None):
    """ Generates a PIL file from a .sys. (peppercompiler wrapper)

    Args:
        basename: The default name of filetypes to be produced and accessed.
        args: A tuple of system arguments.
        outputname: the PIL file produced by the compiler. (<basename>.pil)
        savename: the save file produced by the compiler. def: (<basename>.save)
        fixed_file: filename specifying sequence constraints.
        synth: Boolean, whether or not to produce an output. Deprecated.
        includes: path to folder holding component files referenced by .sys. (location of this file)
    Returns:
        Nothing
    """
    from peppercompiler.compiler import compiler
    if outputname is None:
        outputname = '{}.pil'.format(basename)
    if savename is None:
        savename = '{}.save'.format(basename)
    if includes is None:
        includes = []
    includes.append(data_dir)
    compiler(basename, args, outputname, savename, fixed_file, synth, includes)

def call_design(basename,
                infilename=None,
                outfilename=None,
                cleanup=True,
                verbose=False,
                reuse=False,
                just_files=False,
                struct_orient=False,
                old_output=False,
                tempname=None,
                extra_pars="",
                findmfe=False,
                spuriousbinary="spuriousSSM"):
    """ Generates an MFE file from a .pil file. (peppercompiler wrapper)

    Args:
        basename: The default name of filetypes to be produced and accessed.
        infilename: PIL file read by the designer. (basename.pil)
        outfilename: MFE file read by the designer. (basename.mfe)
        cleanup: Boolean, Delete st wc eq files (True)
        verbose: Boolean, verbose designer output (True)
        reuse: Boolean, if available and appropriate, use wc st eq files (False)
        just_files: Boolean, only produce wc st eq files (False)
        struct_orient: Boolean, list structures in MFE file (False)
        old_output: Deprecated (False)
        tempname: Optional temporary name for wc st eq files (None)
        extra_pars: Options sent to spurious designer. ('')
        findmfe: Use DNAfold to do something mysterious. (True)
        spuriousbinary: Compiled C++ for negative design. (spuriousSSM)
    Returns:
        Nothing
    """
    from peppercompiler.design.spurious_design import design
    if not infilename:
        infilename = '{}.pil'.format(basename)
    if not outfilename:
        outfilename = '{}.mfe'.format(basename)
    design(basename, infilename, outfilename, cleanup, verbose, reuse,
              just_files, struct_orient, old_output, tempname, extra_pars,
              findmfe, spuriousbinary)
    if not os.path.isfile(outfilename):
        raise RuntimeError('Expected MFE not created, expect SSM failure')

def call_finish(basename,
                savename=None,
                designname=None,
                seqname=None,
                strandsname=None,
                run_kin=False,
                cleanup=True,
                trials=24,
                time=1e6,
                temp=25.0,
                conc=1,
                spurious=False,
                spurious_time=10.0):
    """ Generates a .seq file from an .mfe file. (peppercompiler wrapper)

    Args:
        basename: The default name of all files produced and accessed.
        savename: File storing process states. (basename.save)
        designname: MFE file, read for sequences (basename.mfe)
        seqname: Output file containing all sequences (basename.seq)
        strandsname: Output file containing all strand sequences (None)
        run_kin: Run spurious kinetic tests on sequences (False)
        cleanup: Delete temporary files (True)
        trials: Number of kinetics trials to run (24)
        time: Simulation seconds (1000000)
        temp: Degrees celsius for simulations (25)
        conc: Concentration of strands in simulations in uM (1)
        spurious: Run pairwise kinetics tests (false)
        spurious_time: Simulation time (s) for spurious kinetics (10.0)
    Returns:
        Nothing
    """
    from peppercompiler.finish import finish
    if not savename:
        savename = '{}.save'.format(basename)
    if not designname:
        designname = '{}.mfe'.format(basename)
    if not seqname:
        seqname = '{}.seq'.format(basename)

    finish(savename, designname, seqname, strandsname, run_kin,
                  cleanup, trials, time, temp, conc, spurious, spurious_time)

def read_crn(in_file):
    """ Interprets a CRN from a text file.

    Maintains a list of reactions and species. For each reaction, the rate
    constant, reactants, products, and stoichiometric coefficients are read.
    The interpreter relies on a lot of regex to extract tokens from the lines
    of texts.

    Tokens are as follows:
        * Alphanumeric are species
        * Numeric before alphanumeric are stoichiometric identifiers
        * Arrow (->) separates reactants from products
        * Parentheses enclose the rate constant, which python should be able
          to evaluate
    Args:
        in_file : String of the file name holding the CRN specification

    Returns:
        crn_info : A tuple containing lists called 'reactions' and 'species'.
                   'reactions' contains a list of dicionaries keyed by
                   'reactants', 'products', 'rate', 'stoich_r', and
                   'stoich_p'. 'species' list holds strings representing
                   signal species names.
    """
    import re
    fid = open(in_file, 'r')
    lines = list()
    for line in fid:
        lines.append(line[:-1])

    fid.close()

    # Read through the file and extract reaction specifications
    rxn_tup = list()
    spe_ind_dic = dict()
    species_list = list()
    update_ind = 0
    num_pattern = re.compile(r"^[0-9./]+|^[0-9.]+e-?[0-9.]+")
    spe_pattern = re.compile(r"\w+")
    for line in lines:
        # eat empty lines
        if line == '':
            continue

        full_line = line[:]
        # Remove whitespace
        line = re.sub(r'\s','',line)

        # Check for reaction rate
        rate_match = re.search(r'\(.*\)', line)
        if rate_match:
            rate_str = rate_match.group(0)[1:-1]
            rate = float(eval(rate_str))
            line = re.sub(r'\(' + rate_str + '\)', '', line)
        else:
            rate = 1

        # Split into reactants and products
        rxn_eq = re.split('->',line)
        try:
            assert len(rxn_eq)==2
        except AssertionError as e:
            print('Check reaction arrow use.')
            raise

        stoich = 1
        reactants = list()
        products = list()
        stoich_r = list()
        stoich_p = list()
        for subline, lhs_flag in zip(rxn_eq, (True, False)):
            tokens = re.split(r'[ +]+', subline)
            for token in tokens:
                # Attempt to scrape for coefficients
                coeff_string = num_pattern.search(token)
                if coeff_string:
                    coeff_string = num_pattern.search(token).group(0)
                    try:
                        stoich = eval(coeff_string)
                    except SyntaxError as e:
                        print('improper coefficient syntax!')
                        raise
                    token = token.replace(coeff_string, '')
                else:
                    stoich = 1

                # Remaining token string should be species identifier
                if spe_pattern.match(token):
                    if token not in spe_ind_dic:
                        spe_ind_dic[token] = update_ind
                        update_ind += 1
                        species_list.append(token)

                    spe = spe_ind_dic[token]

                    if lhs_flag:
                        reactants.append(token)
                        stoich_r.append(stoich)
                    else:
                        products.append(token)
                        stoich_p.append(stoich)

                    stoich = 1

        rxn_tup.append({"reactants":reactants,
                        "products":products,
                        "stoich_r":stoich_r,
                        "stoich_p":stoich_p,
                        "rate":rate})

    return (rxn_tup, species_list)

def write_toehold_file(toehold_file, strands, toeholds, n_th):
    """ Writes the fixed file for the given strands and toeholds

    Args:
        toehold_file: File where toehold constraints are written
        strands: List of SignalStrand objects
        toeholds: List of toehold two-big tuples
        n_th: Number of toeholds
    Returns:
        Nothing
    """
    line = 'sequence {} = {} # species {}\n'
    th_names = [th for strand in strands for th in strand.get_ths()]
    th_names = sorted(list(set(th_names)))
    th_data = [(th, ', '.join([strand.name for strand in strands if th in strand.get_ths()]))
                    for th in th_names]
    f = open(toehold_file, 'w')
    for data, seq in zip(th_data, toeholds):
        constraint = line.format(data[0], seq.upper(), data[1])
        f.write(constraint)

    f.close()

def toehold_wrapper(n_ths,
                    thold_l=7,
                    thold_e=7.7,
                    e_dev=1,
                    m_spurious=0.5,
                    e_module=energyfuncs_james):
    """ Wrapper generating toeholds, calls gen_th

    Args:
        n_ths: Number of toeholds
        thold_l: Nt in a toehold (7)
        thold_e: Target deltaG in kCal/Mol (7.7)
        e_dev: Allowable standard deviation in kCal/mole (1)
        m_spurious: Maximum spurious dG as fraction of thold_e (0.5)
        e_module: Thermodynamics used by stickydesign (energyfuncs_james)
    Returns:
        ths: Toeholds, listed as tupled-pairs
        th_score: average toehold dG and the range of dG's
    """
    from .gen_th import get_toeholds
    # Grab parameters from the dictionary or set defaults
    # Toehold length (basepairs)
    thold_l = int(thold_l)
    ths = get_toeholds(n_ths, thold_l, thold_e, e_dev, m_spurious, e_module)
    return ths

def write_sys_file(basename,
                   gates=None,
                   sys_file=None,
                   trans_module=DSDClasses):
    """ Write system file from gates list

    This function takes in filenames and a CRN specification and writes a system
    file, which outlines the overall DNA implementation.

    Args:
        basename: Default name for files accessed and written
        gates: List of gate objects
        sys_file: System file filename (basename + .sys)
        trans_module: module containing scheme variables and classes (DSDClasses)
    Returns:
        Nothing
    """

    # Write header immediately
    if sys_file is None:
        sys_file = basename + '.sys'

    # Clean basename if it was provided with directory prefix
    if os.path.sep in basename:
        basename = os.path.basename(basename)

    with open(sys_file, 'w') as f:
        f.write("declare system " + basename + trans_module.param_string + " -> \n")
        f.write("\n")
        # Comps is defined in Classes file
        for comp in trans_module.comps:
            f.write("import {0}\n".format(comp))
        f.write("\n")
        for rxn in gates:
            f.write(rxn.get_reaction_line())

def process_crn(basename=None,
                design_params=(7, 15, 2),
                trans_module=None,
                crn_file=None):
    """ Generate objects describing DNA implementation

    Gate and strand objects tell the scoring modules, write_sys_file, and
    write_toehold_files which names in the .PIL file refer to the DNA sequence
    domains these functions need to access.  This function, making use of
    other methods, reads in a text file describing an abstract CRN and determines
    the strands and gates necessary to implement the CRN.
    Args:
        basename: Default name for files accessed and written
        design_params: A tuple of parameters to the system file ( (7, 15, 2) )
        trans_module: module containing scheme variables and classes (DSDClasses)
        crn_file: name of the text file specifying the CRN (basename + .crn)
        system_file: name of the system file (basename + .sys)
    Returns:
        gates: A list of gate objects
        strands: A list of strand objects
    """
    if trans_module is None:
        from . import DSDClasses as trans_module

    if crn_file is None:
        crn_file = basename + ".crn"

    reactions, species = read_crn(crn_file)

    output = trans_module.process_rxns(reactions, species, design_params)
    (gates, strands) = output

    return (gates, strands)

def generate_scheme(basename,
                    design_params=(7, 15, 2),
                    trans_module=None,
                    crn_file=None,
                    system_file=None):
    """ Produce SYS file describing a CRN

    A scheme consists a .sys file and lists of gate and strand objects. Gate
    and strand objects tell the scoring modules, write_sys_file, and
    write_toehold_files which names in the .PIL file refer to the DNA sequence
    domains these functions need to access.  This function, making use of
    other methods, reads in a text file describing an abstract CRN, determines
    the strands and gates necessary to implement the CRN, and writes a .sys
    for a DNA approximation of that reaction network.

    Args:
        basename: Default name for files accessed and written
        design_params: A tuple of parameters to the system file ( (7, 15, 2) )
        trans_module: module containing scheme variables and classes (DSDClasses)
        crn_file: name of the text file specifying the CRN (basename + .crn)
        system_file: name of the system file (basename + .sys)
    Returns:
        gates: A list of gate objects
        strands: A list of strand objects
    """
    if trans_module is None:
        from . import DSDClasses as trans_module

    if system_file is None:
        system_file = basename + ".sys"

    (gates, strands) = process_crn(basename, design_params, trans_module, crn_file)

    write_sys_file(basename, gates, system_file, trans_module)
    return (gates, strands)

def generate_seqs(basename,
                  gates,
                  strands,
                  design_params=(7, 15, 2),
                  n_th=2,
                  thold_l=7,
                  thold_e=7.7,
                  e_dev=1,
                  m_spurious=0.5,
                  e_module=energyfuncs_james,
                  outname=None,
                  extra_pars="",
                  system_file=None,
                  pil_file=None,
                  mfe_file=None,
                  seq_file=None,
                  fixed_file=None,
                  save_file=None,
                  strands_file=None,
                  tempname=None):
    """ Produce sequences for a scheme

    This function accepts a base file name, a list of gate objects, a list of
    strand objects, and toehold parameters and calls StickyDesign, the
    peppercompiler, and SpuriousSSM to generate a DNA sequence.

    Args:
        basename: Default name for files accessed and written
        gates: A list of Gate objects
        strands: A list of SignalStrand objects
        design_params: A tuple of parameters to the system file ( (7, 15, 2) )
        n_th: How many toeholds to generate per signal strand
        thold_l: Nt in a toehold (7)
        thold_e: Target deltaG in kCal/Mol (7.7)
        e_dev: Allowable standard deviation in kCal/mole (1)
        m_spurious: Maximum spurious dG as fraction of thold_e (0.5)
        e_module: Thermodynamics used by stickydesign (energyfuncs_james)
        outname: Optional name for files produced as a result of this call (basename + .mfe)
        extra_pars: Options sent to spurious designer. ("")
        system_file: Filename of the peppercompiler system file (basename + .sys)
        pil_file: Filename of the peppercompiler (basename + .pil)
        mfe_file: Filename of the peppercompiler MFE file (basename + .mfe)
        seq_file: Filename of the peppercompiler sequence file (basename + .seq)
        fixed_file: Filename of the peppercompiler fixed file (basename + .fixed)
        save_file: Filename of the peppercompiler save file (basename + .save)
        strands_file: Filename of the peppercompiler strands file (basename + _strands.txt)
    Returns:
        toeholds:
    """
    if type(e_module) is str:
        e_module = importlib.import_module('.' + e_module, 'piperine')

    # Prepare filenames
    if system_file is None:
        system_file = basename + ".sys"
    if pil_file is None:
        pil_file = basename + ".pil"
    if save_file is None:
        save_file = basename + ".save"
    if mfe_file is None:
        if outname is not None:
            mfe_file = outname + '.mfe'
        else:
            mfe_file = basename + ".mfe"
    if seq_file is None:
        if outname:
            seq_file = outname + ".seq"
        else:
            seq_file = basename + ".seq"
    if strands_file is None:
        if outname:
            strands_file = outname + "_strands.txt"
        else:
            strands_file = basename + "_strands.txt"
    if fixed_file is None:
        fixed_file = basename + ".fixed"
    if tempname is None:
        tempname = basename

    # Make toeholds
    tdomains = []
    for strand in strands:
        tdomains += strand.get_ths()
    tdomains = list(set(tdomains))
    n_toeholds = len(tdomains)

    toeholds = toehold_wrapper(n_toeholds,
                               thold_l=thold_l,
                               thold_e=thold_e,
                               e_dev=e_dev,
                               m_spurious=m_spurious,
                               e_module=e_module)
    import numpy as np
    toeholds = np.random.choice(toeholds, len(toeholds), replace=False)

    # Write the fixed file for the toehold sequences and compile the sys file to PIL
    write_toehold_file(fixed_file, strands, toeholds, n_th)
    try:
        call_compiler(basename, args=design_params, fixed_file=fixed_file,
                      outputname=pil_file, savename=save_file)
    except KeyError as e:
        raise(e)

    # Generate sequences
    call_design(basename, pil_file, mfe_file, verbose=False,
                extra_pars=extra_pars, cleanup=False, tempname=tempname)
    # "Finish" the sequence generation
    call_finish(basename, savename=save_file, designname=mfe_file, \
                seqname=seq_file, strandsname=strands_file, run_kin=False)
    return toeholds

def selection(scores):

    if sys.version_info >= (3,1):
        print_fn = lambda x : print(x, end='')
    else:
        print_fn = lambda x : print(x)

    columns = list(zip(*scores))
    ranks = []
    fractions = []
    percents = []
    for col in columns:
        # if 'Index' in col[0] or 'Defect' in col[0] or 'Toehold Avg' in col[0] or 'Range of toehold' in col[0]:
        if 'Index' in col[0] or 'Defect' in col[0] or 'WSI' == col[0]:
            continue
        if 'SSU' in col[0] or 'SSTU' in col[0]:    # for these scores, higher is better
            col = [-float(x) for x in col[1:]]
        else:
            col = [float(x) for x in col[1:]]
        array = np.array(col)
        array_uni = np.unique(array)
        array_ord = array_uni.argsort()
        rank_dict = dict(zip(array_uni, array_ord))
        temp_ranks = np.array([rank_dict[x] for x in array])
        temp = array.argsort()
        colranks = np.array([rank_dict[x] for x in array])
        # low rank is better
        ranks.append(colranks)
        fractions.append((array - array.min())/abs(array.min() + (array.min()==0) ))
        percents.append((array - array.min())/(array.max() - array.min()))
    temp=ranks
    ranks=list(zip(*temp))
    temp=fractions
    fractions=list(zip(*temp))
    temp=percents
    percents=list(zip(*temp))

    print_fn("\nRank array:")
    print_fn("\n                         ")
    for title in scores[0]:
        # if 'Index' in title or 'Defect' in title or 'Toehold Avg' in title or 'Range of toehold' in title:
        if 'Index' in title or 'Defect' in title or 'WSI' == title:
            continue
        print_fn("{:>6s}".format(title[0:6]))
    print_fn("\n")
    i=0
    for r in ranks:
        print_fn("design {:2d}: {:6d} = sum [".format(i,sum(r)))
        for v in r:
            print_fn("{:6d}".format(v))
        print_fn("]\n")
        i=i+1

    print_fn("\nFractional excess array:")
    print_fn("\n                         ")
    for title in scores[0]:
        # if 'Index' in title or 'Defect' in title or 'Toehold Avg' in title or 'Range of toehold' in title:
        if 'Index' in title or 'Defect' in title or 'WSI' == title:
            continue
        print_fn("{:>6s}".format(title[0:6]))
    print_fn("\n")
    i=0
    for f in fractions:
        print_fn("design {:2d}: {:6.2f} = sum [".format(i,sum(f)))
        for v in f:
            print_fn("{:6.2f}".format(v))
        print_fn("]\n")
        i=i+1

    print_fn("\nPercent badness (best to worst) array:")
    print_fn("\n                         ")
    for title in scores[0]:
        # if 'Index' in title or 'Defect' in title or 'Toehold Avg' in title or 'Range of toehold' in title:
        if 'Index' in title or 'Defect' in title or 'WSI' == title:
            continue
        print_fn("{:>6s}".format(title[0:6]))
    print_fn("\n")
    i=0
    for p in percents:
        print_fn("design {:2d}: {:6.2f} = sum [".format(i,100*sum(p)))
        for v in p:
            print_fn("{:6.2f}".format(100*v))
        print_fn("]\n")
        i=i+1

    print_fn("\n")
    worst_rank = 0
    while 1:
        ok_seqs = [i for i in range(len(ranks)) if max(ranks[i])<=worst_rank]
        if len(ok_seqs)==0:
            worst_rank=worst_rank+1
            continue
        else:
            break

    # scores used:
    # TSI avg, TSI max, TO avg, TO max, BM, Largest Match, SSU Min, SSU Avg, SSTU Min, SSTU Avg, Max Bad Nt %,  Mean Bad Nt %, WSI-Intra, WSI-Inter, WSI-Intra-1, WSI-Inter-1, Verboten, Toehold error, Toehold range
    weights = [5,   20,     10,     30,  2,             3,      30,      10,       50,       20,           10,              5,         6,         4,           5,           3,        2,  8,            20]#, 20]

    print_fn("Indices of sequences with best worst rank of " + str(worst_rank) + ": " + str(ok_seqs)+"\n")
    print_fn("  Sum of all ranks, for these sequences:      " + str([sum(ranks[i]) for i in ok_seqs])+"\n")
    print_fn("  Sum of weighted ranks, for these sequences: " + str([sum(np.array(ranks[i])*weights/100.0) for i in ok_seqs])+"\n")
    print_fn("  Sum of fractional excess over best score:   " + str([sum(fractions[i]) for i in ok_seqs])+"\n")
    print_fn("  Sum of weighted fractional excess:          " + str([sum(np.array(fractions[i])*weights/100.0) for i in ok_seqs])+"\n")
    print_fn("  Sum of percent badness scores:              " + str([100*sum(percents[i]) for i in ok_seqs])+"\n")
    print_fn("  Sum of weighted percent badness scores:     " + str([sum(np.array(percents[i])*weights) for i in ok_seqs])+"\n")
    temp = [sum(r) for r in ranks]
    print_fn("Best sum-of-ranks:                   {:6.2f} by [{:d}]      and the worst: {:6.2f} by [{:d}]\n".format( min(temp), np.argmin(temp), max(temp), np.argmax(temp) ))
    winner = np.argmin(temp)
    temp = [sum(np.array(r)*weights/100.0) for r in ranks]
    print_fn("Best sum-of-weighted-ranks:          {:6.2f} by [{:d}]      and the worst: {:6.2f} by [{:d}]\n".format( min(temp), np.argmin(temp), max(temp), np.argmax(temp) ))
    temp = [sum(f) for f in fractions]
    print_fn("Best fractional excess sum:          {:6.2f} by [{:d}]      and the worst: {:6.2f} by [{:d}]\n".format( min(temp), np.argmin(temp), max(temp), np.argmax(temp) ))
    temp = [sum(np.array(f)*weights/100.0) for f in fractions]
    print_fn("Best weighted fractional excess sum: {:6.2f} by [{:d}]      and the worst: {:6.2f} by [{:d}]\n".format( min(temp), np.argmin(temp), max(temp), np.argmax(temp) ))
    temp = [100*sum(p) for p in percents]
    print_fn("Best percent badness sum:            {:6.2f} by [{:d}]      and the worst: {:6.2f} by [{:d}]\n".format( min(temp), np.argmin(temp), max(temp), np.argmax(temp) ))
    temp = [sum(np.array(p)*weights) for p in percents]
    print_fn("Best weighted percent badness sum:   {:6.2f} by [{:d}]      and the worst: {:6.2f} by [{:d}]\n".format( min(temp), np.argmin(temp), max(temp), np.argmax(temp) ))
    print_fn("\n")
    return winner

def selection_wrapper(scores, reportfile = 'score_report.txt'):
    import sys
    stdout = sys.stdout
    try:
        sys.stdout = open(reportfile, 'w')
        winner = selection(scores)
    except Exception as e:
        sys.stdout.close()
        sys.stdout = stdout
        print(e)
        print(sys.exc_info()[0])
        raise
        return 'bad'
    else:
        sys.stdout.close()
        sys.stdout = stdout
    return winner

# Multithreading support
from multiprocessing import Pool
def rep(i, args):
    import time, numpy as np
    from . import tdm
    np.random.seed()

    (basename, gates, strands, design_params, n_th, thold_l, thold_e,
        e_dev, m_spurious, e_module, extra_pars, quick, includes) = args
    testname = basename + str(i) + '.txt'
    try:
        toeholds = generate_seqs(basename,
                                 gates,
                                 strands,
                                 design_params,
                                 n_th=n_th,
                                 thold_l=thold_l,
                                 thold_e=thold_e,
                                 e_dev=e_dev,
                                 m_spurious=m_spurious,
                                 e_module=e_module,
                                 strands_file=testname,
                                 extra_pars=extra_pars,
                                 pil_file=basename+str(i)+'.pil',
                                 mfe_file=basename+str(i)+'.mfe',
                                 seq_file=basename+str(i)+'.seq',
                                 fixed_file=basename+str(i)+'.fixed',
                                 save_file=basename+str(i)+'.save',
                                 tempname=basename+str(i))

        scores, names = tdm.EvalCurrent(basename,
                                        gates,
                                        strands,
                                        testname=testname,
                                        seq_file=basename+str(i)+'.seq',
                                        mfe_file=basename+str(i)+'.mfe',
                                        compile_params=design_params,
                                        quick=quick,
                                        includes=includes,
                                        energetics_module=e_module,
                                        targetdG = thold_e)
        scores = [i] + scores
        return scores
    except KeyError as e:
        print('Error!')
        print(e)
        return (gates, strands, e)

def run_designer(basename=small_crn[:-4],
                 reps=1,
                 design_params=(7, 15, 2),
                 thold_l=7,
                 thold_e=7.7,
                 e_dev=1,
                 m_spurious=0.5,
                 e_module=energyfuncs_james,
                 trans_module=DSDClasses,
                 extra_pars="",
                 temp_files=True,
                 quick=False,
                 includes=None
                ):
    """ Generate and score sequences

    This function links together all component of the compiler pipeline. It
    generates a system and PIL file, then runs negative sequence design
    software multiple times to generate multiple sequences. The scoring wrappper
    accepts the gates and strands lists of objects that allow the scoring
    functions to access and compute on the domains and strands from each
    sequence set.

    Args:
        basename: Default name for files accessed and written (small)
        reps: Number of sequence sets to be generated and scored (1)
        design_params: A tuple of parameters to the system file ( (7, 15, 2) )
        thold_l: Nt in a toehold (7)
        thold_e: Target deltaG in kCal/Mol (7.7)
        e_dev: Allowable standard deviation in kCal/mole (1)
        m_spurious: Maximum spurious dG as fraction of thold_e (0.5)
        e_module: Thermodynamics used by stickydesign (energyfuncs_james)
        trans_module: module containing scheme variables and classes (DSDClasses)
        extra_pars: Options sent to spurious designer. ('')
        quick: Make random scores instead of computing heursitics. Skips time
               consuming computations for debugging purposes. (False)
    Returns:
        Nothing, but writes many basename + extension files, such as:
            system file (.sys)
            sequences (.seq)
            scores (_scores.csv)
    """
    # If module inputs are strings, import them
    if type(trans_module) is str:
        trans_module = importlib.import_module('.' + trans_module, 'piperine')
    #
    if quick:
        extra_pars = "imax=-1 quiet=TRUE"

    from . import tdm
    fixed_file = basename + ".fixed"
    system_file = basename + ".sys"
    pil_file = basename + ".pil"

    (gates, strands) = \
        generate_scheme(basename, design_params, trans_module)

    if reps >= 1:
        with Pool() as p:
            vars = (basename, gates, strands, design_params, trans_module.n_th, thold_l, thold_e,
                e_dev, m_spurious, e_module, extra_pars, quick, includes)
            args = [(i, vars) for i in range(reps)]
            scoreslist = list(p.starmap(rep, args))
        _, names = tdm.EvalCurrent(basename, gates,
                                             strands,
                                             testname=None,
                                             compile_params=design_params,
                                             quick=True,
                                             includes=includes,
                                             energetics_module=e_module,
                                             targetdG = thold_e)
        score_names = ['Set Index'] + names
        scores = [score_names] + scoreslist
        if reps > 2:
            winner = selection_wrapper(scores, reportfile=basename+'_score_report.txt')
        else:
            winner = None
        with open(basename+'_scores.csv', 'w') as f:
            f.write(','.join(score_names))
            f.write('\n')
            f.writelines( [ ','.join(map(str, l)) + '\n' for l in scoreslist ])
            f.write("Winner : {}".format(winner))

    return (gates, strands, winner, scoreslist)

def score_fixed(fixed_file,
                 basename=os.path.dirname(__file__)+'/small',
                 crn_file=None,
                 sys_file=None,
                 pil_file=None,
                 save_file=None,
                 mfe_file=None,
                 seq_file=None,
                 score_file=None,
                 design_params=(7, 15, 2),
                 thold_e=7,
                 trans_module=DSDClasses,
                 e_module=energyfuncs_james,
                 includes=None,
                 quick=False):
    """ Score a sequence set

    This function takes in a fixed file, crn file, and reaction scheme specification
    and outputs the heuristic scores of the set.

    Args:
        fixed_file: Filename pointing to the seqeunce set
        basename: Default name for files accessed and written
        crn_file: Filename of text file specifying the CRN (basename + .crn)
        sys_file: Filename of the peppercompiler system file (basename + .sys)
        pil_file: Filename of the peppercompiler PIL file (basename + .pil)
        save_file: Filename of the peppercompiler save file (basename + .save)
        mfe_file: Filename of the peppercompiler MFE file (basename + .mfe)
        seq_file: Filename of the peppercompiler output seq file (basename + .seq)
        design_params: A tuple of parameters to the system file ( (7, 15, 2) )
        trans_module: Module containing scheme variables and classes (DSDClasses)
        quick: Skip time-consuming steps of minimizing sequence symetry and scoring (False)
    Returns:
        scores: A list containing the scores generated by EvalCurrent
        score_names: A list of strings describing the scores
    """
    from . import tdm
    if crn_file is None:
        crn_file = basename + '.crn'
    else:
        bn = crn_file[:-4]
    if sys_file is None:
        sys_file  = basename + '.sys'
    else:
        bn = sys_file[:-4]
    if pil_file is None:
        pil_file = basename + '.pil'
    else:
        bn = pil_file[:-4]
    if save_file is None:
        save_file = basename + '.save'
    else:
        bn = save_file[:-5]
    if mfe_file is None:
        mfe_file = basename + '.mfe'
    else:
        bn = mfe_file[:-4]
    if seq_file is None:
        seq_file = basename + '.seq'
    else:
        bn = seq_file[:-4]
    if score_file is None:
        score_file = fixed_file[:-6] + '.score'
    if basename is None:
        basename = bn
    extra_pars = ""

    gates, strands = generate_scheme(basename,
                                   design_params,
                                   crn_file=crn_file,
                                   system_file=sys_file,
                                   trans_module=trans_module)
    call_compiler(basename, args=design_params, fixed_file=fixed_file,
                  outputname=pil_file, savename=save_file, includes=includes)

    # Generate MFE
    call_design(basename, pil_file, mfe_file, verbose=False,
                extra_pars=extra_pars, cleanup=False)
    # "Finish" the sequence generation
    call_finish(basename, savename=save_file, designname=mfe_file, \
                seqname=seq_file, run_kin=False)
    scores, score_names = tdm.EvalCurrent(basename,
                                          gates,
                                          strands,
                                          compile_params=design_params,
                                          quick=quick,
                                          includes=includes,
                                          energetics_module=e_module,
                                          targetdG = thold_e)
    with open(score_file, 'w') as f:
        f.write(','.join(score_names))
        f.write('\n')
        f.writelines( [ ','.join(map(str, l)) + '\n' for l in [scores] ])
    return (scores, score_names)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--basename", help='Basename.[small]', type=str)
    parser.add_argument("-l", "--length", help='Toehold length.[7]', type=int)
    parser.add_argument("-e", "--energy", help='Target toehold binding energy'+
                        'in kcal/mol.[7.7]', type=float)
    parser.add_argument("-d", "--deviation", help='Toehold binding energy st'+\
                        'andard deviation limit in kcal/mol.[0.5]', type=float)
    parser.add_argument("-M", "--maxspurious", help='Maximum spurious interac'+
                        'tion energy as a multiple of target binding energy.['+
                        '0.4]', type=float)
    parser.add_argument("-g", '--energetics', help='The name of the energetics'+
                        ' module to be used for toehold generation.[energyfunc'+
                        's_james]', type=str)
    parser.add_argument("-p", '--systemparams', help='A string of integers that'+
                        ' are parameters to the sys file compilation[Finds in module]', type=str)
    parser.add_argument("-n", '--candidates', help='Number of candidate sequences'+
                        ' to generate[1]', type=int)
    parser.add_argument("-m", '--module', help='Module describing the strand'+
                        ' displacement architecture[DSDClasses]', type=str)
    parser.add_argument("-x", '--extrapars', help='Parameters sent to SpuriousSSM[]', type=str)
    parser.add_argument("-q", '--quick', action='store_true',
                        help='Make random numbers instead of computing heuristics to save time[False]')
    args = parser.parse_args()
    ############## Interpret arguments
    if args.basename:
        basename = args.basename
    else:
        basename = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data','small'))
    # Find absolute path to basename
    basedir = os.path.dirname(basename)
    if basedir == '':
        basename = os.getcwd() + os.path.sep + basename
    # Set toehold length in base pairs
    if args.length:
        thold_l = int(args.length)
    else:
        thold_l = int(7)

    # Set target toehold binding energy, kcal/mol
    if args.energy:
        thold_e = args.energy
    else:
        thold_e = 7.7

    # Set allowable toehold binding energy deviation, kcal/mol
    if args.deviation:
        e_dev = args.deviation
    else:
        e_dev = 0.5

    # Set allowable spurious interactions, fraction of target energy.
    # The spurious interactions are calculated with standard SantaLucia parameters
    # and sticky-end contexts, not toehold contexts
    if args.maxspurious:
        m_spurious = args.maxspurious
    else:
        m_spurious = 0.4

    # Import desired energetics module as ef
    if args.energetics:
        energetics = args.energetics
    else:
        energetics = 'energyfuncs_james'

    # Set user-specified spurious interaction heatmap image file name
    if args.candidates:
        reps = args.candidates
    else:
        reps = 1

    if args.module:
        exec('import {} as trans_module'.format(args.module))
    else:
        from . import DSDClasses as trans_module

    # Set user-specified spurious interaction heatmap image file name
    if args.systemparams:
        design_params = [ int(i) for i in args.systemparams.split(' ')]
    else:
        try:
            design_params = trans_module.default_params
        except Exception as e:
            print(e)
            print('Cannot guess default .sys parameters without a module')
            raise

    if args.extrapars:
        extra_pars = args.extrapars
    else:
        extra_pars = ""

    th_params={"thold_l":thold_l, "thold_e":thold_e, "e_dev":e_dev, \
               "m_spurious":m_spurious, "e_module":energetics}

    gates, strands, winner = run_designer(basename, reps, th_params, design_params, trans_module,
                                    extra_pars=extra_pars, quick=args.quick)
    print('Winning sequence set is index {}'.format(winner))
