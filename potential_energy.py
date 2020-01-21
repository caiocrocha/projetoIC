import numpy as np
import math
import matplotlib.pyplot as plt
from class_molecule import Molecule
from rotate import get_rotation_list, init_rotation_axis, set_rotation_angle, rotate_atom
from cross_product_3d import cross_product_3d

def is_main():
    return __name__ == '__main__'


#%%

def recursive_heuristic_conf(molecule, rlist, theta, ntimes, a, b, vez, arquivo):
    init_rotation_axis(molecule, a, b, theta)
    lowest = dihedral_potential(molecule)
    comeback = 0
    for i in range(ntimes):
        for atom in rlist:
            rotate_atom(molecule, atom)
        molecule.write_pdb(arquivo, 'a', vez)
        vez += 1
        Vd = dihedral_potential(molecule)
        if Vd < lowest:
            lowest = Vd
            comeback = i
    set_rotation_angle(comeback * theta)
    for atom in rlist:
        rotate_atom(molecule, atom)
    molecule.write_pdb(arquivo, 'a', vez)
    vez += 1
    k = int(b * (b - 1) / 2)
    for i in range(b-1, -1, -1):
        if (molecule.topology.bond_matrix[k + i] and i != a and molecule.topology.type[i-1] != 'hc'):
            rlist1 = get_rotation_list(molecule, b, i)
            recursive_heuristic_conf(molecule, rlist1, theta, ntimes, b, i, vez, arquivo)
    for i in range(b+1, molecule.num_atoms):
        if(molecule.topology.bond_matrix[int(i*(i-1)/2 + b)] and i != a and molecule.topology.type[i-1] != 'hc'):
            rlist1 = get_rotation_list(molecule, b, i)
            recursive_heuristic_conf(molecule, rlist1, theta, ntimes, b, i, vez, arquivo)

def heuristic_conformation(molecule, theta, arquivo):
    ntimes = int(2*np.pi/theta)
    a = molecule.topology.bond_list[0]
    b = molecule.topology.bond_list[1]
    rlist = get_rotation_list(molecule, a, b)
    molecule.write_pdb('./butane/sqm/sqm_heuristic.pdb', 'w+', 0)
    recursive_heuristic_conf(molecule, rlist, theta, ntimes, a, b, 1, arquivo)

def dihedral_Ep_rotate(molecule, a, b, theta, ntimes, pdf_name, 
                      write_pdb=False, pdb_name=None):
    times = ntimes + 1
    Vd = np.zeros(times, dtype='float32')
    dihed_angle = np.zeros(times, dtype='float32')
    Vd[0], dihed_angle[0] = _dihedral_potential(molecule)
    plt.scatter(dihed_angle[0], Vd[0], marker='.', color='royalblue')
    init_rotation_axis(molecule, a, b, theta)
    rlist = get_rotation_list(molecule, a, b)
    if not write_pdb:
        for i in range(1, times):
            for atom in rlist:
                rotate_atom(molecule, atom)
            Vd[i], dihed_angle[i] = _dihedral_potential(molecule)
            plt.scatter(dihed_angle[i], Vd[i], marker='.', color='royalblue')
    else:
        molecule.write_pdb(pdb_name, 'w+', 0)
        for i in range(1, times):
            for atom in rlist:
                rotate_atom(molecule, atom)
            Vd[i], dihed_angle[i] = _dihedral_potential(molecule)
            plt.scatter(dihed_angle[i], Vd[i], marker='.', color='royalblue')
            molecule.write_pdb(pdb_name, 'a', i)
    plt.xlabel('Degrees (rad)')
    plt.ylabel(r'Elastic potential (kcal $mol^{-1} \AA^{-2}$)')
    plt.grid()
    plt.suptitle('Rotation degrees X Dihedral elastic potential (Vd) graphic')
    plt.title(r'{}$^\circ$ x {} rotations'.format(theta*180/math.pi, ntimes), fontsize=10, loc='right')
    plt.savefig(pdf_name)
    plt.show()
    return dihed_angle, Vd

def minimize_pot_energy(molecule, fx, fy, fz):
    for i in range(molecule.num_atoms):
        fx1 = fx[i]
        fy1 = fy[i]
        fz1 = fz[i]
        N = (fx1*fx1 + fy1*fy1 + fz1*fz1)**0.5 # normal force
        molecule.x[i] -= 0.01*fx1/N
        molecule.y[i] -= 0.01*fy1/N
        molecule.z[i] -= 0.01*fz1/N

def bond_pot_variables(molecule, atom1, atom2):
    bx = molecule.x[atom2] - molecule.x[atom1]
    by = molecule.y[atom2] - molecule.y[atom1]
    bz = molecule.z[atom2] - molecule.z[atom1]
    b = (bx*bx + by*by + bz*bz)**0.5    # distance between atoms 1 and 2
    btype = ('{}-{}'.format(molecule.topology.type[atom1], 
                    molecule.topology.type[atom2])
             )  # bond type (e.g. 'c3-c3' or 'c3-hc')
    try:
        Kb = molecule.topology.bond_types[btype][0] # elastic constant of the bond
        b0 = molecule.topology.bond_types[btype][1] # equilibrium bond length
    except:
        btype = ('{}-{}'.format(molecule.topology.type[atom2], 
                molecule.topology.type[atom1])
                 )
        try:
            Kb = molecule.topology.bond_types[btype][0]
            b0 = molecule.topology.bond_types[btype][1]
        except: pass
    d = b-b0
    # d: difference between the present distance between the two atoms 
    # and the equilibrium distance
    return bx, by, bz, b, b0, Kb, d

def bond_force_variables(molecule, atom1, atom2):
    bx, by, bz, b, b0, Kb, d = bond_pot_variables(molecule, atom1, atom2)
    if b != 0:
        ux = bx/b
        uy = by/b
        uz = bz/b
    else:
        ux = 0
        uy = 0
        uz = 0
    return bx, by, bz, b, b0, Kb, d, ux, uy, uz

def bond_potential(molecule):
    nbonds = molecule.topology.num_bonds
    Vb = 0
    # Vb = np.zeros(nbonds, dtype='float32')
    # count = 0
    for i in range(0, nbonds*2, 2):
        bx, by, bz, b, b0, Kb, d = bond_pot_variables(molecule, 
            atom1 = molecule.topology.bond_list[i]-1, 
            atom2 = molecule.topology.bond_list[i+1]-1)
        Vb += Kb*d*d
        # Vb[count] = Kb*d*d
        # count += 1
    return Vb

def bond_force(molecule, fx, fy, fz):
    for i in range(0, molecule.topology.num_bonds*2, 2):
        atom1 = molecule.topology.bond_list[i]-1
        atom2 = molecule.topology.bond_list[i+1]-1
        bx, by, bz, b, b0, Kb, d, ux, uy, uz = bond_force_variables(molecule, atom1, atom2)
        force = -2*Kb*d  # first derivative of the bond potential Vb
        fx1 = force*ux  # decomposition of the force on the X axis
        fy1 = force*uy  # decomposition of the force on the Y axis
        fz1 = force*uz  # decomposition of the force on the Z axis
        fx2 = -fx1
        fy2 = -fy1
        fz2 = -fz1
        fx[atom1] += fx1
        fy[atom1] += fy1
        fz[atom1] += fz1
        fx[atom2] += fx2
        fy[atom2] += fy2
        fz[atom2] += fz2

def _angle_pot_variables(molecule, atom1, atom2, atom3):
    # global x1, y1, z1, x2, y2, z2, x3, y3, z3
    # global v21x, v21y, v21z, v23x, v23y, v23z, n1, n2
    
    x1 = molecule.x[atom1]
    y1 = molecule.y[atom1]
    z1 = molecule.z[atom1]
    x2 = molecule.x[atom2]
    y2 = molecule.y[atom2]
    z2 = molecule.z[atom2]
    x3 = molecule.x[atom3]
    y3 = molecule.y[atom3]
    z3 = molecule.z[atom3]
    
    v21x = x1 - x2
    v23x = x3 - x2
    v21y = y1 - y2
    v23y = y3 - y2
    v21z = z1 - z2
    v23z = z3 - z2
    norm1 = (v21x*v21x + v21y*v21y + v21z*v21z)**0.5 # norm of vector v21 (or v12)
    norm2 = (v23x*v23x + v23y*v23y + v23z*v23z)**0.5 # norm of vector v23 (or v32)
    
    atype = ('{}-{}-{}'.format(molecule.topology.type[atom1], 
                    molecule.topology.type[atom2], molecule.topology.type[atom3])
             )  # angle type (e.g. 'c3-c3-hc' or 'c3-c3-c3')
    try:
        Ka = molecule.topology.angle_types[atype][0]    # angle elastic constant
        a0 = molecule.topology.angle_types[atype][1]    # equilibrium angle
    except:
        atype = ('{}-{}-{}'.format(molecule.topology.type[atom3], 
                    molecule.topology.type[atom2], molecule.topology.type[atom1])
                 )
        try:
            Ka = molecule.topology.angle_types[atype][0]
            a0 = molecule.topology.angle_types[atype][1]
        except:
            raise AttributeError('Could not find corresponding angle type')
    return a0, Ka, v21x, v21y, v21z, v23x, v23y, v23z, norm1, norm2

def angle_pot_variables(molecule, atom1, atom2, atom3):
    a0, Ka, v21x, v21y, v21z, v23x, v23y, v23z, norm1, norm2 = _angle_pot_variables(molecule, atom1, atom2, atom3)
    if norm1 != 0 and norm2 != 0:
        angle = math.acos((v21x*v23x + v21y*v23y + v21z*v23z)/(norm1*norm2))
    else:
        angle = 0
    return angle-a0, Ka

def angle_force_variables(molecule, atom1, atom2, atom3):
    a0, Ka, v21x, v23x, v21y, v23y, v21z, v23z, norm1, norm2 = _angle_pot_variables(
        molecule, atom1, atom2, atom3)
    nx, ny, nz = cross_product_3d(
        molecule, v21x, v23x, v21y, v23y, v21z, v23z)
    # normal vector of the plane determined by vectors v21 and v23
    vR1x, vR1y, vR1z = cross_product_3d(
        molecule, v21x, nx, v21y, ny, v21z, nz)
    # vR1: resulting vector (orthogonal to v21)
    vR2x, vR2y, vR2z = cross_product_3d(
        molecule, v23x, nx, v23y, ny, v23z, nz)
    # vR2: resulting vector (orthogonal to v23)
    M1 = (vR1x*vR1x + vR1y*vR1y + vR1z*vR1z)**0.5
    M2 = (vR2x*vR2x + vR2y*vR2y + vR2z*vR2z)**0.5
    # the following are the normalization of vR1 and vR2:
    if M1 != 0:
        p1x = vR1x/M1
        p1y = vR1y/M1
        p1z = vR1z/M1
    else:
        p1x = 0
        p1y = 0
        p1z = 0
    if M2 != 0:
        p2x = vR2x/M2
        p2y = vR2y/M2
        p2z = vR2z/M2
    else:
        p2x = 0
        p2y = 0
        p2z = 0
    return a0, Ka, v21x, v23x, v21y, v23y, v21z, v23z, norm1, norm2, p1x, p1y, p1z, p2x, p2y, p2z
        
def angle_potential(molecule):
    nangles = molecule.topology.num_angles
    Va = 0
    # Va = np.zeros(nangles, dtype='float32')
    # count = 0
    for i in range(0, nangles*3, 3):
        delta_angle, Ka = angle_pot_variables(
            molecule, 
            atom1 = molecule.topology.angle_list[i]-1, 
            atom2 = molecule.topology.angle_list[i+1]-1, 
            atom3 = molecule.topology.angle_list[i+2]-1)
        Va += Ka*delta_angle*delta_angle
        # Va[count] = Ka*delta_angle*delta_angle
        # count += 1
    return Va
        
def angle_force(molecule, fx, fy, fz):
    for i in range(0, molecule.topology.num_angles*3, 3):
        atom1 = molecule.topology.angle_list[i]-1
        atom2 = molecule.topology.angle_list[i+1]-1
        atom3 = molecule.topology.angle_list[i+2]-1
        a0, Ka, v21x, v23x, v21y, v23y, v21z, v23z, norm1, norm2, p1x, p1y, p1z, p2x, p2y, p2z = angle_force_variables(
            molecule, atom1, atom2, atom3)
        if norm1 != 0 and norm2 != 0:
            dot = (v21x * v23x + v21y * v23y + v21z * v23z) / (norm1 * norm2)
            if dot > 1:
                dot = 1
            elif dot < -1:
                dot = -1
            angle = math.acos(dot)
            force = -2*Ka*(angle-a0)   # first derivative of the angle potential Va
        else:
            angle = 0
            force = -2 * Ka * (angle - a0)
        if norm1 != 0:
            u1 = force / norm1
            # force multiplied by the partial derivative of Va according to position (x1, y1, z1)
        else:
            u1 = 0
        if norm2 != 0:
            u3 = force / norm2
            # force multiplied by the partial derivative of Va according to position (x3, y3, z3)
        else:
            u3 = 0
        fx1 = p1x*u1
        fy1 = p1y*u1
        fz1 = p1z*u1
        fx2 = p2x*u3
        fy2 = p2y*u3
        fz2 = p2z*u3
        fx[atom1] += fx1
        fy[atom1] += fy1
        fz[atom1] += fz1
        fx[atom3] += fx2
        fy[atom3] += fy2
        fz[atom3] += fz2
        fx[atom2] += -fx1 - fx2
        fy[atom2] += -fy1 - fy2
        fz[atom2] += -fz1 - fz2
        
def get_dihed_type(molecule, atom1, atom2, atom3, atom4):
    dtype = ('{}-{}-{}-{}'.format(molecule.topology.type[atom1], 
                                  molecule.topology.type[atom2], 
                                  molecule.topology.type[atom3], 
                                  molecule.topology.type[atom4])
            )  # dihedral type (e.g. 'c3-c3-c3-c3')
    return dtype
        
def _dihedral_pot_variables(molecule, atom1, atom2, atom3, atom4, dtype):
    x1 = molecule.x[atom1]
    y1 = molecule.y[atom1]
    z1 = molecule.z[atom1]
    x2 = molecule.x[atom2]
    y2 = molecule.y[atom2]
    z2 = molecule.z[atom2]
    x3 = molecule.x[atom3]
    y3 = molecule.y[atom3]
    z3 = molecule.z[atom3]
    x4 = molecule.x[atom4]
    y4 = molecule.y[atom4]
    z4 = molecule.z[atom4]
    
    v21x = x1 - x2
    v21y = y1 - y2
    v21z = z1 - z2
    v23x = x3 - x2
    v23y = y3 - y2
    v23z = z3 - z2
    v34x = x4 - x3
    v34y = y4 - y3
    v34z = z4 - z3
    v32x = -v23x
    v32y = -v23y
    v32z = -v23z
    
    try:
        length = len(molecule.topology.dihedral_types[dtype])
        A1 = np.zeros(length)
        A2 = np.zeros(length)
        A3 = np.zeros(length)
        A4 = np.zeros(length)
        for i in range(length):
            A1[i] = molecule.topology.dihedral_types[dtype][i][0]
            A2[i] = molecule.topology.dihedral_types[dtype][i][1]
            A3[i] = molecule.topology.dihedral_types[dtype][i][2]
            A4[i] = molecule.topology.dihedral_types[dtype][i][3]
    except:
        dtype = ('{}-{}-{}-{}'.format(molecule.topology.type[atom4], 
                                      molecule.topology.type[atom3], 
                                      molecule.topology.type[atom2], 
                                      molecule.topology.type[atom1])
                )  # dihedral type (e.g. 'c3-c3-c3-c3')
        try:
            length = len(molecule.topology.dihedral_types[dtype])
            A1 = np.zeros(length)
            A2 = np.zeros(length)
            A3 = np.zeros(length)
            A4 = np.zeros(length)

            for i in range(length):
                A1[i] = molecule.topology.dihedral_types[dtype][i][0]
                A2[i] = molecule.topology.dihedral_types[dtype][i][1]
                A3[i] = molecule.topology.dihedral_types[dtype][i][2]
                A4[i] = molecule.topology.dihedral_types[dtype][i][3]
        except:
            raise AttributeError('Could not find corresponding dihedral type')
    
    n1x, n1y, n1z = cross_product_3d(
        molecule, v21x, v23x, v21y, v23y, v21z, v23z)
    # normal vector of the plane determined by vectors v21 and v23
    n2x, n2y, n2z = cross_product_3d(
        molecule, v32x, v34x, v32y, v34y, v32z, v34z)
    # normal vector of the plane determined by vectors v32 and v34
    
    nx, ny, nz = cross_product_3d(molecule, n1x, n2x, n1y, n2y, n1z, n2z)
    # normal vector of the plane determined by n1 and n2
    M = (nx*nx + ny*ny + nz*nz)**0.5    # magnitude of normal vector n
    if M != 0:
        det = (nx*abs(nx) + ny*abs(ny) + nz*abs(nz))/M
        # Let u = abs(n)/M (normalization of vector n). The determinant det(n1, n2, u)
        # is proportional to the sine of the angle between vectors n1 and n2. It can be
        # expressed as the triple product between n1, n2 and u. Triple product:
        # (n1 x n2) * u
        dot = n1x * n2x + n1y * n2y + n1z * n2z
        # the dot product between n1 and n2 is proportional to the cosine of the angle
        # dihed_angle = math.atan2(det, dot)
        dihed_angle = math.atan2(det, dot) + np.pi
    else:
        dihed_angle = 0
    
    return (length, A1, A2, A3, A4, dihed_angle, x2, y2, z2, x3, y3, z3,
        v21x, v21y, v21z, v23x, v23y, v23z, v34x, v34y, v34z, v32x, v32y, v32z,
        n1x, n1y, n1z, n2x, n2y, n2z)

def dihedral_pot_variables(molecule, atom1, atom2, atom3, atom4, dtype):
    length, A1, A2, A3, A4, dihed_angle = _dihedral_pot_variables(molecule, atom1, atom2, atom3, atom4, dtype)[0:6]
    return length, A1, A2, A3, A4, dihed_angle

def dihedral_force_variables(molecule, atom1, atom2, atom3, atom4, dtype):
    (length, A1, A2, A3, A4, dihed_angle, x2, y2, z2, x3, y3, z3, 
        v21x, v21y, v21z, v23x, v23y, v23z, v34x, v34y, v34z, v32x, v32y, v32z, 
        n1x, n1y, n1z, n2x, n2y, n2z) = _dihedral_pot_variables(
            molecule, atom1, atom2, atom3, atom4, dtype)
    norm1 = (v21x*v21x + v21y*v21y + v21z*v21z)**0.5 # norm of vector v21 (or v12)
    norm2 = (v23x*v23x + v23y*v23y + v23z*v23z)**0.5 # norm of vector v23 (or v32)
    norm3 = (v34x*v34x + v34y*v34y + v34z*v34z)**0.5 # norm of vector v34 (or v43)

    force = 0
    for i in range(length):
        force += A2[i] * math.sin((A4[i] * dihed_angle) - A3[i]) * A4[i]
    # first derivative of the dihedral potential Vd

    if norm1 == 0 or norm2 == 0:
        f1x = 0
        f1y = 0
        f1z = 0
    else:
        theta1 = math.acos((v21x * v23x + v21y * v23y + v21z * v23z) / (norm1 * norm2))
        M1 = (n1x * n1x + n1y * n1y + n1z * n1z) ** 0.5
        p1x = n1x / M1
        p1y = n1y / M1
        p1z = n1z / M1
        # p1 is the normalization of n1
        u1 = force / (norm1 * math.sin(theta1))
        # force multiplied by the partial derivative of theta1 according to position (x1, y1, z1)
        f1x = p1x * u1
        f1y = p1y * u1
        f1z = p1z * u1

    if norm2 == 0 or norm3 == 0:
        f4x = 0
        f4y = 0
        f4z = 0
    else:
        theta2 = math.acos((v32x*v34x + v32y*v34y + v32z*v34z)/(norm2*norm3))
        M2 = (n2x * n2x + n2y * n2y + n2z * n2z)**0.5
        p2x = n2x / M2
        p2y = n2y / M2
        p2z = n2z / M2
        # p2 is the normalization of n2
        u4 = force/(norm3*math.sin(theta2))
        # force multiplied by the partial derivative of theta2 according to position (x4, y4, z4)
        f4x = p2x*u4
        f4y = p2y*u4
        f4z = p2z*u4

    ox = (x2 + x3)/2
    oy = (y2 + y3)/2
    oz = (z2 + z3)/2
    # The point o is the center of bond v23
    vo3x = x3 - ox
    vo3y = y3 - oy
    vo3z = z3 - oz
    # vector parting from o to (x3, y3, z3)

    norm_vo3 = vo3x*vo3x + vo3y*vo3y + vo3z*vo3z
    if norm_vo3 == 0:
        f3x = 0
        f3y = 0
        f3z = 0
    else:
        const = -1/norm_vo3   # inverse square of the norm of vector vo3
        n_vo3_f4x, n_vo3_f4y, n_vo3_f4z = cross_product_3d(molecule, vo3x, f4x, vo3y, f4y, vo3z, f4z)
        n_v34_f4x, n_v34_f4y, n_v34_f4z = cross_product_3d(molecule, v34x, f4x, v34y, f4y, v34z, f4z)
        n_v21_f4x, n_v21_f4y, n_v21_f4z = cross_product_3d(molecule, v21x, f4x, v21y, f4y, v21z, f4z)
        t3x = const*(n_vo3_f4x + 0.5*n_v34_f4x + 0.5*n_v21_f4x)
        t3y = const*(n_vo3_f4y - 0.5*n_v34_f4y - 0.5*n_v21_f4y)
        t3z = const*(n_vo3_f4z - 0.5*n_v34_f4z - 0.5*n_v21_f4z)
        # t3 is the cross product (vo3 by f3)
        f3x, f3y, f3z = cross_product_3d(molecule, t3x, vo3x, t3y, vo3y, t3z, vo3z)
        
    f2x = -f1x - f3x - f4x
    f2y = -f1y - f3y - f4y
    f2z = -f1z - f3z - f4z
    return f1x, f1y, f1z, f2x, f2y, f2z, f3x, f3y, f3z, f4x, f4y, f4z

def _dihedral_potential(molecule, ForceField='gaff'):
    ndihed = molecule.topology.num_dihedrals
    Vd = 0
    if ForceField == 'opls':
        for i in range(0, ndihed, 4):
            atom1 = molecule.topology.dihedral_list[i]-1, 
            atom2 = molecule.topology.dihedral_list[i+1]-1
            atom3 = molecule.topology.dihedral_list[i+2]-1
            atom4 = molecule.topology.dihedral_list[i+3]-1
            dtype = get_dihed_type(molecule, atom1, atom2, atom3, atom4)
            if 'hc' in dtype:
                continue
            length, A1, A2, A3, A4, dihed_angle = dihedral_pot_variables(
                    molecule, atom1, atom2, atom3, atom4, dtype)
            for j in range(length):
                Vd += 0.5*(
                    A1[j]*(1 + math.cos(dihed_angle)) + A2[j]*(1 - math.cos(2*dihed_angle)) + 
                    A3[j]*(1 + math.cos(3*dihed_angle)) + A4[j])
        
    else:
        for i in range(0, ndihed, 4):
            atom1 = molecule.topology.dihedral_list[i]-1, 
            atom2 = molecule.topology.dihedral_list[i+1]-1
            atom3 = molecule.topology.dihedral_list[i+2]-1
            atom4 = molecule.topology.dihedral_list[i+3]-1
            dtype = get_dihed_type(molecule, atom1, atom2, atom3, atom4)
            if 'hc' in dtype:
                continue
            length, A1, A2, A3, A4, dihed_angle = dihedral_pot_variables(
                    molecule, atom1, atom2, atom3, atom4, dtype)
            for j in range(length):
                Vd += A2[j]*(1 + math.cos((A4[j]*dihed_angle) - A3[j]))

    return Vd, dihed_angle*180/np.pi

def dihedral_potential(molecule, ForceField = 'gaff'):
    Vd = _dihedral_potential(molecule, ForceField)[0]
    return Vd

def dihedral_force(molecule, fx, fy, fz):
    for i in range(molecule.topology.num_dihedrals):
        atom1 = molecule.topology.dihedral_list[i]-1
        atom2 = molecule.topology.dihedral_list[i+1]-1
        atom3 = molecule.topology.dihedral_list[i+2]-1
        atom4 = molecule.topology.dihedral_list[i+3]-1
        dtype = get_dihed_type(molecule, atom1, atom2, atom3, atom4)
        if 'hc' in dtype:
            continue
        f1x, f1y, f1z, f2x, f2y, f2z, f3x, f3y, f3z, f4x, f4y, f4z = dihedral_force_variables(
            molecule, atom1, atom2, atom3, atom4, dtype)
        fx[atom1] += f1x
        fy[atom1] += f1y
        fz[atom1] += f1z
        fx[atom2] += f2x
        fy[atom2] += f2y
        fz[atom2] += f2z
        fx[atom3] += f3x
        fy[atom3] += f3y
        fz[atom3] += f3z
        fx[atom4] += f4x
        fy[atom4] += f4y
        fz[atom4] += f4z

#%%

##############################################################################
if is_main():
    
    molecule = Molecule()

    # pdb, psf, out_pdb, out_psf = molecule.get_cmd_line()

    molecule.read_psf('./3-metil-pentano/3-metil-pentano.psf')
    molecule.read_pdb('./3-metil-pentano/3-metil-pentano.pdb')
    # molecule.read_mol2('./3-metil-pentano/3-metil-pentano.mol2')
    # molecule.write_mol2('3-metil-pentano1.mol2')
    molecule.read_frcmod('./3-metil-pentano/3-metil-pentano.frcmod')

    Vb = bond_potential(molecule)
    Va = angle_potential(molecule)
    Vd = dihedral_potential(molecule)
    fx = np.zeros(molecule.num_atoms, dtype='float32')
    fy = np.zeros(molecule.num_atoms, dtype='float32')
    fz = np.zeros(molecule.num_atoms, dtype='float32')
    bond_force(molecule, fx, fy, fz)
    angle_force(molecule, fx, fy, fz)
    dihedral_force(molecule, fx, fy, fz)

    # minimize_pot_energy(molecule, fx, fy, fz)
    heuristic_conformation(molecule, theta=np.pi, arquivo='./3-metil-pentano/3-metil-pentano_heuristic.pdb')

    Vb1 = bond_potential(molecule)
    Va1 = angle_potential(molecule)
    Vd1 = dihedral_potential(molecule)
    fx1 = np.zeros(molecule.num_atoms, dtype='float32')
    fy1 = np.zeros(molecule.num_atoms, dtype='float32')
    fz1 = np.zeros(molecule.num_atoms, dtype='float32')
    bond_force(molecule, fx1, fy1, fz1)
    angle_force(molecule, fx1, fy1, fz1)
    dihedral_force(molecule, fx1, fy1, fz1)
    '''
    angle_list, Vd_list = dihedral_Ep_rotate(molecule, a=2, b=3, theta=np.pi/18, ntimes=36,
        pdf_name='./Graphs/ignore.pdf', write_pdb=False, pdb_name='./butane/sqm/sqm_rotated1.pdb')
    
    with open ('comparar.dat', 'w+') as arq:
        for i in range(0, len(Vd_list), 10):
            arq.write('{:.3f},{:.6f}\n'.format(angle_list[i], Vd_list[i]))
    
    import pandas as pd
    output=pd.DataFrame(Vd_list, angle_list)
    output.to_csv('comparar.dat')
    '''
