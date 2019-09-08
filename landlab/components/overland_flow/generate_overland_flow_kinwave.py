# -*- coding: utf-8 -*-
"""
Landlab component for overland flow using the kinematic-wave approximation.

Created on Fri May 27 14:26:13 2016

@author: gtucker
"""


import numpy as np

from landlab import Component


class KinwaveOverlandFlowModel(Component):
    """Calculate water flow over topography.

    Landlab component that implements a two-dimensional
    kinematic wave model. This is an extremely simple, unsophisticated
    model, originally built simply to demonstrate the component creation
    process. Limitations to the present version include: infiltration is
    handled very crudely, the called is responsible for picking a stable
    time step size (no adaptive time stepping is used in the `run_one_step`
    method), precipitation rate is constant for a given duration (then zero),
    and all parameters are uniform in space. Also, the terrain is assumed
    to be stable over time. Caveat emptor!

    Examples
    --------
    >>> from landlab import RasterModelGrid
    >>> rg = RasterModelGrid((4, 5), xy_spacing=10.0)
    >>> z = rg.add_zeros("node", "topographic__elevation")
    >>> s = rg.add_zeros("link", "topographic__gradient")
    >>> kw = KinwaveOverlandFlowModel(rg)
    >>> kw.vel_coef
    100.0
    >>> rg.at_node['surface_water__depth']
    array([ 0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,
            0.,  0.,  0.,  0.,  0.,  0.,  0.])
    """

    _name = "KinwaveOverlandFlowModel"

    _input_var_names = ("topographic__elevation", "topographic__gradient")

    _output_var_names = (
        "surface_water__depth",
        "water__velocity",
        "water__specific_discharge",
    )

    _var_units = {
        "topographic__elevation": "m",
        "topographic__gradient": "m/m",
        "surface_water__depth": "m",
        "water__velocity": "m/s",
        "water__specific_discharge": "m2/s",
    }

    _var_mapping = {
        "topographic__elevation": "node",
        "topographic__gradient": "link",
        "surface_water__depth": "node",
        "water__velocity": "link",
        "water__specific_discharge": "link",
    }

    _var_doc = {
        "topographic__elevation": "elevation of the ground surface relative to some datum",
        "topographic__gradient": "gradient of the ground surface",
        "surface_water__depth": "depth of water",
        "water__velocity": "flow velocity component in the direction of the link",
        "water__specific_discharge": "flow discharge component in the direction of the link",
    }

    def __init__(
        self,
        grid,
        precip_rate=1.0,
        precip_duration=1.0,
        infilt_rate=0.0,
        roughness=0.01,
    ):
        """Initialize the KinwaveOverlandFlowModel.

        Parameters
        ----------
        grid : ModelGrid
            Landlab ModelGrid object
        precip_rate : float, optional (defaults to 1 mm/hr)
            Precipitation rate, mm/hr
        precip_duration : float, optional (defaults to 1 hour)
            Duration of precipitation, hours
        infilt_rate : float, optional (defaults to 0)
            Maximum rate of infiltration, mm/hr
        roughness : float, defaults to 0.01
            Manning roughness coefficient, s/m^1/3
        """
        super(KinwaveOverlandFlowModel, self).__init__(grid)

        # Store parameters and do unit conversion

        self._precip = precip_rate / 3600000.0  # convert to m/s
        self._precip_duration = precip_duration * 3600.0  # h->s
        self._infilt = infilt_rate / 3600000.0  # convert to m/s
        self._vel_coef = 1.0 / roughness  # do division now to save time

        # Create fields...
        #   Elevation
        self._elev = grid.at_node["topographic__elevation"]

        #   Slope
        self._slope = grid.at_link["topographic__gradient"]

        #  Water depth
        if "surface_water__depth" in grid.at_node:
            self._depth = grid.at_node["surface_water__depth"]
        else:
            self._depth = grid.add_zeros("node", "surface_water__depth")

        #  Velocity
        if "water__velocity" in grid.at_link:
            self._vel = grid.at_link["water__velocity"]
        else:
            self._vel = grid.add_zeros("link", "water__velocity")
        #  Discharge
        if "water__specific_discharge" in grid.at_link:
            self._disch = grid.at_link["water__specific_discharge"]
        else:
            self._disch = grid.add_zeros("link", "water__specific_discharge")

        # Calculate the ground-surface slope (assume it won't change)
        self._slope[self._grid.active_links] = self._grid.calc_grad_at_link(self._elev)[
            self._grid.active_links
        ]
        self._sqrt_slope = np.sqrt(self._slope)
        self._sign_slope = np.sign(self._slope)

    @property
    def vel_coef(self):
        """TODO"""
        return self._vel_coef

    def run_one_step(self, dt, current_time=0.0):
        """Calculate water flow for a time period `dt`.

        Default units for dt are *seconds*.
        """
        # Calculate water depth at links. This implements an "upwind" scheme
        # in which water depth at the links is the depth at the higher of the
        # two nodes.
        H_link = self._grid.map_value_at_max_node_to_link(
            "topographic__elevation", "surface_water__depth"
        )

        # Calculate velocity using the Manning equation.
        self._vel = (
            -self._sign_slope * self._vel_coef * H_link ** 0.66667 * self._sqrt_slope
        )

        # Calculate discharge
        self._disch = H_link * self._vel

        # Flux divergence
        dqda = self._grid.calc_flux_div_at_node(self._disch)

        # Rate of change of water depth
        if current_time < self._precip_duration:
            ppt = self._precip
        else:
            ppt = 0.0
        dHdt = ppt - self._infilt - dqda

        # Update water depth: simple forward Euler scheme
        self._depth[self._grid.core_nodes] += dHdt[self._grid.core_nodes] * dt

        # Very crude numerical hack: prevent negative water depth
        self._depth[np.where(self._depth < 0.0)[0]] = 0.0


if __name__ == "__main__":
    import doctest

    doctest.testmod()
