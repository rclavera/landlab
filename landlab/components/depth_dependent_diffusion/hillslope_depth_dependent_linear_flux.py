# -*- coding: utf-8 -*-
"""
Created on Fri Apr  8 08:32:48 2016

@author: RCGlade
"""

import numpy as np

from landlab import INACTIVE_LINK, Component


class DepthDependentDiffuser(Component):

    """
    This component implements a depth and slope dependent linear diffusion rule
    in the style of Johnstone and Hilley (2014).

    Hillslope sediment flux uses depth dependent component inspired by
    Johnstone and Hilley (2014). The flux :math:`q_s` is given as:

    .. math::

        q_s = D S H^* (1.0 - exp( H / H^*)

    where :math:`D` is is the diffusivity, :math:`S` is the slope, :math:`H` is
    the soil depth on links, and :math:`H^*` is the soil transport decay depth.

    This component will ignore soil thickness located at non-core nodes.

    Parameters
    ----------
    grid: ModelGrid
        Landlab ModelGrid object
    linear_diffusivity: float
        Hillslope diffusivity, m**2/yr
    soil_transport_decay_depth: float
        characteristic transport soil depth, m

    Examples
    --------
    >>> import numpy as np
    >>> from landlab import RasterModelGrid
    >>> from landlab.components import ExponentialWeatherer
    >>> from landlab.components import DepthDependentDiffuser
    >>> mg = RasterModelGrid((5, 5))
    >>> soilTh = mg.add_zeros('node', 'soil__depth')
    >>> z = mg.add_zeros('node', 'topographic__elevation')
    >>> BRz = mg.add_zeros('node', 'bedrock__elevation')
    >>> expweath = ExponentialWeatherer(mg)
    >>> DDdiff = DepthDependentDiffuser(mg)
    >>> expweath.calc_soil_prod_rate()
    >>> np.allclose(mg.at_node['soil_production__rate'][mg.core_nodes], 1.)
    True
    >>> DDdiff.soilflux(2.)
    >>> np.allclose(mg.at_node['topographic__elevation'][mg.core_nodes], 0.)
    True
    >>> np.allclose(mg.at_node['bedrock__elevation'][mg.core_nodes], -2.)
    True
    >>> np.allclose(mg.at_node['soil__depth'][mg.core_nodes], 2.)
    True

    Now with a slope:

    >>> mg = RasterModelGrid((3, 5))
    >>> soilTh = mg.add_zeros('node', 'soil__depth')
    >>> z = mg.add_zeros('node', 'topographic__elevation')
    >>> BRz = mg.add_zeros('node', 'bedrock__elevation')
    >>> z += mg.node_x.copy()
    >>> BRz += mg.node_x/2.
    >>> soilTh[:] = z - BRz
    >>> expweath = ExponentialWeatherer(mg)
    >>> DDdiff = DepthDependentDiffuser(mg)
    >>> expweath.calc_soil_prod_rate()
    >>> np.allclose(
    ...     mg.at_node['soil_production__rate'][mg.core_nodes],
    ...     np.array([ 0.60653066,  0.36787944,  0.22313016]))
    True
    >>> DDdiff.soilflux(2.)
    >>> np.allclose(
    ...     mg.at_node['topographic__elevation'][mg.core_nodes],
    ...     np.array([ 1.47730244,  2.28949856,  3.17558975]))
    True
    >>> np.allclose(mg.at_node['bedrock__elevation'][mg.core_nodes],
    ...     np.array([-0.71306132,  0.26424112,  1.05373968]))
    True
    >>> np.allclose(mg.at_node['soil__depth'], z - BRz)
    True

    Now, we'll test that changing the transport decay depth behaves as expected.

    >>> mg = RasterModelGrid((3, 5))
    >>> soilTh = mg.add_zeros('node', 'soil__depth')
    >>> z = mg.add_zeros('node', 'topographic__elevation')
    >>> BRz = mg.add_zeros('node', 'bedrock__elevation')
    >>> z += mg.node_x.copy()**0.5
    >>> BRz = z.copy() - 1.0
    >>> soilTh[:] = z - BRz
    >>> expweath = ExponentialWeatherer(mg)
    >>> DDdiff = DepthDependentDiffuser(mg, soil_transport_decay_depth = 0.1)
    >>> DDdiff.soilflux(1)
    >>> soil_decay_depth_point1 = mg.at_node['topographic__elevation'][mg.core_nodes]
    >>> z[:] = 0
    >>> z += mg.node_x.copy()**0.5
    >>> BRz = z.copy() - 1.0
    >>> soilTh[:] = z - BRz
    >>> DDdiff = DepthDependentDiffuser(mg, soil_transport_decay_depth = 1.0)
    >>> DDdiff.soilflux(1)
    >>> soil_decay_depth_1 = mg.at_node['topographic__elevation'][mg.core_nodes]
    >>> np.greater(soil_decay_depth_1[1], soil_decay_depth_point1[1])
    False


    """

    _name = "DepthDependentDiffuser"

    _input_var_names = (
        "topographic__elevation",
        "soil__depth",
        "soil_production__rate",
    )

    _output_var_names = (
        "soil__flux",
        "topographic__slope",
        "topographic__elevation",
        "bedrock__elevation",
        "soil__depth",
    )

    _var_units = {
        "topographic__elevation": "m",
        "topographic__slope": "m/m",
        "soil__depth": "m",
        "soil__flux": "m^2/yr",
        "soil_production__rate": "m/yr",
        "bedrock__elevation": "m",
    }

    _var_mapping = {
        "topographic__elevation": "node",
        "topographic__slope": "link",
        "soil__depth": "node",
        "soil__flux": "link",
        "soil_production__rate": "node",
        "bedrock__elevation": "node",
    }

    _var_doc = {
        "topographic__elevation": "elevation of the ground surface",
        "topographic__slope": "gradient of the ground surface",
        "soil__depth": "depth of soil/weather bedrock",
        "soil__flux": "flux of soil in direction of link",
        "soil_production__rate": "rate of soil production at nodes",
        "bedrock__elevation": "elevation of the bedrock surface",
    }

    def __init__(self, grid, linear_diffusivity=1.0, soil_transport_decay_depth=1.0):
        """Initialize the DepthDependentDiffuser."""
        super(DepthDependentDiffuser, self).__init__(grid)
        # Store grid and parameters

        self._K = linear_diffusivity
        self._soil_transport_decay_depth = soil_transport_decay_depth

        # create fields
        # elevation
        self._elev = self._grid.at_node["topographic__elevation"]
        self._depth = self._grid.at_node["soil__depth"]
        self._soil_prod_rate = self._grid.at_node["soil_production__rate"]

        # slope
        if "topographic__slope" in self._grid.at_link:
            self._slope = self._grid.at_link["topographic__slope"]
        else:
            self._slope = self._grid.add_zeros("link", "topographic__slope")

        # soil flux
        if "soil__flux" in self._grid.at_link:
            self._flux = self._grid.at_link["soil__flux"]
        else:
            self._flux = self._grid.add_zeros("link", "soil__flux")

        # bedrock elevation
        if "bedrock__elevation" in self._grid.at_node:
            self._bedrock = self._grid.at_node["bedrock__elevation"]
        else:
            self._bedrock = self._grid.add_zeros("node", "bedrock__elevation")

    def soilflux(self, dt):
        """Calculate soil flux for a time period 'dt'.

        Parameters
        ----------

        dt: float (time)
            The imposed timestep.
        """

        # update soil thickness
        self._grid.at_node["soil__depth"][:] = (
            self._grid.at_node["topographic__elevation"]
            - self._grid.at_node["bedrock__elevation"]
        )

        # Calculate soil depth at links.
        H_link = self._grid.map_value_at_max_node_to_link(
            "topographic__elevation", "soil__depth"
        )

        # Calculate gradients
        slope = self._grid.calc_grad_at_link(self._elev)
        slope[self._grid.status_at_link == INACTIVE_LINK] = 0.0

        # Calculate flux
        self._flux[:] = (
            -self._K
            * slope
            * self._soil_transport_decay_depth
            * (1.0 - np.exp(-H_link / self._soil_transport_decay_depth))
        )

        # Calculate flux divergence
        dqdx = self._grid.calc_flux_div_at_node(self._flux)

        # Calculate change in soil depth
        dhdt = self._soil_prod_rate - dqdx

        # Calculate soil depth at nodes
        self._depth[self._grid.core_nodes] += dhdt[self._grid.core_nodes] * dt

        # prevent negative soil thickness
        self._depth[self._depth < 0.0] = 0.0

        # Calculate bedrock elevation
        self._bedrock[self._grid.core_nodes] -= (
            self._soil_prod_rate[self._grid.core_nodes] * dt
        )

        # Update topography
        self._elev[self._grid.core_nodes] = (
            self._depth[self._grid.core_nodes] + self._bedrock[self._grid.core_nodes]
        )

    def run_one_step(self, dt):
        """

        Parameters
        ----------
        dt: float (time)
            The imposed timestep.
        """

        self.soilflux(dt)
