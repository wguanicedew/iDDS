#!/usr/bin/env python
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0OA
#
# Authors:
# - Wen Guan, <wen.guan@cern.ch>, 2021


"""
Test client.
"""


from idds.client.clientmanager import ClientManager
from idds.common.utils import json_dumps  # noqa F401


def migrate():
    # dev
    dev_host = 'https://aipanda160.cern.ch:443/idds'
    # doma
    doma_host = 'https://aipanda015.cern.ch:443/idds'

    cm1 = ClientManager(host=doma_host)
    # reqs = cm1.get_requests(request_id=290)
    reqs = cm1.get_requests(request_id=274)

    cm2 = ClientManager(host=dev_host)
    for req in reqs:
        workflow = req['request_metadata']['workflow']
        # print(json_dumps(workflow))
        # print(json_dumps(workflow, sort_keys=True, indent=4))
        req_id = cm2.submit(workflow)
        print(req_id)


if __name__ == '__main__':
    migrate()