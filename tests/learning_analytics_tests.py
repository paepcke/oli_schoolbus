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

"""Tests for the Learning Analytics module."""

__author__ = 'John Orr (jorr@google.com)'

import unittest

from common import crypto
from controllers import utils
from models import config
from models import courses
from models import models
from models import transforms
from modules.learning_analytics import skills_models
from tests.functional import actions

from google.appengine.api import namespace_manager


class AnalyticsEventRestHandlerTests(actions.TestBase):
    COURSE_NAME = 'test_course'
    ADMIN_EMAIL = 'admin@foo.com'
    URL = 'rest/modules/learning_analytics/event'
    XSRF_TOKEN = 'learning-analytics-event'

    def setUp(self):
        super(AnalyticsEventRestHandlerTests, self).setUp()
        self.base = '/' + self.COURSE_NAME
        self.old_namespace = namespace_manager.get_namespace()
        namespace_manager.set_namespace('ns_%s' % self.COURSE_NAME)
        self.course = courses.Course(None, actions.simple_add_course(
            self.COURSE_NAME, self.ADMIN_EMAIL, 'Test Course'))
        config.Registry.test_overrides[
            utils.CAN_PERSIST_TAG_EVENTS.name] = True

    def tearDown(self):
        namespace_manager.set_namespace(self.old_namespace)
        super(AnalyticsEventRestHandlerTests, self).tearDown()

    def _wrap_request(self, payload, xsrf_token=None):
        xsrf_token = xsrf_token or crypto.XsrfTokenManager.create_xsrf_token(
            self.XSRF_TOKEN)
        return {'request': transforms.dumps({
            'xsrf_token': xsrf_token,
            'payload': payload})}

    def _post_request(self, payload, xsrf_token=None):
        return self.post(self.URL, self._wrap_request(payload, xsrf_token))

    def test_rejects_invalid_xsrf_token(self):
        response = self._post_request('{}', xsrf_token='bad_token')
        response = transforms.loads(response.body)
        self.assertEquals(403, response['status'])
        self.assertIn('Bad XSRF token', response['message'])

    def test_if_cannot_persist_tag_events_then_post_is_a_noop(self):
        config.Registry.test_overrides[
            utils.CAN_PERSIST_TAG_EVENTS.name] = False
        response = transforms.loads(self._post_request('{}').body)
        self.assertEquals(200, response['status'])
        self.assertEquals('NO-OP', response['message'])

    def test_rejects_user_not_in_session(self):
        response = transforms.loads(self._post_request('{}').body)
        self.assertEquals(403, response['status'])
        self.assertEquals('User not found', response['message'])

    def test_records_event(self):
        actions.login('user@foo.bar')
        response = transforms.loads(self._post_request('{}').body)
        self.assertEquals(200, response['status'])
        self.assertEquals('OK', response['message'])
        events = models.EventEntity.all().fetch(1000)
        self.assertEquals(1, len(events))
        event = events[0]
        self.assertEquals('learning-analytics-event', event.source)
        self.assertEquals('user@foo.bar', event.user_id)
        self.assertEquals('{}', event.data)


class BKTEstimatorTests(unittest.TestCase):
    """Unit tests for the Baysian Knowledge Tracing model."""

    def test_correct_answer_when_no_guessing(self):
        """Test correct answer when guessing is impossible.

        If the student answers correctly and guessing is impossible then they
        must have known it originally. Since forgetting is impossible, they
        still know it.
        """
        estimator = skills_models.BKTEstimator(
            p_learning=0.1, p_guess=0.0, p_slip=0.2)
        for n in xrange(1, 100):
            prior = n / 100.0

            self.assertEquals(
                1.0, estimator.get_posterior(prior, is_correct=True))

    def test_incorrect_answer_when_no_slipping(self):
        """Test incorrect answer when a slip is impossible.

        If the student answers incorrectly and slipping is impossible then they
        must have not known the item originally. However they may have learned
        it now, so the new estimate is p_learing.
        """
        estimator = skills_models.BKTEstimator(
            p_learning=0.1, p_guess=0.3, p_slip=0.0)
        for n in xrange(1, 100):
            prior = n / 100.0

            self.assertEquals(
                0.1, estimator.get_posterior(prior, is_correct=False))

    def test_probabilities_between_0_and_1(self):
        estimator = skills_models.BKTEstimator.get_standard_estimator()
        for n in xrange(1, 100):
            prior = n / 100.0
            posterior = estimator.get_posterior(prior, is_correct=True)
            self.assertTrue(0.0 < posterior and posterior < 1)
            posterior = estimator.get_posterior(prior, is_correct=False)
            self.assertTrue(0.0 < posterior and posterior < 1)

    def test_p_converges_to_1_with_sequence_of_correct_responses(self):
        """Test the outcome of a long run of correct responses.

        In this case the p estimate converges to 1.
        """
        estimator = skills_models.BKTEstimator.get_standard_estimator()
        p = 0.0
        for n in xrange(1, 100):
            p = estimator.get_posterior(p, is_correct=True)

        self.assertEquals(1.0, p)

    def test_sequence_of_incorrect_responses(self):
        """Test the outcome of a long run of incorrect responses.

        In this case the p estimate converges to a non-zero fixed point. The
        fixed point can be calculated by summing a finite geometric series
        consisting of the the probabilities of the events:

            did not learn i times, then learned and slipped n-i times,

        I.e., t * s^(n-i) * (1-t)^i
        """
        estimator = skills_models.BKTEstimator.get_standard_estimator()
        p = 0.9999
        for n in xrange(1, 100):
            p = estimator.get_posterior(p, is_correct=False)

        self.assertEquals(p, estimator.get_posterior(p, is_correct=False))
        self.assertEquals(0.14, p)


class SkillsMapTests(unittest.TestCase):
    def test_should_parse_well_formed_xml(self):
        skills_map = skills_models.SkillsMap.from_xml(SAMPLE_SKILLS_MAP)

        self.assertEquals(16, len(skills_map.skills))
        self.assertEquals(3, len(skills_map.objectives))

    def test_get_skill_by_id_returns_skill_for_valid_id(self):
        skills_map = skills_models.SkillsMap.from_xml(SAMPLE_SKILLS_MAP)
        self.assertEquals(
            'Operations on whole numbers',
            skills_map.get_skill_by_id(
                'arithmetic_operations_whole').description)

    def test_get_skill_by_id_returns_none_for_invalid_id(self):
        skills_map = skills_models.SkillsMap.from_xml(SAMPLE_SKILLS_MAP)
        self.assertIsNone(skills_map.get_skill_by_id('bad_key'))

    def test_get_objective_by_id_returns_objective_for_valid_id(self):
        skills_map = skills_models.SkillsMap.from_xml(SAMPLE_SKILLS_MAP)
        self.assertEquals(
            'Identify which arithmetic operator to use in a given situation.',
            skills_map.get_objective_by_id(
                'arithmetic_identify').description.strip())

    def test_get_objective_by_id_returns_none_for_invalid_id(self):
        skills_map = skills_models.SkillsMap.from_xml(SAMPLE_SKILLS_MAP)
        self.assertIsNone(skills_map.get_objective_by_id('bad_key'))

    def test_get_skills_for_objective_can_return_multuple_skills(self):
        skills_map = skills_models.SkillsMap.from_xml(SAMPLE_SKILLS_MAP)
        self.assertEquals(
            set([
                'arithmetic_operations_whole',
                'arithmetic_operations_subtract_identify',
                'arithmetic_operations_divide_identify',
                'arithmetic_operations_add_identify',
                'arithmetic_operations_multiply_identify']),
            skills_map.get_skills_for_objective('arithmetic_identify'))

    def test_get_skills_for_objective_can_return_empty_set(self):
        skills_map = skills_models.SkillsMap.from_xml("""\
<?xml version="1.0" encoding="UTF-8"?>
<skills-map>
    <skills></skills>
    <objectives>
        <objective id="objective-1">
            <description>This has no skills</description>
            <skills></skills>
        </objective>
    </objectives>
</skills-map>
""")
        self.assertEquals(
            set([]), skills_map.get_skills_for_objective('objective-1'))

    def test_get_objectives_for_skill_can_return_multuple_skills(self):
        skills_map = skills_models.SkillsMap.from_xml(SAMPLE_SKILLS_MAP)
        self.assertEquals(
            set([
                'arithmetic_operations',
                'arithmetic_identify',
                'arithmetic_operations_negative']),
            skills_map.get_objectives_for_skill('arithmetic_operations_whole'))

    def test_get_objectives_for_skill_can_return_empty_set(self):
        skills_map = skills_models.SkillsMap.from_xml("""\
<?xml version="1.0" encoding="UTF-8"?>
<skills-map>
    <skills>
      <skill id="skill-1">This skill has no objectives</skill>
    </skills>
    <objectives>
    </objectives>
</skills-map>
""")
        self.assertEquals(
            set([]), skills_map.get_objectives_for_skill('skill-1'))


class ResourcesMapTests(unittest.TestCase):
    def test_should_parse_well_formed_xml(self):
        resources_map = skills_models.ResourcesMap.from_xml(
            SAMPLE_RESOURCES_MAP)
        self.assertEquals('stem_readiness', resources_map.id)
        self.assertEquals(10, len(resources_map.resource_ids))

    def test_get_skills_for_resource(self):
        resources_map = skills_models.ResourcesMap.from_xml(
            SAMPLE_RESOURCES_MAP)
        self.assertEquals(
            set([
                'arithmetic_operations_communitive',
                'arithmetic_operations_decimal',
                'arithmetic_operations_divide']),
            resources_map.get_skills_for_resource('arithmetic_p3_q1'))

    def test_get_resources_for_skill(self):
        resources_map = skills_models.ResourcesMap.from_xml(
            SAMPLE_RESOURCES_MAP)
        self.assertEquals(
            set([
                'arithmetic_p3_q2',
                'arithmetic_p3_q9',
                'arithmetic_p3_q10']),
            resources_map.get_resources_for_skill('arithmetic_operations_add'))

    def test_parse_rejects_invalid_skill_id(self):
        resources_map_xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<resources id="resources_id">
    <resource id="resource_id">
        <skills>
            <skill idref="bad_id"/>
        </skills>
    </resource>
</resources>
"""
        skills_map = skills_models.SkillsMap.from_xml(SAMPLE_SKILLS_MAP)
        with self.assertRaises(AssertionError):
            skills_models.ResourcesMap.from_xml(
                resources_map_xml, skills_map=skills_map)

    def test_parse_accepts_valid_skill_id(self):
        skills_map = skills_models.SkillsMap.from_xml(SAMPLE_SKILLS_MAP)
        try:
            skills_models.ResourcesMap.from_xml(
                SAMPLE_RESOURCES_MAP, skills_map=skills_map)
        except AssertionError:
            self.fail()

    def test_get_objectives_for_resource(self):
        skills_map = skills_models.SkillsMap.from_xml(SAMPLE_SKILLS_MAP)
        resources_map = skills_models.ResourcesMap.from_xml(
            SAMPLE_RESOURCES_MAP, skills_map=skills_map)
        self.assertEquals(
            set(['arithmetic_operations']),
            resources_map.get_objectives_for_resource('arithmetic_p3_q1'))

    def test_get_objectives_for_resource_rejected_if_skill_map_missing(self):
        resources_map = skills_models.ResourcesMap.from_xml(
            SAMPLE_RESOURCES_MAP)
        with self.assertRaises(AssertionError):
            resources_map.get_objectives_for_resource('arithmetic_p3_q1')


SAMPLE_SKILLS_MAP = """\
<?xml version="1.0" encoding="UTF-8"?>
<skills-map>
    <skills>
        <skill id="arithmetic_operations_whole">Operations on whole numbers</skill>
        <skill id="arithmetic_operations_decimal">Operations on decimals</skill>
        <skill id="arithmetic_operations_subtract">Subtraction operator</skill>
        <skill id="arithmetic_operations_add">Addition Operator</skill>
        <skill id="arithmetic_operations_multiply">Multiplication Operator</skill>
        <skill id="arithmetic_operations_divide">Division Operator</skill>
        <skill id="arithmetic_operations_communitive">Compare for communitive property</skill>
        <skill id="arithmetic_operations_subtract_identify">Recognize when to use subtraction</skill>
        <skill id="arithmetic_operations_divide_identify">Recognize when to use division</skill>
        <skill id="arithmetic_operations_add_identify">Recognize when to use addition</skill>
        <skill id="arithmetic_operations_multiply_identify">Recognize when to use multiplication</skill>
        <skill id="arithmetic_operations_negative_add_negative">Addition with negative values</skill>
        <skill id="arithmetic_operations_negative_subtract_negative">Subtraction with negative values</skill>
        <skill id="arithmetic_operations_negative_multiply">Multiplication with negative values</skill>
        <skill id="arithmetic_operations_negative_divide">Division with negative values</skill>
        <skill id="arithmetic_operations_negative_less_than">Recognize greater than/less than with negative values</skill>
    </skills>

    <objectives>
        <objective id="arithmetic_operations">
            <description>
                Apply arithmetic operators to problems involving whole
                numbers and decimals.
            </description>
            <skills>
                <skill idref="arithmetic_operations_whole"><!-- This is cross-cutting --></skill>
                <skill idref="arithmetic_operations_decimal"/>
                <skill idref="arithmetic_operations_subtract"/>
                <skill idref="arithmetic_operations_add"/>
                <skill idref="arithmetic_operations_multiply"/>
                <skill idref="arithmetic_operations_divide"/>
                <skill idref="arithmetic_operations_communitive"/>
            </skills>
        </objective>
        <objective id="arithmetic_identify">
            <description>
                Identify which arithmetic operator to use in a given situation.
            </description>
            <skills>
                <skill idref="arithmetic_operations_whole"><!-- This is cross-cutting --></skill>
                <skill idref="arithmetic_operations_subtract_identify"/>
                <skill idref="arithmetic_operations_divide_identify"/>
                <skill idref="arithmetic_operations_add_identify"/>
                <skill idref="arithmetic_operations_multiply_identify"/>
            </skills>
        </objective>
        <objective id="arithmetic_operations_negative">
            <description>
                Apply arithmetic operations to problems involving
                negative values.
            </description>
            <skills>
                <skill idref="arithmetic_operations_whole"><!-- This is cross-cutting --></skill>
                <skill idref="arithmetic_operations_negative_add_negative"/>
                <skill idref="arithmetic_operations_negative_subtract_negative"/>
                <skill idref="arithmetic_operations_negative_multiply"/>
                <skill idref="arithmetic_operations_negative_divide"/>
                <skill idref="arithmetic_operations_negative_less_than"/>
            </skills>
        </objective>
    </objectives>
</skills-map>
"""

SAMPLE_RESOURCES_MAP = """\
<?xml version="1.0" encoding="UTF-8"?>
<resources id="stem_readiness">
    <resource id="arithmetic_p3_q1">
        <skills>
            <skill idref="arithmetic_operations_communitive"/>
            <skill idref="arithmetic_operations_decimal"/>
            <skill idref="arithmetic_operations_divide"/>
        </skills>
    </resource>
    <resource id="arithmetic_p3_q2">
        <skills>
            <skill idref="arithmetic_operations_communitive"/>
            <skill idref="arithmetic_operations_whole"/>
            <skill idref="arithmetic_operations_add"/>
        </skills>
    </resource>
    <resource id="arithmetic_p3_q3">
        <skills>
            <skill idref="arithmetic_operations_communitive"/>
            <skill idref="arithmetic_operations_whole"/>
            <skill idref="arithmetic_operations_divide"/>
        </skills>
    </resource>
    <resource id="arithmetic_p3_q4">
        <skills>
            <skill idref="arithmetic_operations_communitive"/>
            <skill idref="arithmetic_operations_whole"/>
            <skill idref="arithmetic_operations_multiply"/>
        </skills>
    </resource>
    <resource id="arithmetic_p3_q5">
        <skills>
            <skill idref="arithmetic_operations_communitive"/>
            <skill idref="arithmetic_operations_decimal"/>
            <skill idref="arithmetic_operations_multiply"/>
        </skills>
    </resource>
    <resource id="arithmetic_p3_q6">
        <skills>
            <skill idref="arithmetic_operations_communitive"/>
            <skill idref="arithmetic_operations_decimal"/>
            <skill idref="arithmetic_operations_subtract"/>
        </skills>
    </resource>
    <resource id="arithmetic_p3_q7">
        <skills>
            <skill idref="arithmetic_operations_whole"/>
            <skill idref="arithmetic_operations_divide"/>
            <skill idref="arithmetic_operations_divide_identify"/>
        </skills>
    </resource>
    <resource id="arithmetic_p3_q8">
        <skills>
            <skill idref="arithmetic_operations_whole"/>
            <skill idref="arithmetic_operations_divide"/>
        </skills>
    </resource>
    <resource id="arithmetic_p3_q9">
        <skills>
            <skill idref="arithmetic_operations_add_identify"/>
            <skill idref="arithmetic_operations_add"/>
            <skill idref="arithmetic_operations_decimal"/>
        </skills>
    </resource>
    <resource id="arithmetic_p3_q10">
        <skills>
            <skill idref="arithmetic_operations_add_identify"/>
            <skill idref="arithmetic_operations_add"/>
            <skill idref="arithmetic_operations_whole"/>
        </skills>
    </resource>
</resources>
"""
