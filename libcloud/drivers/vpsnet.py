# Licensed to libcloud.org under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# libcloud.org licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from libcloud.providers import Provider
from libcloud.types import NodeState
from libcloud.base import Node, Response, ConnectionUserAndKey, NodeDriver, NodeSize, NodeImage

import base64

# JSON is included in the standard library starting with Python 2.6.  For 2.5
# and 2.4, there's a simplejson egg at: http://pypi.python.org/pypi/simplejson
try: import json
except: import simplejson as json

API_HOST = 'vps.net'
API_VERSION = 'api10json'


class VPSNetResponse(Response):
    
    def parse_body(self):
        try:
            js = json.loads(self.body)
            return js
        except ValueError:
            return self.body

    def parse_error(self):
        try:
            errors = json.loads(self.body)['errors'][0]
        except ValueError:
            return self.body
        else:
            return "\n".join(errors)

class VPSNetConnection(ConnectionUserAndKey):

    host = API_HOST
    responseCls = VPSNetResponse

    def add_default_headers(self, headers):
        user_b64 = base64.b64encode('%s:%s' % (self.user_id, self.key))
        headers['Authorization'] = 'Basic %s' % (user_b64)
        return headers

class VPSNetNodeDriver(NodeDriver):
    
    type = Provider.VPSNET
    name = "vps.net"
    connectionCls = VPSNetConnection

    def _to_node(self, vm):
        if vm['running']:
            state = NodeState.RUNNING
        else:
            state = NodeState.PENDING

        n = Node(id=str(vm['id']),
                 name=vm['label'],
                 state=state,
                 public_ip=None,
                 private_ip=None,
                 driver=self.connection.driver)
        return n

    def _to_image(self, image, cloud):
        image = NodeImage(id=image['id'],
                          name="%s: %s" % (cloud, image['label']),
                          driver=self.connection.driver)

        return image

    def create_node(self, name, image, size, **kwargs):
        headers = {'Content-Type': 'application/json'}
        request = {'virtual_machine':
                        {'label': name,
                         'fqdn': kwargs.get('fqdn', ''),
                         'system_template_id': image.id,
                         'backups_enabled': kwargs.get('backups_enabled', 0),
                         'slices_required': size.id}}

        res = self.connection.request('/virtual_machines.%s' % (API_VERSION,),
                                    data=json.dumps(request),
                                    headers=headers,
                                    method='POST')
        node = self._to_node(res.object['virtual_machine'])
        return node

    def reboot_node(self, node):
        res = self.connection.request('/virtual_machines/%s/%s.%s' % 
                                        (node.id, 'reboot', API_VERSION),
                                        method="POST")
        node = self._to_node(res.object['virtual_machine'])
        return node
        

    def destroy_node(self, node):
        res = self.connection.request('/virtual_machines/%s.%s' % (node.id, API_VERSION),
                                        method='DELETE')
        return res.status == 200

    def list_nodes(self):
        res = self.connection.request('/virtual_machines.%s' % (API_VERSION,))
        return [self._to_node(i['virtual_machine']) for i in res.object] 

    def list_images(self):
        res = self.connection.request('/available_clouds.%s' % (API_VERSION,))

        images = []
        for cloud in res.object:
            label = cloud['cloud']['label']
            templates = cloud['cloud']['system_templates']
            images.extend([self._to_image(image, label) for image in templates])

        return images
