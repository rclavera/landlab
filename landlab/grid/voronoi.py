#! /usr/env/python
"""
Python implementation of VoronoiDelaunayGrid, a class used to create and manage
unstructured, irregular grids for 2D numerical models.

Do NOT add new documentation here. Grid documentation is now built in a semi-
automated fashion. To modify the text seen on the web, edit the files
`docs/text_for_[gridfile].py.txt`.
"""
import numpy as np
from scipy.spatial import Voronoi

from landlab.core.utils import (
    argsort_points_by_x_then_y,
    as_id_array,
    sort_points_by_x_then_y,
)

from ..graph import DualVoronoiGraph
from .base import BAD_INDEX_VALUE, ModelGrid
from .decorators import return_readonly_id_array


def simple_poly_area(x, y):
    """Calculates and returns the area of a 2-D simple polygon.

    Input vertices must be in sequence (clockwise or counterclockwise). *x*
    and *y* are arrays that give the x- and y-axis coordinates of the
    polygon's vertices.

    Parameters
    ----------
    x : ndarray
        x-coordinates of of polygon vertices.
    y : ndarray
        y-coordinates of of polygon vertices.

    Returns
    -------
    out : float
        Area of the polygon

    Examples
    --------
    >>> import numpy as np
    >>> from landlab.grid.voronoi import simple_poly_area
    >>> x = np.array([3., 1., 1., 3.])
    >>> y = np.array([1.5, 1.5, 0.5, 0.5])
    >>> simple_poly_area(x, y)
    2.0

    If the input coordinate arrays are 2D, calculate the area of each polygon.
    Note that when used in this mode, all polygons must have the same
    number of vertices, and polygon vertices are listed column-by-column.

    >>> x = np.array([[ 3.,  1.,  1.,  3.],
    ...               [-2., -2., -1., -1.]]).T
    >>> y = np.array([[1.5, 1.5, 0.5, 0.5],
    ...               [ 0.,  1.,  2.,  0.]]).T
    >>> simple_poly_area(x, y)
    array([ 2. ,  1.5])
    """
    # For short arrays (less than about 100 elements) it seems that the
    # Python sum is faster than the numpy sum. Likewise for the Python
    # built-in abs.
    return 0.5 * abs(sum(x[:-1] * y[1:] - x[1:] * y[:-1]) + x[-1] * y[0] - x[0] * y[-1])


class VoronoiDelaunayGrid(DualVoronoiGraph, ModelGrid):

    """
    This inherited class implements an unstructured grid in which cells are
    Voronoi polygons and nodes are connected by a Delaunay triangulation. Uses
    scipy.spatial module to build the triangulation.

    Create an unstructured grid from points whose coordinates are given
    by the arrays *x*, *y*.

    Parameters
    ----------
    x : array_like
        x-coordinate of points
    y : array_like
        y-coordinate of points
    reorient_links (optional) : bool
        whether to point all links to the upper-right quadrant

    Returns
    -------
    VoronoiDelaunayGrid
        A newly-created grid.

    Examples
    --------
    >>> from numpy.random import rand
    >>> from landlab.grid import VoronoiDelaunayGrid
    >>> x, y = rand(25), rand(25)
    >>> vmg = VoronoiDelaunayGrid(x, y)  # node_x_coords, node_y_coords
    >>> vmg.number_of_nodes
    25

    >>> import numpy as np
    >>> x = [0, 0.1, 0.2, 0.3,
    ...      1, 1.1, 1.2, 1.3,
    ...      2, 2.1, 2.2, 2.3,]
    >>> y = [0, 1, 2, 3,
    ...      0, 1, 2, 3,
    ...      0, 1, 2, 3]
    >>> vmg = VoronoiDelaunayGrid(x, y)
    >>> vmg.node_x # doctest: +NORMALIZE_WHITESPACE
    array([ 0. ,  1. ,  2. ,
            0.1,  1.1,  2.1,
            0.2,  1.2,  2.2,
            0.3,  1.3,  2.3])
    >>> vmg.node_y # doctest: +NORMALIZE_WHITESPACE
    array([ 0.,  0.,  0.,
            1.,  1.,  1.,
            2.,  2.,  2.,
            3.,  3.,  3.])
    >>> vmg.adjacent_nodes_at_node
    array([[ 1,  3, -1, -1, -1, -1],
           [ 2,  4,  3,  0, -1, -1],
           [ 5,  4,  1, -1, -1, -1],
           [ 4,  6,  0,  1, -1, -1],
           [ 5,  7,  6,  3,  1,  2],
           [ 8,  7,  4,  2, -1, -1],
           [ 7,  9,  3,  4, -1, -1],
           [ 8, 10,  9,  6,  4,  5],
           [11, 10,  7,  5, -1, -1],
           [10,  6,  7, -1, -1, -1],
           [11,  9,  7,  8, -1, -1],
           [10,  8, -1, -1, -1, -1]])
    """

    def __init__(
        self,
        x=None,
        y=None,
        reorient_links=True,
        xy_of_reference=(0.0, 0.0),
        xy_axis_name=("x", "y"),
        xy_axis_units="-",
    ):
        """
        Create a Voronoi Delaunay grid from a set of points.

        Create an unstructured grid from points whose coordinates are given
        by the arrays *x*, *y*.

        Parameters
        ----------
        x : array_like
            x-coordinate of points
        y : array_like
            y-coordinate of points
        reorient_links (optional) : bool
            whether to point all links to the upper-right quadrant
        xy_of_reference : tuple, optional
            Coordinate value in projected space of (0., 0.)
            Default is (0., 0.)

        Returns
        -------
        VoronoiDelaunayGrid
            A newly-created grid.

        Examples
        --------
        >>> from numpy.random import rand
        >>> from landlab.grid import VoronoiDelaunayGrid
        >>> x, y = rand(25), rand(25)
        >>> vmg = VoronoiDelaunayGrid(x, y)  # node_x_coords, node_y_coords
        >>> vmg.number_of_nodes
        25
        """
        DualVoronoiGraph.__init__(self, (y, x), sort=True)
        ModelGrid.__init__(
            self,
            xy_axis_name=xy_axis_name,
            xy_axis_units=xy_axis_units,
            xy_of_reference=xy_of_reference,
        )

        self._node_status = np.full(self.number_of_nodes,
                                    self.BC_NODE_IS_CORE, dtype=np.uint8)
        self._node_status[self.perimeter_nodes] = self.BC_NODE_IS_FIXED_VALUE

        # DualVoronoiGraph.__init__(self, (y, x), **kwds)
        # ModelGrid.__init__(self, **kwds)

    @classmethod
    def from_dict(cls, kwds):
        args = (kwds.pop("x"), kwds.pop("y"))
        return cls(*args, **kwds)

    def _create_patches_from_delaunay_diagram(self, pts, vor):
        """
        Uses a delaunay diagram drawn from the provided points to
        generate an array of patches and patch-node-link connectivity.
        Returns ...
        DEJH, 10/3/14, modified May 16.
        """
        from scipy.spatial import Delaunay
        from landlab.core.utils import anticlockwise_argsort_points_multiline
        from .cfuncs import create_patches_at_element, create_links_at_patch

        tri = Delaunay(pts)
        assert np.array_equal(tri.points, vor.points)
        nodata = -1
        self._nodes_at_patch = as_id_array(tri.simplices)
        # self._nodes_at_patch = np.empty_like(_nodes_at_patch)
        self._number_of_patches = tri.simplices.shape[0]
        # get the patches in order:
        patches_xy = np.empty((self._number_of_patches, 2), dtype=float)
        patches_xy[:, 0] = np.mean(self.node_x[self._nodes_at_patch], axis=1)
        patches_xy[:, 1] = np.mean(self.node_y[self._nodes_at_patch], axis=1)
        orderforsort = argsort_points_by_x_then_y(patches_xy)
        self._nodes_at_patch = self._nodes_at_patch[orderforsort, :]
        patches_xy = patches_xy[orderforsort, :]

        # perform a CCW sort without a line-by-line loop:
        patch_nodes_x = self.node_x[self._nodes_at_patch]
        patch_nodes_y = self.node_y[self._nodes_at_patch]
        anticlockwise_argsort_points_multiline(
            patch_nodes_x, patch_nodes_y, out=self._nodes_at_patch
        )

        # need to build a squared off, masked array of the patches_at_node
        # the max number of patches for a node in the grid is the max sides of
        # the side-iest voronoi region.
        max_dimension = len(max(vor.regions, key=len))

        self._patches_at_node = np.full(
            (self.number_of_nodes, max_dimension), nodata, dtype=int
        )

        self._nodes_at_patch = as_id_array(self._nodes_at_patch)
        self._patches_at_node = as_id_array(self._patches_at_node)

        create_patches_at_element(
            self._nodes_at_patch, self.number_of_nodes, self._patches_at_node
        )

        # build the patch-link connectivity:
        self._links_at_patch = np.empty((self._number_of_patches, 3), dtype=int)
        create_links_at_patch(
            self._nodes_at_patch,
            self._links_at_node,
            self._number_of_patches,
            self._links_at_patch,
        )
        patch_links_x = self.x_of_link[self._links_at_patch]
        patch_links_y = self.y_of_link[self._links_at_patch]
        anticlockwise_argsort_points_multiline(
            patch_links_x, patch_links_y, out=self._links_at_patch
        )

        self._patches_at_link = np.empty((self.number_of_links, 2), dtype=int)
        self._patches_at_link.fill(-1)
        create_patches_at_element(
            self._links_at_patch, self.number_of_links, self._patches_at_link
        )
        # a sort of the links will be performed here once we have corners

        self._patches_created = True

    def save(self, path, clobber=False):
        """Save a grid and fields.

        This method uses pickle to save a Voronoi grid as a pickle file.
        At the time of coding, this is the only convenient output format
        for Voronoi grids, but support for netCDF is likely coming.

        All fields will be saved, along with the grid.

        The recommended suffix for the save file is '.grid'. This will
        be added to your save if you don't include it.

        This method is equivalent to
        :py:func:`~landlab.io.native_landlab.save_grid`, and
        :py:func:`~landlab.io.native_landlab.load_grid` can be used to
        load these files.

        Caution: Pickling can be slow, and can produce very large files.
        Caution 2: Future updates to Landlab could potentially render old
        saves unloadable.

        Parameters
        ----------
        path : str
            Path to output file.
        clobber : bool (defaults to false)
            Set to true to allow overwriting

        Examples
        --------
        >>> from landlab import VoronoiDelaunayGrid
        >>> import numpy as np
        >>> import os
        >>> x = np.random.rand(20)
        >>> y = np.random.rand(20)
        >>> vmg = VoronoiDelaunayGrid(x,y)
        >>> vmg.save('./mytestsave.grid')
        >>> os.remove('mytestsave.grid') #to remove traces of this test

        LLCATS: GINF
        """
        import os
        import pickle

        if os.path.exists(path) and not clobber:
            raise ValueError("file exists")

        (base, ext) = os.path.splitext(path)
        if ext != ".grid":
            ext = ext + ".grid"
        path = base + ext

        with open(path, "wb") as fp:
            pickle.dump(self, fp)
