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


"""Module to support learning analytics based on skill mapping."""

__author__ = 'John Orr (jorr@google.com)'

from controllers import utils
from models import custom_modules
from models import models
from models import transforms
from modules.learning_analytics import skills_models


class AnalyticsUpdater(object):

    PROPERTY_KEY = 'learning-analytics'

    def __init__(self):
        pass

    def _get_or_create_student_property(self, student):
        # TODO(jorr): Make this a method in models.models.StudentPropertyEntity
        entity = models.StudentPropertyEntity.get(student, self.PROPERTY_KEY)
        if not entity:
            entity = models.StudentPropertyEntity.create(
                student=student, property_name=self.PROPERTY_KEY)
            entity.put()
        return entity

    def update_student(self, student, payload):
        student_skills_entity = self._get_or_create_student_property(student)
        student_skills_dict = transforms.loads(student_skills_entity.value)

        skills_map_dto = skills_models.SkillsMapDAO.load_or_create()
        skills_map = skills_models.SkillsMap.from_xml(
            skills_map_dto.skills_map_xml)

        # TODO(jorr): Use the event payload data and the skills map to update
        # the skill scores in the student skills data

        student_skills_entity.value = transforms.dumps(student_skills_dict)
        student_skills_entity.put()


class AnalyticsEventRestHandler(utils.BaseRESTHandler):

    EVENT_SOURCE = 'learning-analytics-event'
    URL = '/rest/modules/learning_analytics/event'
    XSRF_TOKEN = 'learning-analytics-event'

    def post(self):
        """Receives event and puts it into datastore."""

        request = transforms.loads(self.request.get('request'))
        if not self.assert_xsrf_token_or_fail(request, self.XSRF_TOKEN, {}):
            return

        if not utils.CAN_PERSIST_TAG_EVENTS.value:
            transforms.send_json_response(self, 200, 'NO-OP')
            return

        user = self.get_user()
        if not user:
            transforms.send_json_response(self, 403, 'User not found')
            return

        payload_json = request.get('payload')
        models.EventEntity.record(self.EVENT_SOURCE, user, payload_json)

        course = self.get_course()

        AnalyticsUpdater().update_student(user, transforms.loads(payload_json))

        transforms.send_json_response(self, 200, 'OK')


def notify_module_enabled():
    pass


def notify_module_disabled():
    pass


custom_module = None


def register_module():
    """Registers this module in the registry."""

    global_routes = []
    namespaced_routes = [
        (AnalyticsEventRestHandler.URL, AnalyticsEventRestHandler)]

    global custom_module
    custom_module = custom_modules.Module(
        'Learning Analytics Module',
        'A module to support learning analytics based on skill mapping',
        global_routes, namespaced_routes,
        notify_module_enabled=notify_module_enabled,
        notify_module_disabled=notify_module_disabled)

    return custom_module
