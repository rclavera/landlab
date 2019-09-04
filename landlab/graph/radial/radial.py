import numpy as np

from ...utils.decorators import read_only_array
from ..voronoi.voronoi import DelaunayGraph


class RadialGraphLayout:
    @staticmethod
    def number_of_nodes(shape):
        return np.sum(np.arange(1, shape[0] + 1)) * shape[1] + 1

    @staticmethod
    def xy_of_node(shape, spacing=1.0, xy_of_center=(0.0, 0.0)):
        """Create the node layout for a radial grid.

        Examples
        --------
        >>> import numpy as np
        >>> from landlab.graph.radial.radial import RadialGraphLayout
        >>> x, y = RadialGraphLayout.xy_of_node((1, 6))
        >>> x
        array([ 0. ,  1. ,  0.5, -0.5, -1. , -0.5,  0.5])
        >>> np.round(y / np.sin(np.pi / 3.0))
        array([ 0.,  0.,  1.,  1.,  0., -1., -1.])
        """
        n_rings, n_points = shape
        n_nodes = RadialGraphLayout.number_of_nodes(shape)

        x = np.empty((n_nodes,), dtype=float)
        y = np.empty((n_nodes,), dtype=float)
        # nodes_per_ring = np.round(2. * np.pi * np.arange(1, n_rings + 1)).astype(int)
        # n_nodes = np.sum(nodes_per_ring) + 1

        x[0] = y[0] = 0.0
        offset = 1
        # for ring in range(0, n_rings):
        for ring in range(1, n_rings + 1):
            # rho = spacing * (ring + 1)
            rho = spacing * ring
            d_theta = np.pi * 2 / (ring * shape[1])
            theta = np.arange(ring * shape[1]) * d_theta

            y[offset : offset + len(theta)] = rho * np.sin(theta)
            x[offset : offset + len(theta)] = rho * np.cos(theta)
            # d_theta = 2. * np.pi / nodes_per_ring[ring]
            # theta = np.arange(nodes_per_ring[ring]) * d_theta

            offset += len(theta)

        x = np.round(x, decimals=6)
        y = np.round(y, decimals=6)

        x += xy_of_center[0]
        y += xy_of_center[1]

        return (x, y)


class RadialNodeLayout(object):
    def __init__(self, n_rings, spacing=1.0, origin=0.0):
        self._n_rings = n_rings

        self._n_rings = int(n_rings)
        self._spacing_of_rings = float(spacing)
        self._origin = tuple(np.broadcast_to(origin, (2,)).astype(float))

        # self._ring_at_node = np.repeat(np.arange(self.number_of_rings),
        #                                 self.nodes_per_ring)

        # y_of_node = graph.radius_at_node * np.sin(graph.angle_at_node) - origin[0]
        # x_of_node = graph.radius_at_node * np.cos(graph.angle_at_node) - origin[1]

        # sorted_nodes = argsort_points_by_x_then_y((x_of_node, y_of_node))

    @property
    def origin(self):
        return self._origin

    @property
    def y_of_node(self):
        return self.radius_at_node * np.sin(self.angle_at_node) - self.origin[0]

    @property
    def x_of_node(self):
        return self.radius_at_node * np.cos(self.angle_at_node) - self.origin[1]

    @property
    def xy_of_node(self):
        return self.x_of_node, self.y_of_node

    @property
    def number_of_rings(self):
        return self._n_rings

    @property
    def spacing_of_rings(self):
        return self._spacing_of_rings

    @property
    @read_only_array
    def radius_of_ring(self):
        return np.arange(0, self.number_of_rings, dtype=float) * self.spacing_of_rings

    @property
    @read_only_array
    def ring_at_node(self):
        return np.repeat(np.arange(self.number_of_rings), self.nodes_per_ring)

    @property
    @read_only_array
    def radius_at_node(self):
        return self.radius_of_ring[self.ring_at_node]

    @property
    @read_only_array
    def angle_at_node(self):
        angle_at_node = np.empty(self.nodes_per_ring.sum(), dtype=float)
        angle_at_node[0] = 0.0
        offset = 1
        for n_nodes in self.nodes_per_ring[1:]:
            angles, step = np.linspace(
                0.0, 2 * np.pi, n_nodes, endpoint=False, retstep=True, dtype=float
            )
            angle_at_node[offset : offset + n_nodes] = np.add(
                angles, 0.5 * step, out=angles
            )
            offset += n_nodes
        return angle_at_node

    @property
    @read_only_array
    def nodes_per_ring(self):
        # nodes_per_ring = np.arange(self.number_of_rings, dtype=int) * self.shape[1]
        # nodes_per_ring[0] = 1
        # return nodes_per_ring
        nodes_per_ring = np.empty(self.number_of_rings, dtype=int)
        nodes_per_ring[0] = 1
        nodes_per_ring[1:] = np.round(2.0 * np.pi * np.arange(1, self.number_of_rings))
        return nodes_per_ring


class RadialGraphExtras(object):
    @property
    def shape(self):
        return self._shape

    @property
    def spacing(self):
        return self._spacing

    @property
    def origin(self):
        return self._origin

    @property
    def number_of_rings(self):
        return self.shape[0]

    @property
    def spacing_of_rings(self):
        return self.spacing

    @property
    # @store_result_in_grid()
    @read_only_array
    def radius_of_ring(self):
        return np.arange(0, self.number_of_rings, dtype=float) * self.spacing_of_rings

    @property
    # @store_result_in_grid()
    @read_only_array
    def angle_spacing_of_ring(self):
        return 2.0 * np.pi / self.nodes_per_ring

    @property
    # @store_result_in_grid()
    @read_only_array
    def nodes_per_ring(self):
        # nodes_per_ring = np.arange(self.number_of_rings, dtype=int) * self.shape[1]
        # nodes_per_ring[0] = 1
        # return nodes_per_ring
        nodes_per_ring = np.empty(self.number_of_rings, dtype=int)
        nodes_per_ring[0] = 1
        nodes_per_ring[1:] = np.round(2.0 * np.pi * np.arange(1, self.number_of_rings))
        return nodes_per_ring

    @property
    # @store_result_in_grid()
    @read_only_array
    def ring_at_node(self):
        return np.repeat(np.arange(self.number_of_rings), self.nodes_per_ring)

    @property
    # @store_result_in_grid()
    @read_only_array
    def radius_at_node(self):
        return self.radius_of_ring[self.ring_at_node]

    @property
    # @store_result_in_grid()
    @read_only_array
    def angle_at_node(self):
        angle_at_node = np.empty(self.nodes_per_ring.sum(), dtype=float)
        angle_at_node[0] = 0.0
        offset = 1
        for n_nodes in self.nodes_per_ring[1:]:
            angles, step = np.linspace(
                0.0, 2 * np.pi, n_nodes, endpoint=False, retstep=True, dtype=float
            )
            angle_at_node[offset : offset + n_nodes] = np.add(
                angles, 0.5 * step, out=angles
            )
            offset += n_nodes
        return angle_at_node

    def empty_cache(self):
        for attr in (
            "_angle_at_node",
            "_radius_at_node",
            "_ring_at_node",
            "_nodes_per_ring",
            "_angle_spacing_of_ring",
            "_radius_of_ring",
        ):
            try:
                del self.__dict__[attr]
            except KeyError:
                pass


class RadialGraph(RadialGraphExtras, DelaunayGraph):

    """Graph of a series of points on concentric circles.

    Examples
    --------
    >>> import numpy as np
    >>> from landlab.graph import RadialGraph
    >>> graph = RadialGraph((1, 4), sort=True)
    >>> graph.number_of_nodes
    5
    >>> graph.y_of_node
    array([-1.,  0.,  0.,  0.,  1.])
    >>> graph.x_of_node
    array([ 0., -1.,  0.,  1.,  0.])
    """

    def __init__(self, shape, spacing=1.0, xy_of_center=(0.0, 0.0), sort=False):
        """Create a structured grid of triangles arranged radially.

        Parameters
        ----------
        shape : tuple of int
            Shape of the graph as number of rings and number of points
            in the first ring.
        spacing : float, optional
            Spacing between rings.
        xy_of_center : tuple of float, optional
            Coordinates of the node at the center of the grid.
        """
        try:
            spacing = float(spacing)
        except TypeError:
            raise TypeError("spacing must be a float")

        xy_of_center = tuple(np.broadcast_to(xy_of_center, 2))

        x_of_node, y_of_node = RadialGraphLayout.xy_of_node(
            shape, spacing=spacing, xy_of_center=xy_of_center
        )

        self._ring_spacing = spacing
        self._shape = tuple(shape)
        self._xy_of_center = xy_of_center

        DelaunayGraph.__init__(self, (y_of_node, x_of_node))

        if sort:
            self.sort()

    @property
    def xy_of_center(self):
        return self._xy_of_center

    @property
    def number_of_rings(self):
        """Number of node rings in grid.

        Returns
        -------
        int
            The number of node rings in the radial grid (not counting the
            center node).

        Examples
        --------
        >>> import numpy as np
        >>> from landlab.graph import RadialGraph
        >>> graph = RadialGraph((1, 4))
        >>> graph.number_of_rings
        1

        LLCATS: GINF
        """
        return self._shape[0]

    @property
    def spacing_of_rings(self):
        """Fixed distance between rings.

        Returns
        -------
        ndarray of float
            The distance from the center node of each node.

        >>> from landlab.graph import RadialGraph
        >>> graph = RadialGraph((2, 6), spacing=2.)
        >>> graph.spacing_of_rings
        2.0

        LLCATS: GINF MEAS
        """
        return self._ring_spacing

    @property
    def radius_at_node(self):
        """Distance for center node to each node.

        Returns
        -------
        ndarray of float
            The distance from the center node of each node.

        >>> from landlab.graph import RadialGraph
        >>> graph = RadialGraph((2, 6), sort=True)
        >>> np.round(graph.radius_at_node, 3)
        array([ 2.,  2.,  2.,  2.,  2.,  1.,  1.,  2.,  1.,  0.,  1.,  2.,  1.,
                1.,  2.,  2.,  2.,  2.,  2.])

        LLCATS: NINF MEAS
        """
        return np.sqrt(
            np.square(self.x_of_node - self._xy_of_center[0])
            + np.square(self.y_of_node - self._xy_of_center[1])
        )

    @property
    def number_of_nodes_in_ring(self):
        """Number of nodes in each ring.

        Returns
        -------
        ndarray of int
            Number of nodes in each ring, excluding the center node.

        >>> from landlab.graph import RadialGraph
        >>> graph = RadialGraph((4, 6))
        >>> graph.number_of_nodes_in_ring
        array([ 6, 12, 24, 48])

        LLCATS: NINF MEAS
        """
        return self._shape[1] * 2 ** np.arange(self.number_of_rings)
