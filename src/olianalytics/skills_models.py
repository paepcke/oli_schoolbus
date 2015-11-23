# Copyright 2014 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""Object model for skill mapping.

The skills mapping is based on three types of entities; Objectives, Skills, and
Resources. 

    * Objectives are broad learning goals for the course
    * Skills are smaller, measurable skills learned in the course
    * Resources are course components (e.g., questions) which measure competence
        at skills and objectives.

The skills mapping consists of a many-many mapping between Resources and Skills,
and a many-many mapping between Skills and Objectives. The mapping between
Resources and Skills is handled by the ResourcesMap class and the mapping
between Objectives and Skills is handled by the SkillsMap class.
"""

__author__ = 'John Orr (jorr@google.com)'

from xml.etree import cElementTree

from models import models

from google.appengine.ext import db


class BKTEstimator(object):
    """A class to implement the Baysian Knowledge Tracing estimator."""

    @classmethod
    def get_standard_estimator(cls):
        return BKTEstimator(p_learning=0.1, p_guess=0.3, p_slip=0.2)

    def __init__(self, p_learning=0.0, p_guess=0.0, p_slip=0.0):
        self._p_learning = p_learning
        self._p_guess = p_guess
        self._p_slip = p_slip

    def get_posterior(self, prior, is_correct):
        """Compute the posterior probability.

        Use the prior and the new data to compute the posterior probability
        according to the BKT model.

        Args:
            prior: float. The prior probability estimate, between 0.0 and 1.0.
            is_correct: bool. Whether this question was answered correctly.

        Returns:
            float. The posterior probability estimate, between 0.0 and 1.0.
        """

        not_prior = 1 - prior

        if is_correct:
            p_not_slip = 1 - self._p_slip
            p = prior * p_not_slip / (
                prior * p_not_slip + not_prior * self._p_guess)
        else:
            p = prior * self._p_slip / (
                prior * self._p_slip + not_prior * (1 - self._p_guess))

        return p + (1 - p) * self._p_learning


class SkillsMap(object):
    """Class to manage the mappings between skills and objectives."""

    @classmethod
    def from_xml(cls, xml_str):
        """Parse the skills map into a SkillsMap object.

        Args:
            xml_str: str. The XML document in string format.

        Returns:
            SkillsMap. The skill map as an object model.
"""
        skills_map = SkillsMap()
        root = cElementTree.XML(xml_str)

        for skill_elt in root.findall('./skills/skill'):
            id_str = skill_elt.get('id')
            description = skill_elt.text
            skill = Skill(id_str, description)
            skills_map._skills.append(skill)
            skills_map._skills_by_id[skill.id] = skill

        for objective_elt in root.findall('./objectives/objective'):
            id_str = objective_elt.get('id')
            # TODO(jorr): Is "description a required element? Or maybe None?
            description = objective_elt.find('./description').text

            objective = Objective(id_str, description)
            skills_map._objectives.append(objective)
            skills_map._objectives_by_id[objective.id] = objective

            for skill_elt in objective_elt.findall('./skills/skill'):
                skill_id = skill_elt.get('idref')
                assert skill_id in skills_map._skills_by_id, (
                    'Objective references unknown skill %s' % skill_id)
                skills_map._skills_to_objectives_map.setdefault(
                    skill_id, set()).add(objective.id)
                skills_map._objectives_to_skills_map.setdefault(
                    objective.id, set()).add(skill_id)

        return skills_map

    def __init__(self):
        self._objectives = []
        self._objectives_by_id = {}
        self._skills = []
        self._skills_by_id = {}
        self._skills_to_objectives_map = {}
        self._objectives_to_skills_map = {}

    def to_xml(self):
        raise NotImplementedError()

    @property
    def objectives(self):
        return self._objectives

    def get_objective_by_id(self, id_str):
        return self._objectives_by_id.get(id_str)

    @property
    def skills(self):
        return self._skills

    def get_skill_by_id(self, id_str):
        return self._skills_by_id.get(id_str)

    def get_skills_for_objective(self, objective_id):
        """Get the set of skills associated with a given objective.

        Args:
            objective_id: str. The id of the objective.

        Returns:
            set. The is's of the skills associated with the given objective. May
                be empty.
        """
        return frozenset(self._objectives_to_skills_map.get(objective_id, []))

    def get_objectives_for_skill(self, skill_id):
        """Get the set of objectives associated with a given skill.

        Args:
            skill_id: str. The id of the skill.

        Returns:
            set. The id's of the objectives associated with the given skill. May
                be empty.
        """
        return frozenset(self._skills_to_objectives_map.get(skill_id, []))


class ResourcesMap(object):
    """Class to manage the mappings between skills and resources."""

    @classmethod
    def from_xml(cls, xml_str, skills_map=None):
        """Parse the resources map into a ResourcesMap object.

        Args:
            xml_str: str. The XML document in string format.
            skills_map: SkillsMap. The skills maps which is referenced in this
                document. If a skills map is provided then the references will
                be verified.

        Returns:
            ResourcesMap. The resources map as an object model.
"""
        root = cElementTree.XML(xml_str)

        # TODO(jorr): Determine what value there is on putting an id field here
        resources_map = ResourcesMap(root.get('id'), skills_map)

        for resource_elt in root.findall('./resource'):
            resource_id = resource_elt.get('id')
            resources_map._resource_ids.append(resource_id)
            for skill_elt in resource_elt.findall('./skills/skill'):
                skill_id = skill_elt.get('idref')
                assert (skills_map is None) or (
                    skills_map.get_skill_by_id(skill_id) is not None)
                resources_map._skills_to_resources_map.setdefault(
                    skill_id, set()).add(resource_id)
                resources_map._resources_to_skills_map.setdefault(
                    resource_id, set()).add(skill_id)

        return resources_map

    def __init__(self, id_str, skills_map):
        self._id = id_str
        self._skills_map = skills_map
        self._skills_to_resources_map = {}
        self._resources_to_skills_map = {}
        self._resource_ids = []

    @property
    def id(self):
        return self._id

    @property
    def resource_ids(self):
        return self._resource_ids

    def to_xml(self):
        raise NotImplementedError()

    def get_skills_for_resource(self, resource_id):
        """Get the set of skills associated with a given resource.

        Args:
            resource_id: str. The id of the resource.

        Returns:
            set. The id's of the skills associated with the given resource. May
                be empty.
        """
        return frozenset(self._resources_to_skills_map.get(resource_id, []))

    def get_objectives_for_resource(self, resource_id):
        """Get the set of objectives associated with a given resource.

        Args:
            resource_id: str. The id of the resource.

        Returns:
            set. The id's of the objectives associated with the given resource
                 by transitive closure. May be empty.
        """
        assert self._skills_map
        objectives = set()
        for skill_id in self.get_skills_for_resource(resource_id):
            objectives.update(
                self._skills_map.get_objectives_for_skill(skill_id))
        return objectives

    def get_resources_for_skill(self, skill_id):
        """Get the set of resources associated with a given skill.

        Args:
            skill_id: str. The id of the skill.

        Returns:
            set. The id's of the resources associated with the given skill. May
                be empty.
        """
        return frozenset(self._skills_to_resources_map.get(skill_id, []))


class Objective(object):

    def __init__(self, id_str, description):
        self._id = id_str
        self._description = description

    @property
    def id(self):
        return self._id

    @property
    def description(self):
        return self._description


class Skill(object):

    def __init__(self, id_str, description):
        self._id = id_str
        self._description = description

    @property
    def id(self):
        return self._id

    @property
    def description(self):
        return self._description


class SkillsMapEntity(models.BaseEntity):
    """The base entity for storing skills mapping.

    This entity is unique per course.
    """

    data = db.TextProperty(indexed=False)


class SkillsMapDTO(object):
    """The lightweight data object for the skills mapping data."""

    SKILLS_MAP_XML_KEY = 'skills_map'
    EMPTY_SKILLS_MAP_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<skills-map>
    <skills></skills>
    <objectives></objectives>
</skills-map>
"""


    def __init__(self, the_id, the_dict):
        self.id = the_id
        self.dict = the_dict

    @property
    def skills_map_xml(self):
        return self.dict.get(self.SKILLS_MAP_XML_KEY, self.EMPTY_SKILLS_MAP_XML)


class SkillsMapDAO(models.BaseJsonDao):
    """Access object for the skills mapping data."""

    DTO = SkillsMapDTO
    ENTITY = SkillsMapEntity
    ENTITY_KEY_TYPE = models.BaseJsonDao.EntityKeyTypeName
    SINGLETON_NAME = 'skills_map_entity'

    @classmethod
    def load_or_create(cls):
        skills_map_dto = cls.load(cls.SINGLETON_NAME)
        if not skills_map_dto:
            skills_map_dto = SkillsMapDTO(cls.SINGLETON_NAME, {})
            cls.save(skills_map_dto)
        return skills_map_dto
