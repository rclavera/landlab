#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Fri Apr  8 08:32:48 2016

@author: RCGlade
"""

import numpy as np

from landlab import Component


class ExponentialWeatherer(Component):

    r"""
    This component implements exponential weathering of bedrock on hillslopes.
    Uses exponential soil production function in the style of Ahnert (1976).

    Consider that :math:`w_0` is the maximum soil production decay depth and
    that :math:`w^*` is the characteristic soil production decay depth. The
    soil production rate :math:`\dot{w}` is given as a function of the soil
    depth :math:`d`,

    .. math::

        \dot{w} = w_0 \exp{\frac{d}{w_*}} \;.

    The `ExponentialWeatherer` only calculates soil production at core nodes.

    Parameters
    ----------
    grid: ModelGrid
        Landlab ModelGrid object
    soil_production__maximum_rate : float
        Characteristic weathering depth
    soil_production__decay_depth : float
        Maximum weathering rate for bare bedrock

    Examples
    --------
    >>> import numpy as np
    >>> from landlab import RasterModelGrid
    >>> from landlab.components import ExponentialWeatherer
    >>> mg = RasterModelGrid((5, 5))
    >>> soilz = mg.add_zeros('node', 'soil__depth')
    >>> soilrate = mg.add_ones('node', 'soil_production__rate')
    >>> expw = ExponentialWeatherer(mg)
    >>> expw.calc_soil_prod_rate()
    >>> np.allclose(mg.at_node['soil_production__rate'], 1.)
    True
    """

    _name = "ExponentialWeatherer"

    _input_var_names = set(("soil__depth",))

    _output_var_names = set(("soil_production__rate",))

    _var_units = {"soil__depth": "m", "soil_production__rate": "m/yr"}

    _var_mapping = {"soil__depth": "node", "soil_production__rate": "node"}

    _var_doc = {
        "soil__depth": "depth of soil/weather bedrock",
        "soil_production__rate": "rate of soil production at nodes",
    }

    def __init__(
        self, grid, soil_production__maximum_rate=1.0, soil_production__decay_depth=1.0
    ):
        super(ExponentialWeatherer, self).__init__(grid)

        # Store grid and parameters

        self._wstar = soil_production__decay_depth
        self._w0 = soil_production__maximum_rate

        # Create fields:
        # soil depth
        self._depth = grid.at_node["soil__depth"]

        # weathering rate
        if "soil_production__rate" in grid.at_node:
            self._soil_prod_rate = grid.at_node["soil_production__rate"]
        else:
            self._soil_prod_rate = grid.add_zeros("node", "soil_production__rate")

        self._verify_output_fields()

    def calc_soil_prod_rate(self):
        """Calculate soil production rate."""
        # apply exponential function
        self._soil_prod_rate[self._grid.core_nodes] = self._w0 * np.exp(
            -self._depth[self._grid.core_nodes] / self._wstar
        )

    def run_one_step(self):
        """

        Parameters
        ----------
        dt: float
            Used only for compatibility with standard run_one_step.
        """
        self.calc_soil_prod_rate()
