#!/usr/bin/env python
"""Simulate the develop of lineages in a landscape.

Component written by Nathan Lyons beginning August 2017.
"""
from collections import defaultdict, OrderedDict
from itertools import count, product
from string import ascii_uppercase

import numpy as np
from pandas import DataFrame

from landlab import Component
from landlab.core.messages import warning_message


class SpeciesEvolverDelegate(object):
    """SpeciesEvolver interface for SpeciesControllers."""

    def __init__(self):
        # Create data structures.

        self._record = OrderedDict([('time', [np.nan])])

        self._species = OrderedDict([('clade', []),
                                     ('species_number', []),
                                     ('time_appeared', []),
                                     ('latest_time', []),
                                     ('object', [])])

        # Set a reference to a function that generates clade names.

        def _get_next_clade_name():
            for size in count(1):
                for s in product(ascii_uppercase, repeat=size):
                    yield ''.join(s)

        self._clade_generator = _get_next_clade_name()

    def _introduce_species(self, species):
        """Add species to SpeciesEvolver.

        The species are introduced at the latest time in the record. Each
        species is assigned an identifier. The species are added to the
        `_species` data structure.

        Parameters
        ----------
        species : list of Species
            The species to introduce.
        """
        # Set species identifier.

        clades = np.array(self._species['clade'])
        nums = np.array(self._species['species_number'])

        for s in species:
            if s.parent_species == None:
                clade = next(self._clade_generator)
                species_num = 0
            else:
                clade = s.parent_species.clade
                species_num = nums[np.where(clades == clade)[0]].max() + 1

            s._identifier = (clade, species_num)

        # Update the species data structure.

        time = np.nanmax(self._record['time'])
        self._update_species_data_structure(time, species)

    def _update_species_data_structure(self, time, species_at_time):
        s_at_time = set(species_at_time)
        s_set = set(self._species['object'])

        # Identify the objects already in the dataframe.
        s_updated = list(s_at_time.intersection(s_set))

        # Identify the objects that are new.
        s_new = list(s_at_time - s_set)

        # Update the latest time value of the updated species.
        for s in s_updated:
            idx = self._species['object'].index(s)
            self._species['latest_time'][idx] = time

        # Insert the data of new species.
        if s_new:
            clade = [s.identifier[0] for s in s_new]
            s_number = [s.identifier[1] for s in s_new]
            t = [time] * len(s_new)

            self._species['clade'].extend(clade)
            self._species['species_number'].extend(s_number)
            self._species['time_appeared'].extend(t)
            self._species['latest_time'].extend(t)
            self._species['object'].extend(s_new)


class SpeciesEvolver(Component):
    """Simulate the develop of lineages in a landscape.

    This component tracks the lineages of species introduced to a model grid.
    ``SpeciesController`` intoduce and manage species. Evolutionary processes
    are coded in species classes. Species are designed to be subclassed when
    the generic implementation is not ideal.

    The standard workflow provides basic functionality. The steps of the
    standard workflow to include in a model driver:

    1.  Instantiate the component.
    2.  Instantiate a SpeciesController with the instantiatized component as
        the first parameter.
    3.  Introduce species using the SpeciesController.
    4.  Increment the model using the ``run_one_step`` method. This method
        calls the evolve function of each species.

    The standard workflow is flexible. The count and spatial distribution of
    species can be set as desired at model onset and later time steps. Species
    can be `GenericSpecies` or custom types, and multiple types may be
    introduced to the same SpeciesEvolver instance.

    This component tracks model time to construct lineage phylogeny. Time is
    unitless within the component, and for example, can be thought of as in
    years. Time is advanced using the `dt` parameter in the ``run_one_step``
    method.

    Time and other variables can be viewed in the class attribute, ``record``.
    Species can send variables in a 'record_add_on' at each time step. Species
    metadata of a component instance can be viewed with the class attribute,
    ``species``.

    Species are assigned identifiers in the order that they are introduced and
    created by parent species. The identifier is a two element tuple
    automatically generated by SpeciesEvolver. The first element is the clade
    id. Clades are lettered from A to Z then AA to AZ and so forth as more
    clades are created. The second identifier element designates the clade
    members numbered in the order of appearance. For example, the first species
    introduced is A.0 and if that species speciates, the first child species is
    A.1.

    The development of this component was inspired by SEAMLESS (Spatially
    Explicit Area Model of Landscape Evolution by SimulationS). See Albert et
    al., 2017, Systematic Biology 66.
    """
    _name = 'SpeciesEvolver'

    def __init__(self, grid):
        """Instantiate SpeciesEvolver.

        Parameters
        ----------
        grid : ModelGrid
            A Landlab ModelGrid.

        Examples
        --------
        >>> from landlab import RasterModelGrid
        >>> from landlab.components import SpeciesEvolver
        >>> from landlab.components.species_evolution import (Species,
        ...                                                   ZoneManager)

        Create a model grid with mountain scale resolution.

        >>> mg = RasterModelGrid((3, 7), 1000)
        >>> z = mg.add_ones('node', 'topographic__elevation')
        >>> z.reshape(mg.shape)
        array([[ 1.,  1.,  1.,  1.,  1.,  1.,  1.],
               [ 1.,  1.,  1.,  1.,  1.,  1.,  1.],
               [ 1.,  1.,  1.,  1.,  1.,  1.,  1.]])

        By default, the field, 'zone_mask' is expected. This field is a boolean
        array where `True` values represents nodes that satisfying zone
        conditions. A zone object is not created here. Only the extent of this
        zone type is defined here.

        >>> mg.at_node['zone_mask'] = z < 100

        Instantiate the component with parameters, the grid and a list of
        zone managers. The initial zones are created at instantiation. In this
        example, one zone is created because all nodes of the zone mask are
        adjacent to each other.

        >>> se = SpeciesEvolver(mg)
        >>> zones = se.zones_at_time(0)
        >>> len(zones) == 1
        True

        All nodes of the grid are included because the elevation of each node
        is below 100 units.

        . . . . . . .       key:    . node in the initial zone
        . . . . . . .
        . . . . . . .

        Seed the zone with a species.

        >>> new_species = Species(zones[0])
        >>> se.introduce_species(new_species)
        >>> len(se.species_at_time(0)) == 1
        True

        Drive a change in the zone mask to demonstrate component functionality.
        Here we begin a new time step where topography is uplifted by 200 units
        forming a ridge that trends north-south in the center of the grid.

        >>> z[[3, 10, 17]] = 200

        The elevation after uplift is represented here.

        - - - ^ - - -       elevation:  - 1
        - - - ^ - - -                   ^ 200
        - - - ^ - - -

        The zone mask field is updated to reflect the elevation change.

        >>> mg.at_node['zone_mask'] = z < 100

        The updated zone mask is below.

        . . . x . . .       key:    . node in zone mask
        . . . x . . .               x node outside of zone mask
        . . . x . . .

        Run a step.

        >>> dt = 1
        >>> se.run_one_step(dt)
        >>> zones = se.zones_at_time(1)
        >>> len(zones) == 2
        True

        A new zone was created because the zone mask was not continuous.

        . . . ^ * * *       key:    . a zone
        . . . ^ * * *               * another zone
        . . . ^ * * *               ^ mountain range

        The split of the initial zone triggered speciation.

        >>> len(se.species_at_time(1)) == 2
        True
        """
        Component.__init__(self, grid)

        self._delegate = SpeciesEvolverDelegate()

        self._species_controllers = []

    # Define attributes

    @property
    def record(self):
        """A DataFrame of SpeciesEvolver variables over time."""
        return DataFrame(self._delegate._record)

    @property
    def species(self):
        """A DataFrame of species variables."""
        cols = list(self._delegate._species.keys())
        cols.remove('object')
        sort_cols = ['clade', 'species_number']
        return DataFrame(
                self._delegate._species,
                columns=cols).sort_values(by=sort_cols).reset_index(drop=True)

    # Update methods

    def run_one_step(self, dt):
        """Run macroevolution processes for a single timestep.

        Data describing the connectivity of zones over time.

        Parameters
        ----------
        dt : float
            The model time step duration. The first time step begins at 0.
            Following time steps are advanced by ``dt``.
        """
        # Insert the new time in the record.

        if self._delegate._record['time'] == [np.nan]:
            time = 0
        else:
            time = np.nanmax(self._delegate._record['time']) + dt

        self._delegate._record['time'].append(time)

        if len(self._delegate._species['object']) == 0:
            msg = 'No species exist. Introduce species to a SpeciesController.'
            print(warning_message(msg))

        # Create an add on to insert into `record`.

        add_on = defaultdict(float)

        # Process species controllers.

        survivors = []

        for sc in self._species_controllers:
            survivors.extend(sc._get_surviving_species(dt, time, add_on))
            self._insert_record_add_on(add_on)

        # Include species count in record.

        ct_add_on = {'species_count': len(survivors)}
        self._insert_record_add_on(ct_add_on)

        self._delegate._update_species_data_structure(time, survivors)

    # Query methods

    def species_at_time(self, time):
        """Get the species that exist at a time.

        Parameters
        ----------
        time : float, string
            The time in the simulation. Alternatively, the initial species is
            determind when this parameter is 'initial'.

        Returns
        -------
        species : Species list
            The SpeciesEvolver species that exist at *time*.

        Examples
        --------
        """
        if time == 'initial':
            extant_at_time = np.isnan(self._delegate._species['time_appeared'])
        else:
            appeared = np.array(self._delegate._species['time_appeared'])
            appeared = appeared[~np.isnan(appeared)]
            latest = np.array(self._delegate._species['latest_time'])
            latest = latest[~np.isnan(latest)]

            appeared_before_time = appeared <= time
            present_at_time = latest >= time
            print(333,appeared_before_time, present_at_time)
            extant_at_time = np.all([appeared_before_time, present_at_time], 0)

        objects = np.array(self._delegate._species['object'])[extant_at_time]

        return list(objects)

    def species_with_identifier(self, identifier_element,
                                return_data_frame=False):
        """Get species using identifiers.

        A singular species is returned when `identifier_element` is a tuple
        with elements that match species in the `species` DataFrame. The
        first element of the tuple is the clade name and the second element is
        the species number.

        The species of a clade are returned when `identifier_element` is
        a string that matches a clade name in the `species` DataFrame.

        The species that share a species number are returned when
        `identifier_element` is an integer that matches species number in the
        `species` DataFrame.

        By default, the species with `identifier_element` will be returned in a
        DataFrame. Alternatively, a list of Species objects can be returned by
        setting `return_objects` to True. A singular species is returned
        when `identifier_element` is a tuple. Otherwise, the species object(s)
        are returned in a list.

        `None` is returned if no species have an identifier that matches
        `identifier_element`.

        Parameters
        ----------
        identifier_element : tuple, string, or integer
            The identifier element of the species to return.
        return_objects : boolean, optional
            True returns species as SpeciesEvolver objects. False (default)
            returns a DataFrame.

        Returns
        -------
        DataFrame, SpeciesEvolver Species, or SpeciesEvolver Species list
            The species with identifiers that matched `identifier_element`. The
            type of the return object is set by `return_objects`.

        Examples
        --------
        >>> from landlab import RasterModelGrid
        >>> from landlab.components import SpeciesEvolver
        >>> from landlab.components.species_evolution import Species
        >>> import numpy as np
        >>> mg = RasterModelGrid((3, 5))
        >>> zone_id = np.array([np.nan, np.nan, np.nan, np.nan, np.nan,
        ...                     np.nan,      1,      2,      3, np.nan,
        ...                     np.nan, np.nan, np.nan, np.nan, np.nan])
        >>> zone_field = mg.add_field('node', 'zone_id', zone_id)
        >>> se = SpeciesEvolver(mg)
        >>> zones = se.zones_at_time(0, return_objects=True)

        Instantiate and introduce a species to each zone.

        >>> species1 = Species(zones[0])
        >>> species2 = Species(zones[1])
        >>> species3 = Species(zones[2], parent_species=species2)
        >>> se.introduce_species(species1)
        >>> se.introduce_species(species2)
        >>> se.introduce_species(species3)

        Get all the species introduced in a dataframe.

        >>> se.species
          clade species time_appeared latest_time     object
        0     A       0             0           0  <Species>
        1     B       0             0           0  <Species>
        2     B       1             0           0  <Species>

        Get the species, B.0.

        >>> se.species_with_identifier(('B', 0))
          clade species time_appeared latest_time     object
        1     B       0             0           0  <Species>

        Get all of the species in clade, B.

        >>> se.species_with_identifier('B')
          clade species time_appeared latest_time     object
        1     B       0             0           0  <Species>
        2     B       1             0           0  <Species>

        Get all of the species with the same number, 0, despite the clade.

        >>> se.species_with_identifier(0)
          clade species time_appeared latest_time     object
        0     A       0             0           0  <Species>
        1     B       0             0           0  <Species>

        Get the species, B.0 as an object rather than dataframe.

        >>> species_obj = se.species_with_identifier(('B', 0),
                                                     return_objects=True)
        >>> species_obj.identifier
        ('B', 0)
        """
        sdf = DataFrame(self._delegate._species)

        element_type = type(identifier_element)

        if element_type == tuple:
            # Get a singular species using a clade name and number.
            clade = identifier_element[0]
            num = identifier_element[1]

            if not np.all([len(identifier_element) == 2,
                           isinstance(clade, str), isinstance(num, int)], 0):
                raise TypeError('`identifier_element` when it is a tuple must '
                                'have a length of 2. The first element must '
                                'be a string, and the second must be an '
                                'integer.')

            s_out = sdf.loc[np.all([sdf.clade == clade,
                                    sdf.species_number == num], 0)]

        elif element_type == str:
            # Get the species of a clade.
            s_out = sdf.loc[sdf.clade == identifier_element]

        elif element_type == int:
            # Get the species that match a number.
            s_out = sdf.loc[sdf.species_number == identifier_element]

        else:
            raise TypeError('`identifier_element` must be a tuple, string, or '
                            'integer.')

        if len(s_out) == 0:
            return None

        if return_data_frame:
            return s_out

        return OrderedDict(s_out.to_dict())

    # Record methods

    def _get_prior_time(self):
        if len(self._delegate._record['time']) < 2:
            return np.nan
        else:
            return sorted(self._delegate._record['time'])[-2]

    def _insert_record_add_on(self, add_on):
        for key, value in add_on.items():
            if key not in self._delegate._record.keys():
                n_records = len(self._delegate._record['time'])
                self._delegate._record[key] = [np.nan] * (n_records - 1)

            self._delegate._record[key].append(value)
