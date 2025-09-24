#!/usr/bin/env python3

from vaspwfc import vaspwfc
import numpy as np
import scipy.integrate as sci
import math as m
from extract import *
from pprint import pprint
import os
import json
import ast

def calc_overlap(Coeff, gvec, Sym_op, center, settings):
    """
    Calculate overlap of a wavefunction and its symmetry
    transformed counterpart or Symmetry Operator Exppectation Value (SOEV).

    Input:
        Coeff: list of plane wave coefficients
        gvec: list of g-vectors
        Sym_op: Symmetry operator matrix
        center: center of orbital, fixed point
        settings: settings dicitonary

    Returns:
        overlap or SOEV
    """
    C = []
    C_p = []
    sym_op_inv = np.linalg.inv(Sym_op)
    r_diff = center - sym_op_inv.dot(center)
    for i, G in enumerate(gvec):
        G_R = G.dot(sym_op_inv)

        #beta = G.dot(center - sym_op_inv.dot(center))
        #beta = G.dot(r_diff)
        #pre_factor = m.e**(2j*m.pi*beta)
        #C.append(pre_factor*Coeff[i])
        C.append(m.e**(2j*m.pi*G.dot(r_diff))*Coeff[i])

        if G_R[0] > 0:
            j = np.where(np.all(gvec == G_R, axis=1))[0][0]
            C_p.append(Coeff[j].conj())
        elif G_R[0] < 0 or G_R[1] < 0 or (G_R[1] == 0 and G_R[2] < 0):
            j = np.where(np.all(gvec == -G_R, axis=1))[0][0]
            C_p.append(Coeff[j])
        else:
            j = np.where(np.all(gvec == G_R, axis=1))[0][0]
            C_p.append(Coeff[j].conj())

    return np.array(C).dot(np.array(C_p))

def get_overlap_list(Coeff, gvec, Sym_ops, center, settings):
    """
    Calculate overlap for all symmetry operations for one band/orbital.

    Inputs:
        Coeff: list of plane wave coefficients
        gvec: list of g-vectors
        Sym_ops: array with symmetry operator info,
                 output for get_symmetry_operators()
        center: center of orbital, fixed point
        settings: settings dicitonary

    Returns:
        list of containing:
        index, symbol, axis, angle and overlap for each operator
    """
    # Identity operator is trivial
    symmetry_info = [[0,Sym_ops[0][0], Sym_ops[2][0], Sym_ops[3][0]]]
    ov_list = [np.real_if_close(np.sum(Coeff*Coeff.conj())).tolist()]

    # Loop over each symmetry operator
    for i, S in enumerate(Sym_ops[1][1:]):

        overlap = calc_overlap(Coeff, gvec, S, center, settings)
        i +=1
        ov_list.append(np.real_if_close(overlap).tolist())
        symmetry_info.append([i, Sym_ops[0][i], Sym_ops[2][i], Sym_ops[3][i]])
    normalizer = 1 / ov_list[0]

    for i in range(len(ov_list)):
        ov_list[i] = ov_list[i]*normalizer

    return ov_list, symmetry_info

def get_overlaps_of_bands(wf_file, name, spin, bands, centers, PGname, Sym_ops, folder_path_out, settings):
    """
    Calculate overlaps for all bands and all symmetries.

    Inputs:
        wf_file: string that is the path to a WAVECAR file
        name: string with name (numbering) of defect
        spin: 1 or 2 for spin up or down
        bands: list of band indices
        centers: list of orbital center of each band
        Sym_ops: array with symmetry operator info,
                 output for get_symmetry_operators()
        folder_path_out: string that is the path to output directory
        settings: settings dicitonary

    Returns:
        list of overlap info of each band
    """

    G_reduction = settings['Gvec_reduction']
    gamma = settings['Gammapoint_calc']


    wav = vaspwfc(wf_file, lgamma=gamma)
    encut = wav._encut
    encut_trunc = encut * G_reduction

    Gvec, KENERGY= gvectors_and_energy(wav, force_Gamma=gamma)


    #Gvec, KENERGY = truncate_gvec(Gvec, KENERGY, encut, G_reduction)
    KENERGY = KENERGY[np.where(KENERGY < encut)[0]]
    Gvec = Gvec[np.where(KENERGY < encut_trunc)[0]]



    pprint(centers)

    result = []

    # Loop of the considered bands
    for i, band_i in enumerate(bands):
        ks = [spin,1,band_i]
        Coeffs = wav.readBandCoeff(*ks, norm=True)

        #Coeffs = truncate_coeffs(Coeffs, KENERGY, encut, G_reduction)
        Coeffs = Coeffs[np.where(KENERGY < encut_trunc)[0]]

        ov_list, symmetry_info = get_overlap_list(Coeffs, Gvec, Sym_ops, centers[i], settings)

        result.append([ks,ov_list])

    ov_json = {"point_group": PGname, "symmetry_operators": symmetry_info, "orbitals": [{"index": result[i][0], "overlaps": str(result[i][1])} for i in range(len(result))]}

    with open(os.path.join(folder_path_out,"Overlaps_"+name+".json"), "w") as outfile:
        outfile.write(json.dumps(ov_json))

    return result

def truncate_gvec(Gvec, KENERGY, encut, reduction):
    """
    Truncates the g-vectors by reducing the cutoff energy.

    Inputs:
        Gvec: list of g-vectors
        KENERGY: list of energy of each g-vector
        encut: cutoff energy
        reduction: factor reducing encut

    Returns:
        truncated list of g-vectors
        truncated list of g-vector energy
    """

    encut_trunc = encut * reduction

    KENERGY = KENERGY[np.where(KENERGY < encut)[0]]

    new_Gvec = []

    for i, en in enumerate(KENERGY):
        if en < encut_trunc:
            new_Gvec.append(Gvec[i])

    #new_Gvec = Gvec[np.where(KENERGY < encut_trunc)[0]]

    return np.asarray(new_Gvec, dtype=int), KENERGY

def truncate_coeffs(Coeffs, KENERGY, encut, reduction):
    """
    Truncates the plane wave coefficients by reducing the cutoff energy.

    Inputs:
        Coeffs: list of plane wave coefficients
        KENERGY: list of energy of each g-vector
        encut: cutoff energy
        reduction: factor reducing encut

    Returns:
        truncated list of coefficients
    """
    encut_trunc = encut * reduction

    new_coeffs = []

    for i, en in enumerate(KENERGY):
        if en < encut_trunc:
            new_coeffs.append(Coeffs[i])

    #new_coeffs = Coeffs[np.where(KENERGY < encut_trunc)[0]]
    return np.array(new_coeffs)

def get_orbital_centers(wf_file, bands_by_degen, name, spin, folder_path_out, settings):
    """
    Calculates the center of the orbital between the chosen bands,
    degenerate states are considered together.

    Input:
        wf_file: filepath to WAVECAR file
        bands_by_degen: bands grouped by degeneracy
        name: string with name (numbering) of defect
        spin: 1 or 2 for spin channel 1 or 2
        folder_path_out: string that is the path to output directory
        settings: settings dicitonary
    Returns:
        list of centers of orbitals
    """



    gamma = settings['Gammapoint_calc']
    grid_mult = settings['realgrid_mult']
    percent = settings['percent_cutoff']

    wav = vaspwfc(wf_file, lgamma=gamma)
    Gvec= wav.gvectors(force_Gamma=gamma)

    grid = wav._ngrid.copy() * grid_mult

    centers = []

    for deg_bands in bands_by_degen:
        wf_array = []
        for band in deg_bands:

            ks = [spin,1,int(band)]
            Coeffs = wav.readBandCoeff(*ks, norm=True)
            realwf = wav.wfc_r(*ks, gvec=Gvec, Cg=Coeffs, ngrid=grid)
            wf_array.append(realwf)

        # Regular center of mass
        #c = find_average_position_general(wf_array, percent)

        # shift the grid so center of mass can be taken for defects close to
        # supercell edges
        shift = find_circular_mean_realspace_opt(wf_array, percent)
        c = find_average_position_shifted(wf_array, percent, shift)


        for i in range(len(deg_bands)):
            centers.append(c)


    c_path = os.path.join(folder_path_out,"Centers_"+name)
    np.save(c_path, centers)
    file = open(c_path+".txt", "w")
    file.write("Band       Center\n")
    for i, deg_bands in enumerate(bands_by_degen):
        file.write(str(deg_bands)+"   "+str(centers[i])+"\n")
    file.close()
    return centers

def get_good_centers(name, bands, no_irr, folder_path_out):
    """
    Removes bad centers from list of centers.

    Inputs:
        name: string with name (numbering) of defect
        bands: list of band indices
        no_irr: list of band indices where the center gave no irrep
        folder_path_out: string that is the path to output directory
    Returns:
        list of centers where all centers produced an irrep
    """

    c_path = os.path.join(folder_path_out,"Centers_"+name+".npy")
    centers = np.load(c_path)
    centers2 = centers
    for band_i in no_irr:
        c = centers[bands.index(band_i)]
        centers2 = centers2[np.all(centers2 != c,axis=1)]
    return centers2

def replace_bad_centers(name, bands, no_irr, good_centers, folder_path_out):
    """
    Replaces bad centers with ones known to be good.

    Inputs:
        name: string with name (numbering) of defect
        bands: list of band indices
        no_irr: list of band indices where the center gave no irrep
        good_centers: list of good centers
        folder_path_out: string that is the path to output directory
    Returns:
        list of good centers minus the one used
        new list of centers with bad ones replaced
    """

    c_path = os.path.join(folder_path_out,"Centers_"+name+".npy")
    centers = np.load(c_path)
    for band_i in no_irr:
        centers[bands.index(band_i)] = good_centers[0]


    c_path2 = os.path.join(folder_path_out,"Centers_"+name)
    np.save(c_path,centers)
    file = open(c_path2+".txt","a+")
    file.write("Bad center switched to: \n")
    for band in no_irr:
        file.write(str(band)+"   "+str(good_centers[0])+"\n")
    file.close()

    return good_centers[1:], centers

def write_overlaps_to_text(overlap_array, folder_path_out, name):
    """
    Writes the overlap array to a .txt file readable by humans.
    Input:
        overlap_array: nested numpy array with all info from overlap calculations
        folder_path_out: string with path to output directory
        name: string with name of

    Returns:
        0
    """

    ov_path = os.path.join(folder_path_out,"Overlaps_"+name+".txt")
    file = open(ov_path, "w+")


    for band in overlap_array:
        file.write(str(band[0])+"\n")
        for sym in band[1]:
            file.write(str(sym)+"\n")
        file.write("\n")
    file.close()
    return 0

def write_overlaps_to_text_fancy(PGname, folder_path_out, name, settings):
    """
    Writes the overlap array to a .txt file readable by humans.
    Input:
        PGname: name of point group
        folder_path_out: string with path to output directory
        name: string with name of
    Returns:
        0
    """

    ov1 = os.path.join(folder_path_out,"Overlaps_"+name+"_S1.json")
    ov2 = os.path.join(folder_path_out,"Overlaps_"+name+"_S2.json")
    f1 = open(ov1,"rb")
    f2 = open(ov2,"rb")
    ov_array1 = json.load(f1)
    ov_array2 = json.load(f2)
    f1.close()
    f2.close()

    rounding = 3
    space = 10+rounding*2

    ov_out = os.path.join(folder_path_out,"Overlaps"+name+".txt")
    file = open(ov_out, "w+")
    ch_table, pos_vector = get_character_table(PGname,settings)

    file.write("Overlaps\n")
    file.write("\nPoint group: "+PGname+"\n")


    sym_string = f"{'Band:':<12}"
    last_sym = "1"
    for sym in ch_table[0][1:]:
        try:
            last_sym = int(last_sym)
            sym_string += f"{sym:<{space}}"*last_sym
        except:
            try:
                int(sym)
            except:
                sym_string += f"{sym:<{space}}"
        last_sym = sym

    file.write("Spin up\n"+sym_string+"\n")

    for orbital_info in ov_array1["orbitals"]:
        ov_string = f"{orbital_info['index'][2]:<12}"
        for overlap in ast.literal_eval(orbital_info["overlaps"]):
            ov = round(np.real(overlap),rounding) + 1j*round(np.imag(overlap),rounding)
            ov = str(ov).strip('(').strip(')')
            ov_string += f"{ov:<{space}}"
        file.write(ov_string+"\n")

    file.write("\nSpin down\n"+sym_string+"\n")

    for orbital_info in ov_array2["orbitals"]:
        ov_string = f"{orbital_info['index'][2]:<12}"
        for overlap in ast.literal_eval(orbital_info["overlaps"]):
            ov = round(np.real(overlap),rounding) + 1j*round(np.imag(overlap),rounding)
            ov = str(ov).strip('(').strip(')')
            ov_string += f"{ov:<{space}}"
        file.write(ov_string+"\n")


    return 0

if __name__ == "__main__":
    0
