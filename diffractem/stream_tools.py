#!/usr/bin/env python
from io import StringIO
import re
from warnings import warn
from copy import deepcopy

BEGIN_GEOM = '----- Begin geometry file -----'
END_GEOM = '----- End geometry file -----'
BEGIN_CELL = '----- Begin unit cell -----'
END_CELL = '----- End unit cell -----'
BEGIN_CHUNK = '----- Begin chunk -----'
END_CHUNK = '----- End chunk -----'
BEGIN_CRYSTAL = '--- Begin crystal'
END_CRYSTAL = '--- End crystal'
BEGIN_PEAKS = 'Peaks from peak search'
END_PEAKS = 'End of peak list'
BEGIN_REFLECTIONS = 'Reflections measured after indexing'
END_REFLECTIONS = 'End of reflections'
HEAD = 'CrystFEL stream format {}.{}'.format(2, 3)
GENERATOR = 'Generated by diffractem StreamParser'
PEAK_COLUMNS = ['fs/px', 'ss/px', '(1/d)/nm^-1', 'Intensity', 'Panel']
REFLECTION_COLUMNS = ['h', 'k', 'l', 'I', 'Sigma(I)', 'Peak', 'Background', 'fs/px', 'ss/px', 'Panel']
ID_FIELDS = ['file', 'Event', 'serial']
CRYSTAL_DATA_FIELS = ['astar', 'bstar', 'cstar', 'predict_refine/det_shift', 
                      'profile_radius', 'diffraction_resolution_limit']


class Crystal:
    
    def __init__(self, line):
        self.astar = (None, None, None)
        self.bstar = (None, None, None)
        self.cstar = (None, None, None)
        self.det_shift = (None, None)
        self.profile_radius = None
        self.resolution = None
        self.start_line = line

    @property
    def initialized(self):
        return all([x is not None 
                    for x in [*self.astar, *self.bstar, *self.cstar,
                              *self.det_shift, self.profile_radius, 
                              self.resolution]])
    
    def __str__(self):
        if not self.initialized:
            warn('Trying to get string from non-initialized crystal from line {}.'.format(self.start_line))
            return None        
        else:
            cs = ' '.join(['{0[0]} {0[1]} {0[2]}'.format(vec) 
                            for vec in [self.astar, self.bstar, self.cstar]])
            cs += ' {0[0]} {0[1]}'.format(self.det_shift)
            cs += ' {0} {1}'.format(self.profile_radius, self.resolution)
            return cs

class Chunk:

    def __init__(self, line):
        self.file = None
        self.Event = None
        self.crystals = []
        self.start_line = line
        
    @property
    def n_cryst(self):
        return len(self.crystals)
    
    @property 
    def initialized(self):
        return (self.file is not None) and (self.Event is not None)
        
    def add_crystal(self, crystal):
        if (not crystal.initialized) or (crystal is None):
            raise RuntimeError('Trying to add non-initialied crystal to chunk from line {}.'.format(self.start_line))
        self.crystals.append(deepcopy(crystal))
        # print(crystal)
        
    def __str__(self):
        if not self.initialized:
            warn('Trying to get string from non-initialized chunk from line {}.'.format(self.start_line))
            return None
        else:
            return '\n'.join([' '.join([self.file, self.Event, str(ii), str(cryst)])
                        for ii, cryst in enumerate(self.crystals)])


def parse_stream(stream, sol=None, return_meta=True, file_label='Image filename', event_label='Event'):

    curr_chunk = None
    curr_cryst = None
    geom = ''
    cell = ''
    command = ''
    parsing_geom = False
    parsing_cell = False
    parsing_peaks = False
    have_cell = False
    have_geom = False
    have_command = False
    parsing_reflections = False
    parse_vec = lambda l: tuple(float(k) for k in re.findall(r'[+-]?\d*\.\d*', l))
    
    with open(stream, 'r') as fh_in, (StringIO() if sol is None else open(sol,'w')) as fh_out:

        for ln, l in enumerate(fh_in):
            
            if parsing_reflections:
                if l.startswith(END_REFLECTIONS):
                    parsing_reflections = False
                else:
                    # here, any reflection parsing would go
                    pass
                    
            elif parsing_peaks:
                if l.startswith(END_PEAKS):
                    parsing_peaks = False
                else:
                    # here, any peak parsing would go
                    pass

            elif l.startswith(BEGIN_CHUNK):
                curr_chunk = Chunk(ln)
                
            elif (curr_chunk is not None) and (curr_cryst is None):
                # parsing chunks (= events = shots) _outside_ crystals
                
                if l.startswith(END_CHUNK):
                    if not curr_chunk.initialized:
                        raise RuntimeError('Incomplete chunk found before line ' + str(ln))
                    if curr_chunk.n_cryst:
                        fh_out.write(str(curr_chunk) + '\n')
                        # print(str(curr_chunk))
                    curr_chunk = None
                    
                elif l.startswith(file_label):
                    curr_chunk.file = l.split(' ')[-1].strip()
                    
                elif l.startswith(event_label):
                    curr_chunk.Event = l.split(' ')[-1].strip()

                elif l.startswith(BEGIN_CRYSTAL):
                    if not curr_chunk.initialized:
                        raise RuntimeError('Crystal for incomplete chunk in ' + str(ln))                
                    curr_cryst = Crystal(ln)
                
            elif curr_cryst is not None:
                # parsing a (single) crystal
                
                if l.startswith(END_CRYSTAL):
                    curr_chunk.add_crystal(curr_cryst)
                    curr_cryst = None
                        
                elif l.startswith('astar'):
                    curr_cryst.astar = parse_vec(l)
                    
                elif l.startswith('bstar'):
                    curr_cryst.bstar = parse_vec(l)
                    
                elif l.startswith('cstar'):
                    curr_cryst.cstar = parse_vec(l)
                    
                elif l.startswith('profile_radius'):
                    curr_cryst.profile_radius = parse_vec(l)[0]
                    
                elif l.startswith('predict_refine/det_shift'):
                    curr_cryst.det_shift = parse_vec(l)
                    
                elif l.startswith('diffraction_resolution_limit'):
                    curr_cryst.resolution = parse_vec(l)[0]
                    
            elif  l.startswith(BEGIN_GEOM) and not have_geom:
                parsing_geom = True
                
            elif parsing_geom:
                if not l.startswith(END_GEOM):
                    geom += l
                else:
                    parsing_geom = False
                    have_geom = True
                
            elif l.startswith(BEGIN_CELL) and not have_cell:
                parsing_cell = True
                
            elif parsing_cell:
                if not l.startswith(END_CELL):
                    cell += l
                else:
                    parsing_cell = False
                    have_cell = True

            elif ('indexamajig' in l) and not have_command:
                command = l
                have_command = True
                                    
            elif l.startswith(BEGIN_PEAKS):
                parsing_peaks = True
                
            elif l.startswith(BEGIN_REFLECTIONS):
                parsing_reflections = True                    
                
        if sol is None:
            out = fh_out.getvalue()
            if return_meta:
                return out, (command, geom, cell)
            else:
                return out
        
        else:
            if return_meta:
                return command, geom, cell

def main():
    from argparse import ArgumentParser
    parser = ArgumentParser(description='Conversion tool from stream to solution file(s) for re-integration/-refinement.')
    
    parser.add_argument('-i', '--input', type=str, help='Input stream file', required=True)
    parser.add_argument('-o', '--output', type=str, help='Output solution file', required=True)
    parser.add_argument('-g', '--geometry-out', type=str, help='Output geometry file (optional)')
    parser.add_argument('-p', '--cell-out', type=str, help='Output cell file (optional)')
    parser.add_argument('--file-field', type=str, help='Field in chunks for image filename', default='Image filename')
    parser.add_argument('--event-field', type=str, help='Field in chunks for event identifier', default='Event')

    args = parser.parse_args()
    
    meta = parse_stream(args.input, args.output, return_meta=True, file_label=args.file_field, event_label=args.event_field)
    print('Original indexamajig call was: \n' + meta[0])
    if args.geometry_out:
        with open(args.geometry_out, 'w') as fh:
            fh.write(meta[1])
    
    if args.cell_out:
        if not meta[1]:
            print('No cell found in stream file. Not writing cell file.')
        else:
            with open(args.cell_out, 'w') as fh:
                fh.write(meta[2])
     
if __name__ == '__main__':
    main()
    