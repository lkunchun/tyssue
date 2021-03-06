import numpy as np
import pandas as pd

from ..utils.utils import set_data_columns, spec_updater

import warnings
import logging
log = logging.getLogger(name=__name__)

'''
Core definitions



The following data is an exemple of the `specs`.
It is a nested dictionnary with two levels.

The first key designs the element name: ('face', 'edge', 'vert') They will
correspond to the dataframes attributes of the Epithelium instance,
(e.g eptm.face_df);

The second level keys design column names of the above dataframes,
default values is allways infered from the python parsed type. Thus
`1` will be cast as `int`, `1.` as `float` and `True` as a `bool`.

    specs = {
        'face': {
            ## Face Geometry
            'perimeter': 0.,
            'area': 0.,
            ## Coordinates
            'x': 0.,
            'y': 0.,
            'z': 0.,
            ## Topology
            'num_sides': 6,
            ## Masks
            'is_alive': True},
        'vert': {
            ## Coordinates
            'x': 0.,
            'y': 0.,
            'z': 0.,
            ## Masks
            'is_active': True},
        'edge': {
            ## Coordinates
            'dx': 0.,
            'dy': 0.,
            'dz': 0.,
            'length': 0.,
            ### Normals
            'nx': 0.,
            'ny': 0.,
            'nz': 1.}
        }
'''

class Epithelium:
    '''
    The whole tissue.

    '''

    def __init__(self, identifier, datasets,
                 specs=None, coords=None):
        '''
        Creates an epithelium

        Parameters:
        -----------
        identifier: string
        datasets: dictionary of dataframes
        the datasets dict specifies the names, data columns
        and value types of the modeled tyssue

        '''
        if coords is None:
            coords = ['x', 'y', 'z']
        self.coords = coords
        # edge's dx, dy, dz
        self.dcoords = ['d'+c for c in self.coords]
        self.dim = len(self.coords)
        # edge's normals
        if self.dim == 3:
            self.ncoords = ['n'+c for c in self.coords]

        # each of those has a separate dataframe, as well as entries in
        # the specification files
        frame_types = {'edge', 'vert', 'face',
                       'cell'}

        # # Really just to ensure the debugger is silent
        # [self.edge_df,
        #  self.vert_df,
        #  self.face_df,
        #  self.cell_df] = [None, ] * 4

        self.identifier = identifier
        if not set(datasets).issubset(frame_types):
            raise ValueError('The `datasets` dictionnary should'
                             ' contain keys in {}'.format(frame_types))
        self.datasets = datasets
        # for name, data in datasets.items():
        #     setattr(self, '{}_df'.format(name), data)
        self.data_names = list(datasets.keys())
        self.element_names = ['srce', 'trgt',
                              'face', 'cell'][:len(self.data_names)]
        if specs is None:
            specs = {name: {} for name in self.data_names}
        if 'settings' not in specs:
            specs['settings'] = {}

        self.specs = specs
        self.update_specs(specs, reset=False)
        self.edge_mindex = pd.MultiIndex.from_arrays(self.edge_idx.values.T,
                                                     names=self.element_names)
        # # Topology (geometry independant)
        self.reset_topo()
        self.bbox = None
        self.set_bbox()

    @property
    def face_df(self):
        return self.datasets['face']

    @face_df.setter
    def face_df(self, value):
        self.datasets['face'] = value

    @property
    def edge_df(self):
        return self.datasets['edge']

    @edge_df.setter
    def edge_df(self, value):
        self.datasets['edge'] = value

    @property
    def cell_df(self):
        #- BC -#
        # Recommends to test if the epithelium has a 'cell' df before returning,
        # some epitheliums don't require this object (2D)
        # Should it raise a warning/error if the user asks for
        # a cell_df from an eptm that doesn't have one ?
        return self.datasets['cell']

    @cell_df.setter
    def cell_df(self, value):
        self.datasets['cell'] = value

    @property
    def vert_df(self):
        return self.datasets['vert']

    @vert_df.setter
    def vert_df(self, value):
        self.datasets['vert'] = value

    # @property
    # def datasets(self):
    #     datasets = {element: getattr(self, '{}_df'.format(element))
    #                 for element in self.data_names}
    #     return datasets

    # # @datasets.getter
    # # def datasets(self, level):
    # #     return getattr(self, '{}_df'.format(level))

    # @datasets.setter
    # def datasets(self, level, new_df):
    #     setattr(self, '{}_df'.format(level), new_df)

    def copy(self, deep_copy=True):
        """
        Returns a copy of the epithelium

        Parameters
        ----------
        deep_copy: bool, default True
            if True, use a copy of the original object's datasets
            to create the new object. If False, datasets are not copied
        """
        if deep_copy:
            datasets = {element: df.copy()
                        for element, df in self.datasets.items()}
        else: #pragma: no cover
            log.info(
                "New epithelium object from {}"
                " without deep copy".format(
                    self.identifier))
            datasets = self.datasets

        identifier = self.identifier+'_copy'
        new = Epithelium(identifier, datasets,
                         specs=self.specs, coords=None)
        return new

    @property
    def settings(self):
        return self.specs['settings']

    def update_specs(self, new, reset=False):

        spec_updater(self.specs, new)
        set_data_columns(self.datasets, new, reset)

    def update_num_sides(self):
        self.face_df['num_sides'] = self.edge_df.face.value_counts().loc[
            self.face_df.index]

    def update_num_faces(self):
        self.cell_df['num_faces'] = self.edge_df.groupby('cell').apply(
            lambda df: df['face'].unique().size)

    def update_mindex(self):
        self.edge_mindex = pd.MultiIndex.from_arrays(self.edge_idx.values.T,
                                                     names=self.element_names)

    def reset_topo(self):
        self.update_num_sides()
        self.update_mindex()
        if 'cell' in self.data_names:
            self.update_num_faces()
        if ('opposite' in self.edge_df.columns) and (
                'cell' not in self.data_names):
            try:
                self.edge_df['opposite'] = get_opposite(self.edge_df)
            except ValueError:
                warnings.warn('Opposites could not be computed, are you sure '
                              'you are using a sheet-like topology?')

    @property
    def face_idx(self):
        return self.face_df.index

    @property
    def cell_idx(self):
        return self.cell_df.index

    @property
    def vert_idx(self):
        return self.vert_df.index

    @property
    def edge_idx(self):
        # Should it return self.edge_df.index instead ?
        return self.edge_df[self.element_names]

    @property
    def Nc(self):
        if 'cell' in self.data_names:
            return self.cell_df.shape[0]
        elif 'face' in self.data_names:
            return self.face_df.shape[0]

    @property
    def Nv(self):
        return self.vert_df.shape[0]

    @property
    def Nf(self):
        return self.face_df.shape[0]

    @property
    def Ne(self):
        return self.edge_df.shape[0]

    @property
    def e_srce_idx(self):
        return self.edge_df['srce']

    @property
    def e_trgt_idx(self):
        return self.edge_df['trgt']

    @property
    def e_face_idx(self):
        return self.edge_df['face']

    @property
    def e_cell_idx(self):
        return self.edge_df['cell']

    @property
    def edge_idx_array(self):
        return np.vstack((self.e_srce_idx,
                          self.e_trgt_idx,
                          self.e_face_idx)).T

    def _upcast(self, idx, df):

        upcast = df.loc[idx]
        upcast.index = self.edge_df.index
        return upcast

    def upcast_cols(self, element, columns):
        """Syntactic sugar to upcast from the
        epithelium datasets.

        Parameters
        ----------
        element: {'srce'|'trgt'|'face'|'cell'}
           corresponding self.edge_df column over which to index
           if element is 'srce' or 'trgt', the upcast data will be
           taken form self.vert_df
        columns: index
           the column(s) to be taken from the input dataset.

        """
        if element in ['srce', 'trgt']:
            dataset = 'vert'
        else:
            dataset = element
        return self._upcast(self.edge_df[element],
                            self.datasets[dataset][columns])

    def upcast_srce(self, df):
        ''' Reindexes input data to self.edge_idx
        by repeating the values for each source entry
        '''
        return self._upcast(self.edge_df['srce'], df)

    def upcast_trgt(self, df):
        ''' Reindexes input data to self.edge_idx
        by repeating the values for each target entry
        '''
        return self._upcast(self.edge_df['trgt'], df)

    def upcast_face(self, df):
        ''' Reindexes input data to self.edge_idx
        by repeating the values for each face entry
        '''
        return self._upcast(self.edge_df['face'], df)

    def upcast_cell(self, df):
        ''' Reindexes input data to self.edge_idx
        by repeating the values for each cell entry
        '''
        return self._upcast(self.edge_df['cell'], df)

    def _lvl_sum(self, df, lvl):
        df_ = df.copy()
        df_.index = self.edge_mindex
        return df_.sum(level=lvl)

    def sum_srce(self, df):
        return self._lvl_sum(df, 'srce')

    def sum_trgt(self, df):
        return self._lvl_sum(df, 'trgt')

    def sum_face(self, df):
        return self._lvl_sum(df, 'face')

    def sum_cell(self, df):
        return self._lvl_sum(df, 'cell')

    def get_orbits(self, center, periph):
        """Returns a dataframe with a `(center, edge)` MultiIndex with `periph`
        elements.

        Parmeters
        ---------
        center: str,
            the name of the center element for example 'face', 'srce'
        periph: str,
            the name of the periphery elements, for example 'trgt', 'cell'

        Example
        -------
        >>> cell_verts = sheet.get_orbits('face', 'srce')
        >>> cell_verts.loc[45]
        edge
        218    75
        219    78
        220    76
        221    81
        222    90
        223    87
        Name: srce, dtype: int64

        """
        orbits = self.edge_df.groupby(center).apply(
            lambda df: df[periph])
        return orbits

    def face_polygons(self, coords):
        def _get_verts_pos(face):
            try:
                edges = _ordered_edges(face)
            except IndexError:
                #- BC -#
                # I'm still trying to figure
                # out a way to raise this exception
                # with altered datasets but to no avail
                # Leaving it included in coverage.
                log.warning('Face is not closed')
                return np.nan
            return np.array([self.vert_df.loc[idx[0], coords]
                             for idx in edges])
        polys = self.edge_df.groupby('face').apply(_get_verts_pos).dropna()
        return polys

    def get_extra_indices(self):
        """Computes extra indices:

        - `self.free_edges`: half-edges at the epithelium boundary
        - `self.dble_edges`: half-edges inside the epithelium,
          with an opposite
        - `self.east_edges`: half of the `dble_edges`, pointing east
          (figuratively)
        - `self.west_edges`: half of the `dble_edges`, pointing west
           (the order of the east and west edges is conserved, so that
           the ith west half-edge is the opposite of the ith east half-edge)
        - `self.sgle_edges`: joint index over free and east edges, spanning
           the entire graph without double edges
        - `self.wrpd_edges`: joint index over free edges followed by the
           east edges twice, such that a vector over the whole half-edge
            dataframe is wrapped over the single edges
        - `self.srtd_edges`: index over the whole half-edge sorted such that
           the free edges come first, then the east, then the west

        Also computes:
        - `self.Ni`: the number of inside full edges
          (i.e. `len(self.east_edges)`)
        - `self.No`: the number of outside full edges
          (i.e. `len(self.free_edges)`)
        - `self.Nd`: the number of double half edges
          (i.e. `len(self.dble_edges)`)
        - `self.anti_sym`: `pd.Series` with shape `(self.Ne,)`
          with 1 at the free and east half-edges and -1
          at the opposite half-edges.

        Notes
        -----

        - East and west is resepctive to some orientation at the
          moment the indices are computed the partition stays valid as
          long as there are no changes in the topology, so due to vertex
          displacement, 'east' and 'west' might not stay valid. This is
          just a practical naming convention.

        - As the name suggest, this method is not working for edges in
          3D pointing *exactly* north or south, ie iff `edge['dx'] ==
          edge['dy'] == 0`. Until we need or find a better solution,
          we'll just assert it worked.
        """

        if 'opposite' not in self.edge_df.columns:
            self.edge_df['opposite'] = get_opposite(self.edge_df)

        self.dble_edges = self.edge_df[self.edge_df['opposite'] >= 0].index
        theta = np.arctan2(self.edge_df.loc[self.dble_edges, 'dy'],
                           self.edge_df.loc[self.dble_edges, 'dx'])

        self.east_edges = self.edge_df.loc[self.dble_edges][
            (theta >= 0) & (theta < np.pi)].index
        self.west_edges = pd.Index(self.edge_df.loc[
            self.east_edges, 'opposite'].astype(np.int), name='edge')

        self.free_edges = self.edge_df[self.edge_df['opposite'] == -1].index
        self.sgle_edges = self.free_edges.append(self.east_edges)
        self.srtd_edges = self.sgle_edges.append(self.west_edges)

        # Index over the east and free edges, then the opposite indexed
        # by their east counterpart
        self.wrpd_edges = self.sgle_edges.append(self.east_edges)

        self.Ni = self.east_edges.size  # number of inside (east) edges
        self.Nd = self.dble_edges.size  # number of non free half edges
        self.No = self.free_edges.size  # number of free halfedges
        try:
            assert (2*self.Ni + self.No) == self.Ne
            assert self.west_edges.size == self.Ni
            assert self.Nd == 2*self.Ni
        # - BC -#
        # Not sure how to build
        # input data so the partition
        # fails (so we can see
        # if the exception is
        # correctly raised).
        # Leaving it in the coverage
        # anyway.
        except AssertionError:
            raise AssertionError('''
            Inconsistent partition:
            total half-edges: %s
            number of free: %s
            number of east: %s
            number of west: %s''' % (self.Ne, self.No, self.Ni,
                                     self.west_edges.size))

        # Anti symetric vector (1 at east and free edges, -1 at opposite)
        self.anti_sym = pd.Series(np.ones(self.Ne),
                                  index=self.edge_df.index)
        self.anti_sym.loc[self.west_edges] = -1

    def sort_edges_eastwest(self):
        """reorder edges such the free edges are first,
        then the first half of the double edges, then the other half of
        the double edges, this way, each subset of the edges dataframe
        are contiguous.
        """
        self.get_extra_indices()
        self.edge_df = self.edge_df.loc[self.srtd_edges]
        self.reset_index()
        self.reset_topo()
        self.get_extra_indices()

    def get_valid(self):
        """Set true if the face is a closed polygon
        """
        is_valid_face = self.edge_df.groupby('face').apply(_test_valid)
        is_valid = self.upcast_face(is_valid_face)
        if 'cell' in self.data_names:
            is_valid_cell = self.edge_df.groupby('cell').apply(
                _is_closed_cell)
            is_valid = is_valid | self.upcast_cell(is_valid_cell)
        self.edge_df['is_valid'] = is_valid

    def get_invalid(self):
        """Returns a mask over edge for invalid faces
        """
        is_invalid_face = self.edge_df.groupby('face').apply(_test_invalid)
        invalid_edges = self.upcast_face(is_invalid_face)
        if 'cell' in self.data_names:
            is_invalid_cell = 1 - self.edge_df.groupby('cell').apply(
                _is_closed_cell)
            invalid_edges = invalid_edges | self.upcast_cell(is_invalid_cell)
        return invalid_edges

    def sanitize(self):
        """Removes invalid faces and associated vertices
        """
        invalid_edges = self.get_invalid()
        self.remove(invalid_edges)

    def remove(self, edge_out):
        """Remove the edges indexed by `edge_out` associated with all
        the cells and faces containing those edges
        """
        top_level = self.element_names[-1]
        log.info('Removing cells at the {} level'.format(top_level))
        fto_rm = self.edge_df.loc[edge_out, top_level].unique()
        if not len(fto_rm):
            log.info('Nothing to remove')
            return
        fto_rm.sort()
        log.info('{} {} level elements will be removed'.format(len(fto_rm),
                                                               top_level))

        edge_df_ = self.edge_df.set_index(
            top_level,
            append=True).swaplevel(0, 1).sort_index()
        to_rm = np.concatenate([edge_df_.loc[c].index.values
                                for c in fto_rm])
        to_rm.sort()
        self.edge_df = self.edge_df.drop(to_rm)

        remaining_verts = np.unique(self.edge_df[['srce', 'trgt']])
        self.vert_df = self.vert_df.loc[remaining_verts]
        if top_level == 'face':
            self.face_df = self.face_df.drop(fto_rm)
        elif top_level == 'cell':
            remaining_faces = np.unique(self.edge_df['face'])
            self.face_df = self.face_df.loc[remaining_faces]
            self.cell_df = self.cell_df.drop(fto_rm)
        self.reset_index()
        self.reset_topo()

    def cut_out(self, bbox, coords=None):
        """Returns the index of edges with
        at least one vertex outside of the
        bounding box

        Parameters
        ----------
        bbox : sequence of shape (dim, 2)
             the bounding box as (min, max) pairs for
             each coordinates.
        coords : list of str of len dim
             the coords corresponding to the bbox.
        """
        if coords is None:
            coords = self.coords
        outs = pd.DataFrame(index=self.edge_df.index,
                            columns=coords)
        for c, bounds in zip(coords, bbox):
            out_vert_ = ((self.vert_df[c] < bounds[0]) |
                         (self.vert_df[c] > bounds[1]))
            outs[c] = (self.upcast_srce(out_vert_) |
                       self.upcast_trgt(out_vert_))

        edge_out = outs.sum(axis=1).astype(np.bool)
        return self.edge_df[edge_out].index

    def set_bbox(self, margin=1.):
        '''Sets the attribute `bbox` with pairs of values bellow
        and above the min and max of the vert coords, with a margin.
        '''
        self.bbox = np.array([[self.vert_df[c].min() - margin,
                               self.vert_df[c].max() + margin]
                              for c in self.coords])

    def reset_index(self):

        new_vertidx = pd.Series(np.arange(self.vert_df.shape[0]),
                                index=self.vert_df.index)
        self.edge_df['srce'] = self.upcast_srce(new_vertidx)
        self.edge_df['trgt'] = self.upcast_trgt(new_vertidx)
        new_fidx = pd.Series(np.arange(self.face_df.shape[0]),
                             index=self.face_df.index)
        self.edge_df['face'] = self.upcast_face(new_fidx)

        self.vert_df.reset_index(drop=True, inplace=True)
        self.vert_df.index.name = 'vert'

        self.face_df.reset_index(drop=True, inplace=True)
        self.face_df.index.name = 'face'

        if 'cell' in self.data_names:
            new_cidx = pd.Series(np.arange(self.cell_df.shape[0]),
                                 index=self.cell_df.index)
            self.edge_df['cell'] = self.upcast_cell(new_cidx)
            self.cell_df.reset_index(drop=True, inplace=True)
            self.cell_df.index.name = 'cell'

        self.edge_df.reset_index(drop=True, inplace=True)
        self.edge_df.index.name = 'edge'

    def triangular_mesh(self, coords):
        '''
        Return a triangulation of an epithelial sheet (2D in a 3D space),
        with added edges between face barycenters and junction vertices.

        Parameters
        ----------
        coords: list of str:
          pair of coordinates corresponding to column names
          for self.face_df and self.vert_df

        Returns
        -------
        vertices: (self.Nf+self.Nv, 3) ndarray
           all the vertices' coordinates
        triangles: (self.Ne, 3) ndarray of ints
           triple of the vertices' indexes forming
           the triangular elements. For each junction edge, this is simply
           the index (srce, trgt, face). This is correctly oriented.
        face_mask: (self.Nf + self.Nv,) mask with 1 iff the vertex corresponds
           to a face center
        '''

        vertices = np.concatenate((self.face_df[coords],
                                   self.vert_df[coords]), axis=0)

        # edge indices as (Nf + Nv) * 3 array
        triangles = self.edge_df[['srce', 'trgt', 'face']].values
        # The src, trgt, face triangle is correctly oriented
        # both vert_idx cols are shifted by Nf
        triangles[:, :2] += self.Nf

        face_mask = np.arange(self.Nf + self.Nv) < self.Nf
        return vertices, triangles, face_mask

    def vertex_mesh(self, coords, vertex_normals=True):
        ''' Returns the vertex coordinates and a list of vertex indices
        for each face of the tissue.
        If `vertex_normals` is True, also returns the normals of each vertex
        (set as the average of the vertex' edges), suitable for .OBJ export
        '''
        # - BC -#
        # This method only works on 3D-epithelium
        vertices = self.vert_df[coords]
        faces = self.edge_df.groupby('face').apply(ordered_vert_idxs)
        faces = faces.dropna()
        if vertex_normals:
            normals = (self.edge_df.groupby('srce')[self.ncoords].mean() +
                       self.edge_df.groupby('trgt')[self.ncoords].mean()) / 2.
            return vertices.values, faces.values, normals.values
        return vertices.values, faces.values

    def validate_closed_cells(self):
        is_closed = self.edge_df.groupby('cell').apply(_is_closed_cell)
        return is_closed


def _ordered_edges(face_edges):
    """Returns "srce", "trgt" and "face" indices
    organized clockwise for each edge.

    Parameters
    ----------
    face_edges: `pd.DataFrame`
        exerpt of an edge_df for a single face

    Returns
    -------
    edges: list of 3 ints
        srce, trgt, face indices, ordered
    """
    srces, trgts, faces = face_edges[['srce', 'trgt', 'face']].values.T
    srce, trgt, face_ = srces[0], trgts[0], faces[0]
    edges = [[srce, trgt, face_]]
    for face_ in faces[1:]:
        srce, trgt = trgt, trgts[srces == trgt][0]
        edges.append([srce, trgt, face_])
    return edges


def ordered_vert_idxs(face):
    try:
        return [idxs[0] for idxs in _ordered_edges(face)]
    except IndexError:
        return np.nan


def _test_invalid(face):
    """ Returns true iff the source and target sets of the faces polygon
    are different
    """
    s1 = set(face['srce'])
    s2 = set(face['trgt'])
    return s1 != s2


def _test_valid(face):
    """ Returns true iff all sources are also targets for the faces polygon
    """
    s1 = set(face['srce'])
    s2 = set(face['trgt'])
    return s1 == s2


def get_opposite(edge_df):
    """
    Returns the indices opposite to the edges in `edge_df`
    """
    st_indexed = edge_df[['srce', 'trgt']].reset_index().set_index(
        ['srce', 'trgt'], drop=False)
    flipped = st_indexed.index.swaplevel(0, 1)
    flipped.names = ['srce', 'trgt']

    opposite = st_indexed.loc[flipped, 'edge'].values
    opposite[np.isnan(opposite)] = -1

    return opposite.astype(np.int)


def _is_closed_cell(e_df):
    edges = e_df[['srce', 'trgt']]
    for e, (srce, trgt) in edges.iterrows():
        if (edges[(edges['srce'] == trgt) &
                  (edges['trgt'] == srce)].index.size != 1):
            return False
    return True
