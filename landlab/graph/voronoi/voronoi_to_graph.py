"""
Examples
--------
>>> from landlab.graph.voronoi.voronoi_to_graph import VoronoiToGraph
>>> from scipy.spatial import Voronoi
>>> import numpy as np
>>> dx, dy = 1., np.sin(np.pi / 3.)
>>> points = [
...     [0., 0.], [dx, 0.], [2. * dx, 0.],
...     [dx * .5, dy], [dx * 1.5, dy], [dx * 2.5, dy],
...     [0., 2. * dy], [dx, 2. * dy], [2. * dx, 3. * dy]]
>>> voronoi = Voronoi(points)
"""
import re
from itertools import combinations

import numpy as np
import xarray as xr
from scipy.spatial import Delaunay, Voronoi

from ...utils import jaggedarray
from ..sort.sort import reverse_one_to_one
from ..sort.intpair import pair_isin


class VoronoiDelaunay(object):
    def __init__(self, xy_of_node):
        # What we need:
        # * [x] xy_of_node
        # * [x] nodes_at_link
        # * [x] links_at_patch
        # And then for the dual graph:
        # * [x] xy_of_corner
        # * [x] corners_at_face
        # * [x] faces_at_cell
        # And the to link the graphs:
        # * [x] node_at_cell
        # * [x] nodes_at_face
        # points == xy_of_node
        # vertices == xy_of_corner
        # regions == corners_at_cell
        # ridge_vertices == corners_at_face
        # ridge_points == nodes_at_face
        # point_region == node_at_cell

        delaunay = Delaunay(xy_of_node)
        voronoi = Voronoi(xy_of_node)

        mesh = xr.Dataset(
            {
                "node": xr.DataArray(
                    data=np.arange(len(voronoi.points)),
                    coords={
                        "x_of_node": xr.DataArray(voronoi.points[:, 0], dims=("node",)),
                        "y_of_node": xr.DataArray(voronoi.points[:, 1], dims=("node",)),
                    },
                    dims=("node",),
                ),
                "corner": xr.DataArray(
                    data=np.arange(len(voronoi.vertices)),
                    coords={
                        "x_of_corner": xr.DataArray(
                            voronoi.vertices[:, 0], dims=("corner",)
                        ),
                        "y_of_corner": xr.DataArray(
                            voronoi.vertices[:, 1], dims=("corner",)
                        ),
                    },
                    dims=("corner",),
                ),
            }
        )
        mesh.update(
            {
                "nodes_at_link": xr.DataArray(
                    np.asarray(voronoi.ridge_points, dtype=int), dims=("link", "Two")
                ),
                "nodes_at_patch": xr.DataArray(
                    np.asarray(delaunay.simplices, dtype=int), dims=("patch", "Three")
                ),
                "corners_at_face": xr.DataArray(
                    voronoi.ridge_vertices, dims=("face", "Two")
                ),
                "corners_at_cell": xr.DataArray(
                    self._corners_at_cell(voronoi.regions),
                    dims=("cell", "max_corners_per_cell"),
                ),
                "n_corners_at_cell": xr.DataArray(
                    [len(cell) for cell in voronoi.regions], dims=("cell",)
                ),
                "nodes_at_face": xr.DataArray(
                    np.asarray(voronoi.ridge_points, dtype=int), dims=("face", "Two")
                ),
                "cell_at_node": xr.DataArray(voronoi.point_region, dims=("node",)),
            }
        )
        self._mesh = mesh

    @staticmethod
    def _corners_at_cell(regions):
        jagged = jaggedarray.JaggedArray(regions)
        return np.asarray(
            jaggedarray.unravel(jagged.array, jagged.offset, pad=-1), dtype=int
        )

    @property
    def number_of_nodes(self):
        return self._mesh.dims["node"]

    @property
    def number_of_links(self):
        return self._mesh.dims["link"]

    @property
    def number_of_patches(self):
        return self._mesh.dims["patch"]

    @property
    def number_of_corners(self):
        return self._mesh.dims["corner"]

    @property
    def number_of_faces(self):
        return self._mesh.dims["face"]

    @property
    def number_of_cells(self):
        return self._mesh.dims["cell"]

    @property
    def x_of_node(self):
        return self._mesh["x_of_node"].values

    @property
    def y_of_node(self):
        return self._mesh["y_of_node"].values

    @property
    def x_of_corner(self):
        return self._mesh["x_of_corner"].values

    @property
    def y_of_corner(self):
        return self._mesh["y_of_corner"].values

    @property
    def nodes_at_patch(self):
        return self._mesh["nodes_at_patch"].values

    @property
    def nodes_at_link(self):
        return self._mesh["nodes_at_link"].values

    @property
    def nodes_at_face(self):
        return self._mesh["nodes_at_face"].values

    @property
    def corners_at_face(self):
        return self._mesh["corners_at_face"].values

    @property
    def corners_at_cell(self):
        return self._mesh["corners_at_cell"].values

    @property
    def n_corners_at_cell(self):
        return self._mesh["n_corners_at_cell"].values

    @property
    def cell_at_node(self):
        return self._mesh["cell_at_node"].values


class VoronoiDelaunayToGraph(VoronoiDelaunay):
    def __init__(self, xy_of_node, perimeter_links=None):
        super(VoronoiDelaunayToGraph, self).__init__(xy_of_node)

        if perimeter_links is not None:
            perimeter_links = np.asarray(perimeter_links, dtype=int)
        self._perimeter_links = perimeter_links

        mesh = self._mesh
        mesh.update(
            {
                "links_at_patch": xr.DataArray(
                    self._links_at_patch(
                        mesh["nodes_at_link"].data, mesh["nodes_at_patch"].data
                    ),
                    dims=("patch", "Three"),
                ),
                "node_at_cell": xr.DataArray(
                    reverse_one_to_one(mesh["cell_at_node"].data), dims=("cell",)
                ),
            }
        )
        mesh.update(
            {
                "faces_at_cell": xr.DataArray(
                    self._links_at_patch(
                        mesh["corners_at_face"].data, mesh["corners_at_cell"].data
                    ),
                    dims=("cell", "max_faces_per_cell"),
                )
            }
        )

        self.drop_corners(self.unbound_corners())
        self.drop_perimeter_faces()
        self.drop_perimeter_cells()

    @staticmethod
    def _links_at_patch(nodes_at_link, nodes_at_patch):
        from ..sort.intpair import map_rolling_pairs_to_values

        links_at_patch_ = np.empty_like(nodes_at_patch, dtype=int)

        link_at_nodes = np.lexsort((nodes_at_link[:, 1], nodes_at_link[:, 0]))
        map_rolling_pairs_to_values(
            (nodes_at_link[link_at_nodes], link_at_nodes), nodes_at_patch, links_at_patch_
        )

        return links_at_patch_

        link_at_nodes = dict()
        for link, link_nodes in enumerate(nodes_at_link):
            link_at_nodes[tuple(link_nodes)] = link
            link_at_nodes[tuple(link_nodes[::-1])] = link

        links_at_patch_ = np.empty_like(nodes_at_patch, dtype=int)
        # for patch, patch_nodes in enumerate(nodes_at_patch):
        #     links_at_patch_[patch] = [
        #         link_at_nodes.get(pair, -1) for pair in zip(patch_nodes, np.roll(patch_nodes, 1))
        #     ]
        tail_nodes_at_patch = np.roll(nodes_at_patch, 1, axis=1)
        for patch, (heads, tails) in enumerate(
            zip(nodes_at_patch, tail_nodes_at_patch)
        ):
            links_at_patch_[patch] = [
                link_at_nodes.get(pair, -1) for pair in zip(heads, tails)
            ]

        return links_at_patch_

    def is_perimeter_face(self):
        return np.any(self.corners_at_face == -1, axis=1)

    def is_perimeter_cell(self):
        from .ext.voronoi import id_array_is_valid, id_array_contains

        is_perimeter_cell = np.empty(len(self.n_corners_at_cell), dtype=bool)
        id_array_contains(
            self.corners_at_cell,
            self.n_corners_at_cell,
            -1,
            is_perimeter_cell.view(dtype=np.uint8),
        )
        is_perimeter_cell |= self.n_corners_at_cell < 3

        # is_perimeter_cell = np.empty(len(self.n_corners_at_cell), dtype=bool)
        # id_array_is_valid(
        #     self.corners_at_cell,
        #     self.n_corners_at_cell,
        #     is_perimeter_cell.view(dtype=np.uint8),
        # )
        # is_perimeter_cell &= self.n_corners_at_cell >= 3

        return is_perimeter_cell

        is_big_cell = self.n_corners_at_cell >= 3

        is_perimeter_cell = np.full(len(self.n_corners_at_cell), False)
        is_perimeter_cell[~is_big_cell] = True

        for cell in np.where(is_big_cell)[0]:
            n_corners = self.n_corners_at_cell[cell]
            if -1 in self.corners_at_cell[cell][:n_corners]:
                is_perimeter_cell[cell] = True

        return is_perimeter_cell

    def is_perimeter_link(self):
        if self._perimeter_links is not None:
            # links = set()
            # for nodes in self._perimeter_links:
            #     links.add(tuple(nodes))
            #     links.add(tuple(nodes[::-1]))
            # is_perimeter_link = np.full(len(self.nodes_at_link), False)
            # for link, link_nodes in enumerate(self.nodes_at_link):
            #     if tuple(link_nodes) in links:
            #         is_perimeter_link[link] = True
            #         links.remove(tuple(link_nodes))
            #         links.remove(tuple(link_nodes[::-1]))
            is_perimeter_link = np.empty(len(self.nodes_at_link), dtype=bool)
            pair_isin(
                self._perimeter_links,
                self.nodes_at_link,
                is_perimeter_link.view(dtype=np.uint8),
            )
        else:
            is_perimeter_link = self.is_perimeter_face()
        return is_perimeter_link

    def unbound_corners(self):
        faces_to_drop = np.where(self.is_perimeter_face() & ~self.is_perimeter_link())

        unbound_corners = self.corners_at_face[faces_to_drop].reshape((-1,))

        return np.unique(unbound_corners[unbound_corners >= 0])

    def is_bound_corner(self):
        corners = np.full(self._mesh.dims["corner"], True)
        corners[self.unbound_corners()] = False

        return corners

    def drop_corners(self, corners):
        if len(corners) == 0:
            return

        # Remove the corners
        corners_to_drop = np.asarray(corners, dtype=int)
        self.drop_element(corners_to_drop, at="corner")

        # Remove bad links
        is_a_link = np.any(self._mesh["corners_at_face"].data != -1, axis=1)
        self.drop_element(np.where(~is_a_link)[0], at="link")

        # Remove the bad patches
        is_a_patch = np.all(self._mesh["links_at_patch"] >= 0, axis=1)
        self.drop_element(np.where(~is_a_patch)[0], at="patch")

    def drop_perimeter_faces(self):
        self.drop_element(np.where(self.is_perimeter_face())[0], at="face")

    def drop_perimeter_cells(self):
        self.drop_element(np.where(self.is_perimeter_cell())[0], at="cell")

    def drop_element(self, ids, at="node"):
        dropped_ids = np.asarray(ids, dtype=int)
        dropped_ids.sort()
        is_a_keeper = np.full(self._mesh.dims[at], True)
        is_a_keeper[dropped_ids] = False

        if at == "patch":
            prefix = re.compile("^{at}(es)?_at_".format(at=at))
        else:
            prefix = re.compile("^{at}(s)?_at_".format(at=at))
        suffix = re.compile("at_{at}$".format(at=at))

        at_ = {}
        if at in self._mesh.coords:
            x = self._mesh["x_of_{at}".format(at=at)].values[is_a_keeper]
            y = self._mesh["y_of_{at}".format(at=at)].values[is_a_keeper]
            data = np.arange(len(x))

            at_[at] = xr.DataArray(
                data=data,
                coords={
                    "x_of_{at}".format(at=at): xr.DataArray(x, dims=(at,)),
                    "y_of_{at}".format(at=at): xr.DataArray(y, dims=(at,)),
                },
                dims=(at,),
            )
            self._mesh = self._mesh.drop(
                ["x_of_{at}".format(at=at), "y_of_{at}".format(at=at)]
            )

        for name, var in self._mesh.variables.items():
            if suffix.search(name):
                at_[name] = xr.DataArray(var.values[is_a_keeper], dims=var.dims)

        self._mesh = self._mesh.drop(list(at_))
        self._mesh.update(at_)

        for name, var in self._mesh.variables.items():
            if prefix.search(name):
                array = var.values.reshape((-1,))
                array[np.in1d(array, dropped_ids)] = -1
                for id_ in dropped_ids:
                    array[array > id_] -= 1

    @property
    def links_at_patch(self):
        return self._mesh["links_at_patch"].values

    @property
    def node_at_cell(self):
        return self._mesh["node_at_cell"].values

    @property
    def faces_at_cell(self):
        return self._mesh["faces_at_cell"].values
